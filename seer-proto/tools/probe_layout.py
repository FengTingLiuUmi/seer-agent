import json, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import flashctl

JS = r"""
(function(){
  function rect(e){var r=e.getBoundingClientRect();return [Math.round(r.left),Math.round(r.top),Math.round(r.width),Math.round(r.height)];}
  var o=document.getElementById('Client');
  var out={win:[window.innerWidth,window.innerHeight],scroll:[scrollX,scrollY],
           body:rect(document.body), obj:o?rect(o):null,
           objWH:o?[o.offsetWidth,o.offsetHeight,o.getAttribute('width'),o.getAttribute('height')]:null,
           box:(document.getElementById('flashContent')?rect(document.getElementById('flashContent')):null),
           iframe:(document.querySelector('iframe')?rect(document.querySelector('iframe')):null),
           iframeSrc:(document.querySelector('iframe')||{}).src||''};
  return JSON.stringify(out);
})()
"""
print(json.dumps(flashctl.post('/eval', {'code': JS}), ensure_ascii=False))