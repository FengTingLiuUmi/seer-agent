from seer_rebuild.session import GameSession


def main():
    s = GameSession("ACCOUNT", "PASSWORD")
    info = s.login(keep=5.0)
    print("登录结果:", info.uid, info.host, info.port, "1001 result =", info.result)
    print("装备/装扮/称号 采集完成 (login body len =", len(info.body_hex) // 2, ")")
    s.close()


if __name__ == "__main__":
    main()