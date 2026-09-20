# -*- coding: utf-8 -*-
"""读/设「输入框权限」（button.cr-permission-setting）—— 这是「AI 总要确认」的真凶。

背景（2026-09-19 查清，重要）：
  输入框左下角那个「默认权限 / 允许完全访问」是**按账号存的**。
  账号若是「默认权限」，任何要动工具/文件/命令的任务都会停下来等人确认
  → 会话在侧边栏被标成「待确认」→ UI 驱动器一直等它跑完 → **看着像卡死循环**。
  实测：account_e 的 3 条专家团会话全卡在「待确认」，进度 2/3 死活不动。

  打开它**不是点一下开关就行**，会再弹一个确认框：
    确认允许完全访问？ … [ ] 我已了解风险，并对自己的数据安全负责  [取消] [允许完全访问]
  必须①勾风险确认 ②点「允许完全访问」，权限才真正生效。
  （这也解释了用户说的「都要确认」。）

用法:
  python set_permission.py                     # 只读当前权限
  python set_permission.py full                # 设为「允许完全访问」
  python set_permission.py account_x full      # 先切号再设
"""
import json
import sys
import time

sys.path.insert(0, r"D:/workbuddy/2026-09-19-00-30-03/buddy-auto")

import account_switch as AS   # noqa: E402
import auto_buddy as core     # noqa: E402
import ui_driver as U         # noqa: E402

READ = r"""
(() => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const b = document.querySelector('button.cr-permission-setting');
  return { found: !!b, text: b ? T(b) : null };
})()
"""

OPEN_PANEL = r"""
(async () => {
  // 残留弹窗先关掉（切号/上次中断留下的）
  const ov = document.querySelector('.wb-modal__overlay');
  if (ov) {
    const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
    const cancel = Array.from(document.querySelectorAll('.wb-modal button'))
      .find(b => T(b) === '取消');
    if (cancel) { realClick(cancel); await sleep(900); }
  }
  if (document.querySelector('.cr-permission-panel')) return { ok: true, already: true };
  const b = document.querySelector('button.cr-permission-setting');
  if (!b) return { ok: false, err: '找不到权限按钮' };
  realClick(b);
  for (let i = 0; i < 10; i++) {
    await sleep(400);
    if (document.querySelector('.cr-permission-panel')) break;
  }
  return { ok: !!document.querySelector('.cr-permission-panel') };
})()
"""

SETTLE = r"""
(async () => {
  // 等界面稳定：切换账号后昵称/输入框是延迟重绘的，读早了会拿到上一个账号的状态
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  let prev = null, same = 0;
  for (let i = 0; i < 24; i++) {
    const nick = T(document.querySelector('.user-menu-trigger') || {});
    const chip = T(document.querySelector('button.cr-permission-setting') || {});
    const cur = nick + '|' + chip;
    if (cur === prev && nick && chip) same++; else same = 0;
    prev = cur;
    if (same >= 3) return { ok: true, nick: nick, chip: chip, waited: i };
    await sleep(500);
  }
  return { ok: false, last: prev };
})()
"""

CLICK_ROW = r"""
(async () => {
  const p = document.querySelector('.cr-permission-panel');
  if (!p) return { ok: false, err: '权限面板没打开' };
  const row = p.querySelector('.cr-permission-panel__row');
  if (!row) return { ok: false, err: '找不到权限行' };
  realClick(row);                       // 会弹「确认允许完全访问？」
  for (let i = 0; i < 20; i++) {
    await sleep(400);
    if (document.querySelector('.wb-modal__overlay')) break;
  }
  return { ok: true, modal: !!document.querySelector('.wb-modal__overlay') };
})()
"""

CONFIRM_FULL = r"""
(async () => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const modal = document.querySelector('.wb-modal');
  if (!modal) return { ok: false, err: '确认弹窗不在' };
  const box = modal.querySelector('input[type=checkbox]');
  const btns = Array.from(modal.querySelectorAll('button'));
  const go = btns.find(b => T(b) === '允许完全访问') || btns.find(b => T(b).indexOf('允许完全访问') !== -1);
  return { ok: true, checked: box ? box.checked : null,
           goDisabled: go ? !!go.disabled : null,
           labelFound: !!modal.querySelector('label.wb-checkbox'), modal: true };
})()
"""

VERIFY = r"""
(() => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const i = document.querySelector('.wb-modal input[type=checkbox]');
  const b = Array.from(document.querySelectorAll('.wb-modal button'))
    .find(x => T(x) === '允许完全访问');
  return { checked: i ? i.checked : null, goDisabled: b ? !!b.disabled : null };
})()
"""


def _js(code, timeout=90):
    try:
        return U.js(code, timeout=timeout)
    except Exception as e:
        return {"err": "%s: %s" % (type(e).__name__, e)}


def read_chip():
    return _js(READ, timeout=40)


