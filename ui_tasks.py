#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
成长任务驱动器（补充版）：处理不在「对话」里的那几类任务。

已有 `ui_driver.py` 负责「新建任务 → 选模板/模型 → 发消息」这条主线。
本文件负责其余界面：设置/外观、发现应用、定时任务、专家中心、技能、资料库、灵感。

约定：每个函数 = 一个任务的一整套动作，返回结构化结果；调用方负责切换账号与领取。

用法（单跑，便于调试）：
    python ui_tasks.py theme 和平精英激战金秋
    python ui_tasks.py settings-txt 外观
    python ui_tasks.py who-theme
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ui_driver as U   # noqa: E402
import cdp as C         # noqa: E402

# --------------------------------------------------------------------------- #
# 通用：设置面板
# --------------------------------------------------------------------------- #
OPEN_SETTINGS = r"""
(async () => {
  const out = { steps: [] };
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const vis = el => { const r = el.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
  // 已经开着就直接用
  if (document.querySelector('.settings-modal')) { out.already = true; return out; }
  // 点侧边栏用户菜单 -> 设置
  const trig = document.querySelector('.user-menu-trigger');
  if (!trig) return { err: '找不到 .user-menu-trigger' };
  realClick(trig);
  await sleep(1500);
  const st = Array.from(document.querySelectorAll('.user-menu-item')).find(el => T(el) === '设置');
  if (!st) return { err: '用户菜单里没有「设置」' };
  realClick(st);
  await sleep(2500);
  out.ok = !!document.querySelector('.settings-modal');
  return out;
})()
"""

NAV_SETTINGS = r"""
(async (name) => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const vis = el => { const r = el.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
  const m = document.querySelector('.settings-modal');
  if (!m) return { err: '设置面板没打开' };
  const el = Array.from(m.querySelectorAll('button, [class*=nav], [class*=item], li, div'))
    .filter(vis).filter(e => T(e) === name)
    .sort((a, b) => a.querySelectorAll('*').length - b.querySelectorAll('*').length)[0];
  if (!el) return { err: '设置里没有导航项 ' + name };
  realClick(el);
  await sleep(2000);
  return { ok: true, page: (m.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 300) };
})
"""

CLOSE_SETTINGS = r"""
(async () => {
  // 优先点关闭按钮；Escape 在别的场景会误关别的模态，只做兜底
  const b = document.querySelector('.settings-modal__close');
  if (b) { realClick(b); await sleep(1000); }
  if (document.querySelector('.settings-modal')) {
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    await sleep(900);
  }
  return { closed: !document.querySelector('.settings-modal') };
})
"""

# 外观页：主题卡片清单 + 当前选中项
READ_THEMES = r"""
(() => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const out = { cards: [], current: null };
  document.querySelectorAll('.appearance-card-cell').forEach(cell => {
    const btn = cell.querySelector('button.appearance-card');
    const nm = cell.querySelector('.appearance-card__name');
    const name = nm ? T(nm) : T(cell);
    if (!name) return;
    const sel = !!btn && /--selected/.test(btn.className.toString());
    if (sel) out.current = name;
    out.cards.push({ name: name, selected: sel,
                     cls: btn ? btn.className.toString().slice(0, 90) : '' });
  });
  return out;
})()
"""

PICK_THEME = r"""
(async (name) => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const cell = Array.from(document.querySelectorAll('.appearance-card-cell'))
    .find(c => { const nm = c.querySelector('.appearance-card__name'); return nm && T(nm) === name; });
  if (!cell) return { err: '外观页找不到主题 ' + name,
                      have: Array.from(document.querySelectorAll('.appearance-card__name')).map(T) };
  const btn = cell.querySelector('button.appearance-card');
  if (!btn) return { err: '主题卡片没有可点按钮' };
  if (/--selected/.test(btn.className.toString())) return { ok: true, already: true };
  realClick(btn);
  await sleep(2500);
  return { ok: true, after: btn.className.toString().slice(0, 90) };
})
"""


# --------------------------------------------------------------------------- #
# 页面内通用的 JS 小工具（每次调用随 IIFE 注入，互不污染）
# --------------------------------------------------------------------------- #
HELPERS = r"""
function wbVis(el) { const r = el.getBoundingClientRect(); return r.width > 8 && r.height > 8; }
function wbT(el) { return (el.innerText || '').replace(/\s+/g, ' ').trim(); }
function wbNorm(s) { return (s || '').replace(/\s+/g, ''); }
function clickSidebar(t) {
  const b = Array.from(document.querySelectorAll('.conversation-list-tab-button'))
    .find(e => wbNorm(wbT(e)) === wbNorm(t));
  if (!b) return null;
  realClick(b);
  return wbT(b);
}
function closeOverlays(n) {
  for (let i = 0; i < (n || 3); i++)
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
}
function findBtn(scope, text) {
  return Array.from((scope || document).querySelectorAll('button')).filter(wbVis)
    .find(b => wbT(b) === text || wbT(b).indexOf(text) !== -1) || null;
}
/* 给受控 <input> 赋值：必须走原生 setter + input 事件，直接改 .value 不触发 React */
function setReactInput(el, val) {
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
  setter.call(el, val);
  el.dispatchEvent(new Event('input', { bubbles: true }));
  el.dispatchEvent(new Event('change', { bubbles: true }));
}
"""

# --------------------------------------------------------------------------- #
# 定时任务（automation_1）
# --------------------------------------------------------------------------- #
ATM_OPEN = r"""
(async (name, inspectOnly) => {
  closeOverlays(3);
  await sleep(600);
  clickSidebar('定时任务');
  await sleep(2500);
  const add = findBtn(document, '添加定时任务');
  if (!add) return { err: '没有「添加定时任务」按钮' };
  realClick(add);
  await sleep(2800);
  const modal = document.querySelector('.wb-modal');
  if (!modal) return { err: '添加对话框没打开' };
  const out = { opened: true };
  const input = modal.querySelector('input.atm-modal-input');
  if (input) { setReactInput(input, name); out.nameSet = input.value; }
  const ed = modal.querySelector('[contenteditable=true]');
  if (ed) { realClick(ed); out.editable = true; }
  out.freqText = (modal.querySelector('.atm-schedule-trigger') || {}).innerText || null;
  if (inspectOnly) {
    const trig = modal.querySelector('.atm-schedule-trigger');
    if (trig) {
      realClick(trig); await sleep(1800);
      const pops = Array.from(document.querySelectorAll('[class*=popover], [class*=dropdown], [class*=select]')).filter(wbVis);
      out.freqOptions = pops.map(p => wbT(p).slice(0, 300));
      closeOverlays(2); await sleep(700);
      const cancel = findBtn(modal, '取消');
      if (cancel) realClick(cancel);
      await sleep(800);
    }
  }
  return out;
})
"""

ATM_OPEN2 = r"""
(async () => {
  closeOverlays(3);
  await sleep(600);
  // 已经在定时任务页就别再点（重复点会切回新建任务页）
  if (!document.querySelector('.automation-main-page')) {
    clickSidebar('定时任务');
    await sleep(2500);
  }
  let add = null;
  for (let i = 0; i < 12 && !add; i++) {
    add = findBtn(document, '添加定时任务');
    if (!add) await sleep(700);
  }
  if (!add) return { err: '没有「添加定时任务」按钮',
                     onPage: !!document.querySelector('.automation-main-page'),
                     visible: Array.from(document.querySelectorAll('button')).filter(wbVis)
                       .map(b => wbT(b)).filter(Boolean).slice(0, 25) };
  realClick(add);
  await sleep(2800);
  const modal = document.querySelector('.wb-modal');
  if (!modal) return { err: '添加对话框没打开' };
  const input = modal.querySelector('input.atm-modal-input');
  if (input) { realClick(input); }
  const okBtn = findBtn(modal, '确定');
  return { opened: true, focusedName: !!input,
           okDisabled: okBtn ? !!okBtn.disabled : null,
           freqText: wbT(modal.querySelector('.atm-schedule-trigger') || modal).slice(0, 60) };
})
"""

ATM_FOCUS_PROMPT = r"""
(async () => {
  const modal = document.querySelector('.wb-modal');
  if (!modal) return { err: '对话框不见了' };
  const ed = modal.querySelector('[contenteditable=true]');
  if (!ed) return { err: '找不到提示词输入区' };
  realClick(ed);
  await sleep(400);
  return { ok: true, focused: document.activeElement === ed || ed.contains(document.activeElement) };
})
"""

ATM_STATE = r"""
(() => {
  const modal = document.querySelector('.wb-modal');
  if (!modal) return { modal: false };
  const input = modal.querySelector('input.atm-modal-input');
  const ed = modal.querySelector('[contenteditable=true]');
  const okBtn = findBtn(modal, '确定');
  return { modal: true,
           name: input ? input.value : null,
           prompt: ed ? (ed.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 80) : null,
           okDisabled: okBtn ? !!okBtn.disabled : null,
           okCls: okBtn ? okBtn.className.toString().slice(0, 80) : null };
})
"""

ATM_LIST = r"""
(async () => {
  await sleep(300);
  if (!document.querySelector('.automation-main-page')) {
    clickSidebar('定时任务');
    await sleep(3000);
  }
  const page = document.querySelector('.automation-main-page');
  return { txt: page ? page.innerText.replace(/\s+/g, ' ').slice(0, 1000) : null };
})
"""

ATM_ERRORS = r"""
(() => {
  const m = document.querySelector('.automation-editor-modal');
  if (!m) return { modal: false };
  const ed = m.querySelector('[contenteditable=true]');
  return { modal: true,
           errs: Array.from(document.querySelectorAll('.automation-workspace__error'))
                   .filter(x => wbT(x)).map(x => wbT(x).slice(0, 100)),
           freq: Array.from(m.querySelectorAll('.atm-schedule-trigger')).map(e => wbT(e)),
           perm: (Array.from(m.querySelectorAll('button'))
                    .filter(b => /完全访问|默认权限/.test(b.innerText || ''))[0] || {}).innerText || null,
           slateText: ed ? (ed.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 60) : null };
})
"""

# 执行频率浮层：把「单次」的日期改到未来（当月最后一个可选日，或下月 1 号）
ATM_PICK_FUTURE = r"""
(async () => {
  const vis = c => { const r = c.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
  let cells = Array.from(document.querySelectorAll('.wb-datepicker-grid__cell'))
    .filter(vis).filter(c => !/other-month|disabled/.test(c.className.toString()));
  if (!cells.length) {
    // 当月没有可选日期 → 翻到下个月
    const nextBtn = document.querySelector(
      '.wb-datepicker-header__btn--next, [class*=datepicker-header] [class*=next], ' +
      '.wb-datepicker-header__title-btn--next');
    if (nextBtn) { realClick(nextBtn); await sleep(1200); }
    cells = Array.from(document.querySelectorAll('.wb-datepicker-grid__cell'))
      .filter(vis).filter(c => !/other-month|disabled/.test(c.className.toString()));
  }
  if (!cells.length) return { err: '日历里找不到任何可选日期' };
  const target = cells[cells.length - 1];   // 当月最后一个可选日
  const rect = target.getBoundingClientRect();
  return { day: (target.innerText || '').trim(),
           cls: target.className.toString().slice(0, 80),
           x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
})
"""

# 权限二次确认框状态
ATM_PERM_STATE = r"""
(() => {
  const d = document.querySelector('.automation-permission-confirm__dialog');
  if (!d) return { confirm: false };
  const fallback = d.querySelector('.automation-permission-confirm__fallback-link');
  const cb = d.querySelector('.automation-permission-confirm__checkbox input');
  const ok = Array.from(d.querySelectorAll('button'))
    .find(b => /确认创建/.test(b.innerText || ''));
  return { confirm: true,
           hasFallback: !!fallback,
           cbChecked: cb ? !!cb.checked : null,
           okDisabled: ok ? !!ok.disabled : null };
})
"""

# 批量管理：状态
ATM_BATCH_STATE = r"""
(() => {
  const p = document.querySelector('.automation-main-page');
  if (!p) return { onPage: false };
  const txt = (p.innerText || '').replace(/\s+/g, ' ');
  return { onPage: true,
           inBatch: /已选择/.test(txt),
           selected: (txt.match(/已选择(\d+)项/) || [])[1] || null,
           names: Array.from(document.querySelectorAll('div.atm-row .atm-row-name'))
                    .map(e => wbT(e)) };
})
"""

ATM_BATCH_ON = r"""
(async () => {
  if (!document.querySelector('.automation-main-page')) {
    clickSidebar('定时任务'); await sleep(3000);
  }
  const p = document.querySelector('.automation-main-page');
  if (!p) return { err: '不在定时任务页' };
  if (/已选择/.test(p.innerText || '')) return { ok: true, already: true };
  const b = findBtn(p, '批量管理');
  if (!b) return { err: '没有「批量管理」按钮' };
  realClick(b);
  await sleep(1500);
  return { ok: /已选择/.test(p.innerText || '') };
})
"""

ATM_BATCH_OFF = r"""
(async () => {
  const p = document.querySelector('.automation-main-page');
  if (!p) return { ok: false };
  if (!/已选择/.test(p.innerText || '')) return { ok: true, already: true };
  const b = findBtn(p, '退出管理');
  if (!b) return { err: '没有「退出管理」按钮' };
  realClick(b);
  await sleep(1200);
  return { ok: true };
})
"""

ATM_BATCH_CONFIRM = r"""
(async () => {
  const m = Array.from(document.querySelectorAll('.wb-modal'))
    .filter(x => x.querySelector('button'))
    .find(x => /删除选中的/.test(x.innerText || ''));
  if (!m) return { modal: false };
  const btn = Array.from(m.querySelectorAll('button'))
    .filter(b => (b.innerText || '').trim() === '删除')
    .sort((a, b) => /danger/.test(b.className.toString())
                  - /danger/.test(a.className.toString()))[0];
  if (!btn) return { modal: true, err: '确认框里没有删除按钮' };
  realClick(btn);
  await sleep(2200);
  return { modal: true, clicked: true };
})
"""

ATM_TEMPLATE = r"""
(async (tplName) => {
  closeOverlays(3);
  await sleep(600);
  if (!document.querySelector('.automation-main-page')) {
    clickSidebar('定时任务');
    await sleep(2500);
  }
  const cands = Array.from(document.querySelectorAll('*')).filter(wbVis)
    .filter(e => e.children.length <= 3 && wbT(e).indexOf(tplName) === 0)
    .sort((a, b) => a.querySelectorAll('*').length - b.querySelectorAll('*').length);
  if (!cands.length) return { err: '找不到模版 ' + tplName };
  const target = cands[0];
  const card = target.closest('[class*=card], [class*=template], [class*=item], li') || target;
  realClick(card);
  await sleep(2800);
  const modal = document.querySelector('.wb-modal');
  if (!modal) return { err: '模版没打开对话框', clicked: wbT(target).slice(0, 30) };
  const input = modal.querySelector('input.atm-modal-input');
  const ed = modal.querySelector('[contenteditable=true]');
  return { opened: true,
           clicked: wbT(target).slice(0, 40),
           name: input ? input.value : null,
           promptLen: ed ? (ed.innerText || '').length : 0,
           prompt: ed ? (ed.innerText || '').replace(/\s+/g, ' ').slice(0, 80) : null,
           placeholder: !!modal.querySelector('[class*=placeholder]:not([style*="display: none"])') };
})
"""

