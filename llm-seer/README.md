# llm-seer —— 逆向 / 素材项目

和 `seer-proto`（可运行的客户端）分开存放，避免把几十 MB 的 SWF 和一次性探针混进客户端仓库。

## 目录

| 目录 | 内容 |
|---|---|
| `swf/` | 官方 SWF **原始文件**（加密/标准）：`Login.swf`、`Client.swf`、`TaomeeLibraryDLL.swf`、`RobotCoreDLL.swf`、`RobotAppDLL.swf` |
| `dec/` | 解包后的标准 SWF（`*.dec.swf`）。解密规则：`7 字节前缀 + zlib(CWS) + 内层 zlib` |
| `ref/` | 参考素材：`flash_as/`（Login.swf 的 271 个 AS）、`login_strings.txt`、`_history.js`、`_login_page.html`、`list105.bin`、`Server.xml`、`flash_ip.txt` |
| `tools/` | 逆向工具：`avm2.py`（自写 SWF/ABC 解析器）、`abcdis.py` |
| `probes/` | 一次性探测脚本（Flash TCP 各种实验、登录链探测、jsdom 页面跑） |
| `logs/` | 上述探测留下的日志 |
| `node_modules/` | 只给 `probes/page_*.mjs` 用（jsdom） |
| `cache/` | Go 构建缓存（`GOCACHE`/`GOMODCACHE`/`GOPATH`）；`seer-proto/build.bat` 指向这里 |

## 关键结论索引

- SWF 解密：见 `seer-proto/docs/HANDOFF.md`「进展：TaomeeLibraryDLL.swf 已解密」
- Flash TCP 服务器行为矩阵：`HANDOFF.md`「进展 2 / 3 / 4」
- 登录链逆向（`AccountManager/login`）：`HANDOFF.md`「进展 10」，素材即 `ref/_history.js`
- 雷小伊 的协议层：见 `seer-proto/docs/SUMMARY.md`

## 注意

- `swf/`、`dec/`、`node_modules/`、`logs/` 都已 gitignore（体积大/含临时数据）
- `ref/flash_as/` 含官方源码级反编译结果，仅供本地研究，不要公开分发