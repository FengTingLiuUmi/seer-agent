# -*- coding: utf-8 -*-
import re
h = open(r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-factor-kb\scrape\raw11.html", encoding="utf-8").read()
r = re.compile(r'<a href="thread-(\d+)-1-1\.html"[^>]*class="xst"[^>]*>(.*?)</a>', re.S)
m = r.findall(h)
print("matches", len(m))
for x in m[:5]:
    print(x)