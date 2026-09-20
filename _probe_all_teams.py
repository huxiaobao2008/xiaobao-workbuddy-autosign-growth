# 只读探测：枚举「专家团」tab 下的**全部**团队（等渲染 + 滚动到底 + 每个分类 tab）。
# 不召唤、不发消息、不花积分。
import sys, json, time
sys.path.insert(0, r"D:\workbuddy\2026-09-19-00-30-03\buddy-auto")
from cdp import connect, unhide
import ui_driver as U
import ui_tasks as UT

cdp, page = connect()
unhide(cdp)
print("[ok] page=", (page.get("url") or "")[:50])

print("[enter]", json.dumps(U.js(UT.EXPERT_ENTER_STEP, timeout=120), ensure_ascii=False)[:100])
# 等专家中心真正挂载（EXPERT_ENTER_STEP 点了按钮就返回，不等挂载）
WAIT_EC = r"""
(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  for (let round = 0; round < 3; round++) {
    for (let i = 0; i < 30; i++) {
      if (document.querySelector('.ec-list-tab')) return { ok: true, round: round, waited: i * 0.5 };
      await sleep(500);
    }
    // 还没挂载 → 再点一次侧栏入口
    const btn = Array.from(document.querySelectorAll('button.conversation-list-tab-button'))
      .find(b => (b.innerText || '').indexOf('专家') !== -1);
    if (btn) { const r = btn.getBoundingClientRect();
      btn.dispatchEvent(new MouseEvent('click', {bubbles:true, clientX:r.x+r.width/2, clientY:r.y+r.height/2})); }
    await sleep(1500);
  }
  return { ok: false, err: '专家中心未挂载' };
})()
"""
print("[wait ec]", json.dumps(U.js(WAIT_EC, timeout=120), ensure_ascii=False)[:120])
pick = UT._as_fn(UT.EXPERT_PICK_STEP)
print("[pick]", json.dumps(U.js("(async () => { const f = %s; return await f('team', null, 0); })()" % pick, timeout=90), ensure_ascii=False)[:100])

SCAN_ONE_CAT = r"""
(async (catName) => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  // 切换到指定分类（catName 为 null 表示当前）
  if (catName) {
    const tab = Array.from(document.querySelectorAll('.ec-category-tab')).find(x => T(x) === catName);
    if (tab) { const r = tab.getBoundingClientRect();
      tab.dispatchEvent(new MouseEvent('click', {bubbles:true, clientX:r.x+r.width/2, clientY:r.y+r.height/2})); }
    await sleep(1500);
  }
  let firstCard = null;
  for (let i = 0; i < 40; i++) {
    firstCard = document.querySelector('.ec-expert-card');
    if (firstCard) break;
    await sleep(500);
  }
  if (!firstCard) return { err: '卡片列表为空' };
  await sleep(1200);
  const cats = Array.from(document.querySelectorAll('.ec-category-tab')).map(T);
  let sc = firstCard.parentElement;
  while (sc && sc !== document.body) {
    const st = getComputedStyle(sc);
    if ((st.overflowY === 'auto' || st.overflowY === 'scroll') && sc.scrollHeight > sc.clientHeight + 20) break;
    sc = sc.parentElement;
  }
  const info = { cats: cats, scrollerCls: sc ? (sc.className || '').toString().slice(0, 50) : null,
                 scrollH: sc ? sc.scrollHeight : 0, clientH: sc ? sc.clientHeight : 0,
                 scrollable: !!(sc && sc.scrollHeight > sc.clientHeight + 20) };
  const seen = new Set(); const names = [];
  const collect = () => {
    Array.from(document.querySelectorAll('.ec-expert-card')).forEach(c => {
      const n = T(c).replace(/^召唤\s*/, '').split(' ')[0].slice(0, 24);
      if (n && !seen.has(n)) { seen.add(n); names.push(n); }
    });
  };
  collect();
  if (sc && sc.scrollHeight > sc.clientHeight + 20) {
    const step = Math.max(120, Math.floor(sc.clientHeight * 0.8));
    let guard = 0;
    for (let y = 0; y <= sc.scrollHeight + step && guard < 60; y += step) {
      sc.scrollTop = y; await sleep(450); collect(); guard++;
      if (sc.scrollTop + sc.clientHeight >= sc.scrollHeight - 5) break;
    }
    sc.scrollTop = 0; await sleep(300);
  }
  info.total = names.length; info.names = names;
  return info;
})()
"""

# 先扫「全部」类（等卡片渲染出来，分类 tab 才会一起出现）
all_names = []
seen_cats = []
scan_fn = UT._as_fn(SCAN_ONE_CAT)      # 去掉尾部 () —— 否则 f 是 Promise 不是函数

def scan_cat(c):
    r = U.js("(async (c) => { const f = %s; return await f(c); })(%s)" % (scan_fn, json.dumps(c)),
             timeout=200)
    if isinstance(r, dict) and r.get("names"):
        print("[cat %s] total=%d scrollable=%s cats=%s" % (c, r.get("total"), r.get("scrollable"),
                                                          json.dumps(r.get("cats"), ensure_ascii=False)))
        for n in r["names"]:
            print("    -", n)
            if n not in all_names:
                all_names.append(n)
        for x in (r.get("cats") or []):
            if x and x not in seen_cats:
                seen_cats.append(x)
    else:
        print("[cat %s] %s" % (c, json.dumps(r, ensure_ascii=False)[:200]))

scan_cat("全部")
# 「全部」扫完后再看有哪些分类（此时 tab 已渲染）
cats = [c for c in (U.js("(() => Array.from(document.querySelectorAll('.ec-category-tab')).map(x=>(x.innerText||'').trim()))()", timeout=30) or []) if c]
print("[cats 完整]", json.dumps(cats, ensure_ascii=False))
for c in cats:
    if c == "全部":
        continue
    scan_cat(c)
    time.sleep(1)

print("\n=== 全部去重后共 %d 个专家团 ===" % len(all_names))
print(json.dumps(all_names, ensure_ascii=False))
cdp.close()
