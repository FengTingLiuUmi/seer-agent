# -*- coding: utf-8 -*-
import inspect
from seerapi import SeerAPI

print("init:", inspect.signature(SeerAPI.__init__))
for m in ["list", "get", "get_by_name", "search_by_name", "paginated_list"]:
    fn = getattr(SeerAPI, m, None)
    if fn:
        try:
            print(m, inspect.signature(fn))
        except (ValueError, TypeError) as e:
            print(m, "sig?", e)

api = SeerAPI()
print("instantiated OK", type(api))
for call in ["search_by_name", "get_by_name", "list"]:
    try:
        if call == "search_by_name":
            r = api.search_by_name("pet", "哈莫")
        elif call == "get_by_name":
            r = api.get_by_name("pet", "帝皇之御")
        else:
            r = api.list("pet", name="哈莫", limit=6)
        print(call, "->", type(r).__name__)
        if hasattr(r, "results"):
            print("   results[0]:", r.results[0] if r.results else None)
        elif isinstance(r, dict):
            print("   keys:", list(r.keys())[:12], "| name=", r.get("name"))
        else:
            print("   repr:", str(r)[:200])
    except Exception as e:
        print(call, "FAIL", type(e).__name__, str(e)[:160])