package main

import (
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"sort"
	"strings"
	"sync"
	"time"
)

// 一条可视化事件：谁发的/收的、什么命令、结果、body
type ev struct {
	T    int64  `json:"t"`
	Dir  string `json:"dir"` // c2s / s2c / info / err
	Cmd  uint32 `json:"cmd,omitempty"`
	Name string `json:"name,omitempty"`
	Len  int    `json:"len,omitempty"`
	Res  int32  `json:"res,omitempty"`
	Body string `json:"body,omitempty"` // hex
	Msg  string `json:"msg,omitempty"`
}

// 面板"可选操作"里的一条
type action struct {
	Group string `json:"group"`
	Name  string `json:"name"`
	Cmd   uint32 `json:"cmd"`
	Body  string `json:"body,omitempty"` // hex
	Note  string `json:"note,omitempty"`
}

// 面板 → 主循环 的发包请求
type actReq struct {
	Cmd   uint32
	Body  []byte
	Label string
}

var (
	evMu    sync.Mutex
	evs     []ev
	evNames map[uint32]string
	evFile  *os.File

	acts   []action
	actChQ chan actReq
)

func initEvents(names map[uint32]string, logPath string) {
	evNames = names
	if logPath != "" {
		evFile, _ = os.OpenFile(logPath, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0644)
	}
}

func loadActions(path string) {
	acts = nil
	b, err := os.ReadFile(path)
	if err != nil {
		return
	}
	var list []action
	if json.Unmarshal(b, &list) == nil {
		acts = list
	}
}

func emit(e ev) {
	if e.T == 0 {
		e.T = time.Now().UnixMilli()
	}
	if e.Cmd != 0 && e.Name == "" && evNames != nil {
		e.Name = evNames[e.Cmd]
	}
	evMu.Lock()
	evs = append(evs, e)
	if len(evs) > 4000 {
		evs = evs[len(evs)-4000:]
	}
	evMu.Unlock()
	if evFile != nil {
		if b, err := json.Marshal(e); err == nil {
			evFile.Write(append(b, '\n'))
			evFile.Sync()
		}
	}
}

func emitFrame(dir string, raw []byte) {
	e := ev{Dir: dir, Len: len(raw)}
	if len(raw) >= 17 {
		e.Cmd = uint32(raw[5])<<24 | uint32(raw[6])<<16 | uint32(raw[7])<<8 | uint32(raw[8])
		e.Res = int32(uint32(raw[13])<<24 | uint32(raw[14])<<16 | uint32(raw[15])<<8 | uint32(raw[16]))
		e.Body = hex.EncodeToString(raw[17:])
		if dir == "s2c" {
			if s := summarize(e.Cmd, raw[17:]); s != "" {
				e.Msg = s
			}
		}
	}
	emit(e)
}

func emitInfo(msg string) { emit(ev{Dir: "info", Msg: msg}) }
func emitErr(msg string)  { emit(ev{Dir: "err", Msg: msg}) }

