#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""侦察：当前页 URL 结构 + 可点击的导航/入口清单。只读。"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ui_driver as U   # noqa: E402

JS = r"""
(async () => {
  const out = { href: location.href, hash: location.hash, search: location.search.slice(0,400) };
  const uniq = (a) => Array.from(new Set(a));
  const vis = el => { const r = el.getBoundingClientRect(); return r.width > 20 && r.height > 12; };

  // 所有可见 button / [role=button] / a 的文本
  const labels = [];
  document.querySelectorAll('button, [role=button], a, [class*=tab], [class*=nav-item]').forEach(el => {
    if (!vis(el)) return;
    const t = (el.innerText || el.getAttribute('aria-label') || el.getAttribute('title') || '')
      .replace(/\s+/g, ' ').trim();
    if (t && t.length <= 24) labels.push(t);
  });
  out.labels = uniq(labels).slice(0, 140);

  // 侧边栏一级入口
  out.sidebar = Array.from(document.querySelectorAll('.conversation-sidebar *'))
    .filter(el => vis(el) && el.children.length === 0 && (el.innerText||'').trim())
    .map(el => (el.innerText||'').replace(/\s+/g,' ').trim())
    .filter(t => t.length <= 20);

  // 常见的容器/标志类
  const marks = ['cr-','wb-','quick-actions','conversation-sidebar','user-menu-trigger'];
  out.classes = {};
  const all = new Set();
  document.querySelectorAll('*').forEach(el => {
    const c = el.className && el.className.toString();
    if (!c) return;
    c.split(/\s+/).forEach(x => { if (x) all.add(x); });
  });
  out.classCount = all.size;
  out.sample = Array.from(all).filter(c => /nav|menu|entry|sidebar|route|home|expert|skill|library|playbook|automation|appear|buddy|canvas/i.test(c)).slice(0, 120);
  return out;
})()
"""


def main():
    print(json.dumps(U.js(JS, timeout=60), ensure_ascii=False, indent=2)[:6000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