ATM_WHY = r"""
(() => {
  const modal = document.querySelector('.wb-modal');
  if (!modal) return { modal: false };
  const ok = Array.from(modal.querySelectorAll('button')).find(b => (b.innerText || '').trim() === '确定');
  const out = { modal: true, okFound: !!ok };
  if (ok) {
    const r = ok.getBoundingClientRect();
    out.rect = { x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height) };
    const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
    const top = document.elementFromPoint(cx, cy);
    out.atPoint = top ? { tag: top.tagName, cls: String(top.className).slice(0, 70),
                          isOk: top === ok || ok.contains(top) } : null;
    out.win = { w: window.innerWidth, h: window.innerHeight };
  }
  const ed = modal.querySelector('[contenteditable=true]');
  out.promptText = ed ? (ed.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 60) : null;
  out.slate = ed ? (ed.getAttribute('data-slate-editor') || ed.className.toString().slice(0, 60)) : null;
  out.toasts = Array.from(document.querySelectorAll('[class*=toast], [class*=wb-message]'))
    .filter(e => (e.innerText || '').trim()).map(e => (e.innerText || '').replace(/\s+/g, ' ').slice(0, 100));
  return out;
})
"""

ATM_COMMIT = r"""
(async (nameInput) => {
  const modal = document.querySelector('.wb-modal');
  if (!modal) return { err: '对话框不见了' };
  const input = modal.querySelector('input.atm-modal-input');
  if (input && nameInput) setReactInput(input, nameInput);
  const ok = findBtn(modal, '确定');
  if (!ok) return { err: '没有「确定」按钮' };
  realClick(ok);
  await sleep(3000);
  return { ok: true, stillOpen: !!document.querySelector('.wb-modal'),
           list: (document.querySelector('.automation-main-page') || {}).innerText
                 ? document.querySelector('.automation-main-page').innerText.replace(/\s+/g, ' ').slice(0, 400) : null };
})
"""

ATM_DELETE = r"""
(async (name) => {
  const rows = Array.from(document.querySelectorAll('*')).filter(wbVis)
    .filter(e => wbT(e) === name && e.children.length <= 2);
  const row = rows[rows.length - 1];
  if (!row) return { err: '列表里找不到 ' + name };
  const card = row.closest('[class*=card], [class*=item], li, tr') || row.parentElement;
  hover(card);
  await sleep(600);
  const more = Array.from(card.querySelectorAll('button, [class*=more], [class*=icon]'))
    .filter(wbVis).filter(b => /more|ellipsis|icon-only/i.test(b.className.toString()))[0];
  if (!more) return { err: '找不到更多按钮' };
  realClick(more); await sleep(1400);
  const del = Array.from(document.querySelectorAll('button, [role=menuitem]'))
    .filter(wbVis).find(b => /删除/.test(wbT(b)));
  if (!del) return { err: '菜单里没有删除' };
  realClick(del); await sleep(1500);
  const confirm = Array.from(document.querySelectorAll('button')).filter(wbVis)
    .find(b => /确认删除|删除/.test(wbT(b)) && /danger|primary/.test(b.className.toString()));
  if (confirm) { realClick(confirm); await sleep(1800); }
  return { ok: true };
})
"""

# --------------------------------------------------------------------------- #
# 发现应用（Buddy_App / Buddy_App_QQ）
# --------------------------------------------------------------------------- #
BUDDY_APP = r"""
(async (appName) => {
  closeOverlays(3);
  await sleep(600);
  clickSidebar('新建任务');
  await sleep(1500);
  const disc = findBtn(document, '发现应用');
  if (!disc) return { err: '找不到「发现应用」' };
  realClick(disc);
  await sleep(2200);
  const pop = Array.from(document.querySelectorAll('.wb-popover')).filter(wbVis)[0];
  if (!pop) return { err: '发现应用弹层没出现' };
  const apps = Array.from(pop.querySelectorAll('*')).filter(wbVis)
    .filter(e => e.children.length <= 3 && wbT(e) && wbT(e).indexOf(appName) === 0)
    .sort((a, b) => a.querySelectorAll('*').length - b.querySelectorAll('*').length);
  if (!apps.length) {
    return { err: '弹层里没有 ' + appName,
             have: Array.from(pop.querySelectorAll('*')).filter(wbVis)
               .map(e => wbT(e)).filter(t => t && t.length < 30).slice(0, 20) };
  }
  realClick(apps[0]);
  await sleep(3000);
  // 可能弹授权框
  const auth = findBtn(document, '确认授权');
  if (auth) { realClick(auth); await sleep(3500); }
  return { ok: true, clicked: wbT(apps[0]).slice(0, 40), authorized: !!auth,
           view: (document.body.innerText || '').replace(/\s+/g, ' ').slice(0, 300) };
})
"""

# --------------------------------------------------------------------------- #
# 专家中心（expert_5 / Expert_team_use_3 / Expert_lighthouse）
#
# 结构（实测）：
#   侧边栏入口 = button.conversation-list-tab-button「专家·技能·连接器」
#   页内顶部 = .um-tab（专家 / 技能 / 连接器）—— 这是「专家·技能·连接器」三个板块
#   列表切换 = .ec-list-tab（「专家」/「专家团」）
#   分类     = .ec-category-tab（全部 / 腾讯专家 / …）
#   卡片     = article.ec-expert-card，召唤按钮 = .ec-card-summon-btn
#   搜索框   = .ec-search-wrapper input（placeholder「搜索专家职称或描述」）
#
# 关键结论（2026-09-19 修正 + 2026-09-20 二次实测改判）：
#   * 单专家（expert_5 / Expert_lighthouse）：召唤 + 建会话即计数，发一句话更稳。
#   * 专家团（Expert_team_use_3）：⚠️ 必须等团队把这一轮说完才计分 ——
#     这与单专家/普通对话（WorkDaddy 发一句「你好」等 end_turn 即完成）**不同**！
#     2026-09-20 account_e 实测：team_first_reply=True「首段稳定回复就收工+删会话」
#     连试 5 个团队全部 nAg=1、+0 —— 首回复时其它 agent 还没加入，删会话把
#     团队协作直接打断；唯一成功记录（2026-09-19 独董会 ~130s +1）是等整轮收尾的
#     旧逻辑。所以专家团 team_first_reply=False、max_wait=300 等自然收尾。
#     对模型敏感：用最省的 Hy3 时多智能体协作会静默退化（全程 nAg=1、进度钉死 0/3、
#     还看不出报错）；改用 Deepseek-V4.1-Flash（0.03x，一次约 2 积分）立刻 0/3 → 1/3。
#     所以专家团固定用 TEAM_MODEL，见下。
#   * 专家团**不能重复**、**不能太冷门**（用户硬约束）：每次取不同卡片（按名字去重），
#     优先选官方/知名团队（腾讯云技术支持、内容创作/智数分析专家团、MVP开发专家团…），
#     避开实测不成立的冷门团队；额度耗尽（429）的账号直接判 0/3，不重试。
#   * 专家团召唤会弹「积分消耗提醒」，按**文案**（不是类名，类名已 CSS-module 哈希）
#     勾选「我已知悉并确认」再点「继续使用」/ data-track-id=expert_team_confirm_continue。
# --------------------------------------------------------------------------- #

# 专家团专用模型默认值。用户 2026-09-20 明确纠正：「我主号当时就是用的**免费模型**
# 完成的任务 —— 已证明不需要收费模型」→ 所以这里**不再把 Hy3 当不可用**，
# 并且允许用环境变量覆盖：TEAM_MODEL=Hy3 python batch_runner.py ...
# （早前「Hy3 撑不起多智能体」的结论是误诊：当时真正的原因是团队召唤确认框被
#  suppress 掉了、协作压根没启动，跟模型无关。）
TEAM_MODEL = os.environ.get("TEAM_MODEL", "Hy3")

# ★ A2（2026-09-20 核验缺陷 #2）：专家团**绝不能裸发团队自带推荐词**。
#   那些推荐词大多要用户给素材（CSV/代码/持仓/云资源），团队上来就反问 →
#   会话挂「待确认」→ 这一轮永不结束 → 服务端永不计分（见核验报告 A1/A2）。
#   chip 必须保留（keep_input=True，清输入框会把 chip 一起清掉），
#   所以做法是**在推荐词后面追加这条自包含执行指令**：不许反问、不等材料、一轮内给结论。
TEAM_SELF_CONTAINED_PROMPT = (
    "执行规则：如果上面的任务需要我提供材料（文件、代码、持仓、账号信息等），"
    "一律不要等待——直接改用合理的示例数据当场完成演示，并在这一轮内给出完整结论与产出清单。"
    "不要向我提问，不要请求确认，不要把问题留到下一轮。")
EXPERT_ENTER = r"""
(async (tabName) => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  // 召唤后视图会离开专家中心（切到新任务）→ 这里最多重试 3 轮把页面拉回来
  for (let attempt = 0; attempt < 3; attempt++) {
    if (document.querySelector('.ec-list-tab')) break;
    await openNewTask();
    await sleep(1100);
    const entry = Array.from(document.querySelectorAll('button.conversation-list-tab-button'))
      .find(b => T(b).indexOf('专家') !== -1);
    if (!entry) return { err: '侧边栏找不到「专家·技能·连接器」' };
    realClick(entry);
    await sleep(1600);
    for (let i = 0; i < 20; i++) {
      if (document.querySelector('.ec-list-tab')) break;
      await sleep(700);
    }
  }
  if (!document.querySelector('.ec-list-tab')) return { err: '专家中心没加载出来' };
  let tab = null;
  if (tabName) {
    tab = Array.from(document.querySelectorAll('.ec-list-tab')).find(e => T(e) === tabName);
    if (!tab) return { err: '没有列表 tab ' + tabName,
                       have: Array.from(document.querySelectorAll('.ec-list-tab')).map(T) };
    if (tab.className.toString().indexOf('is-active') === -1) {
      realClick(tab);
      await sleep(2600);
    }
  }
  const cards = Array.from(document.querySelectorAll('.ec-expert-card'));
  return { ok: true, tab: tab ? T(tab) : null, nCards: cards.length,
           names: cards.map(c => T(c).replace(/^召唤\s*/, '').slice(0, 28)) };
})
"""

EXPERT_SUMMON_AT = r"""
(async (idx) => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const cards = Array.from(document.querySelectorAll('.ec-expert-card'));
  if (!cards.length) return { err: '专家卡片列表为空' };
  const card = cards[idx] || cards[0];
  const btn = card.querySelector('.ec-card-summon-btn')
    || Array.from(card.querySelectorAll('button')).find(b => /召唤/.test(T(b)));
  if (!btn) return { err: '第 ' + idx + ' 张卡片没有召唤按钮' };
  const name = T(card).replace(/^召唤\s*/, '').slice(0, 30);
  realClick(btn);
  await sleep(2500);
  // 专家团：「积分消耗提醒」→ 勾选 → 继续使用
  const ov = document.querySelector('.ec-team-summon-confirm-overlay');
  let confirmed = false;
  if (ov) {
    const lab = ov.querySelector('label.ec-confirm-dialog-checkbox');
    if (lab) { realClick(lab); await sleep(800); }
    const go = ov.querySelector('[data-track-id=expert_team_confirm_continue]')
      || Array.from(ov.querySelectorAll('button')).find(b => /继续使用/.test(T(b)));
    if (go && !go.disabled) { realClick(go); confirmed = true; await sleep(2200); }
  }
  await sleep(2600);
  return { ok: true, idx: idx, name: name, teamConfirm: !!ov, confirmed: confirmed,
           dialogLeft: !!document.querySelector('.ec-team-summon-confirm-overlay'),
           inTask: !!document.querySelector('.cr-message-list-viewport') };
})
"""

EXPERT_SEARCH = r"""
(async (kw) => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const si = document.querySelector('.ec-search-wrapper input');
  if (!si) return { err: '专家中心没有搜索框' };
  realClick(si);
  await sleep(300);
  setReactInput(si, '');
  await sleep(400);
  setReactInput(si, kw);
  await sleep(3400);
  const cards = Array.from(document.querySelectorAll('.ec-expert-card'));
  return { ok: true, kw: kw, nCards: cards.length,
           names: cards.map(c => T(c).replace(/^召唤\s*/, '').slice(0, 30)) };
})
"""

# 一条龙前置：进专家中心 →（可选搜索）→ 切列表 tab → 召唤 → 自动确认积分提醒。
# 返回时输入框里已经有该专家的预填引导语（keep_input=True 时不要清空它）。
EXPERT_PRE = r"""
(async (kind, kw, idx) => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  await openNewTask();
  await sleep(1100);
  for (let a = 0; a < 3; a++) {
    if (document.querySelector('.ec-list-tab')) break;
    const e = Array.from(document.querySelectorAll('button.conversation-list-tab-button'))
      .find(b => T(b).indexOf('专家') !== -1);
    if (!e) return { err: '侧边栏找不到专家入口' };
    realClick(e);
    await sleep(1600);
    for (let i = 0; i < 20; i++) { if (document.querySelector('.ec-list-tab')) break; await sleep(700); }
  }
  if (!document.querySelector('.ec-list-tab')) return { err: '专家中心没加载出来' };
  if (kind === 'search') {
    const si = document.querySelector('.ec-search-wrapper input');
    if (!si) return { err: '专家中心没有搜索框' };
    realClick(si);
    await sleep(300);
    setReactInput(si, '');
    await sleep(400);
    setReactInput(si, kw);
    await sleep(3400);
  } else {
    const tabName = (kind === 'team') ? '专家团' : '专家';
    const tab = Array.from(document.querySelectorAll('.ec-list-tab')).find(x => T(x) === tabName);
    if (!tab) return { err: '没有列表 tab ' + tabName };
    if (tab.className.toString().indexOf('is-active') === -1) {
      realClick(tab);
      await sleep(2600);
    }
  }
  // 卡片是异步渲染的：切 tab / 搜索后要轮询等它出来
  let cards = [];
  for (let i = 0; i < 22; i++) {
    cards = Array.from(document.querySelectorAll('.ec-expert-card'));
    if (cards.length) break;
    await sleep(700);
  }
  if (!cards.length) return { err: '卡片列表为空（渲染超时）',
                              onExpertPage: !!document.querySelector('.ec-list-tab'),
                              activeTab: (document.querySelector('.ec-list-tab.is-active') || {}).innerText || null };
  const card = cards[(kind === 'search') ? 0 : idx] || cards[0];
  const name = T(card).replace(/^召唤\s*/, '').slice(0, 30);
  const btn = card.querySelector('.ec-card-summon-btn')
    || Array.from(card.querySelectorAll('button')).find(b => /召唤/.test(T(b)));
  if (!btn) return { err: '卡片没有召唤按钮' };
  realClick(btn);
  await sleep(2600);
  const ov = document.querySelector('.ec-team-summon-confirm-overlay');
  let confirmed = false;
  if (ov) {
    const lab = ov.querySelector('label.ec-confirm-dialog-checkbox');
    if (lab) { realClick(lab); await sleep(800); }
    const go = ov.querySelector('[data-track-id=expert_team_confirm_continue]')
      || Array.from(ov.querySelectorAll('button')).find(b => /继续使用/.test(b.textContent || ''));
    if (go && !go.disabled) { realClick(go); confirmed = true; await sleep(2500); }
  }
  await sleep(2600);
  const ed = document.querySelector('[contenteditable=true]');
  return { ok: !!ed, name: name, teamConfirm: !!ov, confirmed: confirmed, composer: !!ed,
           guide: ed ? (ed.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 50) : null,
           stillDialog: !!document.querySelector('.ec-team-summon-confirm-overlay') };
})
"""

