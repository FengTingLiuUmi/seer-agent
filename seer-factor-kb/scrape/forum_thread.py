# -*- coding: utf-8 -*-
"""抓单个线程正文，提取楼主+回复的纯文本，保存用于检视结构。
用法：python forum_thread.py <tid> [--page N] [--cookie-file f] [--out html]
"""
import sys, re, json, argparse, urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def fetch(url, cookie=None):
    headers = {"User-Agent": UA}
    if cookie:
        headers["Cookie"] = cookie
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tid")
    ap.add_argument("--page", default=1)
    ap.add_argument("--cookie-file", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    cookie = None
    if args.cookie_file:
        cookie = open(args.cookie_file, encoding="utf-8").read().strip()

    url = f"https://bbs.tiepi.top/thread-{args.tid}-{args.page}-1.html"
    html = fetch(url, cookie)
    out = args.out or f"thread-{args.tid}-p{args.page}.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"tid={args.tid} page={args.page} 已保存 {len(html)} 字节 -> {out}")


if __name__ == "__main__":
    main()