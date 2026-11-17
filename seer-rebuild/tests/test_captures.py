import base64
import json
import os
import unittest

from seer_rebuild.captures import compact_1001_body, iter_capture, summarize
from seer_rebuild.protocol import parse_h5

CMDLOG = r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-auto\cmdlog2.jsonl"
CMDLOG4 = r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-auto\cmdlog4.jsonl"
FRAMES = r"C:\Users\kmdbn\Documents\deepseek-harness\default-workspace\seer\seer-auto\frames.jsonl"


class CaptureTest(unittest.TestCase):
    @unittest.skipUnless(os.path.exists(CMDLOG), "cmdlog2 not present")
    def test_summary(self):
        s = summarize(CMDLOG)
        self.assertGreater(s.frames, 0)
        self.assertEqual(s.login_uid, ACCOUNT)
        self.assertIsNotNone(s.login_body)
        self.assertEqual(len(s.login_body), 79)
        self.assertEqual(int.from_bytes(s.login_body[0x10:0x12], "big"), 0x6835)

    @unittest.skipUnless(os.path.exists(CMDLOG4), "cmdlog4 not present")
    def test_prefixed(self):
        frames = iter_capture(CMDLOG4)
        self.assertGreater(len(frames), 0)
        self.assertTrue(any(f.cmd == 1001 for f in frames))

    def test_compact(self):
        b = compact_1001_body(bytes.fromhex("11" * 16), 26677)
        self.assertEqual(len(b), 79)
        self.assertEqual(int.from_bytes(b[0x10:0x12], "big"), 26677)

    @unittest.skipUnless(os.path.exists(FRAMES), "frames.jsonl not present")
    def test_real_frame_parse(self):
        with open(FRAMES, encoding="utf-8") as fh:
            lines = [l for l in fh.read().splitlines() if l.strip()]
        d = json.loads(lines[0])
        raw = base64.b64decode(d["b64"])
        f = parse_h5(raw)
        self.assertEqual(f.cmd, d["cmd"])
        self.assertEqual(len(f.body), d["len"] - 17)


if __name__ == "__main__":
    unittest.main()