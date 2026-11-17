# 把 seer MCP 注册进当前 DSH profile（可回滚）。
# 用法：pwsh -File register-mcp.ps1            # 追加（已存在则跳过）
#       pwsh -File register-mcp.ps1 -Remove    # 移除
param([switch]$Remove)

$ErrorActionPreference = 'Stop'
$profile = if ($env:DSH_PROFILE_DIR) { $env:DSH_PROFILE_DIR } else { Join-Path $env:USERPROFILE '.dsh\profiles\desktop' }
$yaml = Join-Path $profile 'cordis.patch.yml'
if (-not (Test-Path $yaml)) { throw "找不到 $yaml（DSH profile 路径不对？）" }

$root = Split-Path -Parent $PSScriptRoot
$server = Join-Path $root 'mcp\seer_server.py'
$snippet = @"

# ---- seer MCP（登录/精灵/战斗）----
- id: mcp-seer
  name: "@deepseek-ai/dsh-mcp-client"
  config:
    serverName: seer
    transport: stdio
    command: python
    args:
      - "$($server -replace '\\','/')"
    cwd: "$($root -replace '\\','/')"
    toolCallTimeoutMs: 300000
"@

$text = Get-Content $yaml -Raw -Encoding UTF8
$marker = '# ---- seer MCP（登录/精灵/战斗）----'

if ($Remove) {
    if ($text.Contains($marker)) {
        $i = $text.IndexOf($marker)
        $text = $text.Substring(0, $i).TrimEnd() + "`n"
        Set-Content $yaml $text -Encoding UTF8
        "已移除 seer MCP 注册。重启 DSH 生效。"
    } else { "未找到 seer MCP 注册，无需移除。" }
    return
}

if ($text.Contains($marker)) { "seer MCP 已注册，跳过。重启 DSH 生效。"; return }

$bak = "$yaml.bak-$(Get-Date -Format yyyyMMdd-HHmmss)"
Copy-Item $yaml $bak
Set-Content $yaml ($text.TrimEnd() + "`n" + $snippet) -Encoding UTF8
"已备份到 $bak"
"已追加 seer MCP 注册；重启 DSH 后工具名形如 mcp__seer__seer_login"