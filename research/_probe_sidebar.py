#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""精确 dump 左侧边栏结构（每项的 class / 文本 / 层级），用于写可靠选择器。只读。"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import account_switch as AS   # noqa: E402
import ui_driver as U         # noqa: E402

JS = r"""
(async () => {
  const out = { items: [], tabs: [] };
  const vis = el => { const r = el.getBoundingClientRect(); return r.width > 10 && r.height > 8; };
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 40);

  // 侧边栏里的「可点」元素：带 tab-button / nav / item 类的，或有 role
  const sel = '.conversation-sidebar button, .conversation-sidebar [role=button], ' +
              '.conversation-sidebar a, .sidebar-next button, .sidebar-next [role=button], ' +
              '.sidebar-next a';
  document.querySelectorAll(sel).forEach(el => {
    if (!vis(el)) return;
    out.items.push({ txt: T(el), cls: el.className.toString().slice(0, 110),
                     tag: el.tagName.toLowerCase(),
                     parent: (el.parentElement ? el.parentElement.className.toString().slice(0, 60) : '') });
  });

  // 顶部 menubar（外观菜单在这里）
  document.querySelectorAll('.codebuddy-menubar, .menubar-menu-button, [class*=menubar]').forEach(el => {
    if (!vis(el)) return;
    out.tabs.push({ txt: T(el), cls: el.className.toString().slice(0, 100) });
  });
  return out;
})()
"""


def main():
    print(json.dumps(U.js(JS, timeout=60), ensure_ascii=False, indent=2)[:9000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
