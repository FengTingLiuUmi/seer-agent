import io,sys,json
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8")
p="ontology/pve_cases.json"
d=json.load(io.open(p,encoding="utf-8"))
d["_pending"][0]="希可洛站场已入本体（seer:sustainSkill=奇镰解放 + 站场用法）；仍缺：金石猥咒术「使对手全属性-1」是否对 boss 生效未确认，决定破产之日每击 300 固伤有没有来源；也还没把 金石→破产→奇镰 的顺序做成 Step 序列。"
json.dump(d,io.open(p,"w",encoding="utf-8"),ensure_ascii=False,indent=1)
print("updated")
