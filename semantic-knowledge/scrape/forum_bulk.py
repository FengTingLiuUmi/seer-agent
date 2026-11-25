# -*- coding: utf-8 -*-
"""批量抓取因子线程第 1 页正文，抽取楼主帖 + 全页回帖纯文本，落 JSONL。
输入：threads-*.json（由 forum_enum.py 生成）
输出：threads-content.jsonl（每行一条，增量写入，可断点续抓）
用法：python forum_bulk.py [--cookie-file f] [--limit N] [--skip N]
"""
import os, re, json, time, sys, argparse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

post_re = re.compile(r'<td class="t_f" id="postmessage_(\d+)">(.*?)</td>', re.S)
tag_re = re.compile(r'<(script|style)[^>]*>.*?</\1>|<[^>]+>', re.S)
lock_re = re.compile(r'class="locked"|游客，如果您要查看本帖隐藏内容')
attach_re = re.compile(r'(?:zoomfile|file)="(data/attachment/[^"]+)"')


def html_to_text(html):
    # 块级/换行标签先转成换行，再整体去标签
    html = re.sub(r'<br\s*/?>|</p>|</div>|</tr>|</li>|</h[1-6]>|</font>', "\n", html)
    html = tag_re.sub("", html)
    import html as _h
    txt = _h.unescape(html)
    txt = re.sub(r'[ \t\u00a0]+', " ", txt)
    txt = re.sub(r'\n\s*\n+', "\n", txt)
    return txt.strip()


def fetch(url, cookie=None, tries=3):
    last = None
    for i in range(tries):
        try:
            headers = {"User-Agent": UA}
            if cookie:
                headers["Cookie"] = cookie
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            last = e
            time.sleep(2.0 + i * 1.5)
    raise last


def parse_thread(tid, html):
    title = ""
    m = re.search(r'<span id="thread_subject">(.*?)</span>', html, re.S)
    if m:
        title = html_to_text(m.group(1))
    # 每帖正文
    posts = []
    for pid, body in post_re.findall(html):
        posts.append({"pid": int(pid), "text": html_to_text(body)})
    main_post = posts[0]["text"] if posts else ""
    locked = bool(lock_re.search(html))
    atts = sorted(set(attach_re.findall(html)))
    return {
        "tid": int(tid), "title": title,
        "has_locked_hide": locked,
        "attachments": atts,
        "main_post": main_post,
        "posts": posts,
    }


def load_seen(out):
    seen = set()
    if os.path.exists(out):
        with open(out, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        seen.add(json.loads(line)["tid"])
                    except Exception:
                        pass
    return seen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cookie-file", default=None)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--skip", type=int, default=0)
    ap.add_argument("--out", default=f"{HERE}/threads-content.jsonl")
    args = ap.parse_args()

    cookie = None
    if args.cookie_file:
        cookie = open(args.cookie_file, encoding="utf-8").read().strip()

    # 合并三档索引
    threads = []
    for tidx in ["9", "10", "11"]:
        p = f"{HERE}/threads-{tidx}.json"
        if os.path.exists(p):
            threads += json.load(open(p, encoding="utf-8"))
    threads.sort(key=lambda x: x["tid"])

    seen = load_seen(args.out)
    todo = [t for t in threads if t["tid"] not in seen]
    if args.skip:
        todo = todo[args.skip:]
    if args.limit:
        todo = todo[: args.limit]
    print(f"总线程 {len(threads)}，已抓 {len(seen)}，本次待抓 {len(todo)}", flush=True)

    n = fail_streak = 0
    with open(args.out, "a", encoding="utf-8") as f:
        for t in todo:
            url = f"https://bbs.tiepi.top/thread-{t['tid']}-1-1.html"
            try:
                html = fetch(url, cookie)
                rec = parse_thread(t["tid"], html)
                rec["typeid"] = t["typeid"]
                rec["list_title"] = t["title"]
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
                n += 1
                fail_streak = 0
                if n % 20 == 0:
                    print(f"  进度 {n}/{len(todo)}", flush=True)
            except Exception as e:
                fail_streak += 1
                print(f"  tid={t['tid']} 抓取失败: {str(e)[:80]} (连续失败 {fail_streak})", flush=True)
                # 连续失败 → 论坛可能在限流，拉长冷却，避免越重试越糟
                if fail_streak >= 3:
                    print(f"  连续失败 {fail_streak} 次，冷却 30s 再继续…", flush=True)
                    time.sleep(30)
                    fail_streak = 0
            time.sleep(0.7)
    print(f"完成，新增 {n} 条 -> {args.out}")


if __name__ == "__main__":
    main()