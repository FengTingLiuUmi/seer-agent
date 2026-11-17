import json, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import flashctl

W, H = 1000, 600
JS = r"""
(function(){
  var o=document.getElementById('Client');
  var box=document.getElementById('flashContent')||document.getElementById('myFlashBox');
  if(!o) return 'no-object';
  o.setAttribute('width',{W}); o.setAttribute('height',{H});
  o.style.width='{W}px'; o.style.height='{H}px';
  if(box){ box.style.width='{W}px'; box.style.height='{H}px'; }
  document.body.style.overflow='hidden';
  return 'resized to {W}x{H}, obj='+o.offsetWidth+'x'+o.offsetHeight;
})()
""".replace('{W}', str(W)).replace('{H}', str(H))

print(json.dumps(flashctl.post('/eval', {'code': JS}), ensure_ascii=False))