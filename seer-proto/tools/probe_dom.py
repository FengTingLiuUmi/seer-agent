import json, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import flashctl

JS = r"""
(function(){
  function info(d){
    var out={ids:[],links:[],iframes:[],flash:[]};
    try{
      var e=d.querySelectorAll('[id]');
      for(var i=0;i<e.length && i<25;i++) out.ids.push(e[i].tagName+'#'+e[i].id);
      var a=d.querySelectorAll('a');
      for(var i=0;i<a.length && i<10;i++) out.links.push(((a[i].innerText||'').trim().slice(0,8))+'|'+(a[i].href||'').slice(0,50));
      var f=d.querySelectorAll('iframe');
      for(var i=0;i<f.length && i<5;i++) out.iframes.push((f[i].src||'').slice(0,80));
      var o=d.querySelectorAll('object,embed');
      for(var i=0;i<o.length && i<5;i++) out.flash.push(o[i].tagName+'#'+o[i].id+' '+(o[i].getAttribute('data')||o[i].getAttribute('src')||'').slice(0,60));
    }catch(err){ out.err=String(err.message); }
    return out;
  }
  var res={top:{title:document.title,url:location.href},d0:info(document)};
  try{ if(window.frames.length){ res.f0=info(window.frames[0].document); } }catch(e){ res.f0err=String(e.message); }
  return JSON.stringify(res);
})()
"""

r = flashctl.post('/eval', {'code': JS})
print(json.dumps(r, ensure_ascii=False)[:2000])