# --------------------------------------------------------------------------- #
# 设计创意模式（create_canvas）
#
# 首页场景 pill = .wb-scene-tabs__pill（日常办公 / 代码开发 / **设计创意**）
# 切到设计创意后出现「快捷动作」= button.quick-actions__item
#   （视觉海报 / 运营海报 / PPT设计 / 生成图片 / 生成视频 / 品牌设计 /
#     网站设计 / 移动端App / 设计系统 / Web App / 图标&插画）
# 点快捷动作后会展开「示例提示词」= button.quick-actions-sub__item
#   （例：网站设计 → AI趋势官网 / 球鞋文化网站 / 粗野主义网站）
#
# 关键：**只点快捷动作是不够的** —— 它只往输入框塞一个「网站设计」标签，
# 直接发送 AI 会反问「你想做什么」→ 会话挂成「待确认」，任务不计数。
# 必须再点一个示例提示词，把完整需求填进输入框，再发送。
# --------------------------------------------------------------------------- #
CANVAS_PRE = r"""
(async (action, sugg) => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const vis = b => { const r = b.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
  // 输入框里已经有草稿时，点快捷动作/示例词会弹「输入框里有你写的内容 … 替换」确认框
  const tryReplace = async () => {
    const rep = Array.from(document.querySelectorAll('button')).filter(vis)
      .find(b => T(b) === '替换');
    if (rep) { realClick(rep); await sleep(2400); return true; }
    return false;
  };
  await openNewTask();
  await sleep(1500);
  let sc = await setScene('设计创意');
  if (!sc.ok) {
    await sleep(1500);
    sc = await setScene('设计创意');
  }
  await sleep(2600);
  const items = Array.from(document.querySelectorAll('.quick-actions__item')).filter(isVisible);
  if (!items.length) return { err: '设计创意页没有快捷动作项', scene: sc };
  const it = items.find(e => T(e) === action) || items[0];
  realClick(it);
  await sleep(2500);
  await tryReplace();
  let subs = [];
  for (let i = 0; i < 12; i++) {
    subs = Array.from(document.querySelectorAll('.quick-actions-sub__item')).filter(isVisible);
    if (subs.length) break;
    await sleep(600);
  }
  const sb = subs.find(e => T(e) === sugg) || subs[0];
  if (sb) { realClick(sb); await sleep(2600); await tryReplace(); }
  const ed = document.querySelector('[contenteditable=true]');
  const txt = ed ? (ed.innerText || '').replace(/\s+/g, ' ').trim() : '';
  return { ok: !!ed && txt.length > 12, scene: sc.scene || sc.err,
           action: T(it), suggestion: sb ? T(sb) : null, subs: subs.map(T).slice(0, 6),
           len: txt.length, head: txt.slice(0, 60),
           chips: Array.from(document.querySelectorAll('.phrase-content-wrapper')).map(T) };
})
"""


# --------------------------------------------------------------------------- #
# 灵感（playbook_prompt）
# --------------------------------------------------------------------------- #
PLAYBOOK_PRE = r"""
(async (want) => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  await closeOverlays(3);
  await openNewTask();
  await sleep(1300);
  // 侧边栏「更多 · 灵感」是个二级入口，直接点 sub 那个「灵感」最稳
  let sub = Array.from(document.querySelectorAll('.conversation-list-tab-button-sub'))
    .find(e => T(e).indexOf('灵感') !== -1);
  if (!sub) {
    const more = Array.from(document.querySelectorAll('button.conversation-list-tab-button'))
      .find(b => T(b).indexOf('更多') !== -1);
    if (more) { realClick(more); await sleep(1800); }
    sub = Array.from(document.querySelectorAll('.conversation-list-tab-button-sub'))
      .find(e => T(e).indexOf('灵感') !== -1);
  }
  if (!sub) return { err: '侧边栏找不到「灵感」入口' };
  realClick(sub);
  await sleep(3200);
  const page = document.querySelector('[class*=inspiration], [class*=playbook], [class*=idea]');
  return { ok: true, clicked: T(sub),
           cls: Array.from(new Set(Array.from(document.querySelectorAll('[class*=inspiration], [class*=playbook], [class*=idea], [class*=case]'))
             .map(e => e.className.toString().split(' ')[0]))).slice(0, 40),
           bodyTxt: (document.body.innerText || '').replace(/\s+/g, ' ').slice(0, 600) };
})
"""


# 「做同款」完整流程拆成 4 段独立 JS：点「灵感」会让页面导航，
# 若和后续 await 写在同一次调用里，导航后那次调用永远等不到返回（CDP 超时）。
PB_SIDE = r"""
(() => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const sub = Array.from(document.querySelectorAll('.conversation-list-tab-button-sub'))
    .find(e => T(e).indexOf('灵感') !== -1);
  if (!sub) return { err: '侧边栏没有「灵感」子入口' };
  realClick(sub);
  return { ok: true, side: T(sub) };
})
"""

PB_CARD = r"""
((idx) => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  let cards = Array.from(document.querySelectorAll('.wb-related-playbooks__card'));
  if (!cards.length) {
    const slot = document.querySelector('.wb-home-page__related-playbooks-slot');
    cards = slot ? Array.from(slot.querySelectorAll('button')) : [];
  }
  if (!cards.length) return { err: '页面上没有灵感卡片' };
  const c = cards[idx] || cards[0];
  realClick(c);
  return { ok: true, case: T(c).slice(0, 44), nCards: cards.length };
})
"""

PB_SAME = r"""
(() => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const vis = b => { const r = b.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
  const all = Array.from(document.querySelectorAll('button')).filter(vis);
  const same = all.find(b => T(b) === '做同款') || all.find(b => /做同款/.test(T(b)));
  if (!same) return { err: '没有「做同款」按钮' };
  realClick(same);
  return { ok: true };
})
"""

# 点「替换」并回读输入框（载入灵感会覆盖当前草稿，所以会弹这个确认框）
PB_REPLACE = r"""
(async () => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const vis = b => { const r = b.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
  const all = Array.from(document.querySelectorAll('button')).filter(vis);
  const rep = all.find(b => T(b) === '替换');
  if (rep) { realClick(rep); await sleep(2600); }
  const ed = document.querySelector('[contenteditable=true]');
  const t = ed ? (ed.innerText || '').replace(/\s+/g, ' ').trim() : '';
  return { ok: t.length > 20, replaced: !!rep, len: t.length, head: t.slice(0, 60),
           chips: Array.from(document.querySelectorAll('.phrase-content-wrapper'))
                    .map(x => (x.innerText || '').trim()) };
})
"""


def _fn(src, *args):
    """把「函数定义字符串」包成自执行调用。

    坑（踩过）：`js()` 内部是 `return await (<code>)`；若 code 只是
    `(() => {...})`（**只有定义、没有尾部的 `()`**），await 一个函数对象会
    序列化成 `{}` —— 调用静默失败、也不报错。
    PB_SIDE / PB_SAME / PB_REPLACE 当初就漏了尾部 `()`，导致「做同款」从没被点过。
    所以凡是要调用的一次性 JS，一律走这里包装，别裸传常量。
    """
    a = ",".join(str(x) for x in args)
    return "(async () => { const f = %s; return await f(%s); })()" % (src, a)


def _pb_card_step(idx=0):
    return _fn(PB_CARD, idx)


# 清空专家中心搜索框（跑完把状态还原，别把搜索词留给下一个人）
EXPERT_SEARCH_CLEAR = r"""
(async () => {
  const si = document.querySelector('.ec-search-wrapper input');
  if (!si) return { ok: true, already: true };
  setReactInput(si, '');
  await sleep(1200);
  return { ok: true };
})
"""

# 回首页（专家中心是整页视图，跑完回首页不留下痕迹）
EXPERT_LEAVE = r"""
(async () => {
  await openNewTask();
  await sleep(1200);
  return { ok: true };
})
"""


# --------------------------------------------------------------------------- #
# 任务动作
# --------------------------------------------------------------------------- #
def open_settings():
    return U.js(OPEN_SETTINGS, timeout=90)


def _js_block(block, *args, timeout=120.0):
    """把 HELPERS + 一个 (async (…) => {…}) 函数体拼成一次 JS 调用。"""
    code = ("(async () => {\n" + HELPERS + "\nconst f = " + block.strip() + ";\n"
            "return await f(" + ", ".join(json.dumps(a) for a in args) + ");\n})()")
    return U.js(code, timeout=timeout)


def run_probe(js_file, *args, timeout=180.0):
    """把 research/<jsfile> 的**函数体**（(async (…) => {…}) 形式）连同 HELPERS 一起跑。

    可选 args 会作为参数传给该函数：`python ui_tasks.py raw p_xxx.js 网站设计`
    """
    path = js_file
    if not os.path.isabs(path):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "research", js_file)
    with open(path, encoding="utf-8") as f:
        body = f.read().strip()
    # 兼容两种写法：函数表达式 (async () => {…})，或已自调用的 (async () => {…})()
    if body.endswith("()"):
        body = body[:-2].rstrip()
    code = ("(async () => {\n" + HELPERS + "\nconst f = " + body + ";\n"
            "return await f(" + ", ".join(json.dumps(a) for a in args) + ");\n})()")
    return U.js(code, timeout=timeout)


def atm_inspect(name="夜间资讯摘要"):
    return _js_block(ATM_OPEN, name, True, timeout=120)


def type_into(js_focus, text, click_first=True):
    """聚焦指定元素后用 CDP Input.insertText 真实输入（Slate/受控组件都认）。

    Slate / 富文本编辑器必须先用**真鼠标点击**获得焦点（Slate 内部要建立
    selection），只用 `e.focus()` 是不够的——那样 DOM 会有文字但 Slate 状态仍是空，
    提交时会被校验拦下（"请填写提示词"）。
    """
    if click_first:
        U.mouse_click(js_focus)
    import cdp as C
    cdp, _ = C.connect()
    try:
        ok = cdp.evaluate("(function(){var e=%s; if(!e) return false; e.focus(); return true;})()"
                          % js_focus, timeout=20)
        if not ok:
            return {"ok": False, "err": "找不到目标元素"}
        # Input.insertText 会触发 beforeinput，被「用户活动」监听器算成真人打字，
        # 于是后面每个任务都误判「用户正在使用客户端」而主动让路。必须置位。
        U.driver_typing(True)
        cdp.call("Input.insertText", {"text": text}, timeout=25)
        time.sleep(0.8)
        got = cdp.evaluate(
            "(function(){var e=%s; if(!e) return null;"
            " return (e.value !== undefined ? e.value : (e.innerText||'')).replace(/\\s+/g,' ').slice(0,80);})()"
            % js_focus, timeout=20)
        return {"ok": True, "after": got}
    finally:
        U.driver_typing(False)
        cdp.close()


EDITOR_SEL = ".automation-editor-modal"
OK_EXPR = ("Array.from(document.querySelectorAll('%s button'))"
           ".find(b => (b.innerText||'').trim() === '确定')" % EDITOR_SEL)
NAME_EXPR = "document.querySelector('%s input.atm-modal-input')" % EDITOR_SEL
SLATE_EXPR = "document.querySelector('%s [contenteditable=true]')" % EDITOR_SEL
FREQ_EXPR = "document.querySelector('%s .atm-schedule-trigger')" % EDITOR_SEL
DATE_EXPR = ("document.querySelector('%s .atm-schedule-date-input .wb-datepicker-trigger')"
             % EDITOR_SEL)
FALLBACK_EXPR = "document.querySelector('.automation-permission-confirm__fallback-link')"
CF_CB_EXPR = "document.querySelector('.automation-permission-confirm__checkbox')"
CF_OK_EXPR = ("Array.from(document.querySelectorAll("
              "'.automation-permission-confirm__dialog button'))"
              ".find(b => /确认创建/.test(b.innerText||''))")
DAY_EXPR_T = ("Array.from(document.querySelectorAll('.wb-datepicker-grid__cell'))"
              ".filter(c => !/other-month|disabled/.test(c.className.toString()) "
              "&& (c.innerText||'').trim() === %s)[0]")


def do_automation_1(name="夜间资讯摘要",
                    prompt="用一句话总结今天值得关注的一条 AI 新闻。直接给结果。",
                    day=None):
    """automation_1：设置 1 个自动化任务。

    完整链路（每一步都是踩坑换来的）：
      定时任务页 → 添加定时任务（真点击）→ 名称（原生 setter）→ 提示词（Slate，
      **先真鼠标点编辑器再 Input.insertText**）→ 执行频率浮层 → 日期选择器改到未来
      （单次默认时间是「现在」，必然报"必须晚于当前时间"）→ 关浮层 → 确定（CDP 真鼠标）
      → 权限二次确认框 → **勾「我已知悉并确认」+ 点「确认创建」= 完全访问权限**
      （用户要求；老写法点 fallback-link 降成"默认权限"会让自动化跑起来停下来等人确认）
      → 回读列表校验。

    注意：不要用 Escape 关浮层——那会把整个编辑对话框一起关掉。
    """
    out = {"name": name}
    r = _js_block(ATM_OPEN2, timeout=120)
    out["open"] = r
    if not r.get("opened"):
        out["ok"] = False
        out["err"] = "打开对话框失败：%s" % r
        return out

    # 名称（受控 input：原生 setter + input 事件）
    out["name_type"] = U.js(
        "(async()=>{const i=%s;if(!i)return{err:'no input'};i.focus();"
        "const s=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;"
        "s.call(i,%s);i.dispatchEvent(new Event('input',{bubbles:true}));"
        "i.dispatchEvent(new Event('change',{bubbles:true}));return{v:i.value};})()"
        % (NAME_EXPR, json.dumps(name)))

    # 提示词（Slate：真点击聚焦 → insertText）
    out["prompt_type"] = type_into(SLATE_EXPR, prompt)

    # 执行频率：把「单次」的日期改到未来
    out["m_freq"] = U.mouse_click(FREQ_EXPR)
    time.sleep(1.6)
    out["freq_open"] = U.js("(()=>({popover:!!document.querySelector('.atm-frequency-popover'),"
                            "editor:!!document.querySelector('.automation-editor-modal')}))()")
    out["m_date"] = U.mouse_click(DATE_EXPR)
    time.sleep(1.6)
    out["date_open"] = U.js("(()=>({panel:!!document.querySelector('.wb-datepicker-panel-container'),"
                            "editor:!!document.querySelector('.automation-editor-modal'),"
                            "cells:document.querySelectorAll('.wb-datepicker-grid__cell').length}))()")
    pick = _js_block(ATM_PICK_FUTURE, timeout=90)
    out["day_pick"] = pick
    if pick.get("day"):
        out["m_day"] = U.mouse_click(DAY_EXPR_T % json.dumps(pick["day"]))
        time.sleep(1.4)
    out["schedule"] = _js_block(ATM_ERRORS, timeout=60)

    # 关浮层：点名称输入框（不要用 Escape，会关掉整个对话框）
    out["m_name"] = U.mouse_click(NAME_EXPR)
    time.sleep(0.9)

    # 确定 → 可能弹「完全访问」二次确认
    out["m_ok"] = U.mouse_click(OK_EXPR)
    time.sleep(2.5)
    out["confirm1"] = _js_block(ATM_PERM_STATE, timeout=60)
    if out["confirm1"].get("confirm"):
        # ★ 用户要求（2026-09-19）：这里**给「完全访问权限」**。
        # 原因：选「默认权限」时，自动化真正跑起来会因为用到工具而停下来等人确认，
        # 表现就是用户说的「发起任务时他总提问、得确认他才继续」。
        # 做法：勾「我已知悉并确认」→ 点「确认创建」。
        # 注意**不要**再点 `.automation-permission-confirm__fallback-link`
        # —— 那会把权限降成「默认权限」（老写法，已弃用）。
        out["m_cb"] = U.mouse_click(CF_CB_EXPR)
        time.sleep(1.1)
        out["m_cf_ok"] = U.mouse_click(CF_OK_EXPR)
        time.sleep(3.0)
        cf2 = _js_block(ATM_PERM_STATE, timeout=60)
        out["confirm2"] = cf2
        if cf2.get("confirm"):
            # 兜底：完全访问这条路没走通（勾不动 / 「确认创建」仍禁用）时，
            # 退回「默认权限」至少把任务建出来 —— automation_1 只要求「设置 1 个自动化任务」。
            out["m_fb"] = U.mouse_click(FALLBACK_EXPR)
            time.sleep(1.8)
            out["m_ok2"] = U.mouse_click(OK_EXPR)
            time.sleep(3.0)
            cf3 = _js_block(ATM_PERM_STATE, timeout=60)
            out["confirm3"] = cf3
            if cf3.get("confirm"):
                U.mouse_click(CF_OK_EXPR)
                time.sleep(3.0)

    time.sleep(1.5)
    out["after"] = _js_block(ATM_ERRORS, timeout=60)
    out["list"] = _js_block(ATM_LIST, timeout=120)
    out["created"] = bool(out["list"].get("txt") and name in out["list"]["txt"])
    out["ok"] = out["created"]
    if not out["ok"]:
        out["err"] = "提交后列表里没出现该任务；after=%s" % out["after"]
    return out


