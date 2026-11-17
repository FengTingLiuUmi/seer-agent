import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import flashctl

JS = ("(function(){function R(e){if(!e)return null;var r=e.getBoundingClientRect();var s=getComputedStyle(e);"
      "return {box:[Math.round(r.left),Math.round(r.top),Math.round(r.width),Math.round(r.height)],"
      "z:s.zIndex,pos:s.position,disp:s.display,pe:s.pointerEvents,vis:s.visibility,ov:s.overflow};}"
      "var o=document.getElementById('Client');var ifr=document.getElementById('innerPopIframe');"
      "return JSON.stringify({win:[window.innerWidth,window.innerHeight],"
      "doc:[document.documentElement.scrollWidth,document.documentElement.scrollHeight],"
      "flash:R(o),iframe:R(ifr),iframeSrc:(ifr||{}).src||(ifr||{}).getAttribute&&ifr.getAttribute('src'),"
      "topAtCenter:(function(){var el=document.elementFromPoint(Math.floor(window.innerWidth/2),Math.floor(window.innerHeight/2));return el?el.tagName+'#'+el.id:null})(),"
      "allTags:Array.prototype.slice.call(document.querySelectorAll('body > *')).map(function(e){return e.tagName+'#'+e.id}).join(',')});})()")

print(json.dumps(flashctl.post('/eval', {'code': JS}), ensure_ascii=False))