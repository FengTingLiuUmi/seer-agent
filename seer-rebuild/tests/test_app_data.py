import os
import unittest

from seer_rebuild.battle import Battle
from seer_rebuild.battle_data import BattleData, BossTrait
from seer_rebuild.cjc import BattlePlan

DATA = r"F:\seer\seer_cfg\json"
METHOD = r"F:\seer\seer_cfg\script\method"


class AppDataTest(unittest.TestCase):
    @unittest.skipUnless(os.path.isdir(DATA), "2.0.9 data directory not present")
    def test_load(self):
        d = BattleData(DATA)
        self.assertGreater(len(d.species), 1000)
        self.assertGreater(len(d.moves), 1000)
        self.assertGreater(len(d.effects), 100)
        p = d.make_pet(3437)
        self.assertGreater(p.max_hp, 0)
        self.assertGreater(len(p.skills), 0)
        self.assertIn("龙", d.types)

    @unittest.skipUnless(os.path.isdir(DATA), "2.0.9 data directory not present")
    def test_battle(self):
        d = BattleData(DATA)
        p = d.make_pet(3437, side="player")
        e = d.make_pet(4649, side="enemy")
        e.max_hp = e.hp = 10000
        res = Battle(
            d,
            [p],
            [e],
            boss_traits=[BossTrait(77, [150, 0], "锋锐：每回合附加150点固定伤害")],
            seed=1,
        ).run(max_turns=5)
        self.assertTrue(res.log_lines)
        self.assertIn("当前回合", "\n".join(res.log_lines))

    @unittest.skipUnless(os.path.isdir(METHOD), "2.0.9 method directory not present")
    def test_cjc(self):
        import glob
        paths = glob.glob(os.path.join(METHOD, "**", "*.cjc"), recursive=True)
        if not paths:
            self.skipTest("no .cjc")
        plan = BattlePlan.load(paths[0])
        self.assertTrue(plan.plans or plan.refs)


if __name__ == "__main__":
    unittest.main()