def do_buddy_app(app_name="企鹅教师助手"):
    return _js_block(BUDDY_APP, app_name, timeout=120)


# --------------------------------------------------------------------------- #
# 专家中心驱动器
# --------------------------------------------------------------------------- #
def expert_enter(tab=None):
    return _js_block(EXPERT_ENTER, tab, timeout=180)


def expert_summon(idx=0):
    return _js_block(EXPERT_SUMMON_AT, idx, timeout=180)


def expert_search(kw):
    return _js_block(EXPERT_SEARCH, kw, timeout=180)


def expert_search_clear():
    return _js_block(EXPERT_SEARCH_CLEAR, timeout=60)


def expert_leave():
    return _js_block(EXPERT_LEAVE, timeout=60)


# --------------------------------------------------------------------------- #
# 专家中心：**分步**驱动（重要）
#
# 教训（2026-09-19 实测）：把整条专家流程塞进一次 JS 调用会**必然超时**。
# 原因是「点开专家中心」这一步会让渲染进程主线程阻塞约 45 秒（首屏挂载 + 虚拟列表
# 测量），页面内的 await sleep() 被整体拖慢约 19 倍 —— 实测 sleep(2500) 实际跑了
# 47 秒。JS 里累计几十秒的等待会被放大成几百秒，CDP 一定先超时。
#
# 对策：JS 只做「点击 + 立刻返回」，所有等待交给 **Python 的 time.sleep**
# （不受页面卡顿影响），通过 run_task 的 pre_steps + 逐步 pre_gap 串起来。
# --------------------------------------------------------------------------- #

EXPERT_ENTER_STEP = r"""
(async () => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const loaded = () => !!document.querySelector('.ec-list-tab');
  if (!loaded()) {
    const e = Array.from(document.querySelectorAll('button.conversation-list-tab-button'))
      .find(b => T(b).indexOf('专家') !== -1);
    if (!e) return { ok: false, err: '侧边栏找不到专家入口' };
    realClick(e);
  }
  // 等专家中心真正挂载出来再返回。
  // 坑（真实故障）：专家中心是整页视图、首屏很重；只点一下立刻返回的话，
  // 后续步骤（切 tab / 找卡片）会赶在挂载前执行 → 报「专家中心没加载出来」
  // +「卡片列表为空」。而 run_task 不会因为前置步骤失败就停下，
  // 于是它照样把消息**发进一个普通对话** —— 任务永远 0/3，还白白建了会话。
  // 之前「召唤专家团长期不计数」就是栽在这里。
  for (let i = 0; i < 40; i++) {
    if (loaded()) return { ok: true, clicked: true, waited: i * 0.5 };
    await sleep(500);
  }
  return { ok: false, err: '专家中心 20s 内没挂载出来' };
})()
"""

EXPERT_PICK_STEP = r"""
(async (kind, kw) => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  if (!document.querySelector('.ec-list-tab')) {
    return { ok: false, err: '专家中心没加载出来' };
  }
  if (kind === 'search') {
    // 搜索**不在这里做**：搜索框是受控 input，必须在 JS 之外用 CDP
    // Input.insertText 输入（见 search_expert）。这里只确认搜索框在。
    const si = document.querySelector('.ec-search-wrapper input');
    if (!si) return { ok: false, err: '专家中心没有搜索框' };
    return { ok: true, searchBox: true };
  }
  const tabName = (kind === 'team') ? '专家团' : '专家';
  const tab = Array.from(document.querySelectorAll('.ec-list-tab')).find(x => T(x) === tabName);
  if (!tab) return { ok: false, err: '没有列表 tab ' + tabName };
  if (tab.className.toString().indexOf('is-active') === -1) realClick(tab);
  const cat = Array.from(document.querySelectorAll('.ec-category-tab')).find(x => T(x) === '全部');
  if (cat && cat.className.toString().indexOf('is-active') === -1) realClick(cat);
  return { ok: true, tab: tabName };
})()
"""

EXPERT_SUMMON_STEP = r"""
(async (kind, idx) => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  // 卡片是虚拟列表（react-virtuoso）异步渲染的：切 tab / 搜索后不能立刻取，
  // 必须在这里轮询等它出来。窗口可见的前提下这样等是准的（窗口 hidden 时
  // 虚拟列表永远渲染 0 项，见 cdp.unhide 的说明）。
  let cards = [];
  for (let i = 0; i < 30; i++) {
    cards = Array.from(document.querySelectorAll('.ec-expert-card'));
    if (cards.length) break;
    if (i === 6) {
      // 轻轻推一下滚动容器，帮虚拟列表把可视区算出来
      const ms = document.querySelector('.ec-main-scroll');
      if (ms) ms.scrollTop = Math.min(260, ms.scrollHeight - ms.clientHeight);
    }
    await sleep(600);
  }
  if (!cards.length) {
    const g = document.querySelector('.ec-expert-grid');
    return { ok: false, err: '卡片列表为空',
             gridItems: document.querySelectorAll('.ec-expert-grid-item').length,
             gridLen: g ? g.innerHTML.length : -1,
             featCards: document.querySelectorAll('.ec-featured-scene-card').length,
             count: (document.querySelector('.ec-expert-count') || {}).innerText || null };
  }
  const card = cards[(kind === 'search') ? 0 : idx] || cards[0];
  const name = T(card).replace(/^召唤\s*/, '').slice(0, 30);
  const btn = card.querySelector('.ec-card-summon-btn')
    || Array.from(card.querySelectorAll('button')).find(b => /召唤/.test(T(b)));
  if (!btn) return { ok: false, err: '卡片没有召唤按钮', name: name };
  realClick(btn);
  return { ok: true, name: name, clicked: true, nCards: cards.length };
})()
"""

# 专家团二次确认：先勾选，再点「继续使用」。拆成两步是因为弹窗动画 + 按钮
# disabled → enabled 的切换需要时间，放同一步里等又要被节流放大。
EXPERT_CONFIRM_CHECK_STEP = r"""
(async () => {
  const ov = document.querySelector('.ec-team-summon-confirm-overlay');
  if (!ov) return { ok: true, dialog: false };
  const lab = ov.querySelector('label.ec-confirm-dialog-checkbox');
  if (lab) realClick(lab);
  return { ok: true, dialog: true, checked: !!lab };
})()
"""

EXPERT_CONFIRM_GO_STEP = r"""
(async () => {
  const ov = document.querySelector('.ec-team-summon-confirm-overlay');
  if (!ov) return { ok: true, dialog: false, confirmed: false };
  const go = ov.querySelector('[data-track-id=expert_team_confirm_continue]')
    || Array.from(ov.querySelectorAll('button')).find(b => /继续使用/.test(b.textContent || ''));
  if (!go) return { ok: false, err: '确认弹窗里没有「继续使用」按钮' };
  if (go.disabled) return { ok: false, err: '「继续使用」仍为禁用态（未勾选成功）' };
  realClick(go);
  return { ok: true, dialog: true, confirmed: true };
})()
"""

EXPERT_STATE_STEP = r"""
(async () => {
  // 点完「继续使用」后客户端要切到新会话视图，contenteditable 输入框挂载有延迟
  // （旧版单次快照在挂载完成前就返回 ok=false，整轮候选被误杀，见 2026-09-20 日志
  //   「前置步骤失败：[(3, 'ok=false')]」）→ 这里轮询最多 20s 等它出现。
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  let ed = null;
  for (let i = 0; i < 40; i++) {
    ed = document.querySelector('[contenteditable=true]');
    if (ed) break;
    await sleep(500);
  }
  return { ok: !!ed, composer: !!ed,
           guide: ed ? (ed.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 50) : null,
           stillDialog: !!(document.querySelector('.ec-team-summon-confirm-overlay')
             || Array.from(document.querySelectorAll('[class*="_dialogOverlay"]'))
               .some(el => (el.innerText || '').indexOf('我已知悉并确认') !== -1)) };
})()
"""

# --------------------------------------------------------------------------- #
# 专家团：必须走真人路径（2026-09-19 实测查清的根因，别再退回老写法）
#
# 事实（三次真机对照实验）：
#   1) 卡片角落那个小「召唤」按钮点了**不会**弹「使用提醒」，团队也不成立 ——
#      实测只把团队推荐提示词塞进输入框，发出去后全程只有 1 个 agent 回话，
#      进度永远 0/3。v1/v2/v3 三次实验都是这条路，全 0/3。
#   2) 真人路径「点整张卡片 → 团队详情弹窗 → 点弹窗里的『召唤专家团』」
#      **会**弹「使用提醒」确认框（含「我已知悉并确认」+「继续使用」/「取消」）。
#      不点掉它，团队根本不成立，会话发出去也不计数。
#   3) 桌面端这个确认框的类名是 **CSS-Module 哈希化**的（实测 `_dialogOverlay_peiew_7`），
#      所以老的 `.ec-team-summon-confirm-overlay` 选择器**永远匹配不到** →
#      确认框一直挂着 → 团队永不成立 → 长期 0/3。
#      当年 a/b/c 能 3/3 是因为那时客户端还用着未哈希的类名；客户端一升级就全废。
#      （这条被误诊成「额度用尽」很久，其实是选择器过期。）
#      所以现在改为**按文案定位**，与类名哈希彻底解耦。
# --------------------------------------------------------------------------- #
EXPERT_TEAM_OPEN_MODAL_STEP = r"""
(async () => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  // ⚠️ 2026-09-20 实测：连跑多个团队时，上一个团队的详情弹窗/遮罩没关干净，
  //    会挡住下一张卡片的点击 → 弹窗打不开 → 「找不到召唤专家团」→ 整个候选
  //    白跑（日志里 4 个候选连续报这个错）。所以**先清理残留遮罩**再点卡片。
  try { await closeOverlays(3); } catch (e) {}
  document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}));
  await sleep(600);
  let cards = [];
  for (let i = 0; i < 30; i++) {
    cards = Array.from(document.querySelectorAll('.ec-expert-card'));
    if (cards.length) break;
    await sleep(600);
  }
  if (!cards.length) return { ok: false, err: '专家团卡片列表为空' };
  const idx = %d;
  const card = cards[idx] || cards[0];
  const name = T(card).replace(/^召唤\s*/, '').slice(0, 24);
  // 点卡片 → 等详情弹窗；没出来就再点一次（首次点击可能被残留遮罩吃掉）
  let btn = null;
  for (let attempt = 0; attempt < 2; attempt++) {
    realClick(card);
    for (let i = 0; i < 16; i++) {
      await sleep(500);
      btn = document.querySelector('.ec-modal-summon-btn');
      if (btn && isVisible(btn)) break;
      btn = null;
    }
    if (btn) break;
    document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}));
    await sleep(800);
  }
  if (!btn) return { ok: false, err: '团队详情弹窗没出来（找不到 .ec-modal-summon-btn）', name: name };
  return { ok: true, name: name, modal: true, nCards: cards.length };
})()
"""

EXPERT_TEAM_MODAL_SUMMON_STEP = r"""
(async () => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const ACK = '我已知悉并确认';
  const ackVisible = () => Array.from(document.querySelectorAll('*'))
    .some(el => (el.innerText || '').indexOf(ACK) !== -1);
  let btn = null;
  for (let i = 0; i < 20; i++) {
    btn = document.querySelector('.ec-modal-summon-btn');
    if (btn) break;
    await sleep(400);
  }
  if (!btn) return { ok: false, err: '弹窗里找不到「召唤专家团」' };
  if (btn.disabled) return { ok: false, err: '「召唤专家团」是禁用态' };
  realClick(btn);
  // 等「使用提醒」确认框出现。注意：这个弹窗**不是每个团队都有** ——
  // 实测它只在「金融风险提示」类团队（如交易分析团队）弹出，内容创作类团队直接进；
  // 而且带「不再提示」，用户勾过就不再出现。所以**只等、不强制**：
  // 出现就交给 EXPERT_TEAM_ACK_STEP 点掉，没出现就正常往下走。
  for (let i = 0; i < 24; i++) {
    if (ackVisible()) return { ok: true, dialog: true, summonText: T(btn).slice(0, 16) };
    await sleep(500);
  }
  return { ok: true, dialog: false, note: '无确认框（该类团队不需要）' };
})()
"""

EXPERT_TEAM_ACK_STEP = r"""
(async () => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const ACK = '我已知悉并确认', GO = '继续使用';
  const boxes = () => Array.from(document.querySelectorAll('*'))
    .filter(el => (el.innerText || '').indexOf(ACK) !== -1);
  if (!boxes().length) return { ok: true, dialog: false, note: '无需确认' };
  // 取「最小的」那个容器 —— 避免拿到整页 body
  const dlg = boxes().sort((a, b) => (a.innerText || '').length - (b.innerText || '').length)[0];

  // 1) 勾「我已知悉并确认」
  let checked = false;
  const lab = Array.from(dlg.querySelectorAll('label')).find(l => (l.innerText || '').indexOf(ACK) !== -1);
  if (lab) { realClick(lab); checked = true; }
  else {
    const sp = Array.from(dlg.querySelectorAll('span,div')).find(s => T(s) === ACK);
    if (sp) { realClick(sp); checked = true; }
  }
  await sleep(800);

  // 2) 点「继续使用」—— ⚠️ 不能只在 dlg 里找！2026-09-20 实测：
  //    dlg（最小容器 _dialogContent_*）只有正文+checkbox，**按钮在外层 overlay**
  //    （_dialogOverlay_peiew_7 / ec-team-summon-confirm-overlay）。
  //    另：按钮**渲染比弹窗正文晚**（实测先有正文、后出 footer 按钮）→
  //    必须「等它出现」+「等它解禁（勾选后才从 disabled 变可点）」，两步都要轮询，
  //    否则会在按钮还没挂载时就判「找不到」直接失败（2026-09-20 就这样白跑一次）。
  const findGo = () => document.querySelector('[data-track-id=expert_team_confirm_continue]')
    || Array.from(document.querySelectorAll('button')).find(b => (b.innerText || '').indexOf(GO) !== -1);
  let go = null, enabled = false;
  for (let i = 0; i < 24; i++) {
    go = findGo();
    if (go && !go.disabled) { enabled = true; break; }
    // 还没解锁就再勾一次（有的实现第一次点击 label 没吃上）
    if (i > 0 && i % 4 === 0) {
      const lab2 = Array.from(document.querySelectorAll('label')).find(l => (l.innerText || '').indexOf(ACK) !== -1);
      if (lab2) realClick(lab2);
    }
    await sleep(500);
  }
  if (!go) return { ok: false, err: '确认框里找不到「继续使用」（等了 12s 也没出现）', checked: checked };
  if (!enabled) return { ok: false, err: '「继续使用」仍为禁用态（勾选没生效）', checked: checked };
  realClick(go);

  // 3) 等确认框真正消失
  for (let i = 0; i < 24; i++) {
    await sleep(500);
    if (!boxes().length) return { ok: true, dialog: true, checked: checked, confirmed: true };
  }
  return { ok: false, err: '点完「继续使用」确认框仍在' };
})()
"""


