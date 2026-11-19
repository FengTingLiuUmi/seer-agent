import unittest

from seer_rebuild.yaxue import Target, build_steps

AUTO_OFF = "6afe0b13"


class BuildStepsTest(unittest.TestCase):
    def test_sequence_simple(self):
        ts = [Target(catch_time=0x62D8B735, skill=31505, name="帝皇之御"),
              Target(catch_time=0x602211AE, skill=19314, name="六界神王")]
        steps = build_steps(ts, close_auto=True, recover=False)

        # 关自动恢复 + 发起白虎战 + 准备战斗 + 2 只(切换+出招) + 结束战斗 = 8 步
        self.assertEqual(len(steps), 8)
        self.assertEqual(steps[0].cmd, 41228)
        self.assertEqual(steps[0].body.hex(), AUTO_OFF)
        self.assertEqual(steps[1].cmd, 41129)
        self.assertEqual(steps[1].body.hex(), "000021ec")  # 8684 = 0x21EC 圣尊啸傲·白虎试炼
        self.assertEqual(steps[2].cmd, 2404)
        self.assertEqual(steps[3].cmd, 2407)
        self.assertEqual(steps[3].body.hex(), "62d8b735")
        self.assertEqual(steps[4].cmd, 2405)
        self.assertEqual(steps[4].body.hex(), "00007b11")  # 31505
        self.assertEqual(steps[7].cmd, 2410)

    def test_recover_and_keep_auto(self):
        ts = [Target(catch_time=0x62D8B735, skill=31505)]
        with_recover = build_steps(ts, close_auto=True, recover=True)
        # 关自动恢复 + 治疗(47136) + 发起 + 准备 + (切换+出招) + 结束 = 7 步
        self.assertEqual(len(with_recover), 7)
        self.assertEqual(with_recover[1].cmd, 47136)
        self.assertEqual(with_recover[1].body.hex(), "")

        keep_auto = build_steps(ts, close_auto=False, recover=False)
        self.assertNotIn(41228, [s.cmd for s in keep_auto])
        self.assertEqual(keep_auto[0].cmd, 41129)

    def test_skill_zero_repr(self):
        ts = [Target(catch_time=0x62D8B735, skill=0)]
        steps = build_steps(ts)
        step = next(s for s in steps if s.cmd == 2405)
        self.assertEqual(step.body.hex(), "00000000")

    def test_starter_skips_first_switch(self):
        # 目标等于首发(已在场)时，不发 2407，直接 2405
        ts = [Target(catch_time=0x62D8B735, skill=31505),
              Target(catch_time=0x602211AE, skill=19314)]
        steps = build_steps(ts, starter=0x62D8B735)
        self.assertNotIn(2407, [s.cmd for s in steps[:4]])  # 第一只不切，直接出招
        # 第二只仍要先 2407 再 2405
        cmds = [s.cmd for s in steps]
        self.assertEqual(cmds[3], 2405)  # 第一只直接出招
        self.assertEqual(cmds[4], 2407)  # 切到第二只
        self.assertEqual(cmds[5], 2405)  # 第二只出招


if __name__ == "__main__":
    unittest.main()