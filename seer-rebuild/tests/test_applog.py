import os
import unittest

from seer_rebuild.applog import parse_battle_record, parse_daily_log, summarize

DAILY = r"F:\seer\seer_cfg\DLL\config\日常日志\20260607-ACCOUNT.ini"
BATTLE = r"F:\seer\seer_cfg\DLL\config\日常记录\出招记录\ACCOUNT.txt"


class AppLogTest(unittest.TestCase):
    @unittest.skipUnless(os.path.exists(DAILY), "daily log not present")
    def test_daily(self):
        s = summarize(parse_daily_log(DAILY))
        self.assertGreater(s.events, 0)
        self.assertTrue(s.areas)

    @unittest.skipUnless(os.path.exists(BATTLE), "battle record not present")
    def test_battle(self):
        r = parse_battle_record(BATTLE)
        self.assertTrue(r.player)
        self.assertTrue(r.enemy)
        self.assertIsNotNone(r.result)


if __name__ == "__main__":
    unittest.main()