import os
import struct
import unittest

from seer_rebuild.battle_data import BattleData
from seer_rebuild.pets import parse_bag_43706, parse_bag_45963, parse_pet_list, parse_warehouse_list, release_body

FIX_43706 = os.path.join(os.path.dirname(__file__), "fixture_43706.bin")
FIX_2361 = os.path.join(os.path.dirname(__file__), "fixture_2361.bin")
FIX_45963 = os.path.join(os.path.dirname(__file__), "fixture_45963.bin")
DATA = r"F:\seer\seer_cfg\json"


class ReleaseBodyTest(unittest.TestCase):
    def test_release_body(self):
        self.assertEqual(release_body(0x5FFD1DD6, 0).hex(), "5ffd1dd600000000")
        self.assertEqual(release_body(0x57C55A7F, 1).hex(), "57c55a7f00000001")


@unittest.skipUnless(os.path.exists(FIX_2361), "fixture 2361 missing")
class WarehouseTest(unittest.TestCase):
    def test_parse(self):
        with open(FIX_2361, "rb") as fh:
            body = fh.read()
        pets = parse_warehouse_list(body)
        self.assertGreater(len(pets), 100)
        # 圣灵谱尼 5000 在仓库里，catch_time 1472551551（2016）
        self.assertIn(5000, [p.species_id for p in pets])


@unittest.skipUnless(os.path.exists(FIX_43706), "fixture 43706 missing")
class BagTest(unittest.TestCase):
    def test_count(self):
        with open(FIX_43706, "rb") as fh:
            body = fh.read()
        count, _ = parse_bag_43706(body)
        self.assertEqual(count, 4)

    def test_species(self):
        with open(FIX_43706, "rb") as fh:
            body = fh.read()
        data = BattleData(DATA)
        count, pets = parse_bag_43706(body, data=data)
        self.assertEqual(count, 4)
        species = [p.species_id for p in pets]
        # 已确认的 2 只
        self.assertIn(3512, species)  # 帝皇之御
        self.assertIn(5000, species)  # 圣灵谱尼


@unittest.skipUnless(os.path.exists(FIX_45963), "fixture 45963 missing")
class Bag45963Test(unittest.TestCase):
    def test_parse(self):
        data = BattleData(DATA)
        with open(FIX_45963, "rb") as fh:
            raw = fh.read()
        pets = []
        off = 0
        while off + 4 <= len(raw):
            ln = struct.unpack_from(">I", raw, off)[0]
            body = raw[off + 4:off + 4 + ln]
            p = parse_bag_45963(body, data=data)
            if p:
                pets.append(p)
            off += 4 + ln
        species = [p.species_id for p in pets]
        self.assertEqual(len(pets), 3)
        self.assertEqual(species, [4321, 5000, 4169])  # 至序圣华 / 圣灵谱尼 / 弑序神罗


if __name__ == "__main__":
    unittest.main()