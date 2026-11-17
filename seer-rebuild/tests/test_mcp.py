import io
import json
import unittest

from seer_rebuild.mcp_server import TOOLS, handle_method, serve


class McpProtocolTest(unittest.TestCase):
    def test_tool_list(self):
        result = handle_method("tools/list", {})
        names = [t["name"] for t in result["tools"]]
        for expected in ("seer_login", "seer_battle_simulate", "seer_query", "seer_inventory", "seer_feature"):
            self.assertIn(expected, names)

    def test_initialize(self):
        result = handle_method("initialize", {"protocolVersion": "2024-11-05"})
        self.assertEqual(result["serverInfo"]["name"], "seer-rebuild-mcp")
        self.assertEqual(result["capabilities"]["tools"], {})

    def test_ping(self):
        self.assertEqual(handle_method("ping", {}), {})

    def test_battle_simulate(self):
        result = handle_method(
            "tools/call",
            {"name": "seer_battle_simulate", "arguments": {"player_ids": "3022", "enemy_ids": "4649", "max_turns": 5}},
        )
        self.assertFalse(result["isError"])
        text = result["content"][0]["text"]
        data = json.loads(text)
        self.assertIn("winner", data)
        self.assertIn("log", data)
        self.assertIn("当前回合", data["log"])


class McpServeTest(unittest.TestCase):
    def test_roundtrip(self):
        src = io.StringIO(
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}) + "\n"
            + json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}) + "\n"
        )
        out = io.StringIO()
        serve(src, out)
        replies = [json.loads(l) for l in out.getvalue().splitlines() if l.strip()]
        # 通知不回复，只有 tools/list 的回复
        self.assertEqual(len(replies), 1)
        self.assertEqual(replies[0]["id"], 1)
        self.assertIn("tools", replies[0]["result"])


if __name__ == "__main__":
    unittest.main()