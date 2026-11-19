"""压血 / 自动恢复 / 回复 的命令序列（从 yaxue.pcapng + 雷小伊工具箱流程反解，端口1201）。

实测（伊娜普通第4关前置）：
  41129 [u32 8684]       发起白虎战(8684=圣尊啸傲·白虎试炼)  -> S2C 2503(战斗初始化)
  2404                    准备战斗                            -> S2C 2404(seed)+2504(开战)
  {2407[catch] + 2405[技能]}*N   逐只送血(白虎一发打死)
  2410                    结束战斗

管理类：
  41228 [u32 时间戳]      自动恢复开关（0x6afe0b13=关 / 0x6afe0b1e=开，body 是时间戳）
  42036 [u32 1][u32 flag] 全体回复
"""
import asyncio, struct, sys, os, json

def u32(v): return struct.pack('>I', v & 0xFFFFFFFF)


async def run(account, password, *, catches, skills, close_auto=True, recover=False):
    sys.path.insert(0, r'C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-rebuild')
    from seer_rebuild.client import GameClient
    from seer_rebuild.login import authenticate, get_unity_gateway

    sess = authenticate(account, password)
    host, port = get_unity_gateway()
    sess.host, sess.port, sess.path, sess.mode = host, port, "/", "unity"
    cl = GameClient(sess, mode="unity")
    await cl.connect(timeout=20.0)
    loop = asyncio.get_running_loop()

    async def send(cmd, body=b'', dur=1.0):
        await cl.send(cmd, [body] if body else [])
        end = loop.time() + dur
        while loop.time() < end:
            try:
                f = await asyncio.wait_for(cl.frames.get(), timeout=min(0.6, end - loop.time()))
            except asyncio.TimeoutError:
                continue

    if close_auto:
        await send(41228, u32(0x6afe0b13))
    if recover:
        await send(42036, u32(1) + struct.pack('>I', 0x57a701))
    await send(41129, u32(8684))
    await send(2404, b'', 2.0)
    for ct, sk in zip(catches, skills):
        await send(2407, u32(ct))
        await send(2405, u32(sk), 1.5)
    await send(2410)
    await cl.close()


if __name__ == '__main__':
    # 演示：压血当前要压的手（catch -> 各自可用技能）
    import subprocess
    def dec(r):
        for e in ('utf-8','gbk','gb18030'):
            try: return r.decode(e)
            except UnicodeDecodeError: continue
        return r.decode('utf-8','replace')
    p = subprocess.run(['node', os.path.join(os.environ['DSH_PROFILE_DIR'], 'node_modules', 'dsh-credential-vault', 'vaultctl.mjs'), 'show', '赛尔号测试账号'], capture_output=True)
    cred = json.loads(dec(p.stdout))
    asyncio.run(run(str(cred['username']), cred['secret'],
                    catches=[1782925191, 1619765584, 1781723960, 1717550270],
                    skills=[38020, 32912, 37911, 37005]))