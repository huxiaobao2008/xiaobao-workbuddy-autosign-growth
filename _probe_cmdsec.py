# -*- coding: utf-8 -*-
"""看清「安全中心 → 命令安全」：询问名单 / 放行名单 现在有什么、怎么编辑。"""
import json
import sys
import time

sys.path.insert(0, r"D:/workbuddy/2026-09-19-00-30-03/buddy-auto")

import ui_driver as U      # noqa: E402
import ui_tasks as UT      # noqa: E402

OPEN = r"""
(async () => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const vis = el => { const r = el.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
  const m = document.querySelector('.settings-modal');
  if (!m) return { err: '设置没开' };
  const el = Array.from(m.querySelectorAll('button,[class*=card],[class*=item],li,div'))
    .filter(vis).filter(e => T(e).startsWith('命令安全'))
    .sort((a,b) => a.querySelectorAll('*').length - b.querySelectorAll('*').length)[0];
  if (!el) return { err: '找不到「命令安全」入口' };
  realClick(el);
  await sleep(2000);
  return { ok: true, cls: (el.className||'').toString().slice(0,70) };
})()
"""

DUMP = r"""
(() => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const m = document.querySelector('.settings-modal');
  const txt = T(m);
  const i = txt.indexOf('命令安全');
  const inputs = Array.from(m.querySelectorAll('input')).map(e => ({
      cls: (e.className||'').toString().slice(0,60), ph: e.placeholder||'',
      val: (e.value||'').slice(0,60) }));
  const btns = Array.from(m.querySelectorAll('button')).map(e => T(e))
      .filter(t => t && t.length <= 16);
  return JSON.stringify({
    around: txt.slice(Math.max(0, i), i + 1400),
    inputs: inputs.slice(0, 15),
    btnUniq: Array.from(new Set(btns)).slice(0, 30)
  }, null, 1);
})()
"""


def main():
    r = U.js(UT.OPEN_SETTINGS, timeout=90)
    if not (r or {}).get("ok"):
        r = U.js(UT.OPEN_SETTINGS, timeout=90)
    time.sleep(2.0)
    UT._js_block(UT.NAV_SETTINGS, "安全中心", timeout=90)
    time.sleep(2.0)
    print("[open] " + json.dumps(U.js(OPEN, timeout=90), ensure_ascii=False)[:300], flush=True)
    time.sleep(2.5)
    print(U.js(DUMP, timeout=60), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
