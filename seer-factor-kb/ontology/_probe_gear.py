#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
from seerapi import SeerAPI
from seerapi._models import PageInfo

api = SeerAPI()

def dump(obj, path):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1, default=str)

def to_jsonable(x):
    # Pydantic models -> dict
    try:
        return x.model_dump()
    except Exception:
        return x

# one page of each list (paginated_list returns PagedResponse)
for res in ["suit", "title", "nature"]:
    try:
        r = api.paginated_list(res, PageInfo(offset=0, limit=100))
        data = {k: [to_jsonable(i) for i in getattr(r, k, [])] for k in ["first", "last", "next", "previous"]}
        data["_attrs"] = [a for a in dir(r) if not a.startswith("_")]
        dump(data, f"_list_{res}.json")
        print(res, "keys", list(data.keys()))
    except Exception as e:
        print(res, "ERR", type(e).__name__, str(e)[:200])

# single items (sync get)
for res, ids in [("suit", [1, 2, 3, 100, 1001, 10001]),
                 ("title", [1, 2, 100]),
                 ("nature", [1, 2, 3])]:
    for i in ids:
        try:
            it = api.get(res, i)
            dump(to_jsonable(it), f"_get_{res}_{i}.json")
            print(res, i, "ok")
        except Exception as e:
            print(res, i, "ERR", type(e).__name__, str(e)[:120])