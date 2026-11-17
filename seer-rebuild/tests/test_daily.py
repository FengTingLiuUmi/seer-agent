import asyncio
import os
import unittest

from seer_rebuild.daily import AppDailyConfig, CommandTask, DailyRunner, TaskContext, load_app_daily_config
from seer_rebuild.progress import Observer, ProgressTracker
from seer_rebuild.protocol import Frame

CFG = r"F:\seer\seer_cfg\DLL\config\一键日常配置\一键日常ACCOUNT.ini"


class FakeClient:
    def __init__(self):
        self.sent = []

    async def request(self, cmd, args=None, *, timeout=10.0):
        self.sent.append((cmd, args))
        return Frame(cmd, 1, 0, b'{"ok":1}', b"")


class FakeSession:
    uid = 1


class DailyTest(unittest.TestCase):
    @unittest.skipUnless(os.path.exists(CFG), "app daily config not present")
    def test_config(self):
        cfg = load_app_daily_config(CFG)
        self.assertTrue(cfg.enabled("日常领取"))
        self.assertFalse(cfg.enabled("绿宝石"))
        self.assertEqual(cfg.value("失败次数"), 5)

    def test_runner(self):
        c = FakeClient()
        progress = ProgressTracker()
        ctx = TaskContext(c, FakeSession(), progress, Observer(), AppDailyConfig(), dry_run=False)
        tasks = [CommandTask("a", 8016), CommandTask("b", 2875, requires_write=True)]
        out = asyncio.run(DailyRunner(tasks, progress=progress, dry_run=False).run(ctx))
        self.assertEqual([x.name for x in tasks], ["a", "b"])
        self.assertEqual([s[0] for s in c.sent], [8016, 2875])
        self.assertEqual(out.records["a"].state.value, "done")

    def test_dry_run_skips_write(self):
        c = FakeClient()
        ctx = TaskContext(c, FakeSession(), ProgressTracker(), Observer(), AppDailyConfig(), dry_run=True)
        task = CommandTask("w", 2875, requires_write=True)
        detail = asyncio.run(task.run(ctx))
        self.assertIn("dry-run", detail)
        self.assertEqual(c.sent, [])


if __name__ == "__main__":
    unittest.main()