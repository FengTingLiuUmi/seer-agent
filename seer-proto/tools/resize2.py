import json, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import flashctl


def ev(js):
    return flashctl.post('/eval', {'code': js}).get('result')


def resize(w, h):
    js = ("(function(){var o=document.getElementById('Client');if(!o)return 'no-obj';"
          "o.setAttribute('width',%d);o.setAttribute('height',%d);o.style.width='%dpx';o.style.height='%dpx';"
          "var b=document.getElementById('flashContent');if(b){b.style.width='%dpx';b.style.height='%dpx';}"
          "return o.offsetWidth+'x'+o.offsetHeight;})()" % (w, h, w, h, w, h))
    return ev(js)


if __name__ == '__main__':
    w = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    h = int(sys.argv[2]) if len(sys.argv) > 2 else 560
    print('resize ->', resize(w, h))
    info = ev("(function(){var o=document.getElementById('Client');var r=o.getBoundingClientRect();"
              "return JSON.stringify({win:[window.innerWidth,window.innerHeight],obj:[Math.round(r.left),Math.round(r.top),Math.round(r.width),Math.round(r.height)],"
              "iframe:(document.querySelector('iframe')||{}).src||''});})()")
    print('layout ->', info)