def ack_team_summon_confirm(**kw):
    """用**真实鼠标**点掉「积分消耗提醒」确认框（Python 步骤）。

    为什么不用 JS 合成事件（EXPERT_TEAM_ACK_STEP）：
    2026-09-20 实测 11 次团队召唤里 **9 次死在确认框**、`sent=false`（消息根本没发出）——
    勾选框是 React 受控组件，合成 MouseEvent 点 label 不触发 onChange
    →「继续使用」一直是 disabled → 授权不通过。
    这跟「输入框权限」那个弹窗是同一个坑（当时也是必须真实鼠标点可见 label）。
    全流程：真实点 checkbox → 等按钮解禁 → 真实点「继续使用」→ 等弹窗消失。
    确认框不存在（该类团队不需要）时直接放行。
    """
    def _state():
        return U.js(r"""
(() => {
  const ov = document.querySelector('.ec-team-summon-confirm-overlay')
          || document.querySelector('[class*="_dialogOverlay"]');
  const ack = Array.from(document.querySelectorAll('*'))
    .some(el => (el.innerText || '').indexOf('我已知悉并确认') !== -1);
  const go = document.querySelector('[data-track-id=expert_team_confirm_continue]');
  const cb = document.querySelector('.ec-confirm-dialog-checkbox');
  return { has: !!ov && ack, go: !!go, goDisabled: go ? go.disabled : null,
           cb: !!cb,
           cbChecked: (() => { if (!cb) return null;
             const inp = cb.querySelector('input') || cb.previousElementSibling;
             return inp && 'checked' in inp ? inp.checked : null; })() };
})()
""", timeout=40)

    st = _state()
    if not (isinstance(st, dict) and st.get("has")):
        # ⚠️ 2026-09-20 实锤：确认框没弹 = 授权事件没发 = 团队对话**不计分**。
        # 老写法这里直接放行（"该类团队不需要"），结果 suppress 键被并发完成的其他
        # 团队会话写回 true 时，召唤静默跳过确认框 → 整轮白跑。现在：再清一次键、
        # 最多等 15s 让确认框出现；仍不出现就**判失败**（pre_must_ok 会拦住不发消息）。
        try:
            U.reset_team_summon_suppress()
        except Exception:
            pass
        for _ in range(30):
            time.sleep(0.5)
            st = _state()
            if isinstance(st, dict) and st.get("has"):
                break
        if not (isinstance(st, dict) and st.get("has")):
            return {"ok": False, "dialog": False,
                    "err": "确认框未弹出（已再清一次 suppress 键并等 15s）——授权事件不会触发，拒绝继续"}

    # 1) 真实鼠标点「我已知悉并确认」的 label
    r1 = U.mouse_click("document.querySelector('.ec-confirm-dialog-checkbox')"
                       " || Array.from(document.querySelectorAll('label'))"
                       ".find(l => (l.innerText || '').indexOf('我已知悉并确认') !== -1)")
    checked = False
    for _ in range(20):
        time.sleep(0.4)
        st = _state()
        if isinstance(st, dict) and st.get("go") and st.get("goDisabled") is False:
            checked = True
            break
        # 还没解禁：再真实点一次 label（偶发第一次没吃上）
        U.mouse_click("document.querySelector('.ec-confirm-dialog-checkbox')"
                      " || Array.from(document.querySelectorAll('label'))"
                      ".find(l => (l.innerText || '').indexOf('我已知悉并确认') !== -1)")
    if not checked:
        return {"ok": False, "err": "勾选「我已知悉并确认」未生效（继续使用仍禁用）",
                "click": r1, "state": st}

    # 2) 真实鼠标点「继续使用」
    r2 = U.mouse_click("document.querySelector('[data-track-id=expert_team_confirm_continue]')")
    for _ in range(20):
        time.sleep(0.5)
        st = _state()
        if isinstance(st, dict) and not st.get("has"):
            return {"ok": True, "dialog": True, "checked": True, "confirmed": True,
                    "click_cb": r1, "click_go": r2}
    return {"ok": False, "err": "点了「继续使用」确认框仍在", "click_go": r2, "state": st}


def _team_name_eq(card_title, want):
    """卡片标题与团队名的宽容匹配（标题可能带前后缀或被截断）。"""
    a = (card_title or "").strip()
    b = (want or "").strip()
    if not a or not b:
        return False
    return a == b or a in b or b in a


def list_team_cards():
    """运行时读「专家团」tab 的真实卡片名单（顺序 = 卡片下标）。

    2026-09-20 教训：服务端会整表更换卡片名单/顺序，静态 TEAM_NAMES 必然过期，
    按硬编码下标召唤会点错团队。召唤一律以这里的真实名单 + 名字定位。
    读不到返回 []，调用方应据此中止而不是退回旧下标盲试。
    """
    # 实测面板在两次调用之间可能被 app 关掉/重置，单次探测偶发读空 —— 重试一次基本必成。
    for attempt in range(2):
        r = U.js(r"""
(async () => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const entry = () => Array.from(document.querySelectorAll('button.conversation-list-tab-button'))
    .find(b => T(b).indexOf('专家') !== -1);
  const up = () => !!document.querySelector('.ec-list-tab');
  for (let round = 0; round < 3; round++) {
    if (up()) break;
    if (!entry()) { await sleep(1200); continue; }
    entry().click();
    await sleep(1800);
    for (let i = 0; i < 20 && !up(); i++) await sleep(600);
  }
  if (!up()) return { ok: false, err: '专家中心没加载出来' };
  let tab = Array.from(document.querySelectorAll('.ec-list-tab')).find(x => T(x) === '专家团');
  if (!tab) return { ok: false, err: '没有「专家团」tab' };
  if ((tab.className || '').toString().indexOf('is-active') === -1) {
    tab.click(); await sleep(2800);
  }
  await sleep(1000);
  let cards = [];
  for (let i = 0; i < 20; i++) {
    cards = Array.from(document.querySelectorAll('.ec-expert-card'));
    if (cards.length) break;
    await sleep(600);
  }
  const names = cards.map(c => {
    const t = c.querySelector('.ec-card-title, h3, [class*="title"]');
    return (t && T(t)) ? T(t) : T(c).replace(/^召唤\s*/, '').slice(0, 24);
  });
  return { ok: cards.length > 0, names: names };
})()
""", timeout=90)
        if isinstance(r, dict) and r.get("ok"):
            return [str(x) for x in (r.get("names") or [])]
        time.sleep(3.0)
    return []


def summon_team_by_index(idx, want_name=None):
    """一次调用内完成：确保专家中心打开 → 切「专家团」→ 点第 idx 张卡片 → 点弹窗内「召唤专家团」。

    为什么要合并成一步（2026-09-20 实测教训）：专家中心面板**在两次独立 CDP 调用之间会被关掉**
    （app 单视图、切号/重绘后回落），于是「点开弹窗」这一步经常报「卡片列表为空」
    → pre_must_ok 拦下 → 消息根本没发出去（11 次里 9 次这样）。
    把「开面板/切 tab/点卡片/点召唤」放进同一个 Python 步骤里连续执行（每段仍各自等待渲染），
    面板被关掉的窗口就从「步与步之间」缩短到几乎为零。

    返回：{ok, stage, nCards, name, dialog} —— stage 标明卡在哪一阶段，便于排查。
    """
    # 1) 确保面板打开并切到「专家团」
    r1 = U.js(r"""
(async () => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const entry = () => Array.from(document.querySelectorAll('button.conversation-list-tab-button'))
    .find(b => T(b).indexOf('专家') !== -1);
  const up = () => !!document.querySelector('.ec-list-tab');
  for (let round = 0; round < 3; round++) {
    if (up()) break;
    const e = entry();
    if (!e) return { ok: false, stage: 'entry', err: '侧边栏找不到专家入口' };
    const rc = e.getBoundingClientRect();
    e.dispatchEvent(new MouseEvent('click', {bubbles:true, clientX:rc.x+rc.width/2, clientY:rc.y+rc.height/2}));
    for (let i = 0; i < 24; i++) { await sleep(500); if (up()) break; }
  }
  if (!up()) return { ok: false, stage: 'panel', err: '专家中心打不开' };
  await sleep(1500);
  const tab = Array.from(document.querySelectorAll('.ec-list-tab')).find(x => T(x) === '专家团');
  if (tab && (tab.className || '').toString().indexOf('is-active') === -1) {
    const rc = tab.getBoundingClientRect();
    tab.dispatchEvent(new MouseEvent('click', {bubbles:true, clientX:rc.x+rc.width/2, clientY:rc.y+rc.height/2}));
    await sleep(3000);
  }
  await sleep(1500);
  // 等卡片出现
  let cards = [];
  for (let i = 0; i < 30; i++) {
    cards = Array.from(document.querySelectorAll('.ec-expert-card'));
    if (cards.length) break;
    await sleep(600);
  }
  return { ok: true, stage: 'panel-ok', nCards: cards.length };
})()
""", timeout=180)
    if not (isinstance(r1, dict) and r1.get("ok")):
        return r1

    # 1.5) 按名字定位卡片下标（2026-09-20 改版教训：静态下标会点错团队）。
    #      want_name 优先；面板刚被 r1 打开且已停在「专家团」tab，这里只读不点。
    if want_name:
        names = list_team_cards()
        hit = next((i for i, nm in enumerate(names) if _team_name_eq(nm, want_name)), None)
        if hit is None:
            return {"ok": False, "stage": "cards", "want": want_name,
                    "err": "卡片名单里找不到团队 %r（实际 %s）" % (want_name, names)}
        idx = hit

    # 2) 定位第 idx 张卡片 → 滚动到可见（**不在这里点**）。
    #    ⚠️ A4（核验缺陷 #4）：老代码 `cards[idx] || cards[0]` 越界时**静默兜底到第 0 张**
    #    → 会跑错团队且难发现。现在越界直接失败。
    r2 = U.js(r"""
(async () => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const idx = %d;
  let cards = [];
  for (let i = 0; i < 30; i++) {
    cards = Array.from(document.querySelectorAll('.ec-expert-card'));
    if (cards.length) break;
    await sleep(600);
  }
  if (idx >= cards.length) {
    return { ok: false, stage: 'cards', idx: idx, nCards: cards.length,
             err: '卡片下标越界（拒绝兜底第 0 张，防止跑错团队）' };
  }
  const card = cards[idx];
  if (!card) return { ok: false, stage: 'cards', err: '卡片列表为空', nCards: cards.length };
  // 名字取卡片内标题元素（仅用于日志；A4：老 split(' ')[0] 解析出的是整段文本，不可信）
  const tEl = card.querySelector('.ec-card-title, h3, [class*="title"]');
  const name = (tEl && T(tEl)) ? T(tEl) : T(card).replace(/^召唤\s*/, '').slice(0, 16);
  // ⚠️ 必须点**卡片内部的 .ec-card-main**：点外层 article 不触发详情弹窗（2026-09-20 实测）。
  //    点击动作改由 Python 侧 **CDP 真实鼠标**完成（A5：合成 MouseEvent 在 React 上不可靠，
  //    今天 3 次「团队详情弹窗没出来」即此因）。
  const target = card.querySelector('.ec-card-main') || card;
  target.scrollIntoView({block: 'center', behavior: 'instant'});
  await sleep(600);
  return { ok: true, stage: 'card-located', name: name, nCards: cards.length, idx: idx };
})()
""" % idx, timeout=180)
    if not (isinstance(r2, dict) and r2.get("ok")):
        return r2

    # 2.1) CDP **真实鼠标**点卡片（A5）→ 等详情弹窗
    card_sel = ("(document.querySelectorAll('.ec-expert-card')[%d] || {})"
                ".querySelector('.ec-card-main')" % idx)
    rc_card = U.mouse_click(card_sel)
    btn_state = None
    for _i in range(40):
        time.sleep(0.5)
        btn_state = U.js("(() => { const b = document.querySelector('.ec-modal-summon-btn');"
                         " return b ? {ok: true, disabled: !!b.disabled} : {ok: false}; })()",
                         timeout=30)
        if isinstance(btn_state, dict) and btn_state.get("ok"):
            break
    if not (isinstance(btn_state, dict) and btn_state.get("ok")):
        return {"ok": False, "stage": "modal", "name": r2.get("name"), "click": rc_card,
                "err": "团队详情弹窗没出来（真实点击后 20s 内无 .ec-modal-summon-btn）"}
    if btn_state.get("disabled"):
        return {"ok": False, "stage": "modal", "err": "「召唤专家团」是禁用态", "name": r2.get("name")}

    # 3) CDP **真实鼠标**点弹窗里的「召唤专家团」→ 等「积分消耗提醒」确认框（可能没有）（A5）
    rc_btn = U.mouse_click("document.querySelector('.ec-modal-summon-btn')")
    r3 = U.js(r"""
(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const ACK = '我已知悉并确认';
  const ackVisible = () => Array.from(document.querySelectorAll('*'))
    .some(el => (el.innerText || '').indexOf(ACK) !== -1);
  for (let i = 0; i < 30; i++) {
    if (ackVisible()) return { ok: true, stage: 'summoned', dialog: true };
    await sleep(500);
  }
  return { ok: true, stage: 'summoned', dialog: false, note: '无确认框（该类团队不需要）' };
})()
""", timeout=180)
    return {"ok": bool(isinstance(r3, dict) and r3.get("ok")),
            "stage": (r3 or {}).get("stage"), "name": r2.get("name"),
            "nCards": r2.get("nCards"), "dialog": (r3 or {}).get("dialog"),
            "err": (r3 or {}).get("err"), "panel": r1, "modal": r2, "summon": r3,
            "click_card": rc_card, "click_btn": rc_btn}


def _as_fn(src):
    """把 '(async (a) => {...})()' 还原成函数表达式 '(async (a) => {...})'。

    坑：这些常量写成「立即调用的 IIFE」是为了能直接当 pre_steps 用；
    但要拿它当函数传给别的代码时，必须先把尾部那对 `()` 去掉 ——
    否则 `const f = (async()=>{})()` 拿到的是 Promise，调用 f(...) 会报
    「TypeError: f is not a function」（踩过两次了）。
    """
    s = (src or "").rstrip()
    if s.endswith("()"):
        s = s[:-2]
    return s


def search_expert(kw):
    """在专家中心的搜索框里输入关键词。

    **必须走 CDP，不能在 JS 里改 input.value。** 搜索框是 React 受控组件，
    直接赋值不触发 onChange，列表不刷新。

    `setReactInput()` 是定义在 ui_tasks.HELPERS 里的（`_js_block` 会注入），
    **但它不在 ui_driver.PRELUDE 里**。而这一步是作为 pre_steps 的一项经 `js()`
    执行的（只注入 PRELUDE）→ 引用它就抛 ReferenceError。
    异常又被 run_task 里 pre_steps 的 except 吞掉 → 搜索静默失效 →
    最后召唤的是列表里第一个专家（实测召成了「微信小程序开发者」），
    Expert_lighthouse 因此长期 0/1。
    教训：**JS 里用到的助手，先确认它真的在那次注入的作用域里**（PRELUDE？HELPERS？）。
    """
    cdp, page = C.connect()
    try:
        ok = cdp.evaluate(
            "(function(){var e=document.querySelector('.ec-search-wrapper input');"
            "if(!e) return false; e.focus(); if(e.select) e.select(); return true;})()",
            timeout=25)
        if not ok:
            return {"ok": False, "err": "找不到专家搜索框"}

        def key(t, k, code, vk, mods=0):
            cdp.call("Input.dispatchKeyEvent", {
                "type": t, "modifiers": mods, "key": k, "code": code,
                "windowsVirtualKeyCode": vk, "nativeVirtualKeyCode": vk}, timeout=15)

        key("keyDown", "a", "KeyA", 65, 2)     # modifiers=2 -> Ctrl+A 全选
        key("keyUp", "a", "KeyA", 65, 2)
        key("rawKeyDown", "Backspace", "Backspace", 8)
        key("keyUp", "Backspace", "Backspace", 8)
        time.sleep(0.5)
        # CDP 派发的键事件是 isTrusted=true，会被「用户活动」监听器当成真人打字
        # → 后续任务误判让路。搜索这类高频动作必须明确置位。
        U.driver_typing(True)
        cdp.call("Input.insertText", {"text": kw}, timeout=25)
        time.sleep(0.8)
        val = cdp.evaluate(
            "(function(){var e=document.querySelector('.ec-search-wrapper input');"
            "return e ? e.value : null;})()", timeout=20)
        return {"ok": True, "searched": kw, "value": val}
    finally:
        try:
            U.driver_typing(False)
        except Exception:
            pass
        cdp.close()


