# 计分信号抓取实验：account_f（1/3，没用过独董会）上跑一次独董会，
# 全程 hook 页面 fetch/XHR 抓「请求+响应」，对比进度增量，找出计分的确切信号。
# 结果决定：乡下人第 3 个团队怎么救。
import sys, json, time, os
sys.path.insert(0, r"D:\workbuddy\2026-09-19-00-30-03\buddy-auto")
from cdp import connect, unhide
import ui_driver as U
import ui_tasks as UT
import auto_buddy as core
import tasks as T
import account_switch as AS

KEY = "account_f"
NICK = "15661172224"      # account_f 昵称（核对用）
IDX = 6                   # 独董会

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
print("[1] connected, hidden=", end="")
print(U.js("document.hidden", timeout=15))

# --- 切号 + 核对 ---
r = AS.switch_to(KEY, reload=False)
print("[2] switch:", json.dumps({"ok": r.get("ok"), "menu": (r.get("after") or {}).get("menu")},
                                ensure_ascii=False))
nick = U.js("(document.querySelector('.user-menu-trigger')||{innerText:''}).innerText.trim()", timeout=20)
if not (nick and NICK in str(nick)):
    print("[ABORT] 当前昵称=%s 不是 %s —— 账号核对失败，中止（不跑任何东西）" % (nick, NICK))
    cdp.close()
    sys.exit(2)
print("[2.1] 昵称核对通过:", nick)

# --- 注入网络捕获 hook（fetch + XHR，抓 growth/task/expert/credit 相关请求+响应片段） ---
HOOK = r"""
(() => {
  if (window.__cap2) { window.__cap2.length = 0; return 'reinit'; }
  window.__cap2 = [];
  const KEY_RE = /(growth|activity|task|expert|team|credit|billing|meter|conversation|as\/)/i;
  const of = window.fetch;
  window.fetch = function(...args) {
    const url = String((args[0] && args[0].url) || args[0] || '');
    const method = (args[1] && args[1].method) || 'GET';
    const rec = { t: Date.now(), url: url.slice(0, 160), method: method, body: '' };
    const p = of.apply(this, args);
    if (KEY_RE.test(url)) {
      window.__cap2.push(rec);
      p.then(resp => {
        try {
          const ct = resp.headers.get('content-type') || '';
          if (ct.indexOf('json') !== -1 || ct.indexOf('text') !== -1) {
            resp.clone().text().then(tx => { rec.status = resp.status; rec.resp = tx.slice(0, 600); });
          } else { rec.status = resp.status; rec.resp = '(binary)'; }
        } catch (e) {}
      }).catch(() => {});
    }
    return p;
  };
  const ox = XMLHttpRequest.prototype.open, osn = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function(m, u) { this.__u = String(u || ''); this.__m = m; return ox.apply(this, arguments); };
  XMLHttpRequest.prototype.send = function(b) {
    if (KEY_RE.test(this.__u || '')) {
      const rec = { t: Date.now(), url: (this.__u || '').slice(0, 160), method: this.__m,
                    body: b ? String(b).slice(0, 200) : '', xhr: true };
      window.__cap2.push(rec);
      this.addEventListener('load', () => {
        try { rec.status = this.status; rec.resp = String(this.responseText || '').slice(0, 600); } catch (e) {}
      });
    }
    return osn.apply(this, arguments);
  };
  return 'installed';
})()
"""
print("[3] hook:", U.js(HOOK, timeout=30))

p0 = prog()
print("[4] before:", json.dumps(p0, ensure_ascii=False))

# 等用户停止输入（让路护栏：刚敲过键就不开新任务）
print("[5] 等 25s 避开用户输入窗口...")
time.sleep(25)

# --- 跑独董会一次（完整轮，不提前收工，不删会话留现场） ---
print("[6] run_expert_once 独董会 idx=%d (等整轮, max_wait=300, 不删会话) ..." % IDX)
t0 = time.time()
res = UT.run_expert_once(kind="team", idx=IDX, prompt="", model=None,
                         max_wait=300, delete_after=False, team_first_reply=False)
run = res.get("run") or {}
nags = [x.get("nAg") for x in (run.get("log") or []) if isinstance(x, dict) and x.get("nAg")]
print("[7] result: ok=%s reason=%s secs=%.0f nAg轨迹=%s sent=%s created=%s err=%s"
      % (res.get("ok"), run.get("reason"), time.time() - t0,
         nags[:10], res.get("sent"), (res.get("created_title") or "")[:30], (res.get("err") or "")[:80]))
print("[7.1] final:", json.dumps(run.get("final"), ensure_ascii=False))

time.sleep(3)
p1 = prog()
print("[8] after:", json.dumps(p1, ensure_ascii=False))

# --- dump 捕获的网络请求 ---
cap = U.js("(() => (window.__cap2 || []).slice(-40))()", timeout=40)
print("[9] captured %d requests:" % len(cap or []))
for c in (cap or [])[-25:]:
    print("   %s %s %s %s" % (c.get("method"), c.get("url", "")[:90],
                              c.get("status", ""), (c.get("resp") or "")[:140].replace("\n", " ")))

# --- 切回主号 ---
back = AS.switch_to("account_a", reload=False)
print("[10] 切回主号:", back.get("ok"), (back.get("after") or {}).get("menu"))

diff = (p1.get("progress") or "") != (p0.get("progress") or "")
print("\n=== 结论: 进度 %s -> %s (%s) ===" % (p0.get("progress"), p1.get("progress"),
      "有变化!" if diff else "无变化"))
cdp.close()
