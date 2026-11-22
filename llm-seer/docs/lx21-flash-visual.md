# 雷小伊登录器 2.0.21 —— Flash 端「可视化操作」依据

## 一、被逆向的目标

`F:\seer\雷小伊登录器 2.0.21.exe`（12.7 MB）

| 事实 | 证据 |
|---|---|
| 加壳（UPX 变体，非原版 UPX） | PE 段名 `.upx0/.upx1/.upx2`，但 `upx -d` 报 `NotPackedException` |
| IAT 被打成 stub | 每个 DLL 只剩 1 个导入项（如 `KERNEL32: GetVersion`、`USER32: PostThreadMessageA`） |
| 疑似 Delphi/VCL | 导入包含 `ole32 CoRevokeClassObject`、`oledlg`、`comctl32 ImageList_Destroy`、`msvfw32 DrawDibDraw`、`avifil32 AVIStreamInfo`、`GDI32 CreateBrushIndirect`、`MSIMG32 GradientFill` |

⇒ **静态看不进去**（真实 import 与字符串都在壳里），要么内存 dump，要么从它依赖的**磁盘件**还原行为。

## 二、结论：它的「Flash 可视化操作」= Flash 播放器 + 大漠插件 + 识图模板

磁盘证据（都在 `F:\seer` 和用户目录）：

| 组件 | 位置 | 说明 |
|---|---|---|
| **Flash Player ActiveX 34.0.0.155** | `C:\Windows\SysWOW64\Macromed\Flash\Flash32_34_0_0_155.ocx`（11.3 MB）/ `System32\...\Flash64_34_0_0_155.ocx`（13.1 MB）+ `FlashUtil64_..._ActiveX.dll` | 系统已装（EOL 版本仍被本机保留），说明登录器用 OCX 宿主播放 SWF |
| **独立 Flash 播放器** | `C:\Users\kmdbn\Downloads\外国版flash.exe`（10.2 MB, ver 1.0.0.0） | 备用播放方式（projector） |
| **大漠插件** | `F:\seer\识图\dm.dll`（823 KB） | ProgID `dm.dmsoft`；字符串计数：`FindPic×16`、`Capture×17`、`BindWindow×8`、`GetColor×10` ⇒ 找图/找色/截图/绑窗口 |
| **识图模板** | `F:\seer\识图\img\确认{1..18}.bmp`（2.5–5.7 KB） | 18 张「确认」按钮模板 |
| **Flash 端业务插件** | `F:\seer\seer_cfg\DLL\center\一键Flash端老SPT成就v1.1.dll`（6.6 MB, ver 6.7.8.5） | 插件市场按需下载的 Flash 侧扩展 |
| 插件市场清单 | `F:\seer\seer_cfg\DLL\list.ini`（21.8 KB） | 「精灵/工具/精灵王」分类与下载链接 |

**还原出的操作链（推断，全部环节都有对应磁盘证据）**：

```
登录器(2.0.21)
  ├─ 创建/托管 Flash 宿主窗口（Flash32.ocx 或 外国版flash.exe）
  │     └─ 加载官方 SWF（登录 → 进入游戏）
  ├─ dm.BindWindow(hwnd, "gdi"/"dx", ...)           ← 绑定游戏窗口
  ├─ dm.Capture → dm.FindPic(识图\img\*.bmp)        ← 找按钮/状态
  ├─ dm.MoveTo/LeftClick                            ← 点击
  └─ 加载 seer_cfg\DLL\center\*.dll                 ← 业务扩展（成就/日常）
```

也就是说：**它不靠"协议"理解游戏，而是"看图 + 点鼠标"**——这正是我们要给 agent 的 Flash 视觉能力。

## 三、对 seer-proto 的意义：这条链可以不依赖它的内核就复刻

关键点：**不需要逆出 2.0.21 内部代码**，因为可视化操作所需的三件东西都在磁盘上：
窗口（Flash 宿主）+ 截图 + 模板匹配/点击。

已实现的最小驱动（**已验证**）：`seer-proto/tools/visual_driver.py`
（纯 `ctypes + PIL + numpy`，普通权限，不依赖 dm.dll / COM）

