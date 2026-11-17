import unittest

from seer_rebuild.session import GameSession, LoginInfo


class SessionTest(unittest.TestCase):
    def test_structure(self):
        s = GameSession("a", "b")
        self.assertEqual(s.account, "a")
        self.assertEqual(s.password, "b")
        self.assertIsNone(s._login)

    def test_login_info_type(self):
        # 只验证 dataclass 字段结构，不实测连网
        info = LoginInfo(uid=1, host="h", port=1203, result=0, body_hex="", masked_session="x")
        self.assertEqual(info.uid, 1)
        self.assertEqual(info.port, 1203)


if __name__ == "__main__":
    unittest.main()