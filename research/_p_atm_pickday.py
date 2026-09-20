#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在日历里选未来日期（默认 30 号），然后回读日程。"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import ui_driver as U         # noqa: E402

DAY = sys.argv[1] if len(sys.argv) > 1 else "30"

CELL = ("Array.from(document.querySelectorAll('.wb-datepicker-grid__cell'))"
        ".filter(c => !/other-month|disabled|selected/.test(c.className) "
        "&& (c.innerText||'').trim() === %s)[0]" % json.dumps(DAY))


def main():
    print("panelOpen:", U.js("(()=>!!document.querySelector('.wb-datepicker-panel-container'))()"))
    print("cellFound:", U.js("(()=>{const c=%s;return c?{t:c.innerText,cls:c.className.slice(0,70)}:'none';})()" % CELL))
    r = U.mouse_click(CELL)
    print("clickDay:", json.dumps(r, ensure_ascii=False))
    time.sleep(1.2)
    print(json.dumps(U.js(r"""(()=>({
      date: (document.querySelector('.atm-schedule-date-input input')||{}).value,
      time: (document.querySelector('.atm-schedule-time-input input')||{}).value,
      freq: (document.querySelector('.atm-frequency-select .wb-select__value')||{}).innerText,
      trigger: (document.querySelector('.automation-editor-modal .atm-schedule-trigger')||{}).innerText,
      errs: Array.from(document.querySelectorAll('.automation-workspace__error')).map(e=>(e.innerText||'').replace(/\s+/g,' ').trim()),
      popoverOpen: !!document.querySelector('.atm-frequency-popover'),
      datePanelOpen: !!document.querySelector('.wb-datepicker-panel-container')
    }))()"""), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
