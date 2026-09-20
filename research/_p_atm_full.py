#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""automation_1 全流程诊断：开框 → 填名 → 填提示词 → 点确定 → 校验。"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import ui_tasks as T          # noqa: E402
import ui_driver as U         # noqa: E402
import cdp as C               # noqa: E402

NAME = "自动刷任务测试A"
PROMPT = "用一句话总结今天值得关注的一条 AI 新闻。直接给结果。"


def step(tag, obj):
    print("[%s] %s" % (tag, json.dumps(obj, ensure_ascii=False)[:400]))
    sys.stdout.flush()


def main():
    # 0. 先关掉可能残留的对话框
    U.js("(async()=>{for(let i=0;i<3;i++)document.dispatchEvent("
         "new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));return 1;})()")
    time.sleep(1.2)

    # 1. 打开对话框
    r = T._js_block(T.ATM_OPEN2, timeout=120)
    step("open2", r)
    if not r.get("opened"):
        return 1

    # 2. 填名字（原生 setter）
    r = U.js("(async()=>{const m=document.querySelector('.wb-modal');"
             "const i=m.querySelector('input.atm-modal-input');"
             "if(!i)return{err:'no input'};"
             "i.focus(); const s=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;"
             "s.call(i,%s); i.dispatchEvent(new Event('input',{bubbles:true}));"
             "i.dispatchEvent(new Event('change',{bubbles:true}));"
             "return {val:i.value};})()" % json.dumps(NAME))
    step("setName", r)

    # 3. 提示词：CDP 真键输入
    r = T.type_into("document.querySelector('.wb-modal [contenteditable=true]')", PROMPT)
    step("typePrompt", r)

    # 4. 状态
    r = T._js_block(T.ATM_STATE, timeout=60)
    step("state", r)

    # 5. 用 CDP 真鼠标点「确定」
    r = U.mouse_click("Array.from(document.querySelectorAll('.wb-modal button'))"
                      ".find(b => (b.innerText||'').trim() === '确定')")
    step("mouseOK", r)
    time.sleep(3.5)

    # 6. 检查模态是否关闭
    r = U.js("(()=>({modal:!!document.querySelector('.wb-modal'),"
             "toasts:Array.from(document.querySelectorAll('[class*=toast],[class*=wb-message]'))"
             ".filter(e=>(e.innerText||'').trim()).map(e=>(e.innerText||'').replace(/\\s+/g,' ').slice(0,120))}))()")
    step("afterClick", r)

    # 7. 列表
    r = T._js_block(T.ATM_LIST, timeout=120)
    step("list", {"has": NAME in (r.get("txt") or ""), "txt": (r.get("txt") or "")[:400]})
    return 0


if __name__ == "__main__":
    sys.exit(main())
