# 按**团队名字**召唤并跑完一个专家团（乡下人 account_e），免费模型 Hy3。
# 用法：python _run_team_byname.py "智数分析"
import sys, json, time
sys.path.insert(0, r"D:\workbuddy\2026-09-19-00-30-03\buddy-auto")
from cdp import connect, unhide
import ui_driver as U
import ui_tasks as UT
import auto_buddy as core
import tasks as T
import account_switch as AS

NAME = sys.argv[1] if len(sys.argv) > 1 else "智数分析"
MODEL = sys.argv[2] if len(sys.argv) > 2 else "Hy3"
KEY, NICK = "account_e", "乡下人"

def prog():
    cfg = core.load_config()
    acct = next(a for a in cfg["accounts"] if a["key"] == KEY)
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

cdp, page = connect()
unhide(cdp)
nick = U.js("(document.querySelector('.user-menu-trigger')||{innerText:''}).innerText.trim()", timeout=20)
print("[nick]", nick)
if NICK not in str(nick):
    r = AS.switch_to(KEY, reload=False); time.sleep(2)
    print("[switch]", r.get("ok"), (r.get("after") or {}).get("menu"))

# 按名字选卡片的步骤
OPEN_BY_NAME = r"""
(async () => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const want = %s;
  let cards = [];
  for (let i = 0; i < 30; i++) {
    cards = Array.from(document.querySelectorAll('.ec-expert-card'));
    if (cards.length) break;
    await sleep(600);
  }
  if (!cards.length) return { ok: false, err: '专家团卡片列表为空' };
  const card = cards.find(c => T(c).indexOf(want) !== -1);
  if (!card) return { ok: false, err: '找不到团队：' + want, names: cards.map(c => T(c).slice(0, 14)) };
  const name = T(card).replace(/^召唤\s*/, '').slice(0, 24);
  realClick(card);
  let btn = null;
  for (let i = 0; i < 24; i++) { await sleep(500); btn = document.querySelector('.ec-modal-summon-btn'); if (btn) break; }
  if (!btn) return { ok: false, err: '团队详情弹窗没出来', name: name };
  return { ok: true, name: name, modal: true, nCards: cards.length, byName: true };
})()
""" % json.dumps(NAME)

# 前置清理：关掉上一个流程可能残留的确认框/弹窗（否则挡住侧栏、点不动入口）
PREP = r"""
(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const acts = [];
  for (let i = 0; i < 3; i++) {
    const cancel = document.querySelector('[data-track-id=expert_team_confirm_cancel]');
    if (cancel) { realClick(cancel); acts.push('cancel'); await sleep(900); } else break;
  }
  for (let i = 0; i < 2; i++) {
    document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}));
    acts.push('esc'); await sleep(600);
  }
  const left = Array.from(document.querySelectorAll('[class*="_dialogOverlay"], .ec-modal-overlay'))
    .filter(el => el.offsetHeight > 20).length;
  return { ok: true, acts: acts, leftoverOverlays: left };
})()
"""

pick = UT._as_fn(UT.EXPERT_PICK_STEP)
steps = [U.reset_team_summon_suppress,
         PREP,
         UT.EXPERT_ENTER_STEP,
         "(async () => { const f = %s; return await f('team', null, 0); })()" % pick,
         OPEN_BY_NAME,
         UT.EXPERT_TEAM_MODAL_SUMMON_STEP,
         UT.EXPERT_TEAM_ACK_STEP,
         UT.EXPERT_STATE_STEP]
gaps = [2, 2, 6, 5, 2, 2, 2, 2]

print("[before]", json.dumps(prog(), ensure_ascii=False))
print("[run] 团队=%s 模型=%s" % (NAME, MODEL))
t0 = time.time()
r = U.run_task(template=None, prompt="", model=MODEL, use_template=False,
               pre_steps=steps, pre_gap=gaps, keep_input=True, pre_clear=True,
               pre_must_ok=True, delete_after=False, max_wait=300,
               team_first_reply=False, yield_to_user=False)
run = r.get("run") or {}
logs = [x for x in (run.get("log") or []) if isinstance(x, dict)]
nags = [x.get("nAg") for x in logs]
print("[pre_steps] " + json.dumps(r.get("pre_steps"), ensure_ascii=False)[:600])
print("[result] ok=%s reason=%s secs=%.0f model_used=%s sent=%s"
      % (r.get("ok"), run.get("reason"), time.time()-t0, r.get("model_used"), r.get("sent")))
print("[nAg 轨迹] %s" % nags[:16])
print("[status 轨迹] %s" % [x.get("status") for x in logs][:10])
print("[final] %s" % json.dumps(run.get("final"), ensure_ascii=False))
if r.get("err"):
    print("[err] %s" % r["err"][:200])
time.sleep(3)
print("[after]", json.dumps(prog(), ensure_ascii=False))
print("[created_title] %s" % (r.get("created_title") or ""))
cdp.close()
