# -*- coding: utf-8 -*-
"""检索层基准回归：mechanisms / docs(SSOT) / index(投影) / stats(先验) / plan(召回) 的不变量。
运行：$env:PYTHONPATH="...\.pylibs"; PYTHONUTF8=1 python test_kb.py
"""
import os, sys, json, unittest

HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
sys.path.insert(0, HERE)
SCRAPE = os.path.join(HERE, "..", "scrape").replace("\\", "/")

import mechanisms as M
import plan as P


class TestMechanisms(unittest.TestCase):
    def test_extract_golden(self):
        self.assertEqual(
            set(M.extract("单精灵；必先；封属；300固伤；免疫物攻；减伤16.7%")),
            {"singlePet", "firstStrike", "sealAttr", "fixedDamage", "immunePhysical", "damageReduction"})
        self.assertIn("twoLife", M.extract("必先；封属；两命；全属性+1"))
        self.assertIn("onlyFirstStrike", M.extract("只吃先制技能伤害"))

    def test_no_unmapped_over_all_traits(self):
        with open(f"{SCRAPE}/factors-final.json", encoding="utf-8") as f:
            fin = json.load(f)
        unmapped = 0
        for e in fin:
            for s in e.get("stages", []):
                if s.get("traits") and not M.extract(s["traits"]):
                    unmapped += 1
        self.assertEqual(unmapped, 0, "存在无法抽到任何机制标签的特性文本")


class TestDocs(unittest.TestCase):
    def test_catalog_unique_and_complete(self):
        cat = P.load_catalog()
        ids = [c["doc_id"] for c in cat]
        self.assertEqual(len(ids), len(set(ids)), "doc_id 不唯一")
        self.assertGreaterEqual(len(cat), 234)
        self.assertEqual(sum(c["n_stages"] for c in cat), 1267)

    def test_apex_only_on_stage5(self):
        import glob
        bad = []
        for fp in glob.glob(f"{HERE}/docs/*/*.json"):
            if fp.endswith("catalog.json"):
                continue
            with open(fp, encoding="utf-8") as f:
                d = json.load(f)
            for s in d["stages"]:
                if s.get("apex") and s["stage"] != 5:
                    bad.append((d["doc_id"], s["stage"]))
        self.assertEqual(bad, [])

    def test_every_stage_has_mech_when_traits(self):
        import glob
        for fp in glob.glob(f"{HERE}/docs/*/*.json"):
            if fp.endswith("catalog.json"):
                continue
            with open(fp, encoding="utf-8") as f:
                d = json.load(f)
            for s in d["stages"]:
                if s.get("traits"):
                    self.assertTrue(s.get("mech"), f"{d['doc_id']} 第{s['stage']}关有traits却无mech")
                    self.assertIsInstance(s["mech"], list)


class TestIndex(unittest.TestCase):
    def test_index_count_matches_docs(self):
        from whoosh import index
        ix = index.open_dir(f"{HERE}/index")
        self.assertEqual(ix.doc_count(), 1267)


class TestStats(unittest.TestCase):
    def test_stats_shape(self):
        with open(f"{HERE}/stats.json", encoding="utf-8") as f:
            st = json.load(f)
        self.assertIn("default_mechs", st)
        self.assertIn("by_position_difficulty", st)
        self.assertIn("cold_start_hints", st)
        for m in ("firstStrike", "sealAttr", "fixedDamage"):
            self.assertIn(m, st["default_mechs"], f"{m} 应为默认机制")

    def test_apex_two_life_prior(self):
        with open(f"{HERE}/stats.json", encoding="utf-8") as f:
            st = json.load(f)
        p5 = st["by_position"].get("5", {})
        self.assertGreater(p5.get("twoLife", {}).get("pct", 0), 30,
                           "第5关两命占比应显著（本体关先验）")


class TestPlan(unittest.TestCase):
    def test_r1_returns_whole_block(self):
        r = P.plan("佩洛瑟斯", "地狱", 3)
        self.assertEqual(len(r["r1_exact"]["stages"]), 5)
        self.assertIn("单精灵", r["query_hard_gates"] or r["query_mech"])

    def test_r1_error_for_unknown(self):
        r = P.plan("佩洛瑟斯", "简单", 3)
        self.assertIn("error", r)

    def test_r2_recall_full_coverage(self):
        r = P.plan("佩洛瑟斯", "地狱", 3)
        self.assertTrue(r["similar"], "应召回相似关")
        for c in r["similar"][:5]:
            self.assertEqual(c.get("gaps"), [], f"{c['doc_id']} 出现硬门缺口")
            self.assertNotEqual(c["doc_id"], "佩洛瑟斯#地狱", "不应召回当前关自身")


if __name__ == "__main__":
    unittest.main(verbosity=2)