```powershell
python tools\visual_driver.py list                 # 列窗口（hwnd/尺寸/标题）
python tools\visual_driver.py capture <hwnd> a.png # 抓客户区（PrintWindow，可抓后台）
python tools\visual_driver.py find <hwnd> tpl.png  # 归一化互相关模板匹配
python tools\visual_driver.py clicktpl <hwnd> tpl.png   # 找到就点中心
```
实测：任意窗口抓图 `1016×660`，自截模板匹配 **score = 1.000**。

与 dm.dll 的取舍：

| | 我们的驱动 | 大漠 dm.dll |
|---|---|---|
| 依赖 | PIL/numpy（已装） | 需 `regsvr32` 注册（**需管理员**；实测 exit 5 拒绝），且是 32 位 COM |
| 能力 | 截图/匹配/点击 | 多了：dx/后台绑窗口、找色、字库 OCR、内存读写、键鼠后台 |
| 适合 | 快速起步、可审计 | 需要「后台操作/OCR」时再上 |

## 四、和协议客户端的分工

| 场景 | 用谁 |
|---|---|
| 读数据（成就/玩家/好友）、发命令、批量日常 | **seerproto**（协议层，精确、快、可读） |
| Flash 独有内容、必须"真画面"的界面、给 agent 提供视觉证据 | **visual_driver**（看图操作） |
| 需要后台/多开/OCR | 再考虑注册 dm.dll |

## 六、宿主实验记录（黑屏定位）

| 尝试 | 结果 | 结论 |
|---|---|---|
| PowerShell WinForms + WebBrowser(IE) + Flash `classid` | 窗口出现、`GET /Login.swf 200`（Flash 已去拉文件），但 `readyState=Interactive`、`swf=HtmlElement`、`callback=no`、截图全黑 | IE 的 ActiveX 未实例化（沙箱也写不了 `FEATURE_BROWSER_EMULATION`） |
| 同上，32 位 PowerShell + X-UA-Compatible=edge | 同样全黑 | 与位数无关 |
| **Electron 11 (32位) + Pepper Flash 15**（官方登录器同款） | 已下载解压 `host/electron11-32/`，`main.js`/`package.json` 就绪；启动后无输出、窗口仍是旧宿主 | 待排查：32 位 electron 启动参数/崩溃 |

**关键发现（黑屏根因方向）**：

- 系统 Flash OCX 是 **34.0.0.155**，属 EOL 版本（Adobe 终止开关），即便实例化也可能不播内容；
- **官方登录器自带 Pepper Flash 15**：
  `F:\SeerLauncher\resources\app.asar.unpacked\plugins\pepflashplayer32_15_0_0_152.dll`（14.9 MB, 32 位）
- 官方登录器本体 = Electron/CEF（`SeerLauncher.exe` 104.9 MB，`resources/app.asar` 7.4 MB，`core.asar`）
- ⇒ 正确的 Flash 运行时是**这个 32 位 Pepper Flash + Chromium 87 级内核**，不是系统 OCX。

**下一步（唯一动作）**：用 `host/electron11-32/electron.exe . --ppapi-flash-path=<pepflash dll> --ppapi-flash-version=15.0.0.152`
跑起来后：
1. 确认 `[state]` 里 `cb=true`（`startWebSessionLogin` 已注册）；
2. 用 `seerLogin(hex(uid+session))` 直接进世界；
3. 之后挂 `tools/tcp_proxy.py` 观察/注入。

## 七、自建 Flash 宿主的最终结论

**成功做到了什么**（`llm-seer/host/`）：
- Electron **11.5.0**(32 位) + **pepflashplayer32_15_0_0_152.dll**（官方登录器同款）→ Flash 正常运行
- 完整启动链（本地静态站 `serve.py` + 官方 CDN 补齐文件）：
  `Client.swf → config/seer.xml → version/zzz_config.txt → version/version<ver>.swf → dll/Assets.swf →
   config/Server.xml → resource/xml/update.xml → config/dll.xml → resource/xml/servername.xml →
   dll/TaomeeLibraryDLL.swf → dll/Login.swf` → **登录画面（小梅）正常渲染**
