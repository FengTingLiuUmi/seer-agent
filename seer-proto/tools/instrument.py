import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import flashctl

INSTR = ("(function(){if(window.__probe){return 'already'}window.__probe=[];"
         "var fa=window.gamePublic&&gamePublic.forAs;if(!fa)return 'no-forAs';"
         "['openInnerFrame','closeInnerFrame','callActionScriptFunc','loginWithThird','confirmInitLocal','getSessionID','getAd'].forEach(function(k){"
         "var f=fa[k];if(typeof f!=='function')return;"
         "fa[k]=function(){var a=Array.prototype.slice.call(arguments).map(function(x){try{return String(x).slice(0,80)}catch(e){return '?'}});"
         "window.__probe.push({k:k,a:a,t:Date.now()});try{return f.apply(this,arguments)}catch(e){window.__probe.push({k:k,err:String(e.message)});}};});"
         "try{if(window.Client){['getSession','kickOffFun'].forEach(function(k){var f=window.Client[k];if(typeof f==='function'){"
         "window.Client[k]=function(){window.__probe.push({k:'Client.'+k,t:Date.now()});return f.apply(this,arguments);};}});}}catch(e){}"
         "document.addEventListener('mousedown',function(e){window.__probe.push({k:'mousedown',x:e.clientX,y:e.clientY,tag:(e.target&&e.target.tagName||'')});},true);"
         "document.addEventListener('keydown',function(e){window.__probe.push({k:'keydown',code:e.keyCode});},true);"
         "return 'instrumented';})()")

READ = "(function(){return JSON.stringify((window.__probe||[]).slice(-25))})()"

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'read':
        print(flashctl.post('/eval', {'code': READ}).get('result'))
    else:
        print(flashctl.post('/eval', {'code': INSTR}).get('result'))