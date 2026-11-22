# -*- coding: utf-8 -*-
"""读 2301 单精灵详情，取关键精英精灵的 level。只读。"""
import asyncio, json, os, struct, sys
sys.path.insert(0, r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild")
os.environ["PYTHONIOENCODING"] = "utf-8"
from seer_rebuild.connection import open_unity
from seer_rebuild.commands import Cmd

def vault(name):
    import subprocess
    p = subprocess.run(["node", os.path.join(os.environ["DSH_PROFILE_DIR"], "node_modules",
                       "dsh-credential-vault", "vaultctl.mjs"), "show", name], capture_output=True)
    return json.loads(p.stdout.decode("utf-8", "replace"))

targets = {
    1658369845: "帝皇之御B", 1676555665: "帝皇之御C", 1613750784: "六界帝神",
    1659858712: "六界神王", 1610423766: "时空界皇", 1612503920: "圣光莫妮卡",
    1655656403: "蒂朵", 1718386667: "加尔鲁特", 1611937728: "千裳",
    1780942544: "闪光皮神", 1472551551: "圣灵谱尼", 1783026442: "神寂克罗诺斯",
    1674394140: "斯克鲁恩", 1610254294: "索比斯", 1719501515: "星光鲁斯王",
    1780518283: "泰坦", 1718379678: "西塔伦", 1782925191: "极渊DS-001",
    1649735537: "至序圣华", 1623393109: "启灵元神", 1613480178: "邪灵主宰摩哥斯",
    1458381168: "重生之翼", 1729402002: "天启星魂", 1611349897: "三藏",
    1611349900: "蒙奇多克",
}

async def main():
    cred = vault("赛尔号测试账号")
    u, s = str(cred["username"]), cred["secret"]
    c = await open_unity(u, s, timeout=25.0)
    out = {}
    for ct, nm in targets.items():
        await c.send(Cmd.GET_PET_INFO, [struct.pack(">I", ct)])
        loop = asyncio.get_running_loop()
        end = loop.time() + 3.0
        body = b""
        while loop.time() < end:
            try:
                f = await asyncio.wait_for(c.frames.get(), timeout=min(0.8, end-loop.time()))
            except asyncio.TimeoutError:
                continue
            if f.cmd == Cmd.GET_PET_INFO:
                body = f.body; break
        if len(body) >= 0x28:
            species = struct.unpack_from(">I", body, 0)[0]
            level = struct.unpack_from(">I", body, 0x24)[0]
            out[nm] = {"species_id": species, "level": level, "catch": ct}
        else:
            out[nm] = {"catch": ct, "body_len": len(body), "raw": body[:40].hex()}
    await c.close()
    print(json.dumps(out, ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(main())