# -*- coding: utf-8 -*-
"""提取 SeerAPI 各资源 schema 的字段名（用于对齐「加成/效果」建模）。用法：python inspect_schemas.py"""
import os, json

HERE = os.path.dirname(os.path.abspath(__file__))
DUMP = os.path.join(HERE, "schema_dump")
os.makedirs(DUMP, exist_ok=True)

RES = ["title", "suit", "suit_bonus", "mintmark", "ability_mintmark", "universal_mintmark",
       "equip", "equip_type", "gem", "gem_category", "energy_bead", "nature",
       "buff", "buff_type", "battle_effect", "pet_effect", "pet_effect_group",
       "skill_effect_type", "skill_effect_param", "field_effect"]

def props_of(schema):
    out = {}
    for part in schema.get("allOf", []) or []:
        if "properties" in part:
            out.update(part["properties"])
    if "properties" in schema:
        out.update(schema["properties"])
    return out

for r in RES:
    tmp = os.path.join(DUMP, f"{r}.json")
    rc = os.system(f'seerapi describe {r} --scope item > "{tmp}" 2>nul')
    try:
        with open(tmp, encoding="utf-8", errors="replace") as fh:
            d = json.load(fh)
        schema = d.get("schema", {})
        props = props_of(schema)
        print(f"## {r} ({len(props)}) -> " + ", ".join(sorted(props.keys())))
    except Exception as e:
        print(f"## {r} ERR {e}")