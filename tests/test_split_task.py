#!/usr/bin/env python3
"""Split units and the documentador: every part of a split unit with a task sees that task;
the parts that are not the last open one only comment, the last one completes it.
Run: python3 tests/test_split_task.py [-v]"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

CLI = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin", "roadmap")


class SplitTask(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = self.tmp.name
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(("ROADMAP_", "CLAUDE"))}
        subprocess.run(["git", "init", "-q", self.repo], check=True)
        self.rm("init", "t", "--title", "Test")
        self.dir = os.path.join(self.repo, ".claude", "roadmaps", "t")
        path = os.path.join(self.dir, "roadmap.json")
        with open(path) as f:
            rm = json.load(f)
        rm["documentador"] = {"project_id": 7}
        rm["units"] = [
            {"id": "01", "title": "Con tarea", "file": "units/01-con-tarea.md", "model": "haiku",
             "depends_on": [], "status": "pending", "task": 100},
            {"id": "02", "title": "Sin tarea", "file": "units/02-sin-tarea.md", "model": "haiku",
             "depends_on": [], "status": "pending", "task": None},
        ]
        for u in rm["units"]:
            with open(os.path.join(self.dir, u["file"]), "w") as f:
                f.write(f"# {u['id']}\n")
        with open(path, "w") as f:
            json.dump(rm, f)
        self.rm("validate", "t")

    def tearDown(self):
        self.tmp.cleanup()

    def rm(self, *args):
        r = subprocess.run([CLI, *args], cwd=self.repo, env=self.env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout

    def doc(self, unit):
        lines = [x for x in self.rm("brief", "t", unit).splitlines() if x.startswith("Documentador:")]
        self.assertEqual(self.rm("task", "-r", "t", unit).splitlines(), lines)
        if "-v" in sys.argv:
            print(f"\n  {unit}: " + "\n      ".join(lines), end="")
        return lines

    def split(self, unit, n):
        self.rm("split", "-r", "t", unit, "--children", json.dumps([{"title": f"parte {i}"} for i in range(1, n + 1)]))

    def assertComments(self, unit, task, owner):
        [line] = self.doc(unit)
        self.assertIn(f"task {task} (of unit {owner}, split; shared", line)
        self.assertIn("only comments", line)
        self.assertNotIn("completes", line)

    def assertCompletes(self, unit, task, owner):
        [line] = self.doc(unit)
        self.assertIn(f"task {task} (of unit {owner}, split; this is its last open part)", line)
        self.assertIn("completes it", line)

    def test_own_task_and_no_task(self):
        self.assertIn("task 100 (this unit's own). This session completes it", self.doc("01")[0])
        self.assertEqual(self.doc("02"), ["Documentador: off"])

    def test_split(self):
        self.split("01", 3)
        self.assertComments("01.1", 100, "01")
        self.rm("done", "-r", "t", "01.1")
        self.assertComments("01.2", 100, "01")
        self.rm("done", "-r", "t", "01.2")
        self.assertCompletes("01.3", 100, "01")

    def test_split_of_unit_without_task(self):
        self.split("02", 2)
        self.assertEqual(self.doc("02.1"), ["Documentador: off"])
        self.rm("done", "-r", "t", "02.1")
        self.assertEqual(self.doc("02.2"), ["Documentador: off"])

    def test_nested_split(self):
        self.split("01", 2)
        self.rm("done", "-r", "t", "01.1")
        self.assertCompletes("01.2", 100, "01")
        # The last part splits again: its parts take over, and only the last of them completes.
        self.split("01.2", 2)
        self.assertComments("01.2.1", 100, "01")
        self.rm("done", "-r", "t", "01.2.1")
        self.assertCompletes("01.2.2", 100, "01")

    def test_nested_split_of_a_middle_part(self):
        self.split("01", 3)
        self.split("01.1", 2)
        self.rm("done", "-r", "t", "01.1.1")
        self.assertComments("01.1.2", 100, "01")
        self.rm("done", "-r", "t", "01.1.2")
        self.assertComments("01.2", 100, "01")
        self.rm("done", "-r", "t", "01.2")
        self.assertCompletes("01.3", 100, "01")

    def test_blocked_part_keeps_task_open(self):
        self.split("01", 2)
        self.rm("block", "-r", "t", "01.1", "¿A o B?")
        self.assertIn("documentador task 100 (of 01)", self.rm("blocked", "t"))
        # 01.2 cannot complete while 01.1 is blocked.
        self.assertComments("01.2", 100, "01")
        self.rm("unblock", "-r", "t", "01.1")
        self.rm("done", "-r", "t", "01.1")
        self.assertCompletes("01.2", 100, "01")

    def test_part_with_its_own_task(self):
        self.split("01", 2)
        self.rm("set", "-r", "t", "01.2", "task=200")
        self.rm("done", "-r", "t", "01.1")
        own, parent = self.doc("01.2")
        self.assertIn("task 200 (this unit's own)", own)
        self.assertIn("task 100 (of unit 01, split; this is its last open part)", parent)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]] + [a for a in sys.argv[1:] if a != "-v"], verbosity=2 if "-v" in sys.argv else 1)
