# -*- coding: utf-8 -*-
"""把 _sec9.md 拼到知识库文档末尾（替换已有的 ## 9. 段落）。一次性修复脚本。"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
KB = os.path.join(HERE, "..", "赛尔号因子PVE打法知识库.md")
SEC = os.path.join(HERE, "_sec9.md")

t = open(KB, encoding="utf-8").read()
i = t.find("## 9.")
if i > 0:
    t = t[:i].rstrip() + "\n\n"
sec = open(SEC, encoding="utf-8").read()
out = t + sec
open(KB, "w", encoding="utf-8").write(out)
print("len", len(out), "backspace", out.count("\b"), "formfeed", out.count("\x0c"))