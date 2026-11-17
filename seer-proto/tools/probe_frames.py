import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import flashctl

JS = (r"""
(function(){
  var out=[]; 
  function walk(w, path, depth){
    if(depth>2) return;
    var info={path:path, href:null, title:null, err:null, inputs:[], buttons:[], ids:[], ifr:[]};
    try{ info.href=(w.location.href||'').slice(0,120); }catch(e){ info.err='href:'+e.message; }
    try{ info.title=w.document.title; }catch(e){ info.err=(info.err||'')+' doc:'+e.message; }
    try{
      var d=w.document;
      var ins=d.querySelectorAll('input');
      for(var i=0;i<ins.length && i<8;i++) info.inputs.push(ins[i].type+'#'+ins[i].id+'/'+ins[i].name);
      var bs=d.querySelectorAll('a,button');
      for(var i=0;i<bs.length && i<10;i++) info.buttons.push(((bs[i].innerText||'').trim().slice(0,8))+'#'+bs[i].id);
      var idn=d.querySelectorAll('[id]');
      for(var i=0;i<idn.length && i<15;i++) info.ids.push(idn[i].tagName+'#'+idn[i].id);
      var fr=d.querySelectorAll('iframe');
      for(var i=0;i<fr.length && i<5;i++) info.ifr.push(fr[i].id+'|'+(fr[i].src||'').slice(0,80));
    }catch(e){ info.err=(info.err||'')+' q:'+e.message; }
    out.push(info);
    for(var i=0;i<w.frames.length;i++){ try{ walk(w.frames[i], path+'/'+i, depth+1); }catch(e){} }
  }
  walk(window,'',0);
  return JSON.stringify(out);
})()
""")

print(json.dumps(flashctl.post('/eval', {'code': JS}), ensure_ascii=False)[:3000])