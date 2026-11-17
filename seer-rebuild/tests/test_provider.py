import shutil
import unittest

from seer_rebuild.provider import SeerApiError, SeerApiProvider, build_provider


@unittest.skipUnless(shutil.which("seerapi"), "seerapi CLI not installed")
class SeerApiProviderTest(unittest.TestCase):
    def test_pet_and_skill(self):
        p = SeerApiProvider()
        pet = p.pet(3022)
        self.assertEqual(pet["id"], 3022)
        self.assertIn("base_stats", pet)
        skill = p.skill(19248)
        self.assertEqual(skill["power"], 85)
        self.assertEqual(p.name("item", 300697), "全面提升药剂")

    def test_find_by_name(self):
        p = SeerApiProvider()
        items = p.find("pet", "王之哈莫", limit=3)
        self.assertTrue(items)


class BuildProviderTest(unittest.TestCase):
    def test_off_by_default(self):
        self.assertIsNone(build_provider(False))

    def test_on(self):
        self.assertIsNotNone(build_provider(True))


if __name__ == "__main__":
    unittest.main()