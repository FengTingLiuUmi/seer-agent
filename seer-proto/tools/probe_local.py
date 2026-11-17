import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import flashctl

JS = ("(function(){var o=document.getElementById('Client');"
      "return JSON.stringify({url:location.href.slice(0,120),title:document.title,"
      "hasObj:!!o,tag:o?o.tagName:null,pct:(o&&o.PercentLoaded?o.PercentLoaded():'na'),"
      "client:typeof window.Client,getSession:(typeof window.Client==='object'&&window.Client&&window.Client.getSession?'fn':'no'),"
      "sws:(typeof window.Client==='object'&&window.Client&&window.Client.startWebSessionLogin?'fn':'no'),"
      "bodyLen:document.body.innerHTML.length});})()")
print(json.dumps(flashctl.post('/eval', {'code': JS}), ensure_ascii=False)[:600])
print(json.dumps(flashctl.get('/state'), ensure_ascii=False)[:400])