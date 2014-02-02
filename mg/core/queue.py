#!/usr/bin/python2.6

# This file is a part of Metagam project.
#
# Metagam is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
# 
# Metagam is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with Metagam.  If not, see <http://www.gnu.org/licenses/>.

from mg.core.applications import Module
from mg.core.cass import CassandraObject, CassandraObjectList, ObjectNotFoundException
from mg.core.tools import *
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

class Schedule(CassandraObject):
    clsname = "Schedule"
    indexes = {
        "updated": [[], "updated"],
    }

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

class ScheduleList(CassandraObjectList):
    objcls = Schedule

class Queue(Module):
    def register(self):
        self.rhook("queue.add", self.queue_add)
        self.rhook("queue.schedule", self.queue_schedule)
        self.rhook("objclasses.list", self.objclasses_list)
        self.rhook("app.check", self.check)
        self.rhook("queue.schedule_task", self.schedule_task)

    def objclasses_list(self, objclasses):
        objclasses["Schedule"] = (Schedule, ScheduleList)

    def queue_add(self, hook, args={}, at=None, priority=100, unique=None, app_tag=None, app_cls=None):
        "Add single event to queue"
        int_app = self.app().inst.int_app
        if app_tag is None:
            app_tag = self.app().tag
        if app_cls is None:
            app_cls = self.app().inst.cls
        if at is None:
            at = self.now()
        elif not re_datetime.match(at):
            ct = CronTime(at)
            if ct.valid:
                next = ct.next()
                if next is None:
                    raise CronError("Invalid cron time")
                at = next.strftime("%Y-%m-%d %H:%M:%S")
            else:
                raise CronError("Invalid cron time")
        # Store queue entry
        def insert():
            int_app.sql_write.do("insert into queue_tasks(id, cls, app, at, priority, `unique`, hook, data) values (?, ?, ?, ?, ?, ?, ?, ?)", uuid4().hex, app_cls, app_tag, at, int(priority), unique, hook, json.dumps(args))
        if unique is not None:
            with int_app.lock(["queue"], reason="insert-unique-queue-task"):
                # Not reliable. May lose queue task if interrupted between queries.
                # Problem will be fixed automatically at midnight app.check.
                int_app.sql_write.do("delete from queue_tasks where app=? and `unique`=?", app_tag, unique)
                insert()
        else:
            insert()

    def queue_schedule(self, empty=False):
        "Return application schedule object"
        int_app = self.app().inst.int_app
        app_cls = self.app().inst.cls
        app_tag = self.app().tag
        if empty:
            sched = int_app.obj(Schedule, app_tag, data={
                "cls": app_cls,
                "entries": {},
            })
        else:
            try:
                sched = int_app.obj(Schedule, app_tag)
                sched.set("cls", app_cls)
            except ObjectNotFoundException:
                sched = int_app.obj(Schedule, app_tag, data={
                    "entries": {},
                })
        sched.app = weakref.ref(self.app())
        return sched

    def check(self):
        "Fast-check application (on create / nightly)"
        sched = self.call("queue.schedule", empty=True)
        self.call("queue-gen.schedule", sched)
        self.debug("Generated schedule for the project %s: %s", sched.uuid, sched.data["entries"])
        sched.store()
        self.schedule_update(sched)

    def schedule_update(self, sched):
        app_tag = sched.uuid
        inst = self.app().inst
        cls = inst.cls
        int_app = inst.int_app
        entries = sched.get("entries")
        existing = int_app.sql_write.selectall_dict("select * from queue_tasks where cls=? and app=?", cls, app_tag)
        for task in existing:
            task["data"] = json.loads(task["data"])
        existing = dict([(task.get("unique"), task) for task in existing if task["data"].get("schedule")])
        for hook, params in entries.iteritems():
            existing_params = existing.get(hook)
            if not existing_params:
                self.schedule_task(sched.get("cls"), app_tag, hook, params)
            elif existing_params.get("priority") != params.get("priority") or existing_params.get("at") != params.get("at"):
                self.schedule_task(sched.get("cls"), app_tag, hook, params)
        for hook, task in existing.iteritems():
            if not entries.get(hook):
                int_app.sql_write.do("delete from queue_tasks where id=?", task["id"])

    def schedule_task(self, cls, app, hook, params):
        if cls is not None:
            self.call("queue.add", hook, {"schedule": True, "at": params["at"]}, at=params["at"], priority=params["priority"], unique="%s.%s.%s" % (cls, app, hook), app_tag=app, app_cls=cls)

class QueueRunner(Module):
    def register(self):
        self.rhook("core.fastidle", self.fastidle)
        self.queue_task_running = False

    def queue_task_runner(self):
        inst = self.app().inst
        instid = inst.instid
        cls = inst.cls
        try:
            try:
                # Free my tasks
                self.sql_write.do("update queue_tasks set locked='', locked_till=null, priority=priority-1 where cls=? and locked=?", cls, instid)
                # Free tasks locked too long
                self.sql_write.do("update queue_tasks set locked='', locked_till=null, priority=priority-1 where locked_till<?", self.now())
                while True:
                    lock = self.lock(["queue"], reason="execute-queue")
                    if not lock.trylock():
                        return
                    try:
                        # Find task to run
                        tasks = self.sql_write.selectall_dict("select * from queue_tasks where cls=? and locked='' and at<=? order by priority desc limit 1", cls, self.now())
                        if not tasks:
                            return
                        task = tasks[0]
                        self.sql_write.do("update queue_tasks set locked=?, locked_till=? where id=?", instid, self.now(86400), task["id"])
                        ctl = self.sql_write.selectall_dict("select * from queue_tasks where id=?", task["id"])
                    finally:
                        lock.unlock()
                    # Execute task
                    app_tag = str(task["app"])
                    hook = str(task["hook"])
                    args = json.loads(task["data"])
                    self.debug("Executing %s.%s", app_tag, hook)
                    app = self.app().inst.appfactory.get_by_tag(app_tag)
                    if app is None:
                        self.info("Found queue event for unknown application %s", app_tag)
                        main_app = self.main_app()
                        if main_app.call("project.missing", app_tag):
                            self.info("Removing missing project %s", app_tag)
                            main_app.call("project.cleanup", app_tag)
                    else:
                        schedule = args.get("schedule")
                        at = args.get("at")
                        if schedule:
                            del args["schedule"]
                            if at:
                                del args["at"]
                        try:
                            app.call(hook, **args)
                            success = True
                        except Exception as e:
                            self.exception(e)
                            success = False
                        if success:
                            self.info("Finished task %s (%s in application %s)", task["id"], task["hook"], task["app"])
                            # Reschedule finished task to later time
                            if schedule:
                                try:
                                    sched = self.obj(Schedule, app_tag)
                                    entries = sched.get("entries")
                                except ObjectNotFoundException:
                                    entries = {}
                                params = entries.get(hook)
                                if params is not None:
                                    self.call("queue.schedule_task", task.get("cls"), app_tag, hook, params)
                            self.sql_write.do("delete from queue_tasks where id=?", task["id"])
                        else:
                            self.error("Failed task %s (%s in application %s)", task["id"], task["hook"], task["app"])
                            self.sql_write.do("update queue_tasks set locked='', locked_till=null, priority=priority-10, at=? where id=? and locked=?", self.now(5), task["id"], instid)
            except Exception as e:
                self.exception(e)
        finally:
            self.queue_task_running = False

    def fastidle(self):
        if not self.queue_task_running:
            self.queue_task_running = True
            Tasklet.new(self.queue_task_runner)()

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
