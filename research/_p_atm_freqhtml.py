#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""打印 atm-frequency-popover 的 HTML 全文。"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import ui_driver as U         # noqa: E402

JS = r"""(()=>{
  const p = document.querySelector('.atm-frequency-popover');
  return p ? p.outerHTML : 'NO POPOVER';
})()"""

h = U.js(JS)
print((h or "")[:6000])
