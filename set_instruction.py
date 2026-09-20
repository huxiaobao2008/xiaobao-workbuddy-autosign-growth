# -*- coding: utf-8 -*-
"""设置「个性化 → 自定义指令」（对所有任务生效的全局规则）。

保存机制（已从 React props 读出）：
  textarea.personalization-panel__textarea
    onChange -> setCustomPrompt(value)      （受控组件，必须走原生 setter + input 事件）
    onBlur   -> savePersonalizationValues(toneStyle, customPrompt)   ← **失焦才保存**

用法:
  python set_instruction.py                 # 只读当前内容
  python set_instruction.py "<要写入的文本>"  # 写入并失焦保存，再回读校验
"""
import json
import sys
import time

sys.path.insert(0, r"D:/workbuddy/2026-09-19-00-30-03/buddy-auto")

import ui_driver as U      # noqa: E402
import ui_tasks as UT      # noqa: E402

DEFAULT_TEXT = ("执行任务时请直接完成并给出最终结果：不要向我提问、不要请求我确认、"
                "不要等我回复，也不要把任务挂起等待确认；信息不全时自行做合理假设并继续完成。")

READ = r"""
(() => {
  const t = document.querySelector('.personalization-panel__textarea');
  return JSON.stringify({ found: !!t, len: t ? (t.value || '').length : -1,
                          val: t ? (t.value || '') : null }, null, 1);
})()
"""

WRITE = r"""
(async () => {
  const val = __VAL__;
  const t = document.querySelector('.personalization-panel__textarea');
  if (!t) return { err: '找不到自定义指令输入框' };
  t.focus();
  const set = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
  set.call(t, val);
  t.dispatchEvent(new Event('input', { bubbles: true }));
  t.dispatchEvent(new Event('change', { bubbles: true }));
  await sleep(600);
  const afterType = t.value;
  // 失焦保存（onBlur -> savePersonalizationValues）
  t.blur();
  // 再点一下面板空白处，确保 React 收到 blur（elementFromPoint 可能返回 null，要判空）
  const panel = document.querySelector('[class*=personalization-panel]');
  if (panel) {
    const r = panel.getBoundingClientRect();
    const pt = document.elementFromPoint(r.left + 5, r.top + 5);
    if (pt && pt.dispatchEvent) {
      pt.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
    }
  }
  await sleep(1400);
  return { typed: afterType, len: (afterType || '').length };
})()
"""


def main():
    # 参数：无 = 只读；"-" = 写入脚本内置的默认文案（推荐，避开 bash 传中文被吃字符）；
    # 其它 = 当作要写入的文本
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    text = DEFAULT_TEXT if arg == "-" else arg

    r = U.js(UT.OPEN_SETTINGS, timeout=90)
    if not (r or {}).get("ok"):
        U.js(UT.OPEN_SETTINGS, timeout=90)
    time.sleep(2.0)
    UT._js_block(UT.NAV_SETTINGS, "个性化", timeout=90)
    time.sleep(1.8)
    print("[before] " + U.js(READ, timeout=60), flush=True)

    if text:
        out = U.js(WRITE.replace("__VAL__", json.dumps(text)), timeout=90)
        print("[write] " + json.dumps(out, ensure_ascii=False)[:300], flush=True)
        time.sleep(0.8)
        print("[after] " + U.js(READ, timeout=60), flush=True)

        # 关掉设置再打开，确认真的落盘（而不是只在内存里）
        U.js(UT.CLOSE_SETTINGS, timeout=60)
        time.sleep(1.5)
        U.js(UT.OPEN_SETTINGS, timeout=90)
        time.sleep(1.5)
        UT._js_block(UT.NAV_SETTINGS, "个性化", timeout=90)
        time.sleep(1.8)
        print("[reopen] " + U.js(READ, timeout=60), flush=True)

    U.js(UT.CLOSE_SETTINGS, timeout=60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
