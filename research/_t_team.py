# -*- coding: utf-8 -*-
"""测试专家团：召唤 -> 发消息 -> 长等 -> 看对话内容与进度（默认不删）。"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ui_driver as U  # noqa: E402
import ui_tasks as T   # noqa: E402

if __name__ == "__main__":
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    prompt = sys.argv[2] if len(sys.argv) > 2 else "请用一句话说明你们团队的分工。"
    wait_s = int(sys.argv[3]) if len(sys.argv) > 3 else 90

    before = U.stable_task_titles()
    print("before:", json.dumps(before, ensure_ascii=False))

    pre = ("(async () => { const f = %s; return await f('team', null, %d); })()"
           % (T.EXPERT_PRE, idx))
    print("== summon ==")
    s = U.js(pre, timeout=150)
    print(json.dumps(s, ensure_ascii=False, indent=2))
    if not (isinstance(s, dict) and s.get("ok")):
        sys.exit(1)

    print("== type ==")
    print(json.dumps(U.type_text(prompt), ensure_ascii=False))
    print("== send ==")
    print(json.dumps(U.js("(async () => { const s = send(); return s; })()", timeout=40),
                     ensure_ascii=False))

    for i in range(wait_s // 10):
        time.sleep(10)
        st = U.js("(() => { const v=document.querySelector('.cr-message-list-viewport');"
                  " const ags = v?Array.from(v.querySelectorAll('.cr-agent')):[];"
                  " return { t:%d, view:!!v, nAg:ags.length,"
                  "  proc: v?!!v.querySelector('.cr-agent--processing'):false,"
                  "  len: v?(v.innerText||'').length:0,"
                  "  tail: v?(v.innerText||'').replace(/\\s+/g,' ').slice(-260):null }; })()"
                  % ((i + 1) * 10))
        print(json.dumps(st, ensure_ascii=False))

    after = U.stable_task_titles()
    new = [t for t in after if t not in set(before)]
    print("new_titles:", json.dumps(new, ensure_ascii=False))
