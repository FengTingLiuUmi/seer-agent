import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import flashctl

JS = ("(function(){"
      "var s=document.createElement('style');"
      "s.type='text/css';"
      "s.appendChild(document.createTextNode('html,body{margin:0!important;padding:0!important;overflow:hidden!important;background:#000!important;}"
      "#flashContent,#myFlashBox,object,embed{display:block;width:960px!important;height:560px!important;}"
      "body>div{margin:0!important;padding:0!important;}'));"
      "document.getElementsByTagName('head')[0].appendChild(s);"
      "var o=document.getElementById('Client');"
      "if(o){o.setAttribute('width',960);o.setAttribute('height',560);o.style.width='960px';o.style.height='560px';}"
      "var b=document.getElementById('flashContent')||document.getElementById('myFlashBox');"
      "if(b){b.style.width='960px';b.style.height='560px';}"
      "window.scrollTo(0,0);"
      "return JSON.stringify({inner:[window.innerWidth,window.innerHeight],"
      "scroll:[document.documentElement.scrollWidth,document.documentElement.scrollHeight],"
      "bodyScroll:[document.body.scrollWidth,document.body.scrollHeight],"
      "obj:(o?[o.offsetWidth,o.offsetHeight]:null)});})()")

print(json.dumps(flashctl.post('/eval', {'code': JS}), ensure_ascii=False))