# 弹窗里那两个必须走到位的点：
#   1) 勾选「我已了解风险…」—— checkbox 的真身是**隐藏** input.wb-checkbox__former，
#      JS 的 realClick(input) 点不到（合成事件点在隐藏元素上无效）→ 必须用
#      **真实鼠标**点可见的 `label.wb-checkbox`（实测 hitCls=wb-checkbox__label）。
#   2) 点「允许完全访问」—— 勾上之前它一直是 disabled，所以勾完必须**复查**再点。
LABEL_SEL = "document.querySelector('.wb-modal label.wb-checkbox')"
GO_SEL = ("Array.from(document.querySelectorAll('.wb-modal button'))"
          ".find(x => x.innerText.trim() === '允许完全访问')")


def set_full(verbose=True, tries=3):
    """把当前登录账号的输入框权限设为「允许完全访问」。返回 (ok, 说明)。"""
    last = ""
    for attempt in range(1, tries + 1):
        _js(SETTLE, timeout=90)          # 等界面稳定（切号后延迟重绘）
        cur = read_chip()
        if isinstance(cur, dict) and "完全访问" in (cur.get("text") or ""):
            return True, "本来就是完全访问"

        r1 = _js(OPEN_PANEL, timeout=60)
        time.sleep(0.8)
        r2 = _js(CLICK_ROW, timeout=90)
        time.sleep(1.0)
        st = _js(CONFIRM_FULL, timeout=60)

        if verbose:
            print("  第%d次: 面板=%s 弹窗=%s" % (attempt, json.dumps(r1, ensure_ascii=False)[:80],
                                              json.dumps(st, ensure_ascii=False)[:120]), flush=True)

        if isinstance(st, dict) and st.get("modal"):
            if not st.get("checked"):
                _js_strict_mouse(LABEL_SEL)
                time.sleep(0.9)
            v = _js(VERIFY, timeout=40)
            if isinstance(v, dict) and v.get("checked") and not v.get("goDisabled"):
                _js_strict_mouse(GO_SEL)
                time.sleep(1.8)
                after = read_chip()
                if isinstance(after, dict) and "完全访问" in (after.get("text") or ""):
                    return True, json.dumps(after, ensure_ascii=False)
                last = "点了「允许完全访问」但没生效: %s" % json.dumps(after, ensure_ascii=False)
            else:
                last = "风险确认没勾上: %s" % json.dumps(v, ensure_ascii=False)
        else:
            last = "没等到「确认允许完全访问」弹窗（面板=%s 弹窗=%s）" % (
                json.dumps(r1, ensure_ascii=False), json.dumps(r2, ensure_ascii=False))
        time.sleep(1.5)
    return False, last


def _js_strict_mouse(expr):
    """真实鼠标点（CDP Input.dispatchMouseEvent），返回落点是否真的命中。"""
    try:
        return U.mouse_click(expr, timeout=60)
    except Exception as e:
        return {"ok": False, "err": "%s: %s" % (type(e).__name__, e)}


def main():
    args = [a for a in sys.argv[1:]]
    acct = next((a for a in args if a.startswith("account_")), None)
    want = "full" in args

    if "all" in args:
        cfg = core.load_config()
        keys = [a["key"] for a in cfg["accounts"]]
        only = next((a for a in args if a.startswith("only=")), "")
        if only:
            want_keys = {x.strip() for x in only[5:].split(",") if x.strip()}
            keys = [k for k in keys if k in want_keys]
        print("共 %d 个账号" % len(keys), flush=True)
        done = []
        main_key, _main_menu = AS.current_key()   # 先记主号，结束后切回（勿硬编码 account_a）
        for k in keys:
            sw = AS.switch_to(k, reload=False, verify=True)
            if not sw.get("ok"):
                print("[%s] 切号失败，跳过" % k, flush=True)
                done.append((k, False, "切号失败"))
                continue
            time.sleep(1.5)
            ok, info = set_full(verbose=False)
            print("[%s] %s  %s" % (k, "OK" if ok else "FAIL", info), flush=True)
            done.append((k, ok, info))
        good = sum(1 for _, ok, _ in done if ok)
        print("\n---- 汇总：%d/%d 已是完全访问 ----" % (good, len(done)), flush=True)
        for k, ok, info in done:
            if not ok:
                print("  !! %s %s" % (k, info), flush=True)
        back = AS.switch_to(main_key or "account_a", reload=False, verify=True)
        print("切回主号 %s ok=%s" % (main_key or "account_a", back.get("ok")), flush=True)
        return 0

    if acct:
        r = AS.switch_to(acct, reload=False, verify=True)
        print("切号 %s ok=%s" % (acct, r.get("ok")), flush=True)
        time.sleep(2)

    print("当前: %s" % json.dumps(read_chip(), ensure_ascii=False), flush=True)
    if want:
        ok, info = set_full()
        print("%s: %s" % ("成功" if ok else "失败", info), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
