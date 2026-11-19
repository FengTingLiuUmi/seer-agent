"""刷新账号打手库的「动态层」：三处读个体 → 2301 读等级+装备技能 → 缓存。

产物：data/roster_cache.json = { "<species_id>": [ {"catch_time":..,"level":..,"skills":[..]} ] }

用法：
    python scripts/refresh_roster.py
"""
import asyncio, struct, sys, os, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ['PYTHONIOENCODING'] = 'utf-8'

from seer_rebuild.client import GameClient
from seer_rebuild.login import authenticate, get_unity_gateway
from seer_rebuild.pet_details import read_pet_detail


def decode(raw):
    for enc in ('utf-8', 'gbk', 'gb18030'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode('utf-8', 'replace')


def vault(name):
    import subprocess
    p = subprocess.run(['node', os.path.join(os.environ['DSH_PROFILE_DIR'], 'node_modules',
                                             'dsh-credential-vault', 'vaultctl.mjs'), 'show', name],
                       capture_output=True)
    return json.loads(decode(p.stdout))


def read_2303_all(account, password):
    """普通仓库(2303)全量：返回 [{'species_id','flag','catch_time','level'}]"""
    async def run():
        sess = authenticate(account, password)
        host, port = get_unity_gateway()
        sess.host, sess.port, sess.path, sess.mode = host, port, "/", "unity"
        c = GameClient(sess, mode="unity")
        await c.connect(timeout=20.0)
        rows = []
        for offset in (0, 1000, 2000, 3000):
            await c.send(2303, [struct.pack('>I', offset), struct.pack('>I', 1000)])
            loop = asyncio.get_running_loop(); end = loop.time() + 10.0; body = b''
            while loop.time() < end:
                try:
                    f = await asyncio.wait_for(c.frames.get(), timeout=min(1.0, end - loop.time()))
                except asyncio.TimeoutError:
                    continue
                if f.cmd == 2303 and len(f.body) >= 4:
                    body = f.body; break
            if not body:
                break
            cnt = struct.unpack_from('>I', body, 0)[0]
            for k in range(cnt):
                o = 4 + k * 16
                if o + 16 > len(body):
                    break
                sp, fl, ct, lv = struct.unpack_from('>IIII', body, o)
                if 1 <= sp <= 6000:
                    rows.append({'species_id': sp, 'flag': fl, 'catch_time': ct, 'level': lv})
            if cnt < 1000:
                break
        await c.close()
        return rows
    return asyncio.run(run())


def main():
    cred = vault('赛尔号测试账号')
    u, s = str(cred['username']), cred['secret']

    # 三处个体（catch_time）
    indivs = {}
    # 普通仓库已有 level（2303 直接给），用它避免再 2301
    for r in read_2303_all(u, s):
        sp = r['species_id']
        indivs.setdefault(sp, []).append({'catch_time': r['catch_time'], 'level': r['level'], 'skills': None})

    # 普通仓库已带 level（2303 直接给），精英/背包的 2301 装备技能后续按需补
    out = {str(sp): v for sp, v in indivs.items()}
    (ROOT / 'data').mkdir(parents=True, exist_ok=True)
    (ROOT / 'data' / 'roster_cache.json').write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    n = sum(len(v) for v in out.values())
    print('缓存个体数=%d 物种数=%d -> data/roster_cache.json' % (n, len(out)))


if __name__ == '__main__':
    main()