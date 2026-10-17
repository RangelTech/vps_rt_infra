import json
import time
import urllib.request

RELAY = "http://127.0.0.1:9333"


def cmd(method, params=None, session=None, timeout=60):
    body = {"method": method, "params": params or {}, "timeout": timeout}
    if session:
        body["sessionId"] = session
    r = urllib.request.Request(RELAY + "/cmd", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=timeout + 10).read())


def events(clear=True):
    return json.loads(urllib.request.urlopen(RELAY + "/events" + ("?clear=1" if clear else ""), timeout=10).read())


def new_tab(url="about:blank"):
    t = cmd("Target.createTarget", {"url": url})["result"]["targetId"]
    s = cmd("Target.attachToTarget", {"targetId": t, "flatten": True})["result"]["sessionId"]
    cmd("Target.activateTarget", {"targetId": t})
    return t, s


def ev(session, expr, await_promise=False, timeout=60):
    r = cmd("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": await_promise}, session, timeout)
    res = r.get("result", {}).get("result", {})
    if "exceptionDetails" in r.get("result", {}):
        return {"_exception": r["result"]["exceptionDetails"].get("text"), "detail": str(r["result"]["exceptionDetails"])[:300]}
    return res.get("value")


def goto(session, url, wait=3):
    cmd("Page.enable", {}, session)
    cmd("Page.navigate", {"url": url}, session)
    time.sleep(wait)


def shot(session, path):
    import base64
    r = cmd("Page.captureScreenshot", {"format": "png"}, session, 60)
    open(path, "wb").write(base64.b64decode(r["result"]["data"]))
    return path


def close_tab(target):
    cmd("Target.closeTarget", {"targetId": target})


def click(session, x, y, n=1):
    for t in ("mouseMoved",):
        cmd("Input.dispatchMouseEvent", {"type": t, "x": x, "y": y}, session)
    cmd("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": n}, session)
    cmd("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": n}, session)


def typ(session, text):
    cmd("Input.insertText", {"text": text}, session)


def key(session, k, code=None, vk=None, mod=0):
    base = {"key": k, "code": code or k, "windowsVirtualKeyCode": vk or 0, "modifiers": mod}
    cmd("Input.dispatchKeyEvent", dict(base, type="keyDown"), session)
    cmd("Input.dispatchKeyEvent", dict(base, type="keyUp"), session)


def select_all(session):
    key(session, "a", "KeyA", 65, 2)


def click_text(session, text, tag="*", exact=False):
    js = """(()=>{const t=%s;const ex=%s;const els=[...document.querySelectorAll('%s')].filter(e=>{const s=(e.innerText||e.textContent||'').trim();return ex?s===t:s.includes(t)});
    const vis=els.filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0});
    vis.sort((a,b)=>(a.innerText||'').length-(b.innerText||'').length);
    if(!vis.length)return null;const r=vis[0].getBoundingClientRect();return [r.x+r.width/2,r.y+r.height/2,(vis[0].innerText||'').slice(0,40)]})()""" % (json.dumps(text), "true" if exact else "false", tag)
    r = ev(session, js)
    if not r:
        return None
    click(session, r[0], r[1])
    return r


def set_input(session, selector, value, index=0):
    js = """(()=>{const els=[...document.querySelectorAll(%s)].filter(e=>e.offsetParent!==null);const i=els[%d];if(!i)return 'no-input';i.focus();
    const proto=i.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto,'value').set.call(i,%s);
    i.dispatchEvent(new Event('input',{bubbles:true}));i.dispatchEvent(new Event('change',{bubbles:true}));return i.value})()""" % (json.dumps(selector), index, json.dumps(value))
    return ev(session, js)


def ui(session, n=40):
    return ev(session, """(()=>{const out=[];document.querySelectorAll('button,a,input,select,textarea,[role=button],[role=radio],[role=combobox],[role=checkbox],mat-radio-button,mat-checkbox').forEach(e=>{if(!e.offsetParent)return;const r=e.getBoundingClientRect();if(r.width<2)return;
    out.push([e.tagName.toLowerCase(),(e.innerText||e.value||e.getAttribute('aria-label')||e.placeholder||'').trim().slice(0,40),Math.round(r.x+r.width/2),Math.round(r.y+r.height/2)])});return out.slice(0,%d)})()""" % n)