def _search_step(kw):
    """把 search_expert 包成 pre_steps 可用的一步（无参可调用对象）。"""
    def _do():
        return search_expert(kw)
    return _do


def _expert_steps(kind, kw, idx, team_name=None):
    """构造 (pre_steps, pre_gap) —— 每步一次独立调用，间隔由 Python 控制。

    步骤既可以是 JS 字符串（走 CDP Runtime.evaluate），也可以是 Python 可调用对象
    （用于 JS 做不了的事，如往受控 input 里输入搜索词）。

    仍然分步的理由：专家中心首屏挂载较重，把「点击 → 等渲染 → 再点击」拆成
    独立调用，比在一次 JS 里连等更稳，也更好定位失败点（失败看 out["pre_steps"]）。

    间隔取值：前提是窗口可见（cdp.unhide 已保证）。窗口 hidden 时这些间隔会被
    节流放大十几倍，那时 5s 根本不够 —— 所以先确认 document.hidden=false。
    """
    pick_fn = _as_fn(EXPERT_PICK_STEP)
    summon_fn = _as_fn(EXPERT_SUMMON_STEP)

    # 专家团走**独立**路径：点卡片开详情弹窗 → 弹窗内召唤 → 按文案点掉「使用提醒」。
    # 别再退回「点卡片角落小按钮 + .ec-team-summon-confirm-overlay」的老写法，
    # 那条路已被三次真机实验证明永远 0/3（原因见 EXPERT_TEAM_OPEN_MODAL_STEP 的注释）。
    if kind == "team":
        # ⚠️ 2026-09-20 破案后重构（三步合一，见 summon_team_by_index 的 docstring）：
        #   0) 清「团队召唤确认框」抑制标记：suppress 键存在 → 客户端跳过确认框 →
        #      授权流程没走 → 协作不启动（nAg=1）→ 不计分。
        #   1) 一步完成「开面板 → 切专家团 → 点第 idx 张卡 → 点弹窗召唤」
        #      —— 面板在两次调用间会被关掉，分步做 11 次里 9 次报「卡片列表为空」。
        #   2) 真实鼠标点掉确认框（合成事件点不动 React 勾选框）。
        #   3) 读状态收尾。
        return ([U.reset_team_summon_suppress,
                 (lambda idx=idx, nm=team_name: summon_team_by_index(idx, want_name=nm)),
                 ack_team_summon_confirm,
                 EXPERT_STATE_STEP],
                [2, 3, 2, 2])

    steps = [EXPERT_ENTER_STEP]
    gaps = [6]
    if kind == "search":
        steps.append("(async () => { const f = %s; return await f(%s, null, 0); })()"
                     % (pick_fn, json.dumps(kind)))
        gaps.append(2)
        steps.append(_search_step(kw))     # Python 步骤：CDP 真实输入
        gaps.append(7)
    else:
        steps.append("(async () => { const f = %s; return await f(%s, null, 0); })()"
                     % (pick_fn, json.dumps(kind)))
        gaps.append(5)
    steps.append("(async () => { const f = %s; return await f(%s, %d); })()"
                 % (summon_fn, json.dumps(kind), idx))
    gaps.append(5)
    # 注意：kind == "team" 已在函数开头单独 return，不会走到这里。
    steps.append(EXPERT_STATE_STEP)
    gaps.append(2)
    return steps, gaps


def current_account_name():
    """当前客户端登录账号昵称（读左下角 .user-menu-trigger）。"""
    try:
        return U.js("(document.querySelector('.user-menu-trigger')||{innerText:''})"
                    ".innerText.trim().slice(0,40)", timeout=25)
    except Exception:
        return None


def run_expert_once(kind="expert", kw=None, idx=0, prompt=None, model=None,
                    delete_after=True, max_wait=240, verbose=False, team_first_reply=False,
                    expect_nick=None, team_name=None):
    """召唤一个专家/专家团 → 发一句话 → 等对话结束 →（默认）删掉会话。

    重要：**召唤本身不计分**。召唤只是把专家预填进输入框（还带一段引导语），
    服务端只在真正产生一次专家对话时才计数 —— 实测「只召唤」进度不动，
    「召唤后发一句话」立刻 +1。所以必须走 run_task 把消息发出去。

    team_first_reply=True（专家团专用）：检测到 AI 首段稳定回复即判完成，
    不等整队多智能体协作跑完 —— 对应「发起对话、对方回复完就算完成」。

    keep_input=True：不能清空输入框，否则会把预填的专家引导语一起 Ctrl+A 删掉。

    流程用 pre_steps 分步执行（每步一次独立 CDP 调用），原因见本文件顶部
    「专家中心：分步驱动」的说明 —— 一步到位会被页面卡顿拖到超时。
    """
    # prompt=None → 用默认那句；prompt="" → **什么都不输入**，直接发输入框里已有的内容。
    # 专家团例外（A2 修复）：不管调用方传什么，一律改发 TEAM_SELF_CONTAINED_PROMPT ——
    # 它会被 type_text 追加在输入框已有的团队推荐词后面（keep_input=True 保 chip），
    # 作用是压住「推荐词要素材 → 团队反问 → 挂起」的老问题。
    if prompt is None:
        prompt = "用一句话简单介绍你自己。直接回答，不要反问。"
    if kind == "team":
        prompt = TEAM_SELF_CONTAINED_PROMPT

    # ★ 账号硬闸（2026-09-20 用户投诉「跑任务从来不看在哪个账号下面执行」后加的）：
    #   传了 expect_nick 就必须先核对当前登录昵称，对不上**拒绝执行**，
    #   绝不能把任务跑到别的账号上（用户额度不能替别人烧）。
    if expect_nick:
        cur = current_account_name()
        if not (cur and str(expect_nick) in str(cur)):
            return {"ok": False, "expect_nick": expect_nick, "current_nick": cur,
                    "err": "账号核对失败：当前=%s，期望=%s —— 拒绝在错误账号上执行" % (cur, expect_nick)}

    # 专家团对模型敏感：Hy3 会让多智能体协作静默退化（不计数），必须换成 TEAM_MODEL。
    # 只有调用方**显式**传了 model 才尊重它；默认 None 时按团队类型自动挑选。
    if model is None and kind == "team":
        model = TEAM_MODEL

    steps, gaps = _expert_steps(kind, kw, idx, team_name=team_name)
    r = U.run_task(template=None, prompt=prompt, model=model, use_template=False,
                   pre_steps=steps, pre_gap=gaps, keep_input=True, pre_clear=True,
                   pre_must_ok=True,      # 召唤/切 tab 失败就别发消息，别制造假会话
                   delete_after=delete_after, max_wait=max_wait,
                   team_first_reply=team_first_reply,
                   # 专家团：idle-stable 阈值拉到 60s（120 次 × 500ms）。
                   # 团队 agent 之间有 >2s 的天然停顿，默认 2s 阈值会在轮次中途
                   # 误判完成提前收工 → 服务端不计分（nAg=1、+0 的根因，2026-09-20）。
                   idle_stable_polls=(120 if kind == "team" else 4))
    # 2026-09-20 用户指示落地：免费模型（Hy3）额度用尽（429）→ 删掉这条废会话、
    # 换自定义模型（默认 agnes 2.5，env WB_CUSTOM_MODEL 可覆盖）重试一次。
    # 废会话必须删：它不计分，标题还会让账本把该团队误标成「已用」。
    if kind == "team" and (r.get("run") or {}).get("reason") == "quota-exhausted":
        _custom = os.environ.get("WB_CUSTOM_MODEL", "agnes 2.5")
        if (r.get("model") or TEAM_MODEL) != _custom:
            _dead_title = r.get("created_title")
            if _dead_title:
                try:
                    U.delete_conversation(_dead_title, force=True)
                except Exception:
                    pass
            r2 = U.run_task(template=None, prompt=prompt, model=_custom, use_template=False,
                            pre_steps=steps, pre_gap=gaps, keep_input=True, pre_clear=True,
                            pre_must_ok=True, delete_after=delete_after, max_wait=max_wait,
                            team_first_reply=team_first_reply, idle_stable_polls=120)
            r2["retried_with"] = _custom
            r2["first_try_model"] = r.get("model")
            if verbose:
                print(json.dumps(r2, ensure_ascii=False, indent=2))
            return r2
    if verbose:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    return r


def _finish_expert(out, runs):
    out["runs"] = runs
    out["n_ok"] = sum(1 for x in runs if x["ok"])
    out["ok"] = out["n_ok"] >= out["need"]
    if not out["ok"]:
        out["err"] = "只成功 %d/%d 次" % (out["n_ok"], out["need"])
    return out


def do_expert_5(need=5, start=0, budget=240, **kw):
    """expert_5：召唤 need 位专家、各聊一句（每次 +1 进度）。

    budget：总时长预算（秒），兜底防止额度耗尽时无限等待。
    """
    out = {"need": need, "kind": "expert"}
    runs = []
    t0 = time.time()
    for i in range(need):
        # 用户点「停止任务」要**立刻**收手 —— 以前这里不看停止标志，
        # 5 个专家串行跑完要十几分钟，按了停也停不下来（用户投诉过）。
        if U.stop_requested():
            out["stopped"] = True
            out["aborted"] = "收到停止指令，中止剩余 %d 位专家" % (need - i)
            break
        if budget and (time.time() - t0) > budget:
            out["aborted"] = "超时保护：已达预算 %.0fs，中止剩余 %d 位专家" % (budget, need - i)
            out["aborted_at"] = i
            break
        r = run_expert_once(kind="expert", idx=start + i, **kw)
        pre = r.get("pre") or {}
        runs.append({"i": i, "idx": start + i, "ok": bool(r.get("ok")),
                     "expert": pre.get("name"), "summoned": bool(pre.get("ok")),
                     "created": r.get("created_title"),
                     "deleted": bool((r.get("deleted") or {}).get("ok")),
                     "err": r.get("err") or pre.get("err")})
        time.sleep(1.5)
    return _finish_expert(out, runs)


# 专家团名单：**以运行时 DOM 实测为准**（list_team_cards()），以下常量只做兜底与排序参考。
# ⚠️ 2026-09-20 18:20 实测改版教训：服务端把卡片名单/顺序整表换了（MVP开发/游戏工作室/
# 软件工坊/工程保障/智数分析下架；新增 腾讯自选股/产品战略/财税合规/专业文档/内容变现），
# 旧静态下标全部错位 —— 按 idx 召唤点的是完全不同的团队（旧表 idx=7=软件工坊，实际点成
# 产品战略团队；idx=2=游戏工作室，实际点成交易分析团队=已用团队必 +0）。这是长期 +0 的
# 系统性根因。所以候选一律**按名字驱动**：list_team_cards() 读真实名单 → TEAM_PREFERRED
# 排序 → 剔除已用/已试 → summon_team_by_index(idx, want_name=名字) 按名字定位卡片。
TEAM_NAMES = ["腾讯自选股股票投研专家团", "软件开发团队", "交易分析团队",
              "深度研究团队", "内容创作专家团", "独董会", "腾讯云技术支持",
              "产品战略团队", "财税合规专家团", "专业文档生成团队",
              "内容变现商业化专家团", "科研专家团"]

# 兼容别名：老探针/外部脚本可能仍按索引引用；顺序已与新名单对齐。
TEAM_CANDIDATE_IDX = list(range(len(TEAM_NAMES)))

# 候选优先顺序（名字）= 从「自包含、能自己收尾」到「要补材料/多阶段长流程」。
# 依据：独董会实测 ~130s 能收尾计分；财税合规/专业文档/内容变现为新上线自包含问答型
# （未实测，排前先试）；腾讯自选股大概率要持仓；产品战略团队 2026-09-20 实测多阶段
# 长流程（900s 未收尾），放最后兜底。不在真实名单里的名字会被自动跳过。
TEAM_PREFERRED = ["独董会", "财税合规专家团", "专业文档生成团队",
                  "内容变现商业化专家团", "腾讯自选股股票投研专家团",
                  "腾讯云技术支持", "软件开发团队", "交易分析团队",
                  "内容创作专家团", "深度研究团队", "科研专家团", "产品战略团队"]

# 账本比对表：会话标题特征词 → 团队名。
# 依据（2026-09-20 实测）：逐条点开会话读输入框 chip（cr-chip-label）得到的铁证映射 ——
#   "调研AI Agent企业级应用趋势" chip=深度研究团队；"开发贪吃蛇游戏并自我介绍" chip=软件开发团队；
#   "系统全面工程审查与事故响应" chip=工程保障团队；"生成CSV数据画像报告" chip=智数分析专家团；
#   "确定新产品品牌视觉方向…" chip=内容创作专家团；"分析茅台基本面与估值" chip=交易分析团队；
#   "我正在做一项关键决策…独立审议起手卡" chip=独董会。
# 用途：跑之前先读任务区会话标题，**跳过已经用过的团队** —— 服务端要求「3 个不同的专家团队」，
# 同一个团队第二次用必然 +0（2026-09-19 实证），重复试纯烧积分（用户明确要求"先验证已用哪些"）。
TEAM_LEDGER_SIGNS = [
    (["分析CSV", "CSV文件生成", "CSV数据画像", "数据画像报告"], "智数分析专家团"),
    (["新产品品牌视觉", "情绪板"], "内容创作专家团"),
    (["调研AI Agent", "AI Agent企业级"], "深度研究团队"),
    (["独立审议起手卡", "关键决策", "独立审议"], "独董会"),
    (["茅台", "基本面与估值", "持仓"], "交易分析团队"),
    (["贪吃蛇", "游戏并自我介绍"], "软件开发团队"),
    (["工程审查", "事故响应", "工程保障"], "工程保障团队"),
    (["DID", "政策处理效应", "发表级表格"], "科研专家团"),
    (["云资源风险", "轻量云", "云资源"], "腾讯云技术支持"),
    (["WriteFlow", "滚动叙事"], "软件工坊"),
    (["MVP", "产品原型"], "MVP开发专家团"),
    (["游戏开发", "游戏工作室"], "游戏开发工作室"),
    # 2026-09-20 改版后新增团队（标题特征来自实机会话）
    (["功能规格书", "竞品分析", "产品路线图"], "产品战略团队"),
]


def ledger_used_teams():
    """读任务区会话标题 → 反推该账号**已经用过**的专家团名集合。

    会话账本是「用过哪些团队」的最直接证据（每条会话标题 = 该团队的推荐提示词
    或 AI 首答标题）。跑之前先调它，把已用团队从候选里剔掉 —— 见 TEAM_LEDGER_SIGNS。
    注意：被我跑完删掉的会话不在账本里，所以这只是「部分账本」；宁可少判「已用」，
    也不要重复试（重复必 +0）。
    """
    titles = U.task_titles() or []
    blob = " ".join(str(t) for t in titles)
    used = set()
    for keys, name in TEAM_LEDGER_SIGNS:
        if any(k in blob for k in keys):
            used.add(name)
    return sorted(used), titles


