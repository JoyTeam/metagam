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

class QueueTask(CassandraObject):
    _indexes = {
        "app-at": [["app"], "at"],
        "at": [[], "at"],
        "app-unique": [["app", "unique"]],
    }

    def __init__(self, *args, **kwargs):
        kwargs["prefix"] = "QueueTask-"
        CassandraObject.__init__(self, *args, **kwargs)

    def indexes(self):
        return QueueTask._indexes

class QueueTaskList(CassandraObjectList):
    def __init__(self, *args, **kwargs):
        kwargs["prefix"] = "QueueTask-"
        kwargs["cls"] = QueueTask
        CassandraObjectList.__init__(self, *args, **kwargs)

class Queue(Module):
    def register(self):
        Module.register(self)
        self.rhook("queue.add", self.queue_add)
        self.rhook("int-queue.run", self.queue_run)

    def queue_add(self, hook, args={}, at=None, priority=100, unique=None, retry_on_fail=False):
        int_app = self.app().inst.int_app
        with int_app.lock(["queue"]):
            app_tag = self.app().tag
            data = {
                "app": app_tag,
                "at": "%020d" % time.time(),
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
            if at is not None:
                raise RuntimeError("Not implemented")
            task = int_app.obj(QueueTask, data=data)
            task.store()

    def queue_run(self):
        req = self.req()
        m = re.match(r'(\S+?)\/(\S+)', req.args)
        if not m:
            self.call("web.not_found")
        app_tag, hook = m.group(1, 2)
        args = json.loads(req.param("args"))
        app = self.app().inst.appfactory.get(app_tag)
        if app is None:
            self.call("web.not_found")
        app.hooks.call(hook, args)
        self.call("web.response_json", {"ok": 1})

class QueueRunner(Module):
    def register(self):
        Module.register(self)
        self.rhook("queue.process", self.queue_process)
        self.rhook("queue.processing", self.queue_processing)
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
            self.call("cluster.query_server", worker["host"], worker["port"], "/queue/run/%s/%s" % (task.get("app"), task.get("hook")), {
                "args": json.dumps(task.get("args")),
            })
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

    def queue_processing(self):
        return (self.processing, self.processing_uniques, self.workers)
