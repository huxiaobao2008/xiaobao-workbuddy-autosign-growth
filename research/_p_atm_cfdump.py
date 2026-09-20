#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dump「完全访问」二次确认框的按钮与复选框。"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import ui_driver as U         # noqa: E402


def main():
    r = U.js("""(()=>{
      const vis = el => { const r = el.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
      const hits = Array.from(document.querySelectorAll('div,section,article,form')).filter(vis)
        .filter(e => (e.innerText||'').indexOf('完全访问权限运行') >= 0
                  || (e.innerText||'').indexOf('愿意为该任务的执行结果负责') >= 0)
        .sort((a,b)=>a.querySelectorAll('*').length-b.querySelectorAll('*').length);
      const box = hits[0];
      const out = {found: !!box};
      if (!box) return out;
      out.cls = String(box.className).slice(0, 120);
      out.tag = box.tagName;
      out.buttons = Array.from(box.querySelectorAll('button')).map(b => {
        const r = b.getBoundingClientRect();
        return {t:(b.innerText||'').replace(/\\s+/g,' ').trim().slice(0,30),
                cls:String(b.className).slice(0,70),
                dis:!!b.disabled,
                x:Math.round(r.left+r.width/2), y:Math.round(r.top+r.height/2)};
      });
      out.checkboxes = Array.from(box.querySelectorAll('input[type=checkbox],[role=checkbox]')).map(c => {
        const r = c.getBoundingClientRect();
        return {tag:c.tagName, cls:String(c.className).slice(0,70),
                checked:c.checked, aria:c.getAttribute('aria-checked'),
                dis:!!c.disabled,
                x:Math.round(r.left+r.width/2), y:Math.round(r.top+r.height/2)};
      });
      out.clickable = Array.from(box.querySelectorAll('a,span,div,button')).filter(vis)
        .filter(e=>e.children.length<=2 && /改为|默认权限|取消|确认创建|我已了解/.test(e.innerText||''))
        .map(e=>{const r=e.getBoundingClientRect();
          return {tag:e.tagName, cls:String(e.className).slice(0,70),
                  t:(e.innerText||'').replace(/\\s+/g,' ').trim().slice(0,40),
                  x:Math.round(r.left+r.width/2), y:Math.round(r.top+r.height/2)};});
      return out;
    })()""")
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
