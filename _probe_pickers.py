# -*- coding: utf-8 -*-
"""探活：模型选择器 + 模板（快捷动作）列表现在到底长什么样。

背景：account_g 跑 template_5 / Model_chat_GLM5.2 都「对话跑完但进度 +0」，
日志里有 `pickModel` 读 null 的报错 → 怀疑客户端改版、老选择器失效。

用法: python _probe_pickers.py
"""
import json
import sys
import time

sys.path.insert(0, r"D:/workbuddy/2026-09-19-00-30-03/buddy-auto")

import ui_driver as U       # noqa: E402

OPEN_HOME = "(async () => { await openNewTask(); await sleep(1200); return true; })()"

DUMP_MODEL = r"""
(() => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const out = {};
  const trig = document.querySelector('.cr-model-selector__trigger');
  out.trigger_found = !!trig;
  out.trigger_txt = trig ? T(trig).slice(0, 80) : null;
  // 找所有类名里带 model 的元素，看真实类名有没有变
  out.modelish = Array.from(document.querySelectorAll('*'))
    .filter(el => /model/i.test((el.className || '').toString()))
    .slice(0, 25)
    .map(el => el.tagName + '.' + (el.className || '').toString().slice(0, 70) + ' | ' + T(el).slice(0, 40));
  if (trig) {
    realClick(trig);
  }
  return out;
})()
"""

DUMP_MODEL_LIST = r"""
(() => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const out = {};
  const items = Array.from(document.querySelectorAll('.cr-model-selector__item'));
  out.n_items = items.length;
  out.items = items.slice(0, 30).map(el => ({
    cls: (el.className || '').toString().slice(0, 60),
    name: (el.querySelector('.cr-model-selector__item-name') || {}).innerText || null,
    txt: T(el).slice(0, 50)
  }));
  out.trigger_after = (() => {
    const t = document.querySelector('.cr-model-selector__trigger');
    return t ? T(t).slice(0, 60) : null;
  })();
  // 兜底：列出所有像下拉项的容器
  out.anyDropdown = Array.from(document.querySelectorAll('[class*=selector],[class*=dropdown],[class*=menu]'))
    .slice(0, 25)
    .map(el => el.tagName + '.' + (el.className || '').toString().slice(0, 70));
  return out;
})()
"""

DUMP_TEMPLATES = r"""
(() => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const out = {};
  const trig = document.querySelector('.cr-add-menu__trigger');
  out.addBtn_found = !!trig;
  if (trig) realClick(trig);
  return out;
})()
"""

DUMP_TEMPLATES2 = r"""
(() => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const out = {};
  const list = document.querySelector('.quick-actions__list') || document.querySelector('.quick-actions');
  out.list_found = !!list;
  out.items = Array.from(document.querySelectorAll('.quick-actions__item'))
    .map(b => ({ t: T(b).slice(0, 24), w: Math.round(b.getBoundingClientRect().width) }))
    .slice(0, 40);
  // 兜底：任何像「快捷动作 / 模板」的容器
  out.quickish = Array.from(document.querySelectorAll('[class*=quick-action],[class*=quick-actions],[class*=phrase]'))
    .slice(0, 25)
    .map(el => el.tagName + '.' + (el.className || '').toString().slice(0, 70) + ' | ' + T(el).slice(0, 30));
  return out;
})()
"""


def show(tag, js, gap=2):
    r = U.js(js, timeout=90)
    print("\n===== %s =====" % tag, flush=True)
    print(json.dumps(r, ensure_ascii=False, indent=1)[:3500], flush=True)
    time.sleep(gap)
    return r


print("进入首页：", U.js(OPEN_HOME, timeout=90), flush=True)
time.sleep(1)
show("模型选择器（点击前）", DUMP_MODEL)
show("模型下拉（点击后）", DUMP_MODEL_LIST, 1)
U.js("(() => { document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true})); return true; })()")
time.sleep(1)
show("模板 + 按钮", DUMP_TEMPLATES)
show("模板列表（点击后）", DUMP_TEMPLATES2, 1)
