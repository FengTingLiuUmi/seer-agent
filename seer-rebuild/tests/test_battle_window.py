import os
import unittest

from seer_rebuild.applog import parse_battle_record
from seer_rebuild.battle import simulate
from seer_rebuild.battle_window import ReplayModel

DATA = r"F:\seer\seer_cfg\json"
BATTLE = r"F:\seer\seer_cfg\DLL\config\日常记录\出招记录\ACCOUNT.txt"


@unittest.skipUnless(os.path.isdir(DATA), "2.0.9 data directory not present")
class FromResultTest(unittest.TestCase):
    def test_turns_and_hp(self):
        result = simulate(DATA, player_ids=[3022], enemy_ids=[4649], max_turns=8)
        model = ReplayModel.from_result(result)
        self.assertTrue(model.turns)
        first = model.turns[0]
        self.assertEqual(first.turn, 1)
        self.assertTrue(first.player)
        self.assertTrue(first.enemy)
        self.assertGreater(first.player[0].max_hp, 0)
        self.assertTrue(0.0 <= first.player[0].ratio <= 1.0)
        self.assertEqual(model.result in ("胜利", "失败", "平局"), True)

    def test_hp_monotonic_within_turn(self):
        result = simulate(DATA, player_ids=[3437], enemy_ids=[4649], max_turns=10, seed=1)
        model = ReplayModel.from_result(result)
        # 同一回合内文本不应重复（快照切片正确）
        for t in model.turns:
            self.assertFalse(any(x.startswith("—— 第") for x in t.texts))


@unittest.skipUnless(os.path.exists(BATTLE), "battle record not present")
class FromRecordTest(unittest.TestCase):
    def test_replay(self):
        record = parse_battle_record(BATTLE)
        model = ReplayModel.from_record(record)
        self.assertTrue(model.turns)
        first = model.turns[0]
        self.assertTrue(first.player)
        self.assertTrue(first.enemy)
        names = [f.name for f in first.player] + [f.name for f in first.enemy]
        self.assertTrue(any(n and not n.isdigit() for n in names), names)
        self.assertIn(model.result, ("胜利", "失败", "平局"))


if __name__ == "__main__":
    unittest.main()