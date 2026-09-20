#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分离校验：分别测「空表单」「只填名」「只填提示词」时点确定的结果。"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import ui_tasks as T          # noqa: E402
import ui_driver as U         # noqa: E402
import cdp as C               # noqa: E402

PROMPT = "用一句话总结今天值得关注的一条 AI 新闻。直接给结果。"


def step(tag, obj):
    print("[%s] %s" % (tag, json.dumps(obj, ensure_ascii=False)[:500]))
    sys.stdout.flush()


def esc():
    U.js("(async()=>{for(let i=0;i<3;i++)document.dispatchEvent("
         "new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));return 1;})()")
    time.sleep(1.2)


def dump_modal():
    return U.js("(()=>{const m=document.querySelector('.wb-modal');if(!m)return{modal:false};"
                "const errs=Array.from(m.querySelectorAll('[class*=error],[class*=invalid],[class*=help]'))"
                ".filter(e=>(e.innerText||'').trim()).map(e=>({c:String(e.className).slice(0,50),"
                "t:(e.innerText||'').replace(/\\s+/g,' ').trim().slice(0,80)}));"
                "return{modal:true,txt:(m.innerText||'').replace(/\\s+/g,' ').slice(0,300),errs:errs};})()")


def open_modal():
    esc()
    r = T._js_block(T.ATM_OPEN2, timeout=120)
    return r.get("opened")


def click_ok():
    r = U.mouse_click("Array.from(document.querySelectorAll('.wb-modal button'))"
                      ".find(b => (b.innerText||'').trim() === '确定')")
    time.sleep(3.0)
    return r


def set_name(v):
    return U.js("(async()=>{const m=document.querySelector('.wb-modal');"
                "const i=m.querySelector('input.atm-modal-input');if(!i)return{err:'no'};"
                "i.focus();const s=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;"
                "s.call(i,%s);i.dispatchEvent(new Event('input',{bubbles:true}));"
                "i.dispatchEvent(new Event('change',{bubbles:true}));return{v:i.value};})()" % json.dumps(v))


print("=== 1) 空表单点确定 ===")
if open_modal():
    step("initial", dump_modal())
    step("clickOk", click_ok())
    step("result", dump_modal())

print("\n=== 2) 只填名称点确定 ===")
if open_modal():
    step("setName", set_name("测试只填名"))
    step("clickOk", click_ok())
    step("result", dump_modal())

print("\n=== 3) 只填提示词点确定 ===")
if open_modal():
    step("typePrompt", T.type_into("document.querySelector('.wb-modal [contenteditable=true]')", PROMPT))
    step("clickOk", click_ok())
    step("result", dump_modal())

esc()