const pageHTML = `<!doctype html><html lang="zh"><head><meta charset="utf-8">
<title>seer 控制台</title><style>
*{box-sizing:border-box}
body{font:13px/1.5 ui-monospace,Consolas,monospace;background:#0e1218;color:#d5dae3;margin:0;height:100vh;display:flex;overflow:hidden}
#left{width:340px;min-width:260px;border-right:1px solid #263043;display:flex;flex-direction:column;background:#11151c}
#right{flex:1;display:flex;flex-direction:column;min-width:0}
.hd{padding:8px 10px;border-bottom:1px solid #263043;color:#9fd3ff;font-size:13px;display:flex;justify-content:space-between;align-items:center}
.hd span{color:#5c6773;font-weight:normal}
#acts{overflow:auto;padding:6px}
.grp{color:#ffd479;margin:8px 2px 4px;font-size:12px}
.act{display:block;width:100%;text-align:left;margin:2px 0;padding:4px 7px;background:#161d27;color:#c9d3e0;border:1px solid #253041;border-radius:4px;cursor:pointer;font:12px/1.4 ui-monospace,Consolas,monospace}
.act:hover{background:#1d2836;border-color:#3a4d66}
.act b{color:#79c0ff;font-weight:normal}
.act i{color:#5c6773;font-style:normal}
#q{width:100%;margin:6px 0;padding:5px 8px;background:#0b0f14;border:1px solid #253041;color:#d5dae3;border-radius:4px}
#tb{flex:1;overflow:auto;padding:4px 0}
tr.row{display:flex;gap:8px;padding:1px 8px;border-bottom:1px solid #161d27}
tr.row:hover{background:#131a23}
.c2s{color:#7ee787}.s2c{color:#79c0ff}.info{color:#c8a2ff}.err{color:#ff7b72}
.cmd{color:#ffd479;width:52px;text-align:right}
.nm{color:#9aa7b8;width:150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ln{color:#4d5766;width:86px}
.msg{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#c9d3e0}
.raw{color:#3d4757;width:280px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#st{font-size:12px}
#detail{flex:1;overflow:auto;padding:10px 14px;display:none}
#detail h3{margin:0 0 6px;font-size:13px;color:#9fd3ff}
#detail .kv{color:#9aa7b8;margin:2px 0}
#detail pre{background:#0b0f14;border:1px solid #1c2531;padding:8px;border-radius:4px;white-space:pre-wrap;word-break:break-all;font-size:12px;max-height:40vh;overflow:auto}
#detail .back{margin-bottom:8px}
button.mini{background:#161d27;color:#9fd3ff;border:1px solid #253041;border-radius:4px;padding:2px 8px;cursor:pointer;font-size:12px}
</style></head><body>
<div id="left">
  <div class="hd">可选操作 <span id="actcnt"></span></div>
  <div style="padding:6px 10px 0"><input id="q" placeholder="搜索全部命令（如 PET/ACHIEVE/MAP）"></div>
  <div id="acts"></div>
</div>
<div id="right">
  <div class="hd">实时帧 <span><button class="mini" id="fOnly">只看 C2S</button> <span id="st">连接中…</span> <span id="cnt">0</span></span></div>
  <div id="tb"></div>
  <div id="detail"></div>
</div>
<script>
let since=0, rows=[], actsLoaded=false;
let focusCmd=0, focusAt=0, focusName='';
const esc=s=>String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
function renderActs(list){
  const box=document.getElementById('acts'); const g={};
  list.forEach(a=>{(g[a.group]=g[a.group]||[]).push(a)});
  let h='';
  for(const k of Object.keys(g)){
    h+='<div class="grp">'+esc(k)+'</div>';
    for(const a of g[k]) h+='<button class="act" data-cmd="'+a.cmd+'" data-body="'+(a.body||'')+'" data-name="'+esc(a.name)+'"><b>'+a.cmd+'</b> '+esc(a.name)+(a.note?' <i>'+esc(a.note)+'</i>':'')+'</button>';
  }
  box.innerHTML=h;
  Array.prototype.forEach.call(box.querySelectorAll('button.act'),function(b){b.onclick=function(){send(+b.dataset.cmd,b.dataset.body,b.dataset.name)};});
}
async function loadActs(){
  const r=await fetch('/actions'); const j=await r.json();
  renderActs(j.actions||[]);
  document.getElementById('actcnt').textContent=(j.actions||[]).length+' 项';
}
async function send(cmd,bodyHex,name){
  try{
    const r=await fetch('/act',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({cmd,body:bodyHex})});
    const j=await r.json();
    if(!j.ok){alert('发送失败: '+(j.error||''));return;}
    focusCmd=cmd; focusAt=Date.now(); focusName=name||''; renderFrames();
  }catch(e){alert('发送失败: '+e.message)}
}
document.getElementById('q').addEventListener('keydown',async ev=>{
  if(ev.key!=='Enter')return;
  const q=ev.target.value.trim(); if(!q)return loadActs();
  const r=await fetch('/cmds?q='+encodeURIComponent(q)); const j=await r.json();
  renderActs((j.cmds||[]).map(c=>({group:'搜索结果（空 body，可能报错）',name:c.name,cmd:c.cmd})));
  document.getElementById('actcnt').textContent=(j.cmds||[]).length+' 项';
});
function hexBytes(h){var b=[];for(var i=0;i+1<h.length;i+=2)b.push(parseInt(h.substr(i,2),16));return b;}
function decodeText(h){
  var b=hexBytes(h), s='', cur='', i;
  for(i=0;i<b.length;i++){var c=b[i]; if(c>=32&&c<127){cur+=String.fromCharCode(c);} else {if(cur.length>=2){s+=cur+' | ';} cur='';}}
  if(cur.length>=2){s+=cur;}
  var u='';
  try{ u=new TextDecoder('utf-8').decode(new Uint8Array(b)); }catch(e){ u=''; }
  u=u.replace(/[^\x20-\x7e\u4e00-\u9fa5]/g,'');
  return {ascii:s, utf8:u};
}
function u32list(h){var b=hexBytes(h),o=[],i;for(i=0;i+3<b.length&&o.length<40;i+=4){o.push(((b[i]<<24)|(b[i+1]<<16)|(b[i+2]<<8)|b[i+3])>>>0);}return o.join(' ');}
function hexdump(h,max){max=max||384;var b=hexBytes(h.slice(0,max*2)),out='',i,j;for(i=0;i<b.length;i+=16){for(j=0;j<16&&i+j<b.length;j++){out+=('0'+b[i+j].toString(16)).slice(-2)+' ';}out+='\n';}return out;}
function renderDetail(){
  var d=document.getElementById('detail'), tb=document.getElementById('tb'), hit=null, i;
  for(i=rows.length-1;i>=0;i--){var e=rows[i]; if(e.dir==='s2c'&&e.cmd===focusCmd&&e.t>=focusAt-3000){hit=e;break;}}
  var h='<div class="back"><button class="mini" id="backbtn">返回实时帧</button></div>';
  h+='<h3>已跳转：'+focusCmd+' '+(focusName||(hit&&hit.name)||'')+'</h3>';
  if(!hit){
    h+='<div class="kv">等待回包…（若命令缺参数，连线上会断开，右栏历史里能看到）</div>';
  }else{
    var dec=decodeText(hit.body||'');
    h+='<div class="kv">len='+hit.len+' res='+(hit.res===undefined?'':hit.res)+' t='+new Date(hit.t).toLocaleTimeString()+'</div>';
    h+='<div class="kv">摘要：'+esc(hit.msg||'')+'</div>';
    if(dec.utf8){h+='<div class="kv">文本(utf8)：</div><pre>'+esc(dec.utf8)+'</pre>';}
    if(dec.ascii){h+='<div class="kv">文本(ascii 片段)：</div><pre>'+esc(dec.ascii)+'</pre>';}
    h+='<div class="kv">u32 序列：</div><pre>'+u32list(hit.body||'')+'</pre>';
    h+='<div class="kv">前 384 字节：</div><pre class="hexd">'+hexdump(hit.body||'')+'</pre>';
  }
  d.innerHTML=h; d.style.display='block'; tb.style.display='none';
  var bb=document.getElementById('backbtn');
  if(bb){bb.onclick=function(){focusCmd=0;renderFrames();};}
}
function renderFrames(){
  if(focusCmd){renderDetail();return;}
  document.getElementById('tb').style.display='';
  document.getElementById('detail').style.display='none';
  const only=document.getElementById('fOnly').dataset.on==='1';
  const tb=document.getElementById('tb'); let h='';
  for(const e of rows.slice().reverse()){
    if(only && !(e.dir==='c2s'||e.dir==='err')) continue;
    h+='<div class="row"><span class="'+e.dir+'" style="width:34px">'+e.dir.toUpperCase()+'</span>'+
       '<span class="cmd">'+(e.cmd||'')+'</span><span class="nm">'+(e.name||'')+'</span>'+
       '<span class="ln">len='+(e.len||'')+' res='+(e.res===undefined?'':e.res)+'</span>'+
       '<span class="msg">'+esc(e.msg||'')+'</span><span class="raw">'+esc((e.body||'').slice(0,120))+'</span></div>';
  }
  tb.innerHTML=h; document.getElementById('cnt').textContent=rows.length;
}
document.getElementById('fOnly').onclick=function(){this.dataset.on=this.dataset.on==='1'?'0':'1';this.style.color=this.dataset.on==='1'?'#7ee787':'#9fd3ff';renderFrames()};
async function tick(){
  try{
    const r=await fetch('/events?since='+since); const j=await r.json();
    if(j.events&&j.events.length){rows=rows.concat(j.events); since=j.next; renderFrames();}
    document.getElementById('st').textContent='live';
    if(!actsLoaded){actsLoaded=true; loadActs();}
  }catch(e){document.getElementById('st').textContent='断开';}
}
setInterval(tick,700); tick();
</script></body></html>`

