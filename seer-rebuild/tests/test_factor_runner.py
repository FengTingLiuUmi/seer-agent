import unittest

from seer_rebuild.factor import DEFAULT_LINEUP, FACTOR_STAGES, factor_progress, factor_enter_steps, battle_loop_steps, KNOWN_FACTORS
from seer_rebuild.factor_runner import (
    FactorStagePlan,
    FLAG_CLEAR_RESERVE,
    FLAG_TO_BAG,
    FLAG_TO_RESERVE,
    build_factor_stage_steps,
    parse_forever,
    parse_stage_list,
)


class FactorRunnerParseTest(unittest.TestCase):
    def test_parse_stage_list(self):
        # 45543 响应：[count=2] + 2×16B
        body = bytes.fromhex(
            "00000002"
            "00000046" "56e14de5" "00000000" "00000064"
            "00000661" "56e14e22" "00000000" "00000064"
        )
        entries = parse_stage_list(body)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].entry_id, 0x46)
        self.assertEqual(entries[0].progress, 100)
        self.assertEqual(entries[1].entry_id, 0x661)

    def test_parse_forever(self):
        body = bytes.fromhex("0000000400020100000000030000000000000020")
        self.assertEqual(parse_forever(body), [0x20100, 3, 0, 0x20])

    def test_factor_progress(self):
        self.assertEqual(factor_progress([3, 0, 2]), 3)
        self.assertEqual(factor_progress([0, 0, 0]), 0)
        self.assertEqual(factor_progress([]), 0)


class FactorRunnerBuildTest(unittest.TestCase):
    def test_stage_list_bodies_match_capture(self):
        plan = FactorStagePlan(stage_index=1, boss_species=3296, boss_id=0x6F, skills={3296: 0x798A})
        steps = build_factor_stage_steps(plan)
        by_cmd = {}
        for s in steps:
            by_cmd.setdefault(s.cmd, []).append(s)
        # lxy_yz_3 选关时序：45543 分页 [0,999] + [1000,1999]
        lists = by_cmd[45543]
        self.assertEqual(lists[0].body.hex(), "00000000000003e7")
        self.assertEqual(lists[1].body.hex(), "000003e8000007cf")

    def test_fight_bodies_match_capture(self):
        # lxy_yz_2：42396 body=[关卡id][1][1]，2414? 无；2404 空；2405 body=[技能id]
        plan = FactorStagePlan(stage_index=3, boss_species=4938, boss_id=0x6F, skills={4938: 0x798A})
        steps = build_factor_stage_steps(plan)
        by_cmd = {s.cmd: s for s in steps}
        self.assertEqual(by_cmd[42396].body.hex(), "0000006f0000000100000001")
        self.assertEqual(by_cmd[2404].body, b"")
        self.assertEqual(by_cmd[2405].body.hex(), "0000798a")
        # 47136 出现两次（战前 + 战后）
        self.assertEqual(len([s for s in steps if s.cmd == 47136]), 2)

    def test_lineup_switch_flags(self):
        plan = FactorStagePlan(
            stage_index=1,
            boss_species=3296,
            clear_reserve=[0x600EB73D],
            lineup_catch=[0x601F36EB],
            reserve_catch=[0x600B3F89],
        )
        steps = build_factor_stage_steps(plan)
        rel = [s for s in steps if s.cmd == 2304]
        bodies = [s.body.hex() for s in rel]
        self.assertIn("600eb73d00000003", bodies)  # 清待命
        self.assertIn("601f36eb00000001", bodies)  # 加正式
        self.assertIn("600b3f8900000002", bodies)  # 加待命

    def test_collect_step(self):
        plan = FactorStagePlan(stage_index=1, boss_species=3296, factor_id=0x24A052)
        steps = build_factor_stage_steps(plan)
        collect = [s for s in steps if s.cmd == 41413][0]
        self.assertEqual(collect.body.hex(), "0024a0520000000100000000")
        self.assertTrue(collect.write)

    def test_official_enter_steps(self):
        # 官方 Unity 端：41284/41282 body=[design_id][difficulty]（unity_mzyx 实证；1=简单）
        steps = factor_enter_steps(design_id=228, difficulty=1)
        self.assertEqual(len(steps), 2)
        self.assertEqual(steps[0].cmd, 41284)
        self.assertEqual(steps[0].body.hex(), "000000e400000001")
        self.assertEqual(steps[1].cmd, 41282)
        self.assertEqual(steps[1].body.hex(), "000000e400000001")

    def test_stage_plan_uses_design_id(self):
        # 难度固定 1（简单），不随 stage_index 变；第几关由服务端按进度自动推进
        plan = FactorStagePlan(stage_index=3, boss_species=3599, design_id=228)
        steps = build_factor_stage_steps(plan)
        cmd12 = [s for s in steps if s.cmd in (41284, 41282)]
        self.assertEqual([s.body.hex() for s in cmd12], ["000000e400000001", "000000e400000001"])

    def test_battle_loop_steps(self):
        # unity_yz_battle 实证：2404 → 2405(技能) → 2407(切换) → 2405 → 2407 → 2405
        steps = battle_loop_steps(skills=[31505, 19314, 19932], switches=[0x62EF6F18, 0x6AF9CF5E])
        self.assertEqual([s.cmd for s in steps], [2404, 2405, 2407, 2405, 2407, 2405])
        self.assertEqual(steps[1].body.hex(), "00007b11")   # 31505
        self.assertEqual(steps[2].body.hex(), "62ef6f18")   # 切换 catch_time
        self.assertEqual(steps[3].body.hex(), "00004b72")   # 19314

    def test_known_factors_have_design(self):
        jj = KNOWN_FACTORS[2400545]
        self.assertEqual(jj.name, "戟决先锋因子")
        self.assertEqual(jj.design_id, 228)
        self.assertEqual(jj.bosses, [3618, 3595, 3599, 3978, 4857])


class FactorStageDataTest(unittest.TestCase):
    def test_stages_are_current_factor(self):
        self.assertEqual(len(FACTOR_STAGES), 5)
        for st in FACTOR_STAGES:
            self.assertTrue(1 <= st["boss_species"] <= 6000, st)
            self.assertTrue(st.get("boss_name"), st)
        # 谜之英雄因子的 5 关 BOSS（seerapi factor_design 225 固化）
        self.assertEqual([s["boss_species"] for s in FACTOR_STAGES], [4539, 4330, 4137, 4845, 4848])

    def test_default_lineup_is_derivable_not_hardcoded(self):
        # 阵容取决于账号背包（catch_time），不再硬编码；这里只保证空集合不误报
        self.assertEqual(DEFAULT_LINEUP, {})


if __name__ == "__main__":
    unittest.main()