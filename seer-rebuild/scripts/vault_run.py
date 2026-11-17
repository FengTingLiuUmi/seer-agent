"""从 dsh-credential-vault 取凭据，再运行 seer 子命令（把「取凭据 → 登录」串成一条）。

用法：
  python vault_run.py --vault "赛尔号验证用小号" bag
  python vault_run.py --vault "赛尔号验证用小号" factor --list --factor-id 2400611
  python vault_run.py --vault-id <条目id> session snapshot

说明：
  - `--vault <标题>` / `--vault-id <id>` 二选一，指定凭证库条目；
  - 其余参数原样透传给 `seer_rebuild.cli`；
  - 凭据通过环境变量 SEER_ACCOUNT / SEER_PASSWORD 注入（cli 已支持 env 回落），
    secret 不会打印到 stdout/stderr。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

# vaultctl 位置：优先环境变量 DSH_VAULTCTL，再默认 profile 下的 dsh-credential-vault
_DEFAULT_VAULTCTL = r"C:\Users\kmdbn\.dsh\profiles\desktop\node_modules\dsh-credential-vault\vaultctl.mjs"


def _main(argv: list[str]) -> int:
    ref: str | None = None
    rest: list[str] = []
    i = 0
    while i < len(argv):
        if argv[i] in ("--vault", "--vault-id") and i + 1 < len(argv):
            ref = argv[i + 1]
            i += 2
        else:
            rest.append(argv[i])
            i += 1

    if ref is None or not rest:
        print(__doc__)
        return 2

    vaultctl = os.environ.get("DSH_VAULTCTL", _DEFAULT_VAULTCTL)
    proc = subprocess.run(
        ["node", vaultctl, "show", ref],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr or "vaultctl 读取失败\n")
        return proc.returncode or 1
    entry = json.loads(proc.stdout)
    username = (entry.get("username") or "").strip()
    secret = (entry.get("secret") or "").strip()
    if not username or not secret:
        sys.stderr.write("凭证库条目缺少 username/secret\n")
        return 1

    env = dict(os.environ)
    env["SEER_ACCOUNT"] = username
    env["SEER_PASSWORD"] = secret
    env["PYTHONIOENCODING"] = "utf-8"
    # 透传给 seer_rebuild.cli（凭据走 env，不清洗、不打印）
    r = subprocess.run([sys.executable, "-m", "seer_rebuild.cli", *rest], env=env)
    return r.returncode


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))