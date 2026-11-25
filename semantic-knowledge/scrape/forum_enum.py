# -*- coding: utf-8 -*-
"""枚举雷小伊论坛『因子脚本分享』(fid=15) 的全部主题线程。
难度由 typeid 区分：9=简单 / 10=困难 / 11=地狱。
输出 JSON：[{tid, title, typeid}]，按 typeid 汇总；每页结束即落盘，可断点续抓。
用法：python forum_enum.py <typeid> [--start-page N] [--max-pages N] [--out file.json]
"""
import sys, re, json, time, argparse, ssl, urllib.request

BASE_LIST = "https://bbs.tiepi.top/forum.php?mod=forumdisplay&fid=15&filter=typeid&typeid={typeid}&page={page}"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# 只匹配版块主题列表里的标题锚点（class="xst"），排除全局置顶/侧栏里的 thread 链接
thread_re = re.compile(r'<a href="thread-(\d+)-1-\d+\.html"[^>]*class="xst\b[^>]*>(.*?)</a>', re.S)
tag_re = re.compile(r'<[^>]+>')


def fetch(url, tries=6):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # 瞬断/限流/SSL 握手失败都重试
            last = e
            time.sleep(1.0 + i * 0.7)
    raise last


def parse_list(html):
    threads = {}
    for m in thread_re.finditer(html):
        tid = int(m.group(1))
        title = tag_re.sub("", m.group(2)).strip()
        if title and (tid not in threads or len(title) > len(threads[tid])):
            threads[tid] = title
    return threads


def save(data, out):
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("typeid")
    ap.add_argument("--start-page", type=int, default=1)
    ap.add_argument("--max-pages", type=int, default=0)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    typeid = args.typeid
    out = args.out or f"threads-{typeid}.json"

    all_t = {}
    page = args.start_page
    try:
        while True:
            if args.max_pages and page > args.max_pages:
                break
            html = fetch(BASE_LIST.format(typeid=typeid, page=page))
            got = parse_list(html)
            new = {k: v for k, v in got.items() if k not in all_t}
            print(f"typeid={typeid} page={page} 新增 {len(new)} 累计 {len(all_t)}", flush=True)
            all_t.update(got)
            save([{"tid": t, "title": v, "typeid": int(typeid)} for t, v in sorted(all_t.items())], out)
            if not new:  # Discuz 超出末页会重复返回最后一页（全是旧 tid）
                break
            page += 1
            time.sleep(0.4)
            if page > 200:
                break
    finally:
        save([{"tid": t, "title": v, "typeid": int(typeid)} for t, v in sorted(all_t.items())], out)
        print(f"完成 typeid={typeid} 共 {len(all_t)} 线程 -> {out}")


if __name__ == "__main__":
    main()