def do_expert_team_3(need=3, start=0, budget=300, prog_fn=None, **kw):
    """Expert_team_use_3：召唤 need 个**不同**专家团、各聊一句。

    ⚠️ 2026-09-20 实测改判：专家团**必须等团队把这一轮说完**才计分
    （与单专家/普通对话「回复完就算」不同！）。曾试过 team_first_reply=True
    「首段稳定回复就收工+删会话」，account_e 连试 5 个团队全部 nAg=1、+0 ——
    首回复时其它 agent 还没加入（nAg=1），删会话把团队协作直接打断。
    唯一成功记录（2026-09-19 独董会 ~130s +1）用的是等整轮完成的旧逻辑。
    所以这里 **team_first_reply=False**，max_wait=300 等团队自然收尾；
    多阶段长流程团队 300s 不结束就算它 +0，换下一个候选。

    团队按**名字**取**不同**候选（先 list_team_cards() 读运行时真实卡片名单，
    再按 TEAM_PREFERRED 排序、剔除账本已用 —— 静态下标在 2026-09-20 服务端改版后
    全部错位，按 idx 召唤会点错团队，已废弃）。start 用于续跑。

    budget：本任务总时长预算（秒），兜底防卡死；达到预算中止剩余团队。
    """
    out = {"need": need, "kind": "team", "start": start}
    # 候选顺序 = 从「自包含、能自己收尾」到「要你补材料 / 多阶段长流程」。
    # ⚠️ 先剔除**账本里已经用过**的团队（服务端要求 3 个不同团队，重复必 +0）——
    #    用户明确要求「先验证已经用了哪些，别一直用重复的」。
    used, titles = ledger_used_teams()
    live = list_team_cards()
    if not live:
        out["ok"] = False
        out["err"] = ("读不到专家团真实卡片名单（DOM 探测失败）—— 拒绝按过期静态下标盲试"
                      "（2026-09-20 改版后按 idx 召唤=点错团队）")
        return out
    order = [n for n in TEAM_PREFERRED if n in live] + [n for n in live if n not in TEAM_PREFERRED]
    cands = [n for n in order if n not in used]
    out["ledger_used"] = sorted(used)
    out["ledger_n"] = len(titles)
    out["live_cards"] = live
    out["candidates"] = cands
    runs = []
    t0 = time.time()
    if not cands:
        out["ok"] = False
        out["err"] = "真实卡片名单里没有未用过的团队（已用 %s）" % sorted(used)
        return out
    for i in range(need):
        if U.stop_requested():
            out["stopped"] = True
            out["aborted"] = "收到停止指令，中止剩余 %d 个专家团" % (need - i)
            break
        if budget and (time.time() - t0) > budget:
            out["aborted"] = "超时保护：已达预算 %.0fs，中止剩余 %d 个专家团" % (budget, need - i)
            out["aborted_at"] = i
            break
        if i >= len(cands):
            break
        team_name = cands[i]
        # A2 修复：prompt 由 run_expert_once 内部统一改为 TEAM_SELF_CONTAINED_PROMPT
        #（追加在团队推荐词后，压住「推荐词要素材 → 团队反问 → 挂起不计分」的老问题）。
        # team_first_reply=False：必须等团队把这一轮说完；max_wait=1500 兜底。
        # （2026-09-20 实测：财税合规专家团是 6 阶段长流程，900s 也没跑完；超时未完成
        #   会被记入历史账本永久排除 —— 与其错过，不如一次给足。）
        c0 = prog_fn() if prog_fn else None
        r = run_expert_once(kind="team", idx=0, team_name=team_name, prompt="", max_wait=1500,
                           team_first_reply=False, **kw)
        c1 = prog_fn() if prog_fn else None
        delta = (c1 - c0) if (c0 is not None and c1 is not None) else None
        pre = r.get("pre") or {}
        runs.append({"i": i, "team": pre.get("name") or team_name,
                     "ok": bool(r.get("ok")),
                     "confirmed": pre.get("confirmed"), "summoned": bool(pre.get("ok")),
                     "reason": (r.get("run") or {}).get("reason"),
                     "delta": delta, "scored": bool(delta and delta > 0),
                     "created": r.get("created_title"),
                     "deleted": bool((r.get("deleted") or {}).get("ok")),
                     "err": r.get("err") or pre.get("err")})
        time.sleep(1.5)
    out["runs"] = runs
    out["n_ok"] = sum(1 for x in runs if x["ok"])
    # ★ A3（核验缺陷 #3）：成功与否**只认服务端进度**。以前这里拿「消息发出 + idle-stable」
    #   充当成功，进度 +0 也报 ok=True；没有进度核对函数就拒绝虚报成功。
    if prog_fn is None:
        out["ok"] = False
        out["err"] = ("未提供进度核对函数（prog_fn），无法确认服务端是否计分 —— 拒绝虚报成功；"
                      "run 层完成 %d/%d（仅供参考）" % (out["n_ok"], need))
        return out
    out["scored"] = sum(1 for x in runs if x.get("scored"))
    out["ok"] = out["scored"] >= need
    if not out["ok"]:
        out["err"] = out.get("err") or "服务端仅计分 %d/%d 个团队（run 层发出 %d 个）" % (
            out["scored"], need, out["n_ok"])
    return out


def do_expert_lighthouse(kw_search="轻量云", budget=240, **kw):
    """Expert_lighthouse：搜索并召唤「腾讯轻量云」专家、聊一句。

    budget：兼容保留参数。原入口守卫在 t0 赋值后立即判断、恒不触发（死代码），
    已移除；实际时长兜底由 run_expert_once 内部 max_wait 负责。
    """
    r = run_expert_once(kind="search", kw=kw_search, idx=0, **kw)
    pre = r.get("pre") or {}
    out = {"need": 1, "kind": "search", "kw": kw_search}
    return _finish_expert(out, [{
        "i": 0, "ok": bool(r.get("ok")), "expert": pre.get("name"),
        "summoned": bool(pre.get("ok")), "created": r.get("created_title"),
        "deleted": bool((r.get("deleted") or {}).get("ok")),
        "err": r.get("err") or pre.get("err")}])


# --------------------------------------------------------------------------- #
# 开盲盒（RichMeow_Chat 解锁的「限定款 Buddy 盲盒」需要手动开启才能拿到 Buddy）
# --------------------------------------------------------------------------- #
BLINDBOX_ENTER = r"""
(async () => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const vis = el => { const r = el.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
  // 侧边栏可能的入口：Buddy / 我的Buddy / Buddy馆 / 盲盒
  const names = ['盲盒', '我的Buddy', 'Buddy馆', 'Buddy'];
  const sb = Array.from(document.querySelectorAll('button.conversation-list-tab-button, .conversation-list-tab-button-sub'))
    .find(b => names.some(n => T(b).indexOf(n) !== -1));
  if (sb) { realClick(sb); await sleep(2500); }
  // 找「开盲盒 / 开启盲盒 / 拆开盲盒」按钮（只在按钮文案含「盲盒」时才认，避免误点别的「开启」）
  const openBtn = Array.from(document.querySelectorAll('button'))
    .filter(vis).find(b => /盲盒/.test(T(b)));
  return { ok: true, clickedSidebar: !!sb, sidebarName: sb ? T(sb) : null,
           openBtn: openBtn ? T(openBtn) : null, openBtnFound: !!openBtn };
})
"""

BLINDBOX_OPEN = r"""
(async () => {
  const T = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const vis = el => { const r = el.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
  const openBtn = Array.from(document.querySelectorAll('button'))
    .filter(vis).find(b => /盲盒/.test(T(b)));
  if (!openBtn) return { ok: false, err: '没找到「开盲盒」按钮' };
  realClick(openBtn);
  await sleep(3000);
  // 开启后可能弹确认框（「确定 / 开启」之类），点掉它
  const ok = Array.from(document.querySelectorAll('button')).filter(vis)
    .find(b => /^(确定|开启|开盒|拆开|确认|好的)$/.test(T(b)));
  if (ok) { realClick(ok); await sleep(2500); }
  return { ok: true, clicked: T(openBtn) };
})
"""


def do_open_blindbox(verbose=False):
    """open_blindbox：打开已解锁的「限定款 Buddy 盲盒」。

    背景：成长任务 RichMeow_Chat（桌面端对话1次）只是**解锁**盲盒，
    要真正拿到 Buddy 还得在「我的Buddy / Buddy馆」里点「开盲盒」。这一步没有公开
    接口，只能走 UI。

    重要（未线上验证）：重启客户端会杀掉当前 WorkBuddy 会话，无法从自动化会话内
    安全探测真实 DOM。本驱动器按「侧边栏入口 + 文案匹配按钮」的通用思路实现，
    具体入口名 / 按钮文案若与线上不同，会**优雅跳过**（返回 skipped，不中断整个
    一键流程）。请在有客户端的前提下手动确认入口，告诉我实际文案，我再校准选择器。
    """
    out = {}
    r = _js_block(BLINDBOX_ENTER, timeout=120)
    out["enter"] = r
    if not (r.get("openBtnFound")):
        out["skipped"] = "未找到「开盲盒」入口/按钮（可能文案不同或入口在别处），已跳过"
        out["ok"] = False
        if verbose:
            print(json.dumps(out, ensure_ascii=False, indent=2))
        return out
    r2 = _js_block(BLINDBOX_OPEN, timeout=120)
    out["open"] = r2
    out["ok"] = bool(r2.get("ok"))
    if verbose:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    return out


def do_automation_delete(names):
    """在「定时任务」页用批量管理删掉指定名称的自动化（可传单个字符串）。

    用途：automation_1 考的是「创建」这个事件，创建完服务端就计分了
    （实测删除不会让进度倒退），所以按用户「领完就删干净、不留记录」的一贯要求，
    创建 → 领分 → 删掉。
    """
    if isinstance(names, str):
        names = [names]
    out = {"want": names, "deleted": [], "failed": []}
    r = _js_block(ATM_BATCH_ON, timeout=120)
    out["batch_on"] = r
    if not r.get("ok"):
        # 列表本来就是空的（已清干净）→ 视为成功
        st0 = _js_block(ATM_BATCH_STATE, timeout=60)
        if st0.get("onPage") and not (st0.get("names") or []):
            out["ok"] = True
            out["already_clean"] = True
            return out
        out["ok"] = False
        out["err"] = "进不了批量管理：%s" % r
        return out
    time.sleep(0.8)
    for nm in names:
        # 注意：这里不能用 wbT() —— 它定义在别的 JS 块里，而 js() 每次都把代码包进
        # 独立 IIFE，块内的 function 声明不会泄漏到全局，直接引用会报
        # 「ReferenceError: wbT is not defined」。所以取值逻辑就地写全。
        sel = (r"Array.from(document.querySelectorAll('div.atm-row'))"
               r".filter(r => { const e = r.querySelector('.atm-row-name');"
               r" return e && (e.innerText||'').replace(/\s+/g,' ').trim() === %s; })[0]"
               % json.dumps(nm))
        found = U.js("(()=>{const r=%s;return r?true:false;})()" % sel)
        if not found:
            out["failed"].append({"name": nm, "err": "列表里没有这条"})
            continue
        U.mouse_click(sel + ".querySelector('.atm-row-checkbox')")
        time.sleep(0.7)
        out["deleted"].append(nm)
    if not out["deleted"]:
        out["ok"] = False
        out["err"] = "没有任何一条被勾选"
        _js_block(ATM_BATCH_OFF, timeout=60)
        return out
    U.mouse_click("Array.from(document.querySelectorAll('.automation-main-page button'))"
                  ".find(b => (b.innerText||'').trim() === '删除')")
    time.sleep(1.6)
    out["confirm"] = _js_block(ATM_BATCH_CONFIRM, timeout=90)
    time.sleep(1.5)
    _js_block(ATM_BATCH_OFF, timeout=60)
    time.sleep(1.0)
    st = _js_block(ATM_BATCH_STATE, timeout=60)
    out["after"] = st
    left = [n for n in out["deleted"] if n in (st.get("names") or [])]
    out["failed"] += [{"name": n, "err": "删除后仍在列表里"} for n in left]
    out["deleted"] = [n for n in out["deleted"] if n not in left]
    out["ok"] = bool(out["deleted"]) and not out["failed"]
    return out


def do_automation_1_and_clean(name="每日 AI 简报",
                              prompt="用一句话总结今天值得关注的一条 AI 新闻。直接给结果。",
                              keep=False):
    """创建自动化任务 → 校验列表 →（默认）删掉，保持账号干净。"""
    out = do_automation_1(name, prompt)
    if out.get("ok") and not keep:
        out["clean"] = do_automation_delete(name)
    return out


# --------------------------------------------------------------------------- #
# 资料库（Library_read）——内容在跨域 iframe 里，走 U.eval_in_iframe / mouse_click_in_iframe
# --------------------------------------------------------------------------- #
LIB_IFRAME_SIZE = r"""
(() => {
  const f = document.querySelector('iframe.space-panel-iframe');
  if (!f) return { exists: false };
  const r = f.getBoundingClientRect();
  return { exists: true, w: Math.round(r.width), h: Math.round(r.height),
           area: Math.round(r.width) * Math.round(r.height) };
})()
"""

SIDEBAR_LIB = ("Array.from(document.querySelectorAll('.conversation-list-tab-button'))"
               ".find(e => /资料库/.test(e.innerText || ''))")

LIB_DOC_CARD = r"""(()=>{
  const vis = el => { const r = el.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
  const hits = Array.from(document.querySelectorAll('*')).filter(vis)
    .filter(e => /资料库介绍/i.test(e.innerText || '') && (e.innerText || '').length < 40)
    .sort((a, b) => a.querySelectorAll('*').length - b.querySelectorAll('*').length);
  return hits.slice(0, 5).map(e => ({ tag: e.tagName, cls: String(e.className).slice(0, 90),
    t: (e.innerText || '').replace(/\s+/g, ' ').slice(0, 60) }));
})()"""

LIB_SCROLL_JS = r"""(()=>{
  const vis = el => { const r = el.getBoundingClientRect(); return r.height > 100; };
  const cands = Array.from(document.querySelectorAll('*')).filter(e => {
    const cs = getComputedStyle(e);
    return /auto|scroll/.test(cs.overflowY) && e.scrollHeight > e.clientHeight + 40;
  }).map(e => ({ tag: e.tagName, cls: String(e.className).slice(0, 80),
                 sh: e.scrollHeight, ch: e.clientHeight }))
  .sort((a, b) => (b.sh - b.ch) - (a.sh - a.ch));
  return cands.slice(0, 6);
})()"""


OVERLAY_CANCEL = r"""
(async () => {
  const closed = [];
  // 1) 设置面板
  const sc = document.querySelector('.settings-modal__close');
  if (sc) { realClick(sc); closed.push('settings'); await sleep(900); }
  // 2) 各类模态 / 遮挡层：优先点「取消」「关闭」「我知道了」
  for (let round = 0; round < 4; round++) {
    const vis = el => { const r = el.getBoundingClientRect(); return r.width > 8 && r.height > 8; };
    const overlays = Array.from(document.querySelectorAll(
      '.wb-modal__overlay, [class*=dialogOverlay], [class*=confirm-overlay], ' +
      '.wb-modal, [class*=dialogContainer]')).filter(vis);
    if (!overlays.length) break;
    const btns = Array.from(document.querySelectorAll('button')).filter(vis)
      .filter(b => /^(取消|关闭|我知道了|稍后|返回)$/.test((b.innerText || '').trim()));
    if (!btns.length) break;
    realClick(btns[btns.length - 1]);
    await sleep(1000);
    closed.push('modal');
  }
  return { closed: closed };
})()
"""


