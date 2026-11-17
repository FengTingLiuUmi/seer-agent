import json
import os
import unittest

from seer_rebuild.inventory import (
    _u32s,
    parse_clothes_from_1001,
    parse_equipment_from_1001,
    parse_frames_jsonl,
    resolve,
)
from seer_rebuild.provider import SeerApiProvider

FRAMES = r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild\feature1_frames.jsonl"


class InventoryParseTest(unittest.TestCase):
    def test_u32s(self):
        self.assertEqual(_u32s(bytes.fromhex("00000003000000110000002200000033")), [0x11, 0x22, 0x33])

    @unittest.skipUnless(os.path.exists(FRAMES), "feature1 frames not present")
    def test_parse(self):
        snap = parse_frames_jsonl(FRAMES)
        # 2604 CHANGE_CLOTH：换的是「装备」（头盔/护甲/武器），5 件 → equipment
        self.assertEqual(len(snap.equipment), 5)
        self.assertEqual(snap.equipment[0].id, 0x13D8BE)
        self.assertEqual(len(snap.clothes), 0)
        # 42399 MULTI_ITEM_LIST: 29 个道具
        self.assertEqual(len(snap.items), 29)
        self.assertEqual(snap.items[0].id, 0x00049422)

    def test_clothes_from_1001(self):
        # 前部 5 个连续 equip ID = 装扮段
        body = bytes.fromhex("2cf05a6e56e14d8ee9a38ee4b8b6e5819ce79599000000000013d9f90013da020013d9fa0013d8d40013d9fc")
        ids = parse_clothes_from_1001(body)
        self.assertEqual(ids, [0x13D9F9, 0x13DA02, 0x13D9FA, 0x13D8D4, 0x13D9FC])

    def test_equipment_from_1001(self):
        # 装备段：[count=5][id 0]*5
        body = bytes.fromhex("00000005" "0013da3000000000" "0013da3600000000" "0013da3400000000" "0013da3300000000" "0013da3500000000")
        ids = parse_equipment_from_1001(body)
        self.assertEqual(ids, [0x13DA30, 0x13DA36, 0x13DA34, 0x13DA33, 0x13DA35])


@unittest.skipUnless(os.path.exists(FRAMES), "feature1 frames not present")
class InventoryResolveTest(unittest.TestCase):
    def test_resolve_splits_equip_and_cloth(self):
        snap = parse_frames_jsonl(FRAMES)
        resolve(snap, SeerApiProvider())
        # 2604 换的是装备：5 件都在 equipment
        self.assertEqual(len(snap.equipment), 5)
        self.assertTrue(all(e.name for e in snap.equipment), "resolve 后装备有名字")
        self.assertTrue(any(i.name for i in snap.items))

    def test_resolve_title(self):
        snap = parse_frames_jsonl(FRAMES)
        resolve(snap, SeerApiProvider())
        self.assertEqual(len(snap.titles), 1)
        self.assertEqual(snap.titles[0].id, 417)
        self.assertIn("夏日狂想曲", snap.titles[0].name)
        self.assertIn("攻击+60", snap.titles[0].bonus)


if __name__ == "__main__":
    unittest.main()