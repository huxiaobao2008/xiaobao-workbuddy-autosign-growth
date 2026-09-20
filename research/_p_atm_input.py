#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Slate 提示词输入法对比：找出能真正写进 Slate 状态的方式。"""
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
ED_SEL = "document.querySelector('.wb-modal [contenteditable=true]')"


def step(tag, obj):
    print("[%s] %s" % (tag, json.dumps(obj, ensure_ascii=False)[:400]))
    sys.stdout.flush()


def esc():
    U.js("(async()=>{for(let i=0;i<3;i++)document.dispatchEvent("
         "new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));return 1;})()")
    time.sleep(1.2)


def open_modal():
    esc()
    return T._js_block(T.ATM_OPEN2, timeout=120).get("opened")


def errs():
    return U.js("(()=>{const m=document.querySelector('.wb-modal');if(!m)return{modal:false};"
                "const e=Array.from(m.querySelectorAll('[class*=automation-workspace__error]'))"
                ".filter(x=>(x.innerText||'').trim()).map(x=>(x.innerText||'').replace(/\\s+/g,' ').trim().slice(0,80));"
                "const ed=m.querySelector('[contenteditable=true]');"
                "return{modal:true,errs:e,"
                "slateHtml:(ed?ed.innerHTML:'').replace(/\\s+/g,' ').slice(0,200),"
                "text:ed?(ed.innerText||'').replace(/\\s+/g,' ').trim().slice(0,50):null};})()")


def setName(v):
    return U.js("(async()=>{const m=document.querySelector('.wb-modal');const i=m.querySelector('input.atm-modal-input');"
                "i.focus();const s=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;"
                "s.call(i,%s);i.dispatchEvent(new Event('input',{bubbles:true}));"
                "i.dispatchEvent(new Event('change',{bubbles:true}));return{v:i.value};})()" % json.dumps(v))


def click_ok():
    U.mouse_click("Array.from(document.querySelectorAll('.wb-modal button'))"
                  ".find(b => (b.innerText||'').trim() === '确定')")
    time.sleep(2.5)


def cdp_click_editor():
    U.mouse_click(ED_SEL)
    time.sleep(0.4)


def method_insert_text():
    cdp, _ = C.connect()
    try:
        cdp.call("Input.insertText", {"text": PROMPT}, timeout=20)
    finally:
        cdp.close()
    time.sleep(0.8)


def method_exec_command():
    return U.js("(async()=>{const ed=%s; ed.focus();"
                "const ok=document.execCommand('insertText',false,%s);"
                "await sleep(600);"
                "return{exec:ok,text:(ed.innerText||'').replace(/\\s+/g,' ').slice(0,60)};})()"
                % (ED_SEL, json.dumps(PROMPT)))


def method_key_events():
    cdp, _ = C.connect()
    try:
        cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "windowsVirtualKeyCode": 229,
                                            "key": "Process"}, timeout=15)
        for ch in PROMPT:
            cdp.call("Input.dispatchKeyEvent", {"type": "char", "text": ch,
                                                "unmodifiedText": ch}, timeout=15)
        cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", "windowsVirtualKeyCode": 229,
                                            "key": "Process"}, timeout=15)
    finally:
        cdp.close()
    time.sleep(1.0)


def trial(label, fn):
    print("\n===== %s =====" % label)
    if not open_modal():
        step("open", {"err": "fail"})
        return
    setName("测试_" + label)
    cdp_click_editor()
    r = fn()
    if r:
        step("fn", r)
    step("before_ok", errs())
    click_ok()
    step("after_ok", errs())


trial("A_insertText_after_click", method_insert_text)
trial("B_execCommand", method_exec_command)
trial("C_keyEvents", method_key_events)
esc()
