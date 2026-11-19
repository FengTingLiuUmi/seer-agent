window.__ModuleLoader__.load({
  id: '@local/dsh-seer-battle',
  factory(require) {
    const React = require('react');
    const h = React.createElement;
    const { useState, useEffect, useRef } = React;

    const RECORDS_DIR = 'seer/battle-records';
    const SKILLS_PATH = 'seer/seer-rebuild/seer_rebuild/domain_knowledge/skills.json';
    const POLL_MS = 1000;

    // 战斗命令号（与 seer-rebuild/battle_report.py 一致）
    const C_READY = 2404;      // C2S 准备
    const C_SKILL = 2405;      // C2S 出招 / S2C 出招回执
    const C_SWITCH = 2407;     // C2S 换宠
    const C_START = 2504;      // S2C 开战（双方登场 + 血）
    const C_SKILL_RES = 2505;  // S2C 技能结算（双方血量变动）
    const C_OVER = 2506;       // S2C 战斗结束
    const C_WIN = 42390;       // 因子胜利
    const C_PROGRESS = 45827;  // 因子进度推送（=胜利）

    const CATCH_LO = 0x54000000;
    const CATCH_HI = 0x6c000000;

    // ------------------------------------------------------------------
    // 文件读取：通过 workspaceFiles Remote 逐页读取并拼接 UTF-8 文本
    // ------------------------------------------------------------------
    async function readAllLines(remote, sessionId, path, signal) {
      let offset = 1;
      const parts = [];
      for (let i = 0; i < 4096; i += 1) {
        const result = await remote.workspaceFiles.read(
          sessionId,
          path,
          { offset, limit: 5000 },
          signal,
        );
        if (!result.ok) throw result.error;
        const page = result.value;
        parts.push(page.text);
        if (page.eof || page.lines === 0) break;
        offset += page.lines;
      }
      return parts.join('\n');
    }

    async function readJson(remote, sessionId, path, signal) {
      const text = await readAllLines(remote, sessionId, path, signal);
      return JSON.parse(text);
    }

    // ------------------------------------------------------------------
    // 名称解析：技能 id -> 名称（懒加载 + 按 session 缓存）
    // ------------------------------------------------------------------
    const namesCacheBySession = new Map();

    function buildSkillMap(skillsJson) {
      const m = {};
      if (skillsJson && typeof skillsJson === 'object') {
        for (const k of Object.keys(skillsJson)) {
          const v = skillsJson[k];
          if (v && v.name) m[k] = v.name;
        }
      }
      return m;
    }

    function loadNames(remote, sessionId, signal) {
      if (namesCacheBySession.has(sessionId)) return namesCacheBySession.get(sessionId);
      const p = readJson(remote, sessionId, SKILLS_PATH, signal)
        .then((s) => ({ skills: buildSkillMap(s) }))
        .catch((e) => {
          namesCacheBySession.delete(sessionId);
          throw e;
        });
      namesCacheBySession.set(sessionId, p);
      return p;
    }

    // ------------------------------------------------------------------
    // 二进制/协议解析（最佳努力）
    // ------------------------------------------------------------------
    function u32AtHex(hex, byteOff) {
      if (!hex || hex.length < (byteOff + 4) * 2) return null;
      const v = parseInt(hex.substr(byteOff * 2, 8), 16);
      return Number.isFinite(v) ? (v >>> 0) : null;
    }

    function numToHex(n) {
      const v = Number(n);
      if (!Number.isFinite(v) || v < 0) return '';
      return (v >>> 0).toString(16).padStart(8, '0');
    }

    function isCatch(v) {
      return v >= CATCH_LO && v <= CATCH_HI;
    }

    /** 从 2504/2505 里发现敌方：第一个 [catch][当前][满血] 三元组，满血在 Boss 区间。 */
    function discoverEnemy(hex) {
      if (!hex) return null;
      const len = hex.length / 2;
      for (let off = 0; off + 12 <= len; off += 1) {
        const eid = u32AtHex(hex, off);
        if (eid == null || !isCatch(eid)) continue;
        const cur = u32AtHex(hex, off + 4);
        const mx = u32AtHex(hex, off + 8);
        if (cur == null || mx == null) continue;
        if (mx >= 2000 && mx <= 200000 && cur >= 0 && cur <= mx) {
          return { eid, cur, mx };
        }
      }
      return null;
    }

    /** 已知敌方 catch 与满血后，在 catch 之后的近距离内取 [当前][满血] 对里的当前血。 */
    function curAfterCatch(hex, eid, mx) {
      if (!hex || eid == null || mx == null) return null;
      const len = hex.length / 2;
      for (let off = 0; off + 8 <= len; off += 1) {
        if (u32AtHex(hex, off) !== eid) continue;
        for (let k = 4; k <= 32; k += 4) {
          const c = u32AtHex(hex, off + k);
          const m = u32AtHex(hex, off + k + 4);
          if (c == null || m == null) break;
          if (m === mx && c >= 0 && c <= mx) return c;
        }
        return null;
      }
      return null;
    }

    function parseTimelineLines(text) {
      const out = [];
      if (!text) return out;
      for (const raw of text.split('\n')) {
        const s = raw.trim();
        if (!s) continue;
        try {
          out.push(JSON.parse(s));
        } catch (e) {
          // 忽略损坏行
        }
      }
      return out;
    }

    function normDir(d) {
      if (d === 'send') return 'c2s';
      if (d === 'recv') return 's2c';
      return d;
    }

    /**
     * 把实时 timeline 事件流解析成可展示的逐回合日志。
     * events: [ {dir:'c2s'|'s2c'|'send'|'recv', cmd, body(hex), result?} ]
     * latest: 最近一场完整战报（用于我方首发名称 / 标题 / 胜负）
     */
    function buildLiveView(events, names, latest) {
      const skills = (names && names.skills) || {};
      const latestInfo = latest || {};

      const lineup = latestInfo.lineup || [];
      const catchName = {};
      let myName = '';
      for (const p of lineup) {
        if (p.catch_time != null) catchName[numToHex(p.catch_time)] = p.name || '';
        if ((p.slot === '首发' || p.slot === '正式') && !myName) myName = p.name || '';
      }
      if (!myName) myName = '我方精灵';

      const enemyLabel = latestInfo.title || latestInfo.factor_name || '敌方';
      let enemyMax = null;
      let enemyCur = null;
      let enemyCatch = null;
      let round = 0;
      let over = false;
      let winner = latestInfo.winner || '';
      const log = [];

      const push = (type, text) => log.push({ type, text });

      for (const e of events) {
        const dir = normDir(e.dir);
        const cmd = e.cmd;
        const body = e.body || '';

        if (dir === 'c2s') {
          if (cmd === C_READY) {
            push('line', '[我方]准备战斗');
          } else if (cmd === C_SKILL) {
            round += 1;
            push('round', `-----回合 ${round} -----`);
            const sid = u32AtHex(body, 0);
            const name = sid != null ? skills[String(sid)] : null;
            const skillLabel = name || (sid != null ? `技能#${sid}` : '未出招');
            push('line', `[我方]${myName} · ${skillLabel}`);
          } else if (cmd === C_SWITCH) {
            const hex = body.slice(0, 8);
            const nm = catchName[hex];
            if (nm) myName = nm;
            push('line', `[我方]换宠 → ${nm || (`0x${hex}`)}`);
          }
        } else {
          if (cmd === C_START) {
            const d = discoverEnemy(body);
            if (d) {
              enemyCatch = d.eid;
              enemyMax = d.mx;
              enemyCur = d.cur;
            }
            push('line', '战斗开始');
          } else if (cmd === C_SKILL_RES) {
            if (enemyMax != null) {
              const c = curAfterCatch(body, enemyCatch, enemyMax);
              if (c != null) enemyCur = c;
            } else {
              const d = discoverEnemy(body);
              if (d) {
                enemyCatch = d.eid;
                enemyMax = d.mx;
                enemyCur = d.cur;
              }
            }
            if (enemyCur != null && enemyMax != null) {
              push('line', `[敌方]体力 ${enemyCur}/${enemyMax}`);
            }
          } else if (cmd === C_OVER) {
            over = true;
          } else if (cmd === C_WIN || cmd === C_PROGRESS) {
            if (!winner) winner = '胜利';
          }
        }
      }

      if (winner || over) {
        push('end', `---战斗结束[${winner || '未判胜负'}]---`);
      }

      return { myName, enemyLabel, enemyCur, enemyMax, log, round, over, winner };
    }

    function countRounds(events) {
      let n = 0;
      for (const e of events) {
        if (normDir(e.dir) === 'c2s' && e.cmd === C_SKILL) n += 1;
      }
      return n;
    }

    function nowTime() {
      const d = new Date();
      const p = (x) => String(x).padStart(2, '0');
      return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
    }

    // ------------------------------------------------------------------
    // 组件
    // ------------------------------------------------------------------
    function Panel(props) {
      const { sessionId, remote } = props;
      const [open, setOpen] = useState(false);
      const [busy, setBusy] = useState(true);
      const [error, setError] = useState(null);
      const [report, setReport] = useState(null);   // { latest, index }
      const [timeline, setTimeline] = useState([]); // 实时事件流
      const [names, setNames] = useState(null);     // { skills: {...} }
      const [lastSync, setLastSync] = useState({ t: nowTime(), msg: '未打开' });
      const logBoxRef = useRef(null);

      useEffect(() => {
        if (!open || !sessionId || !remote) return undefined;
        let cancelled = false;
        const ctrl = new AbortController();

        const tick = async () => {
          try {
            const latest = await readJson(
              remote, sessionId, `${RECORDS_DIR}/latest.json`, ctrl.signal,
            ).catch(() => null);
            const index = await readJson(
              remote, sessionId, `${RECORDS_DIR}/index.json`, ctrl.signal,
            ).catch(() => null);
            const timelineText = await readAllLines(
              remote, sessionId, `${RECORDS_DIR}/latest.timeline.jsonl`, ctrl.signal,
            ).catch(() => '');
            if (cancelled) return;

            const events = parseTimelineLines(timelineText);
            setReport({ latest, index });
            setTimeline(events);
            setError(null);

            const rounds = countRounds(events);
            const msg = events.length
              ? `已同步 · 第 ${rounds} 回合`
              : (latest && latest.winner) ? `已结束 · ${latest.winner}` : '数据无需更新';
            setLastSync({ t: nowTime(), msg });

            if (events.length && !namesCacheBySession.has(sessionId)) {
              loadNames(remote, sessionId, ctrl.signal)
                .then((n) => { if (!cancelled) setNames(n); })
                .catch(() => {});
            }
          } catch (e) {
            if (cancelled) return;
            setTimeline([]);
            setError(fmtError(e));
          } finally {
            if (!cancelled) setBusy(false);
          }
        };

        setBusy(true);
        tick();
        const timer = setInterval(tick, POLL_MS);
        return () => {
          cancelled = true;
          clearInterval(timer);
          ctrl.abort();
        };
      }, [open, sessionId, remote]);

      const latest = report && report.latest;
      const live = buildLiveView(timeline, names, latest);

      // 血条数据：实时优先，否则取完整战报最后一回合
      let hpCur = live.enemyCur;
      let hpMax = live.enemyMax;
      if (hpMax == null && latest) {
        const turns = latest.turns || [];
        const last = turns[turns.length - 1];
        if (last && last.enemy_hp_max != null) {
          hpMax = last.enemy_hp_max;
          hpCur = last.enemy_hp != null ? last.enemy_hp : last.enemy_hp_max;
        }
      }

      useEffect(() => {
        const box = logBoxRef.current;
        if (box) box.scrollTop = box.scrollHeight;
      }, [open, timeline.length]);

      const btnStyle = {
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        cursor: 'pointer',
      };

      const panelStyle = {
        border: '1px solid var(--dsw-alias-border, #e0e0e0)',
        borderRadius: 8,
        padding: 8,
        marginTop: 8,
        fontSize: 12,
        lineHeight: 1.5,
        textAlign: 'left',
        background: 'var(--dsw-alias-surface, transparent)',
      };

      const statusDot = timeline.length
        ? (live.winner || live.over ? '#c0392b' : '#27ae60')
        : (latest && latest.winner ? '#f39c12' : '#95a5a6');
      const statusText = timeline.length
        ? (live.winner || live.over ? `已结束 · ${live.winner || '未判胜负'}` : '战斗中…')
        : (latest && latest.winner ? `最近一场 · ${latest.winner}` : (latest ? '空闲（有历史战报）' : '空闲'));

      return h('div', { style: { padding: 8 } },
        h('button', { onClick: () => setOpen(!open), style: btnStyle },
          '\u2694\uFE0F 战斗记录 ' + (open ? '收起' : '展开'),
          h('span', {
            style: {
              width: 8, height: 8, borderRadius: '50%',
              background: statusDot, display: 'inline-block',
            },
          }, null),
          h('span', { style: { fontWeight: 400, opacity: 0.75 } }, statusText)),
        open ? h('div', { style: panelStyle }, renderBody({
          busy, error, latest, live, hpCur, hpMax,
          index: report && report.index, logBoxRef,
        })) : null,
        open ? runLogLine(lastSync) : null,
      );
    }

    function fmtError(e) {
      if (e && e.code) return `${e.code}: ${e.message || ''}`;
      if (e && e.name === 'AbortError') return null;
      if (e && e.message) return e.message;
      return String(e);
    }

    function runLogLine(lastSync) {
      return h('div', {
        style: {
          marginTop: 6, fontSize: 11, opacity: 0.7, textAlign: 'left',
          fontFamily: 'ui-monospace, monospace',
        },
      }, `[${lastSync.t}] ${lastSync.msg}`);
    }

    function renderBody(view) {
      const { busy, error, latest, live, hpCur, hpMax, index, logBoxRef } = view;
      if (busy) return h('div', null, '读取中…');
      if (error) return h('div', { style: { color: 'var(--dsw-alias-danger, #c0392b)' } }, '读取失败：' + error);

      const hasLive = live.log.length > 0;

      return h('div', null,
        spritePanel(live, hpCur, hpMax),
        battleLog(live, latest, hasLive, logBoxRef),
        (latest && latest.lineup && latest.lineup.length)
          ? lineupPanel(latest)
          : null,
        hasLive ? null : turnsPanel(latest),
        historyPanel(index),
      );
    }

    function spritePanel(live, hpCur, hpMax) {
      const pct = hpMax > 0 ? Math.max(0, Math.min(100, (hpCur / hpMax) * 100)) : 0;
      const hpText = hpMax != null ? `${hpCur == null ? '?' : hpCur}/${hpMax}` : '体力未知';

      return h('div', { style: { marginBottom: 8 } },
        h('div', { style: { fontWeight: 600, marginBottom: 4 } }, '\u2694\uFE0F 精灵面板'),
        h('div', { style: { display: 'flex', justifyContent: 'space-between', gap: 12 } },
          h('div', null,
            h('div', { style: { opacity: 0.85 } }, '我方'),
            h('div', { style: { fontWeight: 600 } }, live.myName || '我方精灵')),
          h('div', { style: { textAlign: 'right' } },
            h('div', { style: { opacity: 0.85 } }, '敌方'),
            h('div', { style: { fontWeight: 600 } }, live.enemyLabel || '敌方'))),
        h('div', { style: { marginTop: 4 } },
          h('div', { style: { opacity: 0.85 } }, '敌方体力'),
          hpBar(pct, hpText)),
      );
    }

    function hpBar(pct, text) {
      return h('div', {
        style: {
          position: 'relative', height: 16, marginTop: 4,
          background: 'var(--dsw-alias-bg, #f0f0f0)',
          border: '1px solid var(--dsw-alias-border, #d0d0d0)',
          borderRadius: 6, overflow: 'hidden',
        },
      },
        h('div', {
          style: {
            position: 'absolute', left: 0, top: 0, bottom: 0,
            width: `${pct}%`, background: '#e0483e',
            transition: 'width .3s ease',
          },
        }, null),
        h('span', {
          style: {
            position: 'relative', fontSize: 11, lineHeight: '15px',
            padding: '0 6px', color: '#fff', textShadow: '0 0 2px #000',
            whiteSpace: 'nowrap',
          },
        }, text));
    }

    function battleLog(live, latest, hasLive, logBoxRef) {
      const lines = [];
      if (hasLive) {
        for (const l of live.log) {
          const style = l.type === 'round'
            ? { fontWeight: 600, color: 'var(--dsw-alias-info, #2b6cb0)' }
            : l.type === 'end'
              ? { fontWeight: 600, color: (live.winner === '胜利' ? 'var(--dsw-alias-success, #27ae60)' : 'var(--dsw-alias-danger, #c0392b)') }
              : { color: 'var(--dsw-alias-text, inherit)' };
          lines.push(h('div', { key: 'L' + lines.length, style }, l.text));
        }
      } else if (latest && latest.turns && latest.turns.length) {
        lines.push(h('div', { key: 'empty', style: { opacity: 0.65 } }, '本次战斗已结束，见下方回合表。'));
      } else {
        lines.push(h('div', { key: 'empty', style: { opacity: 0.65 } }, '暂无实时战斗（battle-records/latest.timeline.jsonl）。'));
      }

      return h('div', { style: { marginBottom: 8 } },
        h('div', { style: { fontWeight: 600 } }, '\uD83D\uDCDD 战斗日志'),
        h('div', {
          ref: logBoxRef,
          style: {
            marginTop: 4, maxHeight: 200, overflowY: 'auto',
            background: 'var(--dsw-alias-bg, #fafafa)',
            border: '1px solid var(--dsw-alias-border, #e0e0e0)',
            borderRadius: 6, padding: 6,
            fontFamily: 'ui-monospace, SFMono-Regular, monospace',
            fontSize: 12, lineHeight: 1.6,
          },
        }, lines));
    }

    function lineupPanel(latest) {
      const items = (latest.lineup || []).map((m, i) =>
        h('div', { key: 'line' + i },
          (m.slot ? m.slot + '：' : '') + (m.name || '?') + (m.species ? '（精灵 ' + m.species + '）' : '')));
      return h('div', { style: { marginBottom: 8 } },
        h('div', { style: { fontWeight: 600, marginBottom: 2 } }, '我方阵容'),
        items.length ? items : h('div', { style: { opacity: 0.65 } }, '—'));
    }

    function turnsPanel(latest) {
      if (!latest || !latest.turns || !latest.turns.length) return null;
      const turnHead = h('tr', null,
        h('th', { style: { textAlign: 'left', paddingRight: 8 } }, '回合'),
        h('th', { style: { textAlign: 'left', paddingRight: 8 } }, '技能'),
        h('th', { style: { textAlign: 'left', paddingRight: 8 } }, '敌方HP'),
        h('th', { style: { textAlign: 'left' } }, '伤害'));
      const turnRows = latest.turns.map((t, i) =>
        h('tr', { key: 'turn' + i },
          h('td', { style: { paddingRight: 8 } }, t.turn),
          h('td', { style: { paddingRight: 8 } }, t.skill_name || '—'),
          h('td', { style: { paddingRight: 8 } },
            t.enemy_hp != null ? `${t.enemy_hp}${t.enemy_hp_max != null ? '/' + t.enemy_hp_max : ''}` : '—'),
          h('td', null, t.damage != null ? t.damage : '—')));
      return h('div', { style: { marginBottom: 8 } },
        h('div', { style: { fontWeight: 600, marginBottom: 2 } }, '完整战报 · 回合'),
        h('table', { style: { borderCollapse: 'collapse' } },
          h('thead', null, turnHead),
          h('tbody', null, turnRows)));
    }

    function historyPanel(index) {
      const battles = (index && index.battles) || [];
      if (!battles.length) return null;
      return h('details', { style: { marginTop: 4 } },
        h('summary', { style: { cursor: 'pointer' } }, '历史记录（' + battles.length + '）'),
        h('ul', { style: { margin: '4px 0 0', paddingLeft: 18 } },
          battles.slice().reverse().map((b) =>
            h('li', { key: b.id || b.ts },
              (b.title || b.factor_name || b.id)
                + ' · ' + (b.winner || '') + ' · 第' + (b.stage ?? '?') + '关'))));
    }

    return {
      inject: ['slots', 'remote', 'remote.workspaceFiles'],
      apply(ctx) {
        const remote = ctx.remote;
        ctx.slots.inject('conversation.composer.dock', () => ctx.slots.register({
          name: 'conversation.composer.dock',
          id: 'dsh-seer-battle',
          order: 20,
        }, (props) => h(Panel, { ...props, remote })));
      },
    };
  },
});