#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试：点「改为「默认权限」运行 →」后是否直接提交成功。"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import ui_driver as U         # noqa: E402

FALLBACK = "document.querySelector('.automation-permission-confirm__fallback-link')"


def main():
    print("before:", json.dumps(U.js("(()=>({confirm:!!document.querySelector('.automation-permission-confirm__dialog'),"
                                     "editor:!!document.querySelector('.automation-editor-modal')}))()"),
                               ensure_ascii=False))
    r = U.mouse_click(FALLBACK)
    print("clickFallback:", json.dumps(r, ensure_ascii=False))
    for i in range(6):
        time.sleep(1.0)
        st = U.js("(()=>({confirm:!!document.querySelector('.automation-permission-confirm__dialog'),"
                  "editor:!!document.querySelector('.automation-editor-modal'),"
                  "toasts:Array.from(document.querySelectorAll('[class*=toast],[class*=wb-message]'))"
                  ".filter(e=>(e.innerText||'').trim()).map(e=>(e.innerText||'').replace(/\\s+/g,' ').slice(0,90))}))()")
        print("t+%ds %s" % (i + 1, json.dumps(st, ensure_ascii=False)))
        if not st.get("editor") and not st.get("confirm"):
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
