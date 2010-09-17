from mg.core import Module
from mg.core.cass import CassandraObject, CassandraObjectList, ObjectNotFoundException
from concurrence import Tasklet
from concurrence.http import HTTPConnection, HTTPError, HTTPRequest
from stackless import channel
from urllib import urlencode
from uuid import uuid4
import json
import time

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
        self.rhook("queue.process", self.queue_process)
        self.rhook("queue.processing", self.queue_processing)
        self.processing = set()
        self.processing_uniques = set()

    def queue_add(self, hook, args, at=None, priority=100, unique=None, retry_on_fail=False):
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
            print "storing task %s: %s(%s) with priority=%d" % (task.uuid, hook, args, int(priority))
            task.store()

    def queue_process(self):
        self.workers = 1
        self.wait_free = channel()
        while True:
            if self.workers > 0:
                self.workers = self.workers - 1
            else:
                self.wait_free.recv()
            tasks = self.objlist(QueueTaskList, query_index="at", query_finish="%020d" % time.time())
            if len(tasks):
                tasks.sort(key=lambda x, y: cmp(a.get("priority"), b.get("priority")), reverse=True)
                print "sorted tasks: %s" % tasks
                task = tasks[0]
                task.remove()
                Tasklet.new(self.queue_worker)(task)
            else:
                self.workers = self.workers + 1
                Tasklet.sleep(5)

    def queue_worker(self, task):
        print "starting processing task %s (%s)" % (task, task.data)
        self.processing.add(task.uuid)
        unique = task.get("unique")
        if unique is not None:
            self.processing_uniques.add(unique)
        try:
            pass
        finally:
            self.processing.discard(task.uuid)
            if unique is not None:
                self.processing_uniques.discard(unique)
            print "finished processing task %s" % task
            if self.wait_free.balance < 0:
                self.wait_free.send(None)
            else:
                self.workers = self.workers + 1

    def queue_processing(self):
        return (self.processing, self.processing_uniques)
