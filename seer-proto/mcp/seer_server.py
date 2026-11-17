#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""seer MCP 服务器（stdio）：把「登录 + 游戏操作」暴露成模型可直接调用的工具。

架构：
    MCP client ──stdio JSON-RPC──▶ 本文件 ──HTTP──▶ seer-service (:7820)
                                                     └─▶ seerproto.exe -serve ──▶ 游戏网关

设计要点：
  * 只有一个游戏会话（同一账号不能双连，否则互踢）——所有工具共享 seer-service
  * seer-service 不在线时自动拉起（daemon），MCP 退出时不动它（可复用）
  * 高层工具（login/pets/capture）做语义封装；send_cmd 是万能逃生口

工具：
  seer_login        登录（使用加密凭据；可指定 account）
  seer_status       会话/玩家/地图/精灵概览
  seer_pets         拉取精灵列表（当前解码原始片段）
  seer_pet_info     单个精灵详情（2301，需要 bodyHex）
  seer_capture      捕捉当前野生精灵（实验：2409 CATCH_MONSTER）
  seer_fight        战斗动作：use_skill / escape / catch
  seer_send         任意命令（cmd 名或 id + bodyHex）
  seer_events       拉最近的收发帧
  seer_logout       断开会话

注册（DSH profile cordis.patch.yml 或任意 MCP 客户端）：
  command: python
  args: ["<abs>/seer-proto/mcp/seer_server.py"]
