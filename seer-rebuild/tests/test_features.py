import unittest

from seer_rebuild.features import CAPTURE_EQUIP, CAPTURE_FACTOR, bag_steps, factor_steps, list_body, format_steps


class FeatureTest(unittest.TestCase):
    def test_equip_bodies_match_capture(self):
        by_cmd = {s.cmd: s.body for s in bag_steps(
            pet_id=0x6ACE3260,
            item_ids=[0x00049422, 0x00155E20],
            forever_ids=[0x00000B05, 0x0001E4B6],
            cloth_ids=[0x0013D8BE, 0x0013DA30, 0x0013D8C0, 0x0013D8BF, 0x0013D8C1],
            title_id=0x1A1,
        )}
        self.assertEqual(by_cmd[2604].hex(), "000000050013d8be0013da300013d8c00013d8bf0013d8c1")
        self.assertEqual(by_cmd[3404].hex(), "000001a1")

    def test_factor_bodies_match_capture(self):
        by_cmd = {s.cmd: s.body for s in factor_steps(
            item_ids=[0x0024A163],
            factor_ids=[0x0004A0AA, 0x0004A0AB, 0x0004A0A8, 0x0001ECE8],
            pet_id=0x6ACE3260,
            factor_id=0x0024A052,
        )}
        self.assertEqual(by_cmd[42399].hex(), "000000010024a163")
        self.assertEqual(by_cmd[46046].hex(), "000000040004a0aa0004a0ab0004a0a80001ece8")
        self.assertEqual(by_cmd[41413].hex(), "0024a0520000000100000000")

    def test_capture_constants(self):
        self.assertTrue(any(s.cmd == 2604 and s.write for s in CAPTURE_EQUIP))
        self.assertTrue(any(s.cmd == 41413 and s.write for s in CAPTURE_FACTOR))
        self.assertNotIn(2304, [s.cmd for s in CAPTURE_EQUIP + CAPTURE_FACTOR])

    def test_dry_format(self):
        s = format_steps(CAPTURE_EQUIP, dry_run=True)
        self.assertIn("DRY-WRITE", s)
        self.assertIn("CHANGE_CLOTH", s)


if __name__ == "__main__":
    unittest.main()