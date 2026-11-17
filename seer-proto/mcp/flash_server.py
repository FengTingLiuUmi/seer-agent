#!/usr/bin/env python3
"""MCP stdio 服务：把 Flash 宿主的 HTTP 接口包成工具，供大模型直接调用

工具: flash_state / flash_eval / flash_key / flash_click / flash_login / flash_net
依赖: tools/flash_api.py 在 127.0.0.1:7801 运行，且 host_play.ps1 已启动

注册示例（任何 MCP 客户端）:
  command = "python"
  args    = ["C:/.../seer-proto/mcp/flash_server.py"]
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'tools'))
import flashctl  # noqa: E402

SERVER_INFO = {'name': 'seer-flash', 'version': '0.1.0'}
PROTOCOL = '2024-11-05'

TOOLS = [
    {'name': 'flash_state', 'description': '当前 Flash 页面状态（标题/URL/Flash 对象/forAs API/sid/frames）',
     'inputSchema': {'type': 'object', 'properties': {}}},
    {'name': 'flash_eval', 'description': '在 Flash 页面里执行任意 JS 并返回结果（万能入口：可调 gamePublic.forAs.* 与 window.Client.*）',
     'inputSchema': {'type': 'object', 'properties': {'code': {'type': 'string', 'description': 'JS 代码'}},
                     'required': ['code']}},
    {'name': 'flash_key', 'description': '发送按键序列（SendKeys 语法，如 {TAB} 或 {ENTER}）',
     'inputSchema': {'type': 'object', 'properties': {'keys': {'type': 'string'}}, 'required': ['keys']}},
    {'name': 'flash_click', 'description': '按窗口客户区坐标点击（盲点，不读像素）',
     'inputSchema': {'type': 'object', 'properties': {'x': {'type': 'integer'}, 'y': {'type': 'integer'}},
                     'required': ['x', 'y']}},
    {'name': 'flash_login', 'description': '盲注键盘登录（账号 → Tab → 密码 → Enter）',
     'inputSchema': {'type': 'object', 'properties': {}}},
    {'name': 'flash_net', 'description': '列出游戏服务器连接（1863/1864），可等待进入游戏',
     'inputSchema': {'type': 'object', 'properties': {'wait_seconds': {'type': 'integer', 'description': '等待 :1864 连接的秒数，0=只读一次'}}}},
]


def call_tool(name, args):
    args = args or {}
    if name == 'flash_state':
        return flashctl.get('/state')
    if name == 'flash_eval':
        return flashctl.post('/eval', {'code': args.get('code', '')})
    if name == 'flash_key':
        return flashctl.post('/key', {'keys': args.get('keys', '')})
    if name == 'flash_click':
        return flashctl.post('/click', {'x': int(args.get('x', 512)), 'y': int(args.get('y', 330))})
    if name == 'flash_login':
        return flashctl.post('/login')
    if name == 'flash_net':
        wait = int(args.get('wait_seconds', 0) or 0)
        if wait > 0:
            import time
            t0 = time.time()
            while time.time() - t0 < wait:
                conns = [c for c in flashctl.tcp_connections() if c['remote'].endswith(':1864')]
                if conns:
                    return {'ok': True, 'conns': conns, 'seconds': round(time.time() - t0, 1)}
                time.sleep(1)
        return {'ok': True, 'conns': flashctl.tcp_connections()}
    raise ValueError('unknown tool: %s' % name)


def reply(mid, result=None, error=None):
    msg = {'jsonrpc': '2.0', 'id': mid}
    if error is not None:
        msg['error'] = error
    else:
        msg['result'] = result
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + '\n')
    sys.stdout.flush()


def main():
    try:
        sys.stdin.reconfigure(encoding='utf-8', errors='replace')
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            continue
        mid = req.get('id')
        method = req.get('method')
        params = req.get('params') or {}
        if method == 'initialize':
            reply(mid, {'protocolVersion': PROTOCOL, 'capabilities': {'tools': {}}, 'serverInfo': SERVER_INFO})
        elif method in ('notifications/initialized', 'initialized'):
            continue
        elif method == 'tools/list':
            reply(mid, {'tools': TOOLS})
        elif method == 'tools/call':
            name = params.get('name')
            args = params.get('arguments') or {}
            try:
                out = call_tool(name, args)
                reply(mid, {'content': [{'type': 'text', 'text': json.dumps(out, ensure_ascii=False)}],
                            'isError': False})
            except Exception as e:
                reply(mid, {'content': [{'type': 'text', 'text': 'ERROR: %s' % e}], 'isError': True})
        elif method == 'ping':
            reply(mid, {})
        else:
            reply(mid, error={'code': -32601, 'message': 'method not found: %s' % method})


if __name__ == '__main__':
    main()