def dismiss_overlays(verbose=False):
    """关掉会挡住侧边栏的残留浮层（设置面板 / 对话框 / 专家团确认框等）。"""
    out = U.js(OVERLAY_CANCEL, timeout=90)
    if verbose:
        print(json.dumps(out, ensure_ascii=False))
    return out


def ensure_library_open(verbose=False):
    """确保「资料库」面板处于打开状态（侧边栏按钮是开关式的，重复点会关掉）。"""
    out = {"steps": []}
    for i in range(6):
        st = U.js(LIB_IFRAME_SIZE, timeout=30) or {}
        if st.get("area", 0) > 20000:
            out["ok"] = True
            out["already"] = (i == 0)
            out["size"] = st
            return out
        r = U.mouse_click(SIDEBAR_LIB)
        out["steps"].append({"i": i, "click": r})
        if not r.get("ok") and "遮挡" in str(r.get("err")):
            out["dismiss"] = dismiss_overlays()
        time.sleep(3.0)
    st = U.js(LIB_IFRAME_SIZE, timeout=30) or {}
    out["ok"] = st.get("area", 0) > 20000
    out["size"] = st
    if verbose:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    return out


def do_library_read(doc="资料库介绍", verbose=False):
    """Library_read：打开「资料库」→ 打开指定文档 → 滚动读完。

    资料库是跨域 iframe（www.workbuddy.cn/space/...），在 CDP 里是独立的
    "iframe" 目标，必须直连它自己的 ws 才能读写（见 ui_driver.eval_in_iframe）。
    """
    out = {"doc": doc}
    out["open"] = ensure_library_open()
    if not out["open"].get("ok"):
        out["err"] = "打不开资料库面板"
        return out

    # 等 iframe 调试目标就绪
    for _ in range(10):
        if C.find_target(url_substr="space/", type_="iframe"):
            break
        time.sleep(1.0)
    out["cards"] = U.eval_in_iframe(LIB_DOC_CARD)
    if isinstance(out["cards"], dict) and out["cards"].get("err"):
        out["err"] = out["cards"]["err"]
        return out

    DOC_SUB = "codebuddy.work/page/"
    # 已经开着这篇文档就不用再点卡片了
    cur = U.eval_in_iframe("({title:document.title, len:(document.body.innerText||'').length})",
                           url_substr=DOC_SUB)
    if isinstance(cur, dict) and cur.get("title") and doc in cur["title"]:
        out["already_open"] = cur
    else:
        if not out["cards"]:
            out["err"] = "面板里找不到含「%s」的卡片" % doc
            return out
        card_expr = ("Array.from(document.querySelectorAll('*'))"
                     ".filter(e => /资料库介绍/i.test(e.innerText||'') "
                     "&& (e.innerText||'').length < 40)"
                     ".sort((a,b)=>a.querySelectorAll('*').length-b.querySelectorAll('*').length)[0]")
        out["click_card"] = U.mouse_click_in_iframe(card_expr)
        time.sleep(4.0)

    # 正文在**第三层** iframe（workbuddy-space-static.codebuddy.work/page/...），
    # 直连它自己的调试目标来滚动。
    out["doc_open"] = U.eval_in_iframe(
        "({title:document.title, len:(document.body.innerText||'').length,"
        " scrollH: document.documentElement.scrollHeight,"
        " winH: innerHeight})", url_substr=DOC_SUB)
    sc = U.eval_in_iframe(LIB_SCROLL_JS, url_substr=DOC_SUB)
    out["doc_scrollers"] = sc
    if isinstance(sc, list) and sc:
        cls = (sc[0].get("cls") or "").split()
        hits = U.eval_in_iframe(
            "(function(){var t=%s; var els=Array.from(document.querySelectorAll('*'));"
            " var e=els.find(function(x){return (String(x.className)||'').indexOf(t)>=0;});"
            " if(!e) return null; return {tag:e.tagName, cls:String(e.className).slice(0,60)};})()"
            % json.dumps(cls[0] if cls else ""), url_substr=DOC_SUB)
        if isinstance(hits, dict) and hits:
            sel = hits["tag"].lower() + "." + cls[0]
        else:
            sel = "document.scrollingElement"
        out["scroll_target"] = sel
        out["scroll"] = U.iframe_scroll(
            "document.querySelector(%s)" % json.dumps(sel), url_substr=DOC_SUB,
            step=700, wait=0.35)
    else:
        out["scroll"] = U.iframe_scroll(url_substr=DOC_SUB, step=700, wait=0.35)
    # 也想兜底滚一次外层（有些文档正文直接在外层）
    if out.get("scroll", {}).get("steps", 0) <= 1:
        out["scroll_outer"] = U.iframe_scroll(step=700, wait=0.3)

    # 停留一下，模拟真人读完
    time.sleep(3.0)
    out["after"] = U.eval_in_iframe(
        "(function(){var e=document.scrollingElement;"
        " return {title:document.title, top:e?Math.round(e.scrollTop):null,"
        "  max:e?Math.round(e.scrollHeight-e.clientHeight):null,"
        "  len:(document.body.innerText||'').length};})()", url_substr=DOC_SUB)
    out["ok"] = isinstance(out.get("after"), dict) and out["after"].get("len", 0) > 200
    if verbose:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    return out


def settings_nav(name):
    return U.js("(async () => { const f = %s; return await f(%s); })()"
                % (NAV_SETTINGS, json.dumps(name)), timeout=90)


def close_settings():
    return U.js(CLOSE_SETTINGS, timeout=60)


def read_themes():
    return U.js(READ_THEMES, timeout=60)


def pick_theme(name):
    return U.js("(async () => { const f = %s; return await f(%s); })()"
                % (PICK_THEME, json.dumps(name)), timeout=90)


def current_theme():
    """读当前生效的主题名（外观页里带 --selected 的那张卡）。"""
    return (read_themes() or {}).get("current")


def do_hp_appearance(theme="和平精英激战金秋", restore=None, verbose=True):
    """Hp_Appearance：使用「和平精英」主题。

    返回 {ok, before, applied, after, restored}。restore 给定时，任务生效后把主题切回去
    （任务的进度是服务端事件计数，实测改回主题不会让进度倒退）。
    """
    out = {"theme": theme}
    r = open_settings()
    out["open"] = r
    if not r.get("ok") and not r.get("already"):
        out["ok"] = False
        out["err"] = "打开设置失败：%s" % r
        return out
    r = settings_nav("外观")
    out["nav"] = {"ok": r.get("ok"), "err": r.get("err")}
    if not r.get("ok"):
        close_settings()
        out["ok"] = False
        out["err"] = "进入外观页失败"
        return out
    out["before"] = current_theme()
    p = pick_theme(theme)
    out["applied"] = p
    time.sleep(2.5)
    out["after"] = current_theme()
    out["ok"] = bool(out["after"]) and theme in str(out["after"])
    if restore and restore != theme:
        pick_theme(restore)
        time.sleep(2.0)
        out["restored"] = current_theme()
    close_settings()
    if verbose:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    return out


def do_create_canvas(action="网站设计", sugg="AI趋势官网", prompt=None,
                     delete_after=True, max_wait=480, verbose=True):
    """create_canvas：在「设计创意」里点快捷动作 + 示例提示词，发起一次生成。

    只点快捷动作会得到「待确认」；必须再点一个示例提示词把完整需求填进去再发送。
    """
    pre = ("(async () => { const f = %s; return await f(%s, %s); })()"
           % (CANVAS_PRE, json.dumps(action), json.dumps(sugg)))
    r = U.run_task(template=None, prompt=prompt, model=None, use_template=False,
                   pre_js=pre, keep_input=True, delete_after=delete_after,
                   max_wait=max_wait)
    p = r.get("pre") or {}
    out = {"kind": "create_canvas", "ok": bool(r.get("ok")),
           "action": p.get("action"), "suggestion": p.get("suggestion"),
           "promptLen": p.get("len"), "preErr": p.get("err"), "subs": p.get("subs"),
           "created": r.get("created_title"), "runDone": (r.get("run") or {}).get("done"),
           "deleted": bool((r.get("deleted") or {}).get("ok")), "err": r.get("err")}
    if verbose:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    return out


def playbook_open(want=None):
    """打开「灵感」页并返回其结构（给 do_playbook_prompt 与调试用）。"""
    return _js_block(PLAYBOOK_PRE, want, timeout=180)


def do_playbook_prompt(case_idx=0, case=None, prompt=None, delete_after=True,
                       max_wait=900, verbose=True, via_home=True):
    """playbook_prompt：挑一张灵感案例卡片 →「做同款」→「替换」→ 发送。

    via_home=True（**默认**）：直接用**首页自带的**「最佳实践案例」卡片
    （`.wb-related-playbooks__card` 在首页就存在，实测 4 张 + 「做同款」按钮），
    **不点侧边栏的「灵感」**。

    为什么必须绕开侧边栏：点「灵感」会让首页**导航**；导航途中执行的后续点击
    （「做同款」「替换」）返回值为空、逻辑静默失败 —— 表现为
    promptLen=null / created=null / 任务 0/1，却看不到任何报错。
    （这也是最初用 pre_steps 拆步的原因，但拆步只解决了「同一次调用超时」，
    没解决「导航还没结束就点下一步」。直接不走导航最省事。）

    via_home=False 时保留老的侧边栏路径，给需要浏览完整灵感库的场景用。
    """
    if via_home:
        steps = [_pb_card_step(case_idx), _fn(PB_SAME), _fn(PB_REPLACE)]
        gaps = [6.0, 7.0, 5.0]
    else:
        steps = [_fn(PB_SIDE), _pb_card_step(case_idx), _fn(PB_SAME), _fn(PB_REPLACE)]
        gaps = [8.0, 8.0, 7.0, 5.0]
    r = U.run_task(template=None, prompt=prompt, model=None, use_template=False,
                   pre_steps=steps, pre_gap=gaps, keep_input=True,
                   pre_must_ok=True,      # 「做同款」没点成功就别发，别发空壳对话
                   delete_after=delete_after, max_wait=max_wait)
    p = r.get("pre") or {}
    out = {"kind": "playbook_prompt", "ok": bool(r.get("ok")),
           "case": p.get("case") or case, "nCards": p.get("nCards"),
           "promptLen": p.get("len"), "preErr": p.get("err"),
           "created": r.get("created_title"), "runDone": (r.get("run") or {}).get("done"),
           "deleted": bool((r.get("deleted") or {}).get("ok")), "err": r.get("err"),
           "steps": r.get("pre_steps")}
    if verbose:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    return out


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main():
    argv = sys.argv[1:]
    if not argv:
        print(__doc__)
        return 1
    cmd = argv[0]
    rest = argv[1:]

    if cmd == "open-settings":
        print(json.dumps(open_settings(), ensure_ascii=False, indent=2))
    elif cmd == "settings-txt":
        r = settings_nav(rest[0]) if rest else {"err": "用法: settings-txt <导航名>"}
        print(json.dumps(r, ensure_ascii=False, indent=2))
    elif cmd == "close-settings":
        print(json.dumps(close_settings(), ensure_ascii=False))
    elif cmd == "themes":
        print(json.dumps(read_themes(), ensure_ascii=False, indent=2))
    elif cmd == "who-theme":
        print(json.dumps({"current": current_theme()}, ensure_ascii=False))
    elif cmd == "theme":
        r = do_hp_appearance(rest[0] if rest else "和平精英激战金秋",
                             restore=("--restore" in rest and rest[rest.index("--restore") + 1]) or None)
    elif cmd == "hp":
        do_hp_appearance("和平精英激战金秋",
                         restore=rest[0] if rest else None)
    elif cmd == "atm-inspect":
        print(json.dumps(atm_inspect(*(rest[:1] or [])), ensure_ascii=False, indent=2))
    elif cmd == "atm-create":
        print(json.dumps(do_automation_1(*rest[:2]), ensure_ascii=False, indent=2))
    elif cmd == "atm-auto":
        print(json.dumps(do_automation_1_and_clean(*rest[:1]), ensure_ascii=False, indent=2))
    elif cmd == "atm-del":
        print(json.dumps(do_automation_delete(rest), ensure_ascii=False, indent=2))
    elif cmd == "atm-errs":
        print(json.dumps(_js_block(ATM_ERRORS, timeout=60), ensure_ascii=False, indent=2))
    elif cmd == "atm-list":
        print(json.dumps(_js_block(ATM_LIST, timeout=120), ensure_ascii=False, indent=2))
    elif cmd == "atm-template":
        print(json.dumps(_js_block(ATM_TEMPLATE, rest[0] if rest else "每日 AI 新闻推送", timeout=120),
                         ensure_ascii=False, indent=2))
    elif cmd == "atm-why":
        print(json.dumps(_js_block(ATM_WHY, timeout=60), ensure_ascii=False, indent=2))
    elif cmd == "atm-click-ok":
        r = U.mouse_click("Array.from(document.querySelectorAll('.wb-modal button'))"
                          ".find(b => (b.innerText||'').trim() === '确定')")
        time.sleep(3)
        print(json.dumps({"mouse": r, "state": _js_block(ATM_STATE, timeout=60)},
                         ensure_ascii=False, indent=2))
    elif cmd == "buddy":
        print(json.dumps(do_buddy_app(rest[0] if rest else "企鹅教师助手"),
                         ensure_ascii=False, indent=2))
    elif cmd == "expert":
        print(json.dumps(run_expert_once(
            kind=(rest[1] if len(rest) > 1 else "expert"),
            idx=int(rest[0]) if rest else 0, verbose=False,
            delete_after=("--keep" not in rest)),
            ensure_ascii=False, indent=2))
    elif cmd == "expert5":
        print(json.dumps(do_expert_5(int(rest[0]) if rest else 5), ensure_ascii=False, indent=2))
    elif cmd == "team3":
        print(json.dumps(do_expert_team_3(int(rest[0]) if rest else 3,
                                          start=int(rest[1]) if len(rest) > 1 else 0),
                         ensure_ascii=False, indent=2))
    elif cmd == "lighthouse":
        print(json.dumps(do_expert_lighthouse(rest[0] if rest else "轻量云"),
                         ensure_ascii=False, indent=2))
    elif cmd == "expert-enter":
        print(json.dumps(expert_enter(rest[0] if rest else None), ensure_ascii=False, indent=2))
    elif cmd == "expert-search":
        print(json.dumps(expert_search(rest[0] if rest else "轻量云"), ensure_ascii=False, indent=2))
    elif cmd == "canvas":
        print(json.dumps(do_create_canvas(rest[0] if rest else "网站设计",
                                          rest[1] if len(rest) > 1 else "AI趋势官网",
                                          delete_after=("--keep" not in rest)),
                         ensure_ascii=False, indent=2))
    elif cmd == "playbook":
        print(json.dumps(do_playbook_prompt(int(rest[0]) if rest else 0,
                                            delete_after=("--keep" not in rest)),
                         ensure_ascii=False, indent=2))
    elif cmd == "playbook-open":
        print(json.dumps(playbook_open(rest[0] if rest else None), ensure_ascii=False, indent=2))
    elif cmd == "lib":
        print(json.dumps(do_library_read(*(rest[:1] or [])), ensure_ascii=False, indent=2))
    elif cmd == "libopen":
        print(json.dumps(ensure_library_open(verbose=True), ensure_ascii=False, indent=2))
    elif cmd == "libjs":
        print(json.dumps(U.eval_in_iframe(rest[0] if rest else "location.href"),
                         ensure_ascii=False, indent=2))
    elif cmd == "raw":
        if not rest:
            print("用法: raw <research/xxx.js> [args...]")
        else:
            print(json.dumps(run_probe(rest[0], *rest[1:]), ensure_ascii=False, indent=2))
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
