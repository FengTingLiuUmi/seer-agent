import struct
import unittest

from seer_rebuild.protocol import (
    FrameSplitter,
    H5Encoder,
    parse_h5,
    parse_flash,
    pack_flash,
    result_formula,
    serialize_args,
)


class ProtocolTest(unittest.TestCase):
    def test_serialize(self):
        self.assertEqual(serialize_args(["ab", 1, b"\x00", None, [2, "c"]]), b"ab" + struct.pack(">I", 1) + b"\x00" + struct.pack(">I", 2) + b"c")

    def test_h5_roundtrip(self):
        enc = H5Encoder(123456)
        f = enc.pack(1001, [b"\x00" * 8])
        self.assertEqual(len(f), 25)
        total, ver, cmd, uid, result = struct.unpack_from(">IBIII", f, 0)
        self.assertEqual((total, ver, cmd, uid), (25, 0x31, 1001, 123456))
        self.assertNotEqual(result, 0)
        p = parse_h5(f)
        self.assertEqual(p.cmd, 1001)
        self.assertEqual(p.body, b"\x00" * 8)

    def test_result_recurrence(self):
        body = b"\x01\x02\x03\x04"
        v1 = result_formula(0, 1001, body)
        v2 = result_formula(v1, 1001, body)
        self.assertNotEqual(v1, v2)
        # 有符号 32 位回绕
        self.assertTrue(-(2**31) <= v1 < 2**31)

    def test_flash_template(self):
        f = pack_flash(101, b"\x00" * 4, uid=8888)
        self.assertEqual(f.hex(), "000000150000000065000022b80000000000000000")
        p = parse_flash(f)
        self.assertEqual((p.cmd, p.uid, p.body), (101, 8888, b"\x00" * 4))

    def test_splitter_partial(self):
        enc = H5Encoder(1)
        a = enc.pack(1001, [b"a"])
        b = enc.pack(1002, [b"b"])
        sp = FrameSplitter("h5")
        self.assertEqual(sp.push(a[:5]), [])
        out = sp.push(a[5:] + b)
        self.assertEqual([x.cmd for x in out], [1001, 1002])


if __name__ == "__main__":
    unittest.main()