func startView(addr string, ch chan actReq, cmds map[uint32]string) {
	actChQ = ch
	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		fmt.Fprint(w, pageHTML)
	})
	http.HandleFunc("/events", func(w http.ResponseWriter, r *http.Request) {
		since := 0
		fmt.Sscanf(r.URL.Query().Get("since"), "%d", &since)
		evMu.Lock()
		if since < 0 || since > len(evs) {
			since = len(evs)
		}
		out := append([]ev{}, evs[since:]...)
		next := len(evs)
		evMu.Unlock()
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]any{"events": out, "next": next})
	})
	http.HandleFunc("/actions", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]any{"actions": acts})
	})
	http.HandleFunc("/cmds", func(w http.ResponseWriter, r *http.Request) {
		q := strings.ToUpper(strings.TrimSpace(r.URL.Query().Get("q")))
		type row struct {
			Cmd  uint32 `json:"cmd"`
			Name string `json:"name"`
		}
		var out []row
		for id, n := range cmds {
			if n == "" {
				continue
			}
			if q == "" || strings.Contains(strings.ToUpper(n), q) {
				out = append(out, row{id, n})
			}
		}
		sort.Slice(out, func(i, j int) bool { return out[i].Cmd < out[j].Cmd })
		if len(out) > 60 {
			out = out[:60]
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]any{"cmds": out})
	})
	http.HandleFunc("/act", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			Cmd  uint32 `json:"cmd"`
			Body string `json:"body"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil || req.Cmd == 0 {
			w.Header().Set("Content-Type", "application/json")
			json.NewEncoder(w).Encode(map[string]any{"ok": false, "error": "bad request"})
			return
		}
		var body []byte
		if req.Body != "" {
			b, err := hex.DecodeString(req.Body)
			if err != nil {
				w.Header().Set("Content-Type", "application/json")
				json.NewEncoder(w).Encode(map[string]any{"ok": false, "error": "bad hex"})
				return
			}
			body = b
		}
		select {
		case actChQ <- actReq{Cmd: req.Cmd, Body: body, Label: "panel"}:
			w.Header().Set("Content-Type", "application/json")
			json.NewEncoder(w).Encode(map[string]any{"ok": true})
		default:
			w.Header().Set("Content-Type", "application/json")
			json.NewEncoder(w).Encode(map[string]any{"ok": false, "error": "队列满，稍后再试"})
		}
	})
	go func() {
		emitInfo("面板已启动: http://" + addr)
		if err := http.ListenAndServe(addr, nil); err != nil {
			emitErr("http: " + err.Error())
		}
	}()
}