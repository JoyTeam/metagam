import mg
from concurrence import Tasklet
import traceback

class Tasks(mg.Module):
    def register(self):
        self.rhook("int-tasks.index", self.tasks, priv="public")

    def tasks(self):
        cur = Tasklet.current()
        while cur.parent():
            cur = cur.parent()
        tasks = []
        for task, level in cur.tree():
            rtask = {
                "id": id(task),
                "name": task.name,
            }
            try:
                rtask["stack"] = traceback.format_stack(task.frame)
            except AttributeError:
                pass
            tasks.append({
                "level": level,
                "task": rtask
            })
        self.call("web.response_json", {
            "retval": tasks
        })

class TasksAdmin(mg.Module):
    def register(self):
        self.rhook("menu-admin-metagam.cluster", self.menu_cluster)
        self.rhook("ext-admin-tasks.monitor", self.tasks_monitor, priv="monitoring")
        self.rhook("headmenu-admin-tasks.monitor", self.headmenu_tasks_monitor)

    def menu_cluster(self, menu):
        req = self.req()
        if req.has_access("monitoring"):
            menu.append({"id": "tasks/monitor", "text": self._("Tasks monitor"), "leaf": True, "order": 20})

    def headmenu_tasks_monitor(self, args):
        return self._("Tasks monitor")

    def fetch_status(self, dmnid, rdaemon):
        try:
            tasklets = self.call("cluster.query-service", "%s-int" % dmnid, "/tasks", timeout=10)
        except Exception as e:
            rdaemon["error"] = str(e)
        else:
            rdaemon["tasklets"] = tasklets

    def tasks_monitor(self):
        req = self.req()
        int_app = self.app().inst.int_app
        daemons = int_app.call("cluster.daemons").items()
        daemons.sort(cmp=lambda x, y: cmp(x[0], y[0]))
        rdaemons = []
        tasklets = []
        for dmnid, daemon in daemons:
            rdaemon = {
                "id": dmnid,
            }
            tasklets.append(Tasklet.new(self.fetch_status)(dmnid, rdaemon))
            rdaemons.append(rdaemon)
        Tasklet.join_all(tasklets)
        vars = {
            "daemons": rdaemons
        }
        self.call("admin.response_template", "admin/tasks/monitor.html", vars)