- `config/Server.xml` + `ip.txt` 已改指向 `127.0.0.1:18630`（我们自己的 TCP 代理），代理已能应答 policy 并解析 17B 帧

**卡在哪里**：
- `startWebSessionLogin` 等 AS3 回调始终未注册（`cb:false`）。源码位置：
  `Login.as:245` `if (ExternalInterface.available && LoginManager.tmcid == 76) { addCallback("startWebSessionLogin", ...) }`
- `TmdType` 映射表最大只到 72，76 必须由 **flashvars / loaderInfo.parameters** 传入；
  实测 `<object>` 的 `param flashvars`、URL 查询串 `?tmcid=76`（Client.swf 和 Login.swf 两种入口）都不生效
  —— 大概率是 `Client.swf` 加载 `Login.swf` 时自建 `LoaderContext`，参数没有透传
- 直接加载 `dll/Login.swf`（`SEER_MODE=login`）反而连小梅画面都没有 → 它确实依赖 Client.swf 的上下文

**要继续只有两条路**（都超出"只读逆向"范畴）：
1. 改 `Login.swf` 的 ABC：把 `tmcid==76` 判断去掉 / 或直接在文档类里注册回调（需要 AS3 编译器/字节码补丁）
2. 不碰 AS3：让 Flash 客户端只当"显示器"，操作走已经跑通的协议客户端（`seer-proto`）

**当前可用的两件成品**：
- `seer-proto`：Unity 协议客户端（登录→进世界→下发/收包→看板/报告）——**已稳定**
- `llm-seer/host`：官方 Flash 客户端可完整启动并显示登录画面（`SEER_MODE=client`），可作为"看"的载体

## 八、字节码补丁尝试（方案 2）——做到一半

用 FFDec（`java -jar ffdec-cli.jar -importScript in.swf out.swf <dir>`，只编译单个类）做了两次补丁：

| 补丁 | 位置 | 结果 |
|---|---|---|
| 去掉 `tmcid == 76` 守卫 | `Login.as:245` | 编译通过，但 `ExternalInterface.available == false`，回调仍不注册 |
| 直接把会话喂给登录流程 | `initLoginHandle()`：`SIDLogin.get_URL_Session()` → `SIDLogin.S2B("<uid+session>")` | 编译通过（1,694 KB），SWF 正常加载，但界面仍停在“小梅”背景，**代理收不到任何连接** |

**关键实测结论**：
- 本机 Chromium(PPAPI) 里 `ExternalInterface` **完全不可用**（页面桥函数一次都没被调用，`hits: []`），
  所以 `getAd/get_uid/get_sid/getUrlParams/tmcid` 这一整套官方宿主桥接手段全部失效
- 未打补丁时界面也只到“小梅”背景，**登录面板本身没建出来** → 说明 `LoginView` 还依赖
  官方启动器提供的资源/参数（不只是 tmcid）
- 因此“让 Flash 客户端自己完成登录并连上代理”这条，需要继续深挖 `LoginView` 的构造依赖，
  投入产出比已经明显低于直接用协议客户端

**建议**：Flash 端到此为止（作为“能看见的载体”保留），实际操作走 `seer-proto`。

## 五、下一步（按性价比）

1. **用 外国版flash.exe 加载 `llm-seer/swf/Login.swf`**，确认能出登录界面 → 截图 → 建模板库
   （把「登录/进入游戏/图鉴入口」等 UI 元素存到 `llm-seer/ref/templates/`）
2. 若要复刻 2.0.21 的**宿主方式**（OCX 内嵌 vs 独立播放器），做一次内存 dump
   （`re/dump_mem.py`，流程同 2.0.7）→ Ghidra 里搜 `CoCreateInstance` / `ShockwaveFlash` / `CreateWindowEx`
3. 视觉循环（agent）：`capture → 多模板匹配 → 点击 → 等画面变化 → 校验`，与协议层交叉验证