#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按类名 dump automation-permission-confirm 整块。"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import ui_driver as U         # noqa: E402


def main():
    r = U.js("""(()=>{
      const vis = el => { const r = el.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
      const nodes = Array.from(document.querySelectorAll('[class*=automation-permission-confirm]'));
      const root = nodes.length ? nodes[0] : null;
      // 找最外层（向上找到 class 以 automation-permission-confirm 开头且父级不含该前缀）
      let box = root;
      while (box && box.parentElement &&
             /automation-permission-confirm/.test(box.parentElement.className || '')) box = box.parentElement;
      const out = {n:nodes.length, nodeClasses: nodes.map(e=>String(e.className).slice(0,80))};
      if (!box) return out;
      out.rootCls = String(box.className).slice(0, 120);
      const rect = b => { const r = b.getBoundingClientRect();
        return {x:Math.round(r.left+r.width/2), y:Math.round(r.top+r.height/2),
                w:Math.round(r.width), h:Math.round(r.height)}; };
      out.buttons = Array.from(box.querySelectorAll('button')).map(b=>({
        t:(b.innerText||'').replace(/\\s+/g,' ').trim().slice(0,30),
        cls:String(b.className).slice(0,80), dis:!!b.disabled, vis:vis(b), r:rect(b)}));
      out.checkboxes = Array.from(box.querySelectorAll('input[type=checkbox],[role=checkbox],[class*=checkbox]')).map(c=>({
        tag:c.tagName, cls:String(c.className).slice(0,80), checked:c.checked||null,
        aria:c.getAttribute('aria-checked'), dis:!!c.disabled, vis:vis(c), r:rect(c)}));
      out.texts = Array.from(box.querySelectorAll('button,a,span')).filter(vis)
        .filter(e=>e.children.length<=1 && (e.innerText||'').trim())
        .map(e=>({tag:e.tagName, cls:String(e.className).slice(0,70),
                  t:(e.innerText||'').replace(/\\s+/g,' ').trim().slice(0,45), r:rect(e)}));
      return out;
    })()""")
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
