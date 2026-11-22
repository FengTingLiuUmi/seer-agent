#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
base = "schema_dump"

for name in ["suit", "title", "nature"]:
    with open(f"{base}/{name}.json", encoding="utf-8") as f:
        d = json.load(f)
    print("=" * 40, name)
    defs = {}
    for part in d["schema"].get("allOf", []) or []:
        for k, v in (part.get("$defs") or {}).items():
            defs[k] = v
    print("DEFS:", sorted(defs.keys()))
    for k, v in defs.items():
        print(f"--- def {k} ---")
        print(json.dumps(v, ensure_ascii=False, indent=1))
    props = {}
    for part in d["schema"].get("allOf", []) or []:
        props.update(part.get("properties") or {})
    print("PROPS:")
    for k, v in props.items():
        print(f"  {k}: {v.get('description') or v.get('title') or v.get('type') or v.get('$ref')}")