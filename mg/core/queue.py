from mg.core import Module
from mg.core.cass import CassandraObject, CassandraObjectList, ObjectNotFoundException
from concurrence import Tasklet
from concurrence.http import HTTPConnection, HTTPError, HTTPRequest
from stackless import channel
from urllib import urlencode
from uuid import uuid4
import json
import time
import logging
import re
import weakref
import datetime
import calendar

class QueueTask(CassandraObject):
    _indexes = {
        "app-at": [["app"], "at"],
        "at": [[], "at"],
        "app-unique": [["app", "unique"]],
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "QueueTask-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return QueueTask._indexes

class QueueTaskList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "QueueTask-"
        kwargs["cls"] = QueueTask
        CassandraObjectList.__init__(self, *args, **kwargs)

class ScheduleList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "Schedule-"
        kwargs["cls"] = Schedule
        CassandraObjectList.__init__(self, *args, **kwargs)

class Queue(Module):
    def register(self):
        Module.register(self)
        self.rhook("queue.add", self.queue_add)
        self.rhook("int-queue.run", self.queue_run)
        self.rhook("queue.schedule", self.queue_schedule)
        self.rhook("objclasses.list", self.objclasses_list)

    def objclasses_list(self, objclasses):
        objclasses["QueueTask"] = (QueueTask, QueueTaskList)
        objclasses["Schedule"] = (Schedule, ScheduleList)

    def queue_add(self, hook, args={}, at=None, priority=100, unique=None, retry_on_fail=False, app_tag=None):
        int_app = self.app().inst.int_app
        with int_app.lock(["queue"]):
            if app_tag is None:
                app_tag = self.app().tag
            if at is None:
                at = time.time()
            else:
#               print "scheduling queue event at %s" % at
                ct = CronTime(at)
                if ct.valid:
                    next = ct.next()
                    if next is None:
                        raise CronError("Invalid cron time")
                    at = calendar.timegm(next.utctimetuple())
#                   print "calculated time: %s" % at
                else:
                    raise CronError("Invalid cron time")
            data = {
                "app": app_tag,
                "at": "%020d" % at,
                "priority": int(priority),
                "hook": hook,
                "args": args,
            }
            if unique is not None:
                existing = int_app.objlist(QueueTaskList, query_index="app-unique", query_equal="%s-%s" % (app_tag, unique))
                existing.remove()
                data["unique"] = unique
            if retry_on_fail:
                data["retry_on_fail"] = True
            task = int_app.obj(QueueTask, data=data)
            task.store()

    def queue_run(self):
        req = self.req()
        m = re.match(r'(\S+?)\/(\S+)', req.args)
        if not m:
            self.call("web.not_found")
        app_tag, hook = m.group(1, 2)
        args = json.loads(req.param("args"))
        app = self.app().inst.appfactory.get_by_tag(app_tag)
        if app is None:
            self.call("web.not_found")
        app.hooks.call(hook, args)
        self.call("web.response_json", {"ok": 1})

    def queue_schedule(self):
        int_app = self.app().inst.int_app
        app_tag = self.app().tag
        try:
            sched = int_app.obj(Schedule, app_tag)
        except ObjectNotFoundException:
            sched = int_app.obj(Schedule, app_tag, data={
                "entries": {},
            })
        sched.app = weakref.ref(self.app())
        return sched

class Schedule(CassandraObject):
    _indexes = {
        "updated": [[], "updated"],
    }

    def __init__(self, *args, **kwargs):
        kwargs["clsprefix"] = "Schedule-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return Schedule._indexes

    def add(self, hook, at, priority=50):
        self.touch()
        entries = self.data["entries"]
        entries[hook] = {
            "at": at,
            "priority": priority,
        }

    def delete(self, hook):
        self.touch()
        entries = self.data["entries"]
        try:
            del entries[hook]
        except KeyError:
            pass

    def store(self):
        if self.get("entries") and len(self.get("entries")):
            self.set("updated", "%020d" % time.time())
            CassandraObject.store(self)
        else:
            self.remove()
        self.app().hooks.call("cluster.query_director", "/schedule/update/%s" % self.uuid)

class QueueRunner(Module):
    def register(self):
        Module.register(self)
        self.rhook("queue.process", self.queue_process)
        self.rhook("queue.processing", self.queue_processing)
        self.rhook("int-schedule.update", self.schedule_update)
        self.processing = set()
        self.processing_uniques = set()
        self.workers = 4

    def queue_process(self):
        self.wait_free = channel()
        while True:
            try:
                while self.workers <= 0:
                    self.wait_free.receive()
                tasks = self.objlist(QueueTaskList, query_index="at", query_finish="%020d" % time.time(), query_limit=10000)
                if len(tasks):
                    tasks.load()
                    tasks.sort(cmp=lambda x, y: cmp(x.get("priority"), y.get("priority")), reverse=True)
                    if len(tasks) > self.workers:
                        del tasks[self.workers:]
                    queue_workers = self.call("director.queue_workers")
                    if len(queue_workers):
                        tasks.remove()
                        for task in tasks:
                            worker = queue_workers.pop(0)
                            queue_workers.append(worker)
                            self.workers = self.workers - 1
                            Tasklet.new(self.queue_run)(task, worker)
                    else:
                        Tasklet.sleep(5)
                else:
                    Tasklet.sleep(1)
            except TaskletExit:
                raise
            except BaseException as e:
                logging.getLogger("mg.core.queue.Queue").exception(e)

    def queue_run(self, task, worker):
        self.processing.add(task.uuid)
        unique = task.get("unique")
        if unique is not None:
            self.processing_uniques.add(unique)
        success = False
        try:
            res = self.call("cluster.query_server", worker["host"], worker["port"], "/queue/run/%s/%s" % (str(task.get("app")), str(task.get("hook"))), {
                "args": json.dumps(task.get("args")),
            })
            if res.get("error"):
                self.warning("%s.%s(%s) - %s", task.get("app"), task.get("hook"), task.get("args"), res)
            success = True
        except HTTPError as e:
            self.error("Error executing task %s: %s" % (task.get("hook"), e))
        except TaskletExit:
            raise
        except BaseException as e:
            self.exception(e)
        self.workers = self.workers + 1
        self.processing.discard(task.uuid)
        if unique is not None:
            self.processing_uniques.discard(unique)
        if self.wait_free.balance < 0:
            self.wait_free.send(None)
        if not success and task.get("retry_on_fail"):
            task.set("at", "%020d" % (time.time() + 5))
            task.set("priority", task.get_int("priority") - 10)
            task = self.obj(QueueTask, data=task.data)
            task.store()
        elif task.get("args").get("schedule"):
            try:
                sched = self.obj(Schedule, task.get("app"))
                entries = sched.get("entries")
            except ObjectNotFoundException:
                entries = {}
            params = entries.get(task.get("hook"))
            if params is not None:
                self.schedule_task(task.get("app"), task.get("hook"), params)

    def queue_processing(self):
        return (self.processing, self.processing_uniques, self.workers)

    def schedule_update(self):
        req = self.req()
        app_tag = req.args
        try:
            sched = self.obj(Schedule, app_tag)
            entries = sched.get("entries")
        except ObjectNotFoundException:
            entries = {}
#       print "schedule for %s: %s" % (app_tag, entries)
        existing = self.objlist(QueueTaskList, query_index="app-at", query_equal=app_tag)
        existing.load()
        existing = dict([(task.get("unique"), task) for task in existing if task.get("args").get("schedule")])
#       print "existing: %s" % existing
        for hook, params in entries.iteritems():
            existing_params = existing.get(hook)
            if not existing_params:
#               print "adding task %s to the queue" % hook
                self.schedule_task(app_tag, hook, params)
            elif existing_params.get("priority") != params.get("priority") or existing_params.get("args").get("at") != params.get("at"):
#               print "rescheduling task %s in the queue" % hook
                self.schedule_task(app_tag, hook, params)
        for hook, task in existing.iteritems():
            if not entries.get(hook):
#               print "removing task %s from the queue" % hook
                task.remove()
        self.call("web.response_json", {"ok": 1})

    def schedule_task(self, app, hook, params):
#       print "scheduling task %s.%s, params=%s" % (app, hook, params)
        self.call("queue.add", hook, {"schedule": True, "at": params["at"]}, at=params["at"], priority=params["priority"], unique=hook, retry_on_fail=False, app_tag=app)

re_cron_num = re.compile('^\d+$')
re_cron_interval = re.compile('^(\d+)-(\d+)$')
re_cron_step = re.compile('^\*/(\d+)$')

class CronAny(object):
    def check(self, value):
        return True
    def __repr__(self):
        return "CronAny()"

class CronNum(object):
    def __init__(self, value):
        self.value = value
    def check(self, value):
        return value == self.value
    def __repr__(self):
        return "CronNum(%d)" % self.value

class CronInterval(object):
    def __init__(self, min, max):
        self.min = min
        self.max = max
    def check(self, value):
        return value >= self.min and value <= self.max
    def __repr__(self):
        return "CronInterval(%d, %d)" % (self.min, self.max)

class CronStep(object):
    def __init__(self, value):
        self.value = value
    def check(self, value):
        return value % self.value == 0
    def __repr__(self):
        return "CronStep(%d)" % self.value

class CronTime(object):
    def __init__(self, str):
        tokens = str.split(" ")
        self.valid = True
        if len(tokens) != 5:
            self.valid = False
            return
        self.tokens = []
        for token in tokens:
            if token == "*":
                self.tokens.append(CronAny())
                continue
            m = re_cron_num.match(token)
            if m:
                self.tokens.append(CronNum(int(token)))
                continue
            m = re_cron_interval.match(token)
            if m:
                min, max = m.group(1, 2)
                self.tokens.append(CronInterval(int(min), int(max)))
                continue
            m = re_cron_step.match(token)
            if m:
                value = m.group(1)
                if value <= 0:
                    self.valid = False
                    return
                self.tokens.append(CronStep(int(value)))
                continue
            self.valid = False
            return
        
    def __str__(self):
        return str(self.tokens)

    def next(self):
        if not self.valid:
            return None
#       print "now: %s" % datetime.datetime.utcfromtimestamp(time.time())
        tm = datetime.datetime.utcfromtimestamp(time.time() + 60).replace(microsecond=0, second=0)
        done = False
        while not done:
            done = True
            watchdog = 0
            while not self.tokens[0].check(tm.minute):
                done = False
                tm += datetime.timedelta(minutes=1)
                watchdog += 1
                if watchdog > 60:
                    return None
            watchdog = 0
            while not self.tokens[1].check(tm.hour):
                done = False
                tm = (tm + datetime.timedelta(hours=1)).replace(minute=0)
                watchdog += 1
                if watchdog > 24:
                    return None
            watchdog = 0
            while not self.tokens[2].check(tm.day):
                done = False
                tm = (tm + datetime.timedelta(days=1)).replace(minute=0, hour=0)
                watchdog += 1
                if watchdog > 62:
                    return None
            watchdog = 0
            while not self.tokens[3].check(tm.month):
                done = False
                if tm.month == 12:
                    tm = tm.replace(month=1, year=tm.year+1, day=1, minute=0, hour=0)
                else:
                    tm = tm.replace(month=tm.month+1, day=1, minute=0, hour=0)
                watchdog += 1
                if watchdog > 12:
                    return None
            watchdog = 0
            while not self.tokens[4].check(tm.isoweekday() % 7):
                done = False
                tm = (tm + datetime.timedelta(days=1)).replace(minute=0, hour=0)
                watchdog += 1
                if watchdog > 7:
                    return None
        return tm

class CronError(Exception):
    pass
