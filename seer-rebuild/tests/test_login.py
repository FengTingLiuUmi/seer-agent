import unittest

from seer_rebuild.login import (
    APPID,
    LoginSession,
    build_flash_login,
    build_h5_login_body,
    extract_code,
    make_sid,
    oauth_authorize_url,
    parse_gateway,
)


class LoginTest(unittest.TestCase):
    def test_gateway(self):
        self.assertEqual(parse_gateway("h5gy.61.com/wss_online_02/:3002"), ("h5gy.61.com", 3002, "/wss_online_02/"))
        self.assertEqual(parse_gateway("123.207.217.117:3007"), ("123.207.217.117", 3007, "/"))

    def test_code(self):
        self.assertEqual(extract_code("https://account-co.61.com/v3/?r=authorization/success&code=ABC123"), "ABC123")
        self.assertEqual(extract_code("ABC123"), "ABC123")

    def test_oauth_url(self):
        u = oauth_authorize_url("d" * 32, "s" * 8)
        self.assertIn("appid=" + APPID, u)
        self.assertIn("authorization", u)
        self.assertIn("d" * 32, u)

    def test_login_body(self):
        s = LoginSession(uid=ACCOUNT, session="00" * 16, port=3007)
        b = build_h5_login_body(s, area_id=2514)
        self.assertEqual(b[:16], b"\x00" * 16)
        self.assertEqual(int.from_bytes(b[0x52:0x54], "big"), 3007)
        self.assertEqual(int.from_bytes(b[0x54:0x58], "big"), 2514)
        self.assertIn(b"unity_app_taomee", b)
        self.assertIn(b"com.taomee.seer.mobile", b)

    def test_sid(self):
        sid = make_sid(0x01020304, "11" * 16)
        self.assertEqual(sid[:4], b"\x01\x02\x03\x04")
        self.assertEqual(sid[4:], b"\x11" * 16)

    def test_flash_login(self):
        s = LoginSession(uid=123, session="00" * 16)
        f = build_flash_login(s)
        self.assertEqual(f[4], 0)  # Flash version
        self.assertEqual(int.from_bytes(f[5:9], "big"), 1001)
        self.assertEqual(int.from_bytes(f[9:13], "big"), 123)
        self.assertEqual(len(f), 17 + 44)

    def test_unity_login_layout(self):
        from seer_rebuild.login import build_unity_login_body
        s = LoginSession(uid=1, session="aa" * 16)
        b = build_unity_login_body(s, gate_id=0x699, area_id=1)
        self.assertEqual(len(b), 508)
        self.assertEqual(b[0:16], b"\xaa" * 16)
        self.assertEqual(b[0x10:0x16], b"taomee")
        self.assertEqual(int.from_bytes(b[0x50:0x54], "big"), 0x699)  # serverId u32 @0x50
        self.assertEqual(int.from_bytes(b[0x54:0x58], "big"), 1)
        self.assertEqual(b.find(b"unity_app_taomee"), 0x78)
        self.assertEqual(b.find(b"com.taomee.seer.mobile"), 0x98)
        self.assertTrue(b[0x178:0x180].startswith(b"MS-7D76"))

    def test_unity_serverid_random_range(self):
        from seer_rebuild.login import UNITY_SERVERID_RANGE, build_unity_login_body
        s = LoginSession(uid=1, session="aa" * 16)
        for _ in range(20):
            b = build_unity_login_body(s)
            sid = int.from_bytes(b[0x50:0x54], "big")
            self.assertTrue(
                UNITY_SERVERID_RANGE[0] <= sid <= UNITY_SERVERID_RANGE[1],
                f"serverId {sid} out of {UNITY_SERVERID_RANGE}",
            )


if __name__ == "__main__":
    unittest.main()