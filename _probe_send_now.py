# 直接发送当前已召唤好的团队对话并观察（不重开任务，保留 chip 与预填引导语）。
import sys, json, time
sys.path.insert(0, r"D:\workbuddy\2026-09-19-00-30-03\buddy-auto")
from cdp import connect, unhide
import ui_driver as U
import auto_buddy as core
import tasks as T

cdp, page = connect()
unhide(cdp)
nick = U.js("(document.querySelector('.user-menu-trigger')||{innerText:''}).innerText.trim()", timeout=20)
print("[nick]", nick)

def prog():
    cfg = core.load_config()
    acct = next(a for a in cfg["accounts"] if a["key"] == "account_e")
    cred, err = core.load_cred(acct)
    if err:
        return {"err": err}
    lst, e2 = T.fetch_tasks(cred, cfg)
    if e2:
        return {"err": e2}
    for t in lst:
        if t["code"] == "Expert_team_use_3":
            return {"progress": t["progress_text"], "status": t["status_label"]}
    return {"err": "not found"}

print("[before]", json.dumps(prog(), ensure_ascii=False))

# 发送前：确认 chip 与输入内容
pre = U.js(r"""
(() => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const chips = Array.from(document.querySelectorAll('[class*="chip"]')).map(x => T(x)).filter(Boolean).slice(0, 4);
  const ed = document.querySelector('[contenteditable=true]');
  const model = document.querySelector('.cr-model-selector__trigger, [class*="model-selector"]');
  return { chips: chips, input: ed ? (ed.innerText || '').replace(/\s+/g, ' ').slice(0, 60) : null,
           model: model ? T(model).slice(0, 24) : null };
})()
""", timeout=30)
print("[pre-send]", json.dumps(pre, ensure_ascii=False))

s = U.js("(async () => { const r = send(); return r; })()", timeout=60)
print("[send]", json.dumps(s, ensure_ascii=False)[:200])

SNAP = r"""
(() => {
  const v = document.querySelector('.cr-message-list-viewport');
  const agents = v ? Array.from(v.querySelectorAll('.cr-agent')) : [];
  const last = agents[agents.length - 1];
  const stEl = last ? last.querySelector('.cr-agent__processing-status') : null;
  return { nAg: agents.length,
           proc: v ? !!v.querySelector('.cr-agent--processing') : false,
           len: v ? (v.innerText || '').length : 0,
           status: stEl ? (stEl.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 26) : '' };
})()
"""
t0 = time.time()
last_key, stable = None, 0
while time.time() - t0 < 300:
    time.sleep(2)
    sn = U.js(SNAP, timeout=30)
    if not isinstance(sn, dict):
        print("[poll] bad", sn); break
    key = (sn.get("nAg"), sn.get("proc"), sn.get("len"))
    if key != last_key:
        print("  t=%.0fs nAg=%s proc=%s len=%s status=%s" % (time.time()-t0, sn.get("nAg"), sn.get("proc"), sn.get("len"), sn.get("status")))
        last_key, stable = key, 0
    else:
        stable += 1
    if not sn.get("proc") and sn.get("len", 0) > 0 and stable >= 4 and time.time() - t0 > 8:
        print("[done] idle-stable at t=%.0fs" % (time.time()-t0)); break
else:
    print("[timeout] 300s")

time.sleep(3)
print("[after]", json.dumps(prog(), ensure_ascii=False))
cdp.close()