"""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                  # seer-proto
SERVICE = os.path.join(ROOT, 'tools', 'seer_service.py')
SERVICE_URL = os.environ.get('SEER_SERVICE_URL', 'http://127.0.0.1:7820')
SERVICE_PORT = int(urllib.parse.urlparse(SERVICE_URL).port or 7820)

SERVER_INFO = {'name': 'seer', 'version': '0.2.0'}
PROTOCOL = '2024-11-05'

# 常用命令名 → id（与 data/commandid.json 一致；给出中文别名便于模型使用）
ALIASES = {
    'pets': 2303, '精灵列表': 2303, 'GET_PET_LIST': 2303,
    'pet_info': 2301, '精灵详情': 2301, 'GET_PET_INFO': 2301,
    'players': 2003, '地图玩家': 2003, 'LIST_MAP_PLAYER': 2003,
    'achievements': 3401, '成就': 3401, 'ACHIEVELIST': 3401,
    'items': 4475, '背包': 4475, 'ITEM_LIST': 4475,
    'collect': 2313, '采集状态': 2313, 'IS_COLLECT': 2313,
    'use_skill': 2405, '使用技能': 2405, 'USE_SKILL': 2405,
    'catch': 2409, '捕捉': 2409, 'CATCH_MONSTER': 2409,
    'escape': 2410, '逃跑': 2410, 'ESCAPE_FIGHT': 2410,
    'fight_over': 2506, 'FIGHT_OVER': 2506,
}

TOOLS = [
    {'name': 'seer_login',
     'description': '登录赛尔号并进入世界（密码从本机加密凭据读取，不需明文）。'
                    '同一账号只能有一条连接；若已在世界中会直接返回状态。',
     'inputSchema': {'type': 'object', 'properties': {
         'account': {'type': 'string', 'description': '米米号，缺省用服务默认账号'},
         'password': {'type': 'string', 'description': '可选：临时密码（正常情况留空，用本机加密凭据）'},
         'force': {'type': 'boolean', 'description': '已在线时强制重登（默认 false）'}}}},
    {'name': 'seer_status',
     'description': '查看会话状态：是否 ready、玩家昵称、地图、精灵数、最近错误、在线时长。',
     'inputSchema': {'type': 'object', 'properties': {}}},
    {'name': 'seer_pets',
     'description': '拉取精灵仓库列表（GET_PET_LIST 2303）。返回回包长度与解码结果（原始 hex 供进一步解析）。',
     'inputSchema': {'type': 'object', 'properties': {'waitMs': {'type': 'integer', 'description': '等待回包毫秒，默认 6000'}}}},
    {'name': 'seer_pet_info',
     'description': '查询单个精灵详情（GET_PET_INFO 2301）。需要 bodyHex（精灵的 petId/index 编码，4 字节大端，如 0000008f）。',
     'inputSchema': {'type': 'object', 'properties': {
         'bodyHex': {'type': 'string', 'description': '4 字节十六进制，如 0000008f'},
         'waitMs': {'type': 'integer'}}, 'required': ['bodyHex']}},
    {'name': 'seer_capture',
     'description': '捕捉当前战斗中的野生精灵（实验能力）：发 CATCH_MONSTER 2409，等待战斗帧回包，'
                    '返回 2409/2506/2002 等帧供判断成功与否。需先处于战斗状态。',
     'inputSchema': {'type': 'object', 'properties': {
         'bodyHex': {'type': 'string', 'description': '可选：捕捉请求 body（默认空，由服务端按当前战斗索引）'},
         'waitMs': {'type': 'integer', 'description': '默认 8000'}}}},
    {'name': 'seer_fight',
     'description': '战斗动作。action=use_skill 用技能（2405）；escape 逃跑（2410）；catch 捕捉（2409）。',
     'inputSchema': {'type': 'object', 'properties': {
         'action': {'type': 'string', 'enum': ['use_skill', 'escape', 'catch']},
         'bodyHex': {'type': 'string', 'description': '可选 body；use_skill 一般是技能槽/技能 id'},
         'waitMs': {'type': 'integer'}}, 'required': ['action']}},
    {'name': 'seer_send',
     'description': '万能入口：发送任意命令（cmd 可写 id 或名字/中文别名，如 2303 / GET_PET_LIST / 精灵列表），'
                    '返回匹配的 S2C 回包（bodyHex）。',
     'inputSchema': {'type': 'object', 'properties': {
         'cmd': {'type': ['integer', 'string']},
         'bodyHex': {'type': 'string'},
         'waitMs': {'type': 'integer', 'description': '默认 5000'},
         'expect': {'type': 'boolean', 'description': '是否等待回包，默认 true'}},
         'required': ['cmd']}},
    {'name': 'seer_events',
     'description': '拉最近的收发帧（c2s/s2c），用于观察游戏对某个操作的反应。',
     'inputSchema': {'type': 'object', 'properties': {
         'since': {'type': 'integer', 'description': '从哪个 seq 之后开始，0=从头'},
         'limit': {'type': 'integer', 'description': '默认 80'}}}},
    {'name': 'seer_logout',
     'description': '断开当前游戏会话（释放单实例锁）。', 'inputSchema': {'type': 'object', 'properties': {}}},
]


# ---------------------------------------------------------------- HTTP / 服务

def http(method, path, body=None, timeout=200):
    url = SERVICE_URL + path
    data = None
    headers = {'Content-Type': 'application/json'}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode('utf-8'))
        except Exception:
            return {'ok': False, 'error': 'HTTP %s' % e.code}
    except (urllib.error.URLError, ConnectionError, socket.timeout) as e:
        return {'ok': False, 'error': 'seer-service 不可达: %s' % e, 'offline': True}


def service_up(timeout=1.5):
    try:
        with urllib.request.urlopen(SERVICE_URL + '/health', timeout=timeout) as r:
            return json.loads(r.read().decode('utf-8')).get('ok', False)
    except Exception:
        return False


def ensure_service(wait=12.0):
    """不在线就作为后台 daemon 拉起 seer-service（共享给 UI/MCP）。"""
    if service_up():
        return True
    try:
        flags = 0
        if os.name == 'nt':
            flags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        subprocess.Popen([sys.executable, SERVICE, '--port', str(SERVICE_PORT)],
                         cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=flags if os.name == 'nt' else 0)
    except Exception:
        return False
    t0 = time.time()
    while time.time() - t0 < wait:
        if service_up(0.5):
            return True
        time.sleep(0.25)
    return False


def need_service():
    if not ensure_service():
        raise RuntimeError('seer-service 未能启动（%s）' % SERVICE_URL)
    return True


def summarize_status(st):
    s = st.get('state') or {}
    m = s.get('map') or {}
    return {
        'ok': st.get('ok'),
        'ready': st.get('ready'),
        'logged_in': st.get('logged_in'),
        'account': st.get('account'),
        'nick': m.get('nick'),
        'map_head': (m.get('head') or '')[:8],
        'entered': s.get('entered'),
        'pets': 0 if not s.get('pets') else s['pets'][0].get('count'),
        'dead_reason': st.get('dead_reason'),
        'error': st.get('error'),
        'cooldown_left': st.get('login_cooldown_left'),
        'view': st.get('view'),
        'events': st.get('event_seq'),
    }


# ---------------------------------------------------------------- 工具实现

def tool_login(args):
    need_service()
    account = args.get('account')
    force = bool(args.get('force', False))
    body = {'account': account, 'force': force}
    if args.get('password'):
        body['password'] = args['password']
    r = http('POST', '/api/login', body, timeout=240)
    out = summarize_status(r)
    out['elapsed'] = r.get('elapsed')
    if not r.get('ok'):
        out['proto_out'] = (r.get('proto_out') or '')[-800:]
    return out


def tool_status(args):
    if not service_up():
        return {'ok': False, 'ready': False, 'error': 'seer-service 未运行（调用 seer_login 会拉起）'}
    return summarize_status(http('GET', '/api/status'))


def tool_pets(args):
    need_service()
    r = http('POST', '/api/pets', {'waitMs': int(args.get('waitMs', 6000))})
    return {'ok': r.get('ok'), 'rawLen': r.get('rawLen'), 'pets': r.get('pets'),
            'error': r.get('error'), 'frames': (r.get('frames') or [])[:1]}


def tool_pet_info(args):
    need_service()
    body = (args.get('bodyHex') or '').strip()
    r = http('POST', '/api/petinfo', {'bodyHex': body, 'waitMs': int(args.get('waitMs', 6000))})
    return r


def send(cmd, body_hex='', wait_ms=6000, expect=True):
    need_service()
    r = http('POST', '/api/send', {'cmd': cmd, 'bodyHex': body_hex or '',
                                   'waitMs': int(wait_ms), 'expect': bool(expect)})
    if not r.get('ok'):
        return {'ok': False, 'error': r.get('error')}
    frames = r.get('frames') or []
    return {'ok': bool(frames) or not expect, 'cmd': cmd, 'frames': frames,
            'timed_out': not frames and expect}


def resolve(alias):
    if isinstance(alias, int):
        return alias
    a = str(alias).strip()
    if a.isdigit():
        return int(a)
    if a in ALIASES:
        return ALIASES[a]
    up = a.upper()
    if up in ALIASES:
        return ALIASES[up]
    return alias          # 交给服务端按 commandid.json 解析


def tool_capture(args):
    body = (args.get('bodyHex') or '').strip()
    wait = int(args.get('waitMs', 8000))
    # 捕捉通常伴随 2409 请求 + 战斗结束帧（2506/2002/8002）
    r = send(2409, body, wait)
    if not r.get('ok') and r.get('error'):
        return r
    frames = r.get('frames') or []
    got = [f['cmd'] for f in frames]
    return {
        'ok': bool(frames),
        'sent': 2409,
        'frames': frames,
        'note': '成功与否看回包：出现 2506/2002/2001 等战斗结束帧，或 2409 回包携带宠物信息；'
                '当前捕捉 body 格式待实战校准（可传 bodyHex 覆盖）。',
        'got_cmds': got,
        'timed_out': r.get('timed_out'),
    }


def tool_fight(args):
    act = args.get('action')
    m = {'use_skill': 2405, 'escape': 2410, 'catch': 2409}
    if act not in m:
        return {'ok': False, 'error': 'action 必须是 use_skill/escape/catch'}
    return send(m[act], args.get('bodyHex') or '', int(args.get('waitMs', 6000)))


def tool_send(args):
    return send(resolve(args.get('cmd')), args.get('bodyHex') or '',
                int(args.get('waitMs', 5000)), bool(args.get('expect', True)))


def tool_events(args):
    if not service_up():
        return {'ok': False, 'error': 'seer-service 未运行'}
    since = int(args.get('since', 0) or 0)
    limit = int(args.get('limit', 80) or 80)
    r = http('GET', '/api/events?since=%d&limit=%d' % (since, limit))
    evs = r.get('events') or []
    for e in evs:
        if e.get('bodyHex') and len(e['bodyHex']) > 160:
            e['bodyHex'] = e['bodyHex'][:160] + '…'
    return {'ok': True, 'seq': r.get('seq'), 'events': evs}


def tool_logout(args):
    if not service_up():
        return {'ok': True, 'note': '服务未运行'}
    return http('POST', '/api/logout', {})


CALL = {
    'seer_login': tool_login,
    'seer_status': tool_status,
    'seer_pets': tool_pets,
    'seer_pet_info': tool_pet_info,
    'seer_capture': tool_capture,
    'seer_fight': tool_fight,
    'seer_send': tool_send,
    'seer_events': tool_events,
    'seer_logout': tool_logout,
}


# ---------------------------------------------------------------- MCP 协议

def reply(mid, result=None, error=None):
    msg = {'jsonrpc': '2.0', 'id': mid}
    if error is not None:
        msg['error'] = error
    else:
        msg['result'] = result
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + '\n')
    sys.stdout.flush()


def handle(req):
    mid = req.get('id')
    method = req.get('method')
    params = req.get('params') or {}
    if method == 'initialize':
        return reply(mid, {'protocolVersion': PROTOCOL, 'capabilities': {'tools': {}},
                           'serverInfo': SERVER_INFO})
    if method in ('notifications/initialized', 'initialized'):
        return
    if method == 'tools/list':
        return reply(mid, {'tools': TOOLS})
    if method == 'tools/call':
        name = params.get('name')
        args = params.get('arguments') or {}
        fn = CALL.get(name)
        if not fn:
            return reply(mid, error={'code': -32601, 'message': 'unknown tool: %s' % name})
        try:
            out = fn(args)
            text = json.dumps(out, ensure_ascii=False)
            if len(text) > 60000:
                text = text[:60000] + '…(truncated)'
            reply(mid, {'content': [{'type': 'text', 'text': text}],
                        'isError': not out.get('ok', True) and bool(out.get('error'))})
        except Exception as e:
            reply(mid, {'content': [{'type': 'text', 'text': 'ERROR: %s' % e}], 'isError': True})
        return
    if method == 'ping':
        return reply(mid, {})
    return reply(mid, error={'code': -32601, 'message': 'method not found: %s' % method})


def main():
    try:
        sys.stdin.reconfigure(encoding='utf-8', errors='replace')
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    # 预热：尽量让 UI/MCP 共享同一个服务；失败不影响协议层
    ensure_service(wait=3.0)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            continue
        handle(req)


if __name__ == '__main__':
    main()