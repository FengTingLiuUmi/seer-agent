import io,sys,json
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8")
p="ontology/pve_cases.json"
d=json.load(io.open(p,encoding="utf-8"))
d["_pending"]=[x for x in d["_pending"] if not str(x).startswith("仍有 64") and not str(x).startswith("still")]
d["_pending"].append("仍有 59 个社区简称本体认不出（八戒/冰熊/帝/星巴克以外的组合名…）。已解决 5 个：邪灵主宰、星光布布（别名）+ 星巴克、三兄弟、西游（阵容）。")
d["_pending"].append("label 不统一：58 只精灵有两个 rdfs:label（纯名 + 纯名带 PVE 注解），2167 条魂印完全没有 label。用户 2026-11-25 决定先不改数据；工具侧已把取值改成确定性规则（不带括号优先→最短→字典序）。")
json.dump(d,io.open(p,"w",encoding="utf-8"),ensure_ascii=False,indent=1)
print("pending:",len(d["_pending"]))
