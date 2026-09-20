# 验证闭环：account_g（0/3 白板号）跑独董会。
# 前置：清「团队召唤确认框」suppress 键（2026-09-20 破案的根因修复）。
# 预期：确认框恢复弹出 → 授权流程走通 → 协作启动（nAg>1）→ 0/3 → 1/3 计分。
import sys, json, time
sys.path.insert(0, r"D:\workbuddy\2026-09-19-00-30-03\buddy-auto")
from cdp import connect, unhide
import ui_driver as U
import ui_tasks as UT
import auto_buddy as core
import tasks as T
import account_switch as AS

KEY = "account_g"
NICK = "15047889319"
IDX = 6  # 独董会

def prog():
    cfg = core.load_config()
    acct = next(a for a in cfg["accounts"] if a["key"] == KEY)
    cred, err = core.load_cred(acct)
    if err:
        return {"err": err}
    lst, err = T.fetch_tasks(cred, cfg)
    if err:
        return {"err": err}
    for t in lst:
        if t["code"] == "Expert_team_use_3":
            return {"progress": t["progress_text"], "status": t["status_label"]}
    return {"err": "task not found"}

cdp, page = connect()
unhide(cdp)
print("[1] connected, hidden=", U.js("document.hidden", timeout=15))

r = AS.switch_to(KEY, reload=False)
print("[2] switch:", json.dumps({"ok": r.get("ok"), "menu": (r.get("after") or {}).get("menu")},
                                ensure_ascii=False))
time.sleep(2)
nick = U.js("(document.querySelector('.user-menu-trigger')||{innerText:''}).innerText.trim()", timeout=20)
if not (nick and NICK in str(nick)):
    print("[ABORT] 昵称核对失败: %s" % nick)
    cdp.close()
    sys.exit(2)
print("[2.1] 昵称核对通过:", nick)

p0 = prog()
print("[3] before:", json.dumps(p0, ensure_ascii=False))

# 注入网络捕获 hook（放在跑之前最后一刻，避开切号后的页面刷新）
HOOK = r"""
(() => {
  window.__cap2 = [];
  const of = window.fetch;
  window.fetch = function(...args) {
    const url = String((args[0] && args[0].url) || args[0] || '');
    const method = (args[1] && args[1].method) || 'GET';
    const rec = { t: Date.now(), url: url.slice(0, 150), method: method };
    window.__cap2.push(rec);
    if (window.__cap2.length > 200) window.__cap2.shift();
    const p = of.apply(this, args);
    p.then(resp => {
      try { resp.clone().text().then(tx => { rec.status = resp.status; rec.resp = tx.slice(0, 400); }); } catch (e) {}
    }).catch(() => {});
    return p;
  };
  return 'installed-all';
})()
"""
print("[4] hook:", U.js(HOOK, timeout=30))

print("[5] 等 25s 避开用户输入窗口...")
time.sleep(25)

print("[6] run_expert_once 独董会（含第0步清suppress键；确认框应弹出并被ACK走通）...")
t0 = time.time()
res = UT.run_expert_once(kind="team", idx=IDX, prompt="", model=None,
                         max_wait=300, delete_after=False, team_first_reply=False)
run = res.get("run") or {}
nags = [x.get("nAg") for x in (run.get("log") or []) if isinstance(x, dict) and x.get("nAg")]
pre = res.get("pre") or {}
print("[7] err=%s" % (res.get("err") or "(none)"))
print("[7.0] model_used=%s prepare=%s" % (res.get("model_used") or res.get("model"),
                                          json.dumps(res.get("prepare"), ensure_ascii=False)[:200]))
for i, s in enumerate(res.get("pre_steps") or []):
    print("    step%d: %s" % (i, json.dumps(s, ensure_ascii=False)[:160]))
# 对话首条 AI 回复内容（看团队上下文是否注入）
first_reply = U.js(r"""
(() => {
  const v = document.querySelector('.cr-message-list-viewport');
  if (!v) return {view: false};
  const agents = Array.from(v.querySelectorAll('.cr-agent'));
  const texts = agents.map(a => (a.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 120));
  const modelEl = document.querySelector('.cr-model-selector__trigger');
  return {view: true, nAg: agents.length, model: modelEl ? (modelEl.innerText || '').slice(0, 30) : null,
          agentTexts: texts.slice(0, 3)};
})()
""", timeout=40)
print("[7.15] 对话现场:", json.dumps(first_reply, ensure_ascii=False)[:600])
print("[7.1] result: ok=%s reason=%s secs=%.0f nAg轨迹=%s sent=%s created=%s"
      % (res.get("ok"), run.get("reason"), time.time() - t0, nags[:12],
         res.get("sent"), (res.get("created_title") or "")[:30]))
print("[7.2] final:", json.dumps(run.get("final"), ensure_ascii=False))

time.sleep(3)
p1 = prog()
print("[8] after:", json.dumps(p1, ensure_ascii=False))

cap = U.js("(() => (window.__cap2 || []).slice(-30))()", timeout=40)
print("[9] captured %d:" % len(cap or []))
for c in (cap or [])[-20:]:
    print("   %s %s %s %s" % (c.get("method"), c.get("url", "")[:85],
                              c.get("status", ""), (c.get("resp") or "")[:130].replace("\n", " ")))

back = AS.switch_to("account_a", reload=False)
print("[10] 切回主号:", back.get("ok"))

print("\n=== 结论: 进度 %s -> %s | nAg=%s | 确认框=%s ==="
      % (p0.get("progress"), p1.get("progress"),
         max(nags) if nags else None, pre.get("dialog")))
cdp.close()
