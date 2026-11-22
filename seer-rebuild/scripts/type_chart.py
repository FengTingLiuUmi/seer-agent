"""从 seerapi 拉取全属性克制表，反查 6 个防御类型的 2x/4x 攻击属性。"""
import asyncio, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from seerapi import SeerAPI  # noqa: E402


async def main():
    async with SeerAPI() as api:
        info = {}
        async for it in api.list("element_type"):
            tid = it.id
            name = it.name
            rels = {}
            for r in (it.relations or []):
                rels[r.target_type.id] = r.multiple
            info[tid] = {"name": name, "relations": rels}
        ids = sorted(info)

    print("== element_type 表 ==")
    for tid in ids:
        print(f"  {tid}: {info[tid]['name']}")

    targets = {11: "战斗", 13: "暗影", 15: "龙", 2: "水", 14: "神秘", 3: "火"}
    print("\n== 反查：攻击属性 -> 防御类型（>=2x）==")
    for def_id, dname in targets.items():
        hits = []
        for att_id in ids:
            m = info[att_id]["relations"].get(def_id)
            if m and m >= 2:
                hits.append(f"{info[att_id]['name']} x{m}")
        print(f"  防御[{dname}]({def_id}) 被: {', '.join(hits) or '无'}")

    print("\n== 双属性 BOSS 4x 候选（两单属性都被同一攻击属性 2x）==")
    bosses = {
        "库坦 战斗+暗影": (11, 13),
        "艾莫莉萨 战斗+龙": (11, 15),
        "卡威治 水+神秘": (2, 14),
        "沙罗摩奥 火+暗影": (3, 13),
        "瓦坎 神秘+战斗": (14, 11),
    }
    for bn, (a, b) in bosses.items():
        hits4 = []
        for att_id in ids:
            ma = info[att_id]["relations"].get(a)
            mb = info[att_id]["relations"].get(b)
            if (ma or 0) >= 2 and (mb or 0) >= 2:
                hits4.append(info[att_id]["name"])
        print(f"  {bn}: 4x = {', '.join(hits4) or '无'}")


asyncio.run(main())