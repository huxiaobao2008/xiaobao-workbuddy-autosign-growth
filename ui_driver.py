#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
客户端 UI 驱动器（CDP）

背景：成长任务的进度由服务端检测「真实产品使用事件」得出，纯 API 刷不动
（见 research/云会话链路验证结论.md）。唯一可行路径是驱动桌面客户端本体做真实操作。
本模块通过 CDP 在被开调试端口的客户端渲染进程里执行真实鼠标/键盘事件序列。
已实测打通：template_5（2/5→5/5 并领取 100 分）、Model_chat_GLM5.2、black_cat。

前置：客户端带调试端口启动（双击 restart-cdp.cmd，端口 9222），且客户端
      登录的必须是目标任务所属账号。

用法：
    python ui_driver.py status                        # 当前模型 / 页面状态
    python ui_driver.py shot <png路径>                # 截图
    python ui_driver.py model <模型名>                # 切换新建任务的模型
    python ui_driver.py template <模板名>             # 一条命令跑完：建任务→选模型→选模板
                                                     #   →补指令→发送→等完成→删掉自己的会话
    python ui_driver.py template <模板名> --keep      # 同上，但保留会话
    python ui_driver.py template <模板名> --model X   # 指定模型
    python ui_driver.py batch-template 幻灯片,深度研究 # 连做多个
    python ui_driver.py list                          # 列出侧边栏任务会话
    python ui_driver.py del "<标题关键字>"             # 删指定会话（含二次确认）
    python ui_driver.py del-top                       # 删「任务」区最新一条
    python ui_driver.py cleanup [名字,名字]            # 批量删（默认按模板名单）
    python ui_driver.py clear / type "<文字>"          # 清空 / 打字

模板名（新建任务输入框左侧「+」展开，横向可滚动，当前只渲染约 8 个）：
    文档处理 / 金融服务 / 数据分析及可视化 / 个人工作台 / 深度研究 /
    视频生成 / 幻灯片 / 产品管理

几条必须知道的坑（都踩过）：
1. 编辑器是 Slate 受控组件：改 innerText / dispatch input 无效，
   必须用 CDP Input.insertText 打字、Input.dispatchKeyEvent 发 Ctrl+A/Backspace 清空。
2. 只发一个模板标签、不带任何指令时，AI 会反问「你想要什么」并把会话挂成
   「待确认」，对话不算完成、任务也不计数 —— 必须补一句 prompt。
3. WorkBuddy 会把视图切回「活跃会话」。用户自己那个会话一旦有新动静，
   querySelector('[contenteditable=true]') / button.cr-send-button 命中的就是它，
   读到的 --stop 与计时器全是错的 → 整个序列必须一条命令连贯跑完，中途不要插入别的操作。
4. 完成判定不能只看发送按钮的 --stop（等用户回答时也不消失）。
   可靠信号：.cr-message-list-viewport 内最后一个 .cr-agent 的
   .cr-agent--processing 消失，且结构（气泡数/文本长度）连续 4 拍不再变化。
5. 刚发完消息的会话处于「选中」态、归档按钮禁用。删除前先点一次「新建任务」
   切到首页把选中态解除。删除不会让任务进度倒退（进度是服务端事件计数，实测验证）。
"""
import json
import os
import sys
import time

sys.path.insert(0, __file__.rsplit("\\", 1)[0])

import cdp as C   # noqa: E402

# --------------------------------------------------------------------------- #
# 「停止任务」信号（跨进程）
#
# server 的「停止任务」按钮会写这个文件；UI 驱动在**每个轮询分段之间**检查它，
# 命中就立刻收手（点一下客户端的停止生成按钮、清理自己刚建的会话）。
# 用文件而不是内存标志：run_all / batch_runner 是 server 的**子进程**，
# 内存变量不共享，只有文件两边都看得见。
# --------------------------------------------------------------------------- #
STOP_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "STOP_ALL")


def stop_requested():
    try:
        return os.path.exists(STOP_FILE)
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# 「用户正在输入」护栏（2026-09-19 用户投诉后加）
#
# 用户原话：「给你打个字 你总给我新开任务」。
# 原因是 run_task 第一步就 openNewTask() —— 会把用户正在打字的输入框整个换掉、
# 写好的内容直接没了。驱动器不该跟用户抢界面。
#
# 做法：页面上挂一个 keydown 监听（只装一次），记录**用户**最后一次敲键的时间；
# 驱动器自己打字时把 __wbDriverTyping 置位，避免把自己的按键算成用户行为。
# run_task 开工前先问一次：用户 45 秒内敲过键、或输入框里有非空内容且获得焦点
#   → 直接让路，什么都不做。
# --------------------------------------------------------------------------- #
USER_WATCH = r"""
(() => {
  // 版本号：老版本（V1，无 isTrusted 过滤）的监听器一旦装上就摘不掉，
  // 它写的 window.__wbUserKey 会一直污染判断。所以 V2 换一个**不同的变量名**，
  // 让老监听器的写入彻底失效 —— 不必 reload 页面就能生效。
  if (window.__wbWatchV !== 2) {
    window.__wbWatchV = 2;
    window.__wbUserKey2 = Date.now() - 60000;
    window.__wbDriverTyping = false;
    window.__wbDriverUntil = 0;
    const mark = (e) => {
      // ① 页面内合成事件（isTrusted=false）一律不算用户：
      //    驱动器自己会用 `new KeyboardEvent('keydown',{key:'Escape'})` 关浮层
      //    （useTemplate 等 6 处），老代码把它当「用户刚敲过键」，
      //    导致同账号后面 45s 内的任务集体让路（create_canvas/playbook_prompt 曾各丢 2 项）。
      if (e && e.isTrusted === false) return;
      // ② 驱动器正在打字 / 刚打完（时间窗，容忍事件异步投递）
      if (window.__wbDriverTyping) return;
      if (Date.now() < (window.__wbDriverUntil || 0)) return;
      window.__wbUserKey2 = Date.now();
    };
    document.addEventListener('keydown', mark, true);
    document.addEventListener('beforeinput', mark, true);
    document.addEventListener('paste', mark, true);
  }
  const ed = document.querySelector('[contenteditable=true]');
  return {
    idleSec: Math.round((Date.now() - window.__wbUserKey2) / 1000),
    edLen: ed ? (ed.innerText || '').trim().length : 0,
    focused: !!(ed && document.activeElement === ed),
    driverTyping: !!window.__wbDriverTyping,
    installed: true
  };
})()
"""

# 用户安静多久才算「没在用」。
# 15s 是经验值：真人打字词与词之间的停顿通常 <5s，15s 足够判「正在写」；
# 而**绝不能设太大** —— 45s 时出过事故：驱动器自己合成 Escape 键留下的
# 误标记会让后面 45s 内的任务全部主动让路（create_canvas / playbook_prompt
# 在 account_m/n/o/q 就是这么被静默丢掉的，进度各少 2 项）。
USER_IDLE_SEC = 15


def user_busy(idle_sec=None):
    """用户是不是正在用客户端。返回 (busy, 详情)。

    判据**只看一件事**：用户最近 idle_sec 秒内有没有真的敲过键。
    刻意**不**把「输入框里有内容」当判据 —— 驱动器自己会往输入框塞东西
    （召唤专家留下的引导语、上一次中断的残留），那样会把每次运行都误判成"用户在用"。
    busy=True 时不要新建任务 —— openNewTask() 会吃掉用户正在写的内容。
    """
    idle = USER_IDLE_SEC if idle_sec is None else idle_sec
    try:
        st = js(USER_WATCH, timeout=30)
    except Exception as e:
        return False, {"err": "%s: %s" % (type(e).__name__, e)}
    if not isinstance(st, dict):
        return False, {"err": "watch 返回异常"}
    i = st.get("idleSec")
    if i is not None and i < idle:
        return True, st
    return False, st


def driver_typing(on=True):
    """告诉页面「现在是驱动器在操作」，别把按键算到用户头上。

    除了布尔位，还打一个 3s 的时间窗：CDP 派发的键事件是**异步投递**的，
    实测只置位/复位布尔位时事件会落在复位之后 → 仍然污染判断（V1 实测踩到）。
    """
    if on:
        expr = ("(() => { window.__wbDriverTyping = true;"
                " window.__wbDriverUntil = Date.now() + 3000; return true; })()")
    else:
        expr = "(() => { window.__wbDriverTyping = false; return true; })()"
    try:
        return js(expr, timeout=20)
    except Exception:
        # 不抛：置位失败不该带崩任务。但调用方要知道它可能没生效。
        return None


# --------------------------------------------------------------------------- #
# 模型策略（用户要求：完成任务时挑「积分消耗最少或免费」的模型，
#           只有任务明确指定模型时才用指定模型，不要一律用一个模型）
# 2026-09-20 用户补充指示：DeepSeek **不进黑名单**（免费/优惠额度照用）；
#           免费额度用完以后，由自定义模型「agnes 2.5」兜底做积分任务
#           （模型名可用环境变量 WB_CUSTOM_MODEL 覆盖，须与客户端 UI 显示名一致）。
# --------------------------------------------------------------------------- #
CHEAP_MODELS = ["Hy3", "Deepseek-V4.1-Flash",
                os.environ.get("WB_CUSTOM_MODEL", "agnes 2.5")]
# 依次尝试：Hy3=限时免费 0.00x → Flash=独家优惠 0.03x → 自定义 agnes 2.5 兜底
TASK_MODEL_RULES = {
    # 任务 code -> 必须使用的模型（任务描述里点名了模型）
    "Model_chat_GLM5.2": "GLM-5.2",
    "black_cat": "GLM-5.2",
}
# 已知不可用/不划算的模型：Hy4 preview 会触发频率限制（实测报「超出频率限制，08:00 重置」）
AVOID_MODELS = ["Hy4 preview"]

# 首页模板（用于 template_5 任务）；这些名字同时也是自动化生成的会话标题，
# 收尾清理时按这份名单删除，绝不碰用户自己的会话。
TEMPLATE_NAMES = ["文档处理", "金融服务", "数据分析及可视化", "个人工作台", "幻灯片", "深度研究"]

# 每个模板配一句「短、便宜、必定有答复」的指令。只发模板标签不带指令时，
# AI 会反问并挂成「待确认」，任务不计数 —— 所以每个模板都要有默认指令。
TEMPLATE_PROMPTS = {
    "文档处理": "把这句话整理成一句话：今天开会讨论了排期、人手和预算。直接给结果，不用解释。",
    "金融服务": "用一句话说明什么是复利。只给答案。",
    "数据分析及可视化": "数字 1,2,3,4,5 的平均值是多少？一句话回答。",
    "个人工作台": "用一句话给我一个今天立刻能用的时间管理建议。",
    "幻灯片": "只要一页：用一句话介绍人工智能。不用生成文件，直接给要点。",
    "深度研究": "用两句话说明什么是碳中和。直接给结论，不要展开调研。",
    "视频生成": "用一句话说明短视频前 3 秒该怎么做。",
    "产品管理": "用一句话说明 MVP 的核心思想。",
    "最新新闻": "用一句话概括最近科技领域有什么大事。",
    "帮我写作": "写一句 20 字以内的开工祝福语。",
    "日常翻译": "把 hello world 翻译成中文，只要译文。",
    "生活小知识": "用一句话说一个厨房生活小技巧。",
    "工作技巧": "用一句话说一个提高专注力的小技巧。",
    "旅游攻略": "用一句话推荐一个适合秋天去的地方。",
}


def pick_model_for(task_code=None):
    """任务该用哪个模型。

    任务点名了模型（Model_chat_GLM5.2 / black_cat）→ 返回点名的那个；
    其余一律返回 **None**，含义是「交给 run_task 自动挑最省的」
    （run_task 会按 CHEAP_MODELS 依次回退，单个模型不可用时自动换下一个）。

    为什么不直接返回 CHEAP_MODELS[0]：那样就没有回退余地了 ——
    Hy3 一旦撞上限流/下架，整个任务会直接失败。
    """
    if task_code and task_code in TASK_MODEL_RULES:
        return TASK_MODEL_RULES[task_code]
    return None


def model_label(model):
    """给人看的模型说明（用于日志/打印）。"""
    return model or ("自动最省(%s)" % " → ".join(CHEAP_MODELS))


# --------------------------------------------------------------------------- #
# 注入到页面里的公共 JS 前置（真实鼠标事件 + 查找工具）
# --------------------------------------------------------------------------- #
PRELUDE = r"""
/* 注意：这些辅助函数会在同一个页面里被反复注入，所以一律用 var / function 声明。
   const / let 在同一全局作用域重复声明会抛
   "Identifier 'x' has already been declared"。 */
var sleep = ms => new Promise(r => setTimeout(r, ms));
var txt = el => (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim();
function realClick(el) {
  const r = el.getBoundingClientRect();
  const opt = { bubbles: true, cancelable: true, composed: true,
                clientX: r.left + r.width / 2, clientY: r.top + r.height / 2,
                view: window, button: 0 };
  el.dispatchEvent(new PointerEvent('pointerdown', opt));
  el.dispatchEvent(new MouseEvent('mousedown', opt));
  el.dispatchEvent(new PointerEvent('pointerup', opt));
  el.dispatchEvent(new MouseEvent('mouseup', opt));
  el.dispatchEvent(new MouseEvent('click', opt));
}
function hover(el) {
  const r = el.getBoundingClientRect();
  const opt = { bubbles: true, cancelable: true, composed: true,
                clientX: r.left + r.width / 2, clientY: r.top + r.height / 2, view: window };
  ['pointerover', 'pointerenter', 'mouseover', 'mouseenter', 'mousemove'].forEach(t =>
    el.dispatchEvent(t.startsWith('pointer') ? new PointerEvent(t, opt) : new MouseEvent(t, opt)));
}
var exact = (sel, t) => Array.from(document.querySelectorAll(sel)).find(el => txt(el) === t);
var has = (sel, t) => Array.from(document.querySelectorAll(sel)).find(el => txt(el).includes(t));
function deepest(sel, t) {
  const cands = Array.from(document.querySelectorAll(sel)).filter(el => txt(el) === t);
  return cands.length ? cands[cands.length - 1] : null;
}
async function openNewTask() {
  const nb = exact('button', '新建任务');
  if (nb) { realClick(nb); await sleep(2500); return true; }
  return !!document.querySelector('.wb-home-composer__chips');
}
async function pickModel(name) {
  const trig = document.querySelector('.cr-model-selector__trigger');
  if (!trig) return { ok: false, err: '找不到模型选择器' };
  if (txt(trig).includes(name)) return { ok: true, already: true };
  realClick(trig);
  await sleep(1500);
  for (const it of document.querySelectorAll('.cr-model-selector__item')) {
    const nm = it.querySelector('.cr-model-selector__item-name');
    if (nm && txt(nm) === name) {
      realClick(it);
      await sleep(1500);
      const after = txt(document.querySelector('.cr-model-selector__trigger'));
      return { ok: after.includes(name), after };
    }
  }
  return { ok: false, err: '模型列表里没有 ' + name };
}
async function useTemplate(name) {
  const trig = document.querySelector('.cr-add-menu__trigger');
  if (!trig) return { ok: false, err: '找不到 + 按钮' };
  realClick(trig);
  await sleep(1200);
  // 模板行是横向滚动的（quick-actions--fade-right），当前只渲染一屏，
  // 靠后的模板（生活小知识/旅游攻略…）要滚动才会进 DOM。
  const list = document.querySelector('.quick-actions__list')
            || document.querySelector('.quick-actions');
  const find = () => Array.from(document.querySelectorAll('.quick-actions__item'))
        .find(b => txt(b) === name && b.getBoundingClientRect().width > 10);
  let item = find();
  for (let i = 0; i < 14 && !item; i++) {
    if (!list) break;
    if (list.scrollLeft + list.clientWidth >= list.scrollWidth - 2) {
      // 已经到最右还没找到，回卷一次再确认（DOM 可能是虚拟化的）
      list.scrollLeft = 0;
      await sleep(400);
      item = find();
      break;
    }
    list.scrollLeft = list.scrollLeft + Math.max(150, Math.round(list.clientWidth * 0.6));
    await sleep(500);
    item = find();
  }
  if (!item) {
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    return { ok: false, err: '模板列表里没有 ' + name };
  }
  realClick(item);
  await sleep(1600);
  document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
  await sleep(300);
  const chips = Array.from(document.querySelectorAll('.phrase-content-wrapper')).map(e => txt(e));
  const ed = document.querySelector('[contenteditable=true]');
  return { ok: chips.length > 0, chips: chips, input: ed ? txt(ed).slice(0, 120) : null };
}
function send() {
  const b = document.querySelector('button.cr-send-button');
  if (!b) return { ok: false, err: '找不到发送按钮' };
  realClick(b);
  return { ok: true };
}
/* 等一次对话真正跑完：先等「停止」态出现（=确实开始生成），再等它消失。 */
async function waitDone(maxSec) {
  const t0 = Date.now();
  let started = false;
  for (let i = 0; i < 40; i++) {
    await sleep(500);
    if (document.querySelector('[class*=send-button--stop]')) { started = true; break; }
  }
  if (!started) return { started: false, secs: Math.round((Date.now() - t0) / 1000) };
  for (let i = 0; i < maxSec * 2; i++) {
    await sleep(500);
    if (!document.querySelector('[class*=send-button--stop]')) {
      return { started: true, settled: true, secs: Math.round((Date.now() - t0) / 1000) };
    }
  }
  return { started: true, settled: false, secs: maxSec };
}
var convoCount = () => document.querySelectorAll('.conversation-item').length;
function pageState() {
  const body = txt(document.body);
  return {
    model: txt(document.querySelector('.cr-model-selector__trigger') || { innerText: '' }),
    sending: !!document.querySelector('[class*=send-button--stop]'),
    unknownError: body.includes('发生未知错误'),
    rateLimited: body.includes('超出频率限制'),
    taskCount: (body.match(/任务 \((\d+)\)/) || [])[1] || null
  };
}
/* ------------------------- 侧边栏会话（任务）管理 ------------------------- */
function convoItems() {
  return Array.from(document.querySelectorAll('.conversation-item'));
}
function findConvo(title) {
  return convoItems().find(it => txt(it).includes(title)) || null;
}
function convoList() {
  return convoItems().map(it => {
    const card = it.querySelector('.cb-agent-card') || it;
    const cls = card.className.toString();
    return {
      title: txt(it).slice(0, 60),
      selected: cls.indexOf('_selected_') !== -1,
      deletable: !!it.querySelector('button.agent-card-more-button') && cls.indexOf('_selected_') === -1
    };
  });
}
/* 删除一个会话：hover -> More -> 删除任务 -> 确认删除
   拒绝删除当前选中的会话（就是用户自己正在用的那个）。 */
/* 用户自己的会话，任何自动删除都不得碰。
   注意：会话标题是应用**自动生成/会变**的（本对话就从「Buddy加油站自动签到…」
   变成了「询问当前项目进度」），所以这里按关键字匹配，且宁可多列。
   真正的安全兜底是：run_task 只按 created_title 精确删自己刚建的那条。 */
var PROTECT_TITLES = ['Buddy加油站自动签到', '询问当前项目进度', '短剧转场生硬待优化',
                      '继续执行任务', '生成包公偏见录', '包公偏见录', '包拯漫剧'];
function protectedTitle(t) {
  return PROTECT_TITLES.some(p => t.indexOf(p) !== -1);
}

async function deleteConvoEl(it, force) {
  const out = { title: txt(it).slice(0, 40), steps: [] };
  if (protectedTitle(out.title) && !force) {
    out.err = '命中保护名单（用户自己的会话），拒绝删除';
    return out;
  }
  const card = it.querySelector('.cb-agent-card') || it;
  if (card.className.toString().indexOf('_selected_') !== -1) {
    out.err = '是当前正在使用的会话，拒绝删除';
    return out;
  }
  hover(card); await sleep(450);
  const more = it.querySelector('button.agent-card-more-button');
  if (!more) { out.err = '找不到更多按钮'; return out; }
  realClick(more); await sleep(1400);
  out.steps.push('more');
  const menu = document.querySelector('.conversation-context-menu');
  if (!menu) { out.err = '菜单未弹出'; return out; }
  const del = Array.from(menu.querySelectorAll('button')).find(b => txt(b).includes('删除'));
  if (!del) { out.err = '菜单里没有删除项'; return out; }
  realClick(del); await sleep(1500);
  out.steps.push('menu-delete');
  let confirm = null;
  for (let i = 0; i < 20; i++) {
    confirm = Array.from(document.querySelectorAll('button')).find(b => {
      const r = b.getBoundingClientRect();
      if (r.width < 30 || r.height < 18) return false;
      const c = b.className.toString();
      return c.indexOf('wb-button--danger') !== -1 || txt(b) === '确认删除';
    });
    if (confirm) break;
    await sleep(300);
  }
  if (!confirm) {
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    out.err = '没等到确认按钮';
    return out;
  }
  realClick(confirm); await sleep(2200);
  out.steps.push('confirmed');
  out.gone = !document.contains(it);
  out.ok = out.gone;
  if (!out.gone) out.err = '点了确认但会话仍在';
  return out;
}
async function deleteConvo(title, force) {
  const it = findConvo(title);
  if (!it) return { title: title, err: '侧边栏找不到该会话' };
  return await deleteConvoEl(it, force);
}
/* 删「刚创建的那条」：只看任务区第一条（新会话必置顶），且**标题必须对得上**
   才动手 —— 2026-09-20 用户实锤的误删根因：老 deleteConvo(title) 用 includes
   模糊匹配 + find 返回第一条，当侧栏存在同名/同前缀的旧会话（历史跑同任务
   留下的）时，删掉的总是最上面的那条 —— 用户原话「早期的任务不删除，
   都是删除的现在的任务」。所以：标题对不上 = 宁可不删，绝不猜。 */
async function deleteNewTask(expectTitle) {
  const items = Array.from(document.querySelectorAll('.conversation-section-tasks .conversation-item'));
  if (!items.length) return { ok: false, err: '任务区为空' };
  const it = items[0];
  const title = txt(it).replace(/\s+\d+\s*(秒|分钟|小时|天)前$/, '')
                        .replace(/\s+刚刚$/, '').trim();
  const exp = (expectTitle || '').trim();
  const match = exp && (title.indexOf(exp) === 0 || exp.indexOf(title) === 0);
  if (!match) {
    return { ok: false, err: '任务区第一条不是本次新建的会话（防误删，拒绝）',
             top: title.slice(0, 40), expect: exp.slice(0, 40) };
  }
  return await deleteConvoEl(it, false);
}
/* 删掉「任务」区最新的一条（自动化刚建的就在最上面）。
   刚发完消息的会话处于「选中」态、卡上的归档按钮是禁用的，所以先点一次
   「新建任务」切到首页把选中态解除，再删。
   跳过当前仍被选中的会话（用户自己的），返回删掉的标题。 */
async function deleteTopTask() {
  const first = () => {
    const items = Array.from(document.querySelectorAll('.conversation-section-tasks .conversation-item'));
    return items.find(it => {
      const card = it.querySelector('.cb-agent-card') || it;
      return card.className.toString().indexOf('_selected_') === -1
          && !!it.querySelector('button.agent-card-more-button');
    }) || null;
  };
  let target = first();
  if (!target) {
    await openNewTask();          // 切首页 = 解除选中
    await sleep(600);
    target = first();
  }
  if (!target) return { ok: false, err: '没有可删的任务会话' };
  return await deleteConvoEl(target);
}
/* 任务区最上面一条的标题（去掉「刚刚 / 3分钟前」这类相对时间后缀） */
function topTaskTitle() {
  const it = document.querySelector('.conversation-section-tasks .conversation-item');
  if (!it) return null;
  return txt(it).replace(/\s+\d+\s*(秒|分钟|小时|天)前$/, '').replace(/\s+刚刚$/, '').slice(0, 50);
}
/* 「任务」区全部标题（去掉相对时间后缀）。
   用途：跑任务前先拍一张快照，跑完后再拍一张，**只删新增的那条**。
   为什么不用「第一条」：切换账号后侧边栏是延迟重绘的，读到的「第一条」
   可能是上一个账号的会话 —— 据此删除会误删用户的会话。 */
function taskTitles() {
  return Array.from(document.querySelectorAll('.conversation-section-tasks .conversation-item'))
    .map(it => txt(it).replace(/\s+\d+\s*(秒|分钟|小时|天)前$/, '')
                       .replace(/\s+刚刚$/, '').slice(0, 50))
    .filter(Boolean);
}
/* 关掉可能残留的遮挡层（设置弹窗、授权弹窗…）。
   不做这一步的话，后面的点击会被遮住或点到弹窗上。 */
function isVisible(el) {
  if (!el) return false;
  const r = el.getBoundingClientRect();
  return r.width > 8 && r.height > 8;
}
async function closeOverlays(maxRound) {
  const out = { closed: [] };
  const rounds = maxRound || 3;
  for (let i = 0; i < rounds; i++) {
    const overlays = Array.from(document.querySelectorAll(
      '[class*=modal-overlay], [class*=dialog-overlay], [class*=modal_], [class*=settings-modal]'))
      .filter(el => isVisible(el) && el.className.toString().indexOf('__') === -1);
    const open = overlays.filter(el => {
      const cls = el.className.toString();
      return (cls.indexOf('overlay') !== -1 || cls.indexOf('settings-modal') !== -1);
    });
    if (!open.length) break;
    let hit = null;
    for (const ov of open) {
      const cls = ov.className.toString();
      hit = ov.querySelector('[class*=__close]')
         || Array.from(ov.querySelectorAll('button')).find(b =>
              isVisible(b) && /关闭|取消|知道了|返回/.test(txt(b)))
         || (cls.indexOf('overlay') !== -1 ? ov : null);
      if (hit) { realClick(hit); out.closed.push(hit.className.toString().slice(0, 60)); break; }
    }
    if (!hit) {
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
      out.closed.push('escape');
    }
    await sleep(900);
  }
  return out;
}
/* 切换首页场景（日常办公 / 代码开发 / 设计创意）。 */
async function setScene(name) {
  const pills = Array.from(document.querySelectorAll('.wb-scene-tabs__pill'))
    .filter(p => isVisible(p));
  const cur = pills.find(p => p.className.toString().indexOf('--active') !== -1);
  if (cur && txt(cur) === name) return { ok: true, already: true, scene: name };
  const pill = pills.find(p => txt(p) === name);
  if (!pill) return { ok: false, err: '找不到场景 ' + name,
                      scenes: pills.map(p => txt(p)) };
  realClick(pill);
  await sleep(2200);
  const after = Array.from(document.querySelectorAll('.wb-scene-tabs__pill'))
    .filter(p => isVisible(p) && p.className.toString().indexOf('--active') !== -1)
    .map(p => txt(p))[0];
  return { ok: after === name, scene: after };
}
"""


def js(code, timeout=120.0):
    """在渲染进程里跑一段 JS（可用 PRELUDE 里的工具函数）。

    整段包进 IIFE：页面是长期存活且会被反复注入的，顶层声明会残留，
    只要有一次用 const/let 定名，后续注入就报 "already been declared"。
    IIFE 给每次注入独立作用域，彻底避免这类冲突。
    """
    wrapped = "(async () => {\n" + PRELUDE + "\nreturn await (\n" + code + "\n);\n})()"
    cdp, page = C.connect()
    try:
        return cdp.evaluate(wrapped, timeout=timeout)
    finally:
        cdp.close()


# --------------------------------------------------------------------------- #
# 动作
# --------------------------------------------------------------------------- #
def status():
    return js("(() => ({ url: location.href.slice(0, 90), ...pageState() }))()", timeout=30)


def shot(path, full=False):
    cdp, page = C.connect()
    try:
        n = C.screenshot(cdp, path, full=full)
        return {"path": path, "bytes": n}
    finally:
        cdp.close()


def set_model(name):
    return js("(async () => { await openNewTask(); return await pickModel(%s); })()" % json.dumps(name))


def click_text(text):
    return js("(async () => { const el = exact('button', %s) || deepest('*', %s);"
              " if (!el) return {ok:false, err:'没找到'}; realClick(el); await sleep(1500);"
              " return {ok:true, state: pageState()}; })()" % (json.dumps(text), json.dumps(text)))


def clear_input():
    """清空输入框。

    编辑器是 Slate（受控、data-slate-editor），直接改 innerText / dispatch input 都不生效，
    必须走真实按键：CDP Input.dispatchKeyEvent 发 Ctrl+A 全选，再 Backspace 删除。
    """
    cdp, page = C.connect()
    try:
        ok = cdp.evaluate(
            "(function(){var e=document.querySelector('[contenteditable=true]');"
            "if(!e) return false; e.focus();"
            "window.__wbDriverTyping = true;"
            "window.__wbDriverUntil = Date.now() + 8000; return true;})()",
            timeout=20)
        if not ok:
            return {"ok": False, "err": "找不到输入框"}

        def key(t, k, code, vk, mods=0):
            cdp.call("Input.dispatchKeyEvent", {
                "type": t, "modifiers": mods, "key": k, "code": code,
                "windowsVirtualKeyCode": vk, "nativeVirtualKeyCode": vk}, timeout=15)

        key("keyDown", "a", "KeyA", 65, 2)          # modifiers=2 -> Ctrl
        key("keyUp", "a", "KeyA", 65, 2)
        key("rawKeyDown", "Backspace", "Backspace", 8)
        key("keyUp", "Backspace", "Backspace", 8)
        time.sleep(0.7)
        left = cdp.evaluate(
            "(function(){var e=document.querySelector('[contenteditable=true]');"
            "window.__wbDriverTyping = false; window.__wbDriverUntil = 0;"
            "return {text: e ? (e.innerText||'').replace(/\\s+/g,' ').trim().slice(0,60) : null,"
            "        chips: document.querySelectorAll('.phrase-content-wrapper').length};})()",
            timeout=20)
        return {"ok": True, "after": left}
    finally:
        # 保险：万一上面中途抛异常，__wbDriverTyping 必须复位，
        # 否则让路护栏会永久失明（真的会去抢用户的输入框）。
        try:
            driver_typing(False)
        except Exception:
            pass
        cdp.close()


_RECT_JS = (
    "(function(){var e=%s; if(!e) return null;"
    " var r=e.getBoundingClientRect();"
    " var cx=r.left+r.width/2, cy=r.top+r.height/2;"
    " var top=document.elementFromPoint(cx,cy);"
    " return {x:cx, y:cy, w:Math.round(r.width), h:Math.round(r.height),"
    "         inView: r.top>=0 && r.left>=0 && r.bottom<=window.innerHeight && r.right<=window.innerWidth,"
    "         hit: !!(top && (top===e || e.contains(top) || top.contains(e))),"
    "         hitCls: top ? String(top.className).slice(0,70) : null};})()")


def mouse_click(js_expr, timeout=30):
    """用 CDP 真实鼠标事件点击元素（合成事件对某些按钮无效时的兜底）。

    js_expr 是一段返回元素的 JS 表达式，例如
    "document.querySelector('.wb-modal .wb-button--primary')"。

    注意：不能用 scrollIntoView 之后立刻读 rect——平滑滚动还没结束，
    读到的坐标是旧位置，点击会落到别的元素上。这里分三步：
    滚动（instant）→ 重新读 rect → 用 elementFromPoint 校验落点再点。
    """
    cdp, _ = C.connect()
    try:
        # 1) 需要时先滚动（instant，避免平滑滚动造成坐标过期）
        try:
            cdp.evaluate(
                "(function(){var e=%s; if(!e) return 0;"
                " var r=e.getBoundingClientRect();"
                " if (r.top<0 || r.bottom>window.innerHeight) {"
                "   if (e.scrollIntoView) e.scrollIntoView({block:'center', behavior:'instant'}); }"
                " return 1;})()" % js_expr, timeout=timeout)
        except C.CdpError:
            return {"ok": False, "err": "找不到元素"}
        time.sleep(0.35)
        try:
            rect = cdp.evaluate(_RECT_JS % js_expr, timeout=timeout)
        except C.CdpError:
            return {"ok": False, "err": "找不到元素"}
        if not rect:
            return {"ok": False, "err": "找不到元素"}
        if rect["w"] < 2 or rect["h"] < 2:
            return {"ok": False, "err": "元素不可见", "rect": rect}
        if not rect["hit"]:
            return {"ok": False, "err": "落点被遮挡", "rect": rect}
        x, y = rect["x"], rect["y"]
        cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y,
                                              "button": "none"}, timeout=15)
        time.sleep(0.12)
        cdp.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y,
                                              "button": "left", "clickCount": 1}, timeout=15)
        time.sleep(0.09)
        cdp.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y,
                                              "button": "left", "clickCount": 1}, timeout=15)
        time.sleep(0.5)
        return {"ok": True, "rect": rect}
    finally:
        cdp.close()


def type_text(text, do_send=False):
    """往输入框打字（追加在已有内容后）。

    Slate 是受控编辑器，改 DOM 无效；用 CDP Input.insertText 模拟真实输入法插入。
    """
    cdp, page = C.connect()
    try:
        ok = cdp.evaluate(
            "(function(){var e=document.querySelector('[contenteditable=true]');"
            "if(!e) return false; e.focus();"
            "window.__wbDriverTyping = true;"
            "window.__wbDriverUntil = Date.now() + 8000;"
            "var s=window.getSelection(); var r=document.createRange();"
            "r.selectNodeContents(e); r.collapse(false); s.removeAllRanges(); s.addRange(r);"
            "return true;})()", timeout=20)
        if not ok:
            return {"ok": False, "err": "找不到输入框"}
        cdp.call("Input.insertText", {"text": text}, timeout=25)
        time.sleep(0.6)
        cdp.evaluate("(function(){window.__wbDriverTyping = false;"
                     " window.__wbDriverUntil = 0; return true;})()", timeout=15)
        if do_send:
            cdp.evaluate("(function(){var b=document.querySelector('button.cr-send-button');"
                         "if(!b) return false; b.click(); return true;})()", timeout=20)
            time.sleep(1.0)
        state = cdp.evaluate(
            "(function(){var e=document.querySelector('[contenteditable=true]');"
            "return {text: e ? (e.innerText||'').replace(/\\s+/g,' ').trim().slice(0,120) : null,"
            "        chips: Array.from(document.querySelectorAll('.phrase-content-wrapper')).map(x=>(x.innerText||'').trim())};})()",
            timeout=20)
        return {"ok": True, "state": state, "sent": do_send}
    finally:
        try:
            driver_typing(False)
        except Exception:
            pass
        cdp.close()


def use_template(name, model=None, wait=True, max_wait=300, clear=True, prompt=None):
    """用某个模板发起一次对话，并等到对话真正结束。

    流程：新建任务 -> 清空输入框 ->（可选）选模型 -> 点「+」选模板 ->（可选）补一句指令
          -> 发送 -> 等生成结束。

    注意：只发一个模板标签、不带任何指令时，AI 会反问「你想要什么」并把会话挂成
    「待确认」，对话不算完成、任务也不计数。所以一定要补 prompt。
    """
    js("(async () => { await openNewTask(); return true; })()", timeout=60)
    cleared = clear_input() if clear else None

    pre = js("""
(async () => {
  const out = { template: %s, steps: [] };
  if (%s) {
    const m = await pickModel(%s);
    out.model = m;
    if (!m.ok) { out.ok = false; return out; }
    out.steps.push('model');
  }
  const t = await useTemplate(%s);
  out.template_result = t;
  if (!t.ok) { out.ok = false; return out; }
  out.steps.push('template');
  out.convoBefore = convoCount();
  out.ok = true;
  return out;
})()
""" % (json.dumps(name),
       "true" if model else "false", json.dumps(model or ""),
       json.dumps(name)), timeout=90)
    if not isinstance(pre, dict) or not pre.get("ok"):
        return {"ok": False, "stage": "prepare", "detail": pre, "cleared": cleared}

    typed = None
    if prompt:
        typed = type_text(prompt)
        if not typed.get("ok"):
            return {"ok": False, "stage": "type", "detail": typed,
                    "prepare": pre, "cleared": cleared}

    post = js("""
(async () => {
  const out = {};
  const s = send();
  if (!s.ok) { out.ok = false; out.err = s.err; return out; }
  out.steps = ['send'];
  await sleep(1500);
  out.stateAfterSend = pageState();
  if (%s) {
    out.wait = await waitDone(%d);
  }
  await sleep(800);
  out.state = pageState();
  out.convoAfter = convoCount();
  out.ok = !out.state.unknownError && !out.state.rateLimited &&
           (out.wait ? out.wait.settled !== false : true);
  return out;
})()
""" % ("true" if wait else "false", max_wait), timeout=max_wait + 120)

    res = dict(post or {})
    res["template"] = name
    res["prepare"] = pre
    res["cleared"] = cleared
    if typed is not None:
        res["typed"] = typed
    return res


# --------------------------------------------------------------------------- #
# 一条命令跑完一个任务（关键：中途不能插入其它操作）
#
# 踩过的坑：WorkBuddy 会在「当前活跃会话」有新动静时把视图切回去。
# 我自己的会话（用户正在用的那个）一旦有工具调用，视图就跳回它，
# 此时 document.querySelector('[contenteditable=true]') / button.cr-send-button
# 命中的是「我自己的会话」而不是目标对话，导致读到错误的 --stop / 计时器状态。
# 所以整个序列必须在一次 JS 调用（或同一条命令内）连贯完成。
# --------------------------------------------------------------------------- #
def run_task(template, prompt, model=None, max_wait=300, poll=True, delete_after=False,
             use_template=True, pre_js=None, keep_input=False, pre_steps=None, pre_gap=3.0,
             pre_timeout=180, pre_clear=False, pre_must_ok=False, stop=None,
             yield_to_user=True, team_first_reply=False, idle_stable_polls=4):
    """新建任务 -> 清空 -> 选模型 -> 选模板 -> 补指令 -> 发送 -> 轮询到对话结束。

    delete_after=True 时，对话结束后立刻把自己刚建的那条会话删掉（用户要求「不留记录」）。
    删除不会让任务进度倒退 —— 进度是服务端事件计数，实测删完 template_5 仍为原值。

    use_template=False 时只选模型、不选模板（给 Model_chat_GLM5.2 / black_cat 用，
    这两类任务只要求「新建对话 + 用某个模型」，不需要模板）。

    pre_js：进入首页后、清空输入框前要执行的 JS（字符串）。用来做「切换场景」这类
    前置动作，例如 create_canvas 需要先点「设计创意」场景 pill。

    pre_steps：前置动作列表，**每项一次独立的 JS 调用**（之间 sleep pre_gap 秒）。
    有些点击会触发页面导航 —— 页面一旦导航，同一次 JS 调用里剩下的 await 就再也
    回不来了（CDP 会一直等到超时）。这类动作必须拆成独立调用，见 do_playbook_prompt。

    keep_input=True 时**不清空**输入框 —— 给「召唤专家」「做同款」这类用：点完输入框里
    已经有预填内容和一个 chip，清空会把 chip 一起删掉（Ctrl+A 是整框全选）。
    """
    out = {"template": template, "prompt": prompt, "model": model}

    def _stopped():
        """是否收到「停止任务」信号（显式 stop 回调 或 全局 STOP 文件）。

        注意：这个定义必须留在本函数**开头** —— 下面分段轮询、以及发送前的
        早退都要用它。曾经因为一次并行编辑把它挤掉，导致 run_task 直接
        `NameError: _stopped`（所有 UI 任务全崩），所以别把它挪走。
        """
        try:
            if stop and stop():
                return True
        except Exception:
            pass
        return stop_requested()

    # 开工前先看一次：已收到停止指令就别再新建会话了。
    if _stopped():
        out["ok"] = False
        out["stopped"] = True
        out["err"] = "收到停止指令，未开始"
        return out

    # 0) 让路给用户：用户正在打字 / 刚敲过键 → 什么都不做。
    #    用户原话「给你打个字 你总给我新开任务」—— openNewTask() 会把输入框整个换掉。
    #    yield_to_user=False 的场景（收尾清理等）可以显式跳过这道闸。
    if yield_to_user:
        busy, info = user_busy()
        out["user_busy"] = info
        if busy:
            out["ok"] = False
            out["yielded"] = True
            out["err"] = "检测到用户正在使用客户端，已让路（不自作主张新建任务）：%s" % info
            return out

    # 1) 进入新建任务页，并确认拿到的是「首页输入框」（不是某个已有会话）
    home = js("""
(async () => {
  await openNewTask();
  const ed = document.querySelector('[contenteditable=true]');
  const box = ed ? ed.closest('.wb-home-route__input-box, .cr-input-box') : null;
  return {
    ok: !!ed,
    isHome: !!(box && box.className.toString().indexOf('wb-home-route__input-box') !== -1),
    hasAddMenu: !!document.querySelector('.cr-add-menu__trigger'),
    convoCount: convoCount(),
    title: (document.querySelector('.cr-message-list-viewport') ? 'chat' : 'home')
  };
})()
""", timeout=90)
    out["home"] = home
    if not isinstance(home, dict) or not home.get("ok"):
        out["ok"] = False
        out["err"] = "拿不到新建任务输入框"
        return out

    # 1.5) 前置动作（如切换场景 pill / 进专家中心召唤）
    # pre_timeout 默认 180s：EXPERT_PRE 要进专家中心（最多重试 3 轮 × 14s）+ 等卡片
    # 渲染 + 处理专家团二次确认弹窗，正常也要 40~70s，90s 会偶发超时。
    #
    # pre_clear：先清空输入框再跑 pre_steps。给「召唤专家」这类用 ——
    # 上一次中断可能把专家引导语残留在输入框里（keep_input=True 又不会清），
    # 残留内容会被当成本次要发的内容发出去，任务却对不上号。
    if pre_clear:
        out["pre_clear"] = clear_input()

    if pre_js:
        out["pre"] = js(pre_js, timeout=pre_timeout)

    # 1.55) 多段前置动作：每段一次独立调用（中间留时间让页面稳定/导航）
    #
    # pre_gap 可以是单个数字（每步都用它），也可以是**列表**（逐步指定）。
    # 为什么需要列表：专家中心这类页面「点开」时主线程会被阻塞几十秒，
    # 页面内的 await sleep() 会被整体拖慢十几倍；把等待放回 Python 侧
    # （time.sleep 不受页面卡顿影响）才能稳住。详见 ui_tasks.run_expert_once。
    #
    # pre_steps 的每一项既可以是 JS 字符串，也可以是**无参 Python 可调用对象**。
    # 后者用于「光靠 JS 做不了」的动作 —— 例如往受控 input 里输入文字，
    # 必须走 CDP 的 Input.insertText（见 ui_tasks.search_expert）。
    if pre_steps:
        steps = []
        gaps = (list(pre_gap) if isinstance(pre_gap, (list, tuple))
                else [pre_gap] * len(pre_steps))
        for i, s in enumerate(pre_steps):
            # 每一段前置动作之间都回一次 Python 侧检查停止信号。
            # 用户投诉「我这边停都停不下来」—— 前置阶段（进专家中心、等弹窗）
            # 往往要 60~180s，以前这里完全不看停止标志，按了停也得等它走完。
            if _stopped():
                out["ok"] = False
                out["stopped"] = True
                out["err"] = "前置动作第 %d 步前收到停止指令，已中止" % (i + 1)
                out["pre_steps"] = steps
                return out
            try:
                r = s() if callable(s) else js(s, timeout=pre_timeout)
            except Exception as e:
                r = {"err": "%s: %s" % (type(e).__name__, str(e)[:120])}
            steps.append(r)
            if i < len(pre_steps) - 1:
                time.sleep(gaps[min(i, len(gaps) - 1)])
        out["pre_steps"] = steps
        merged = {}
        for r in steps:
            if isinstance(r, dict):
                for k, v in r.items():
                    if v not in (None, "", [], {}):
                        merged[k] = v
        out["pre"] = merged

        # 1.57) 关键前置步骤失败 → **立刻中止，不要往下发消息**。
        #
        # 为什么必须有这道闸：pre_steps 失败时 run_task 以前会照常往下走，
        # 把 prompt 发进一个"当前碰巧打开的"普通对话 —— 于是：
        #   任务不计分（根本不是那个功能）、还白建/白删一条会话，
        #   而且日志里看不出错（run 显示 sent=true），排查时会被带偏很久。
        # 真实案例：专家中心没挂载出来 → 后续卡片步骤全失败 → 照样发消息 →
        # `Expert_team_use_3` 长期 0/3。
        # 只有显式 pre_must_ok=True 才启用（默认宽松，避免误伤那些
        # 「某一步返回 ok:false 但整体无碍」的驱动器）。
        if pre_must_ok:
            bad = [(i, (r or {}).get("err") or "ok=false")
                   for i, r in enumerate(steps)
                   if not (isinstance(r, dict) and r.get("ok"))]
            if bad:
                out["ok"] = False
                out["err"] = "前置步骤失败，已中止（未发送）：%s" % bad[:3]
                return out

    # 1.6) 拍「跑前」快照 —— 跑完只删新增的那条。
    # 关键：必须放在 openNewTask 之后。刚切完账号时侧边栏还是**上一个账号**的列表，
    # 在那时拍快照会把上一个账号的会话误判成「本次新增」，进而误删用户的会话。
    before_titles = stable_task_titles() if delete_after else None
    if delete_after:
        out["before_titles"] = before_titles

    # 2) 清空输入框（真实按键）；keep_input=True 时保留预填内容与 chip
    if keep_input:
        out["cleared"] = {"ok": True, "skipped": "keep_input"}
    else:
        out["cleared"] = clear_input()

    # 3) 选模型 + 选模板
    #
    # 模型策略（用户硬性要求，省钱）：完成任务一律用**免费 / 最省**那一档
    #   Hy3（限时免费 0.00x）→ 失败再退 Deepseek-V4.1-Flash（0.03x）；
    #   GLM-5.2 **只**给点名要它的任务用（Model_chat_GLM5.2 / black_cat），且各用一次。
    #
    # 坑（真踩过，白烧积分）：各 UI 驱动器一律传 model=None，而老代码这里是
    # `if (model) pickModel(...)` —— model=None 就把整段「选模型」跳过了，
    # 客户端于是沿用它自己当前选中的模型（往往就是 GLM-5.2），
    # 「最省积分」完全没生效。所以现在约定：
    #   model=None  → 自动挑 CHEAP_MODELS（依次回退）
    #   model="X"   → 只用 X
    #   model=""    → 明确表示「不碰模型选择器」（逃生口，给特殊场景用）
    cands = [model] if model else ([] if model == "" else list(CHEAP_MODELS))
    mres = {"ok": True, "skipped": "model='' 明确不选模型"}
    for cand in cands:
        mres = js("(async () => { const m = await pickModel(%s); return m; })()"
                  % json.dumps(cand), timeout=90)
        if isinstance(mres, dict) and mres.get("ok"):
            out["model_used"] = cand
            break
    out["prepare_model"] = mres
    if cands and not (isinstance(mres, dict) and mres.get("ok")):
        # 宁可响亮地失败，也不要静默滑回贵模型
        out["ok"] = False
        out["err"] = "选模型失败（候选 %s）：%s" % (cands, (mres or {}).get("err"))
        return out
    if out.get("model_used"):
        out["model"] = out["model_used"]   # 记下**实际**用上的模型名

    pre = {"model": mres, "steps": []}
    if cands:
        pre["steps"].append("model")
    if use_template:
        t = js("(async () => { const t = await useTemplate(%s); return t; })()"
               % json.dumps(template or ""), timeout=90)
        pre["template_result"] = t
        if not (isinstance(t, dict) and t.get("ok")):
            out["prepare"] = pre
            out["ok"] = False
            out["err"] = "选模板失败"
            return out
        pre["steps"].append("template")
    pre["ok"] = True
    out["prepare"] = pre

    # 4) 补一句指令（必须，否则 AI 反问、对话不算完成）
    if prompt:
        out["typed"] = type_text(prompt)
        if not out["typed"].get("ok"):
            out["ok"] = False
            out["err"] = "输入指令失败"
            return out

    # 5) 发送 + 轮询
    if not poll:
        out["sent"] = js("(async () => { const s = send(); return s; })()", timeout=40)
        out["ok"] = True
        return out

    # 5.1) 发送（单独一步，便于把「发出去了」和「跑完了」分开报）
    sent = js("(async () => { const s = send(); return s; })()", timeout=60)
    out["send"] = sent
    if not (isinstance(sent, dict) and sent.get("ok")):
        out["ok"] = False
        out["err"] = "发送失败：%s" % ((sent or {}).get("err") if isinstance(sent, dict) else sent)
        return out
    out["sent"] = True

    # 5.2) 分段轮询（关键：为了「随时可停」）
    #
    # 老实现是**一整段 JS**（最多 sleep 到 max_wait，playbook 会给到 900s），
    # 期间 Python 侧完全没有控制权 —— 于是「开始之后就不能停」。
    # 现在把它切成 _POLL_CHUNK 次 × 500ms 一段（默认 10s 一段），
    # **段与段之间回 Python 检查停止信号**：用户一点「停止任务」，
    # 最多等一段（约 10s）就收手，而不是傻等到对话自然结束（可能十几分钟）。
    # 分段状态（log/stable/lastKey）通过 prev 传入传出，行为与老实现等价。
    max_iter = max(1, int(max_wait * 2))
    _POLL_CHUNK = 20
    st = None
    post = None
    stopped = False
    start_i = 1
    while start_i <= max_iter:
        if _stopped():
            stopped = True
            break
        r = js("""
(async (prev, iters, startI, maxIter, tf, idleN) => {
  const out = {};
  const view = () => document.querySelector('.cr-message-list-viewport');
  // 额度被用尽时客户端会在会话里贴「429 额度已用尽…购买加量包」，这时 AI **根本没回**，
  // 任何"要真的跑起来才算数"的任务都不会计分。单独标出来，
  // 免得把「没钱了」误诊成「驱动写错了」。
  const quotaTxt = () => {
    const v = view();
    const t = v ? (v.innerText || '') : '';
    const m = t.match(/(额度已用尽|购买加量包|429)/);
    return m ? m[0] : '';
  };
  function snap() {
    const v = view();
    const agents = v ? Array.from(v.querySelectorAll('.cr-agent')) : [];
    const last = agents[agents.length - 1];
    const stEl = last ? last.querySelector('.cr-agent__processing-status') : null;
    const b = document.querySelector('button.cr-send-button');
    // 忙碌状态文字：团队「思考中/生成回复中/等待模型响应」期间 .cr-agent--processing
    // 标记可能消失，只看 proc 会在长流程的阶段间隙被误判「已完成」提前收工
    // （2026-09-20 财税合规专家团 6 阶段流程实测 +0）。注意不能匹配「已处理 XmYs」
    // 计时文字 —— 用动词+「中」的形态，避开「已处理」。
    const busyTxt = stEl ? /思考中|生成回复|等待模型|排队中|运行中|处理中|执行中|正在/.test(stEl.innerText || '') : false;
    return {
      nAg: agents.length,
      proc: v ? !!v.querySelector('.cr-agent--processing') : false,
      busyTxt: busyTxt,
      len: v ? (v.innerText || '').length : 0,
      status: stEl ? (stEl.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 22) : '',
      stop: b ? b.className.toString().indexOf('--stop') !== -1 : false,
      quota: quotaTxt()
    };
  }
  const log = (prev && prev.log) ? prev.log : [];
  let lastKey = (prev && prev.lastKey !== undefined) ? prev.lastKey : null;
  let stable = prev ? (prev.stable || 0) : 0;
  let stuckFor = prev ? (prev.stuckFor || 0) : 0;
  let finished = false, done = false, reason = '', quota = '';
  for (let k = 0; k < iters; k++) {
    const i = startI + k;
    if (i > maxIter) { finished = true; reason = 'timeout'; break; }
    await sleep(500);
    const s = snap();
    // 忙碌 = 处理标记 **或** 状态文字里的活动动词（思考中/生成回复中/等待模型响应…）
    const busy = s.proc || s.busyTxt;
    // 稳定性只看「结构」不看计时文字：已处理 XmYs 会一直跳，不能算变化
    const key = JSON.stringify({ nAg: s.nAg, busy: busy, len: s.len });
    if (key !== lastKey) { log.push({ t: Math.round(i * 0.5), ...s }); lastKey = key; stable = 0; }
    else stable++;
    if (s.proc) stuckFor = 0; else stuckFor++;
    // 额度用尽：再等也没用（AI 不会回），立刻收工并如实标注
    if (s.quota) { finished = true; done = false; reason = 'quota-exhausted'; quota = s.quota; break; }
    // idleN 由 Python 传入（普通任务 4 次=2s；专家团 120 次=60s）。
    // 专家团必须拉长：团队轮次里 agent 与 agent 之间有天然停顿（>2s 很常见），
    // 老的 2s 阈值会在第 1 个 agent 回完、第 2 个还没接上时误判 idle-stable 提前收工
    // → 团队轮次跑不完 → 服务端不计分（2026-09-20 日志 nAg=1、+0、idle-stable 的来源）。
    if (i > 6 && !busy && s.len > 0 && stable >= idleN) {
      // ⚠️ A1（2026-09-20 核验缺陷 #1）：「页面安静」≠「完成」。团队反问用户时
      // 页面同样安静，老逻辑直接判 done → 上层接着开下一个团队 → 列表堆一排「待确认」。
      // 补一条反问检测：最后一条 agent 卡片结尾出现索取素材/请求确认类措辞 → 判**未完成**。
      // 注意只认强请求动词，不认裸问号（独董会收尾的选项菜单也带问号，不能误伤）。
      const v2 = view();
      const ags2 = v2 ? Array.from(v2.querySelectorAll('.cr-agent')) : [];
      const lastCard = ags2[ags2.length - 1];
      const tail = lastCard ? (lastCard.innerText || '').replace(/\\s+/g, ' ').trim().slice(-200) : '';
      const askHit = /(请提供|请上传|请补充|请发送|发给我|需要你|需要您|等你|等待你|确认后我再|告诉我你)/.test(tail);
      out.askTail = tail.slice(-120);
      finished = true;
      if (askHit) { done = false; reason = 'ask-user'; }
      else { done = true; reason = 'idle-stable'; }
      break;
    }
    // 专家团专用：用户实测「发起一次对话、对方回复完」即算完成任务（不要求
    // 多智能体把整轮交付物跑完）。tf=true 时，只要检测到 AI 已给出一段稳定
    // 的首回复（len>120 且 1.5s 内结构不变）就判完成 —— 省去等整队协作的几十秒
    // ~几分钟，也避免「团队一直在 processing 导致永远 idle-stable 不了」而 0/3。
    if (tf && i > 10 && s.len > 120 && stable >= 3) { finished = true; done = true; reason = 'team-first-reply'; break; }
    if (i > 6 && s.proc && stable >= 160) { finished = true; done = false; reason = 'stuck-processing'; break; }
  }
  out.finished = finished; out.done = done; out.reason = reason; out.quota = quota;
  out.last = snap();
  out.state = { log: log, lastKey: lastKey, stable: stable, stuckFor: stuckFor };
  // 「待确认」观测（2026-09-20 用户确认语义：模型问答需要用户回复 —— AI 反问挂起等用户）。
  // 不在这里 break 误判：真实挂起标记的 DOM 位置还没有样本可校准，只做收工观测，
  // 记 pendingSeen 供日志；反问场景本来就会走 idle-stable / team-first-reply 收工，
  // 是否真计分由上层「核对服务端进度增量」定 —— 这才是可靠的判定。
  try {
    const side = document.querySelector('aside') || document.body;
    out.pendingSeen = (side.innerText || '').indexOf('待确认') !== -1;
  } catch (e) { out.pendingSeen = false; }
  return out;
})(%s, %d, %d, %d, %s, %d)
""" % (json.dumps(st or {}), _POLL_CHUNK, start_i, max_iter, json.dumps(bool(team_first_reply)),
       int(idle_stable_polls)), timeout=_POLL_CHUNK + 40)
        if not isinstance(r, dict):
            post = {"done": False, "reason": "poll-error", "err": str(r)[:200]}
            break
        st = r.get("state") or st
        start_i += _POLL_CHUNK
        if r.get("finished"):
            post = {"done": bool(r.get("done")), "reason": r.get("reason"),
                    "quota": r.get("quota")}
            if r.get("pendingSeen"):
                post["pendingSeen"] = True   # 收工时侧边栏有「待确认」（AI 反问挂起等用户回复）
            break

    if stopped:
        # 用户点了「停止任务」：先把正在生成的回答停掉（若还在生成）
        out["stopped"] = True
        out["stop_click"] = js("""
(() => {
  const b = document.querySelector('button.cr-send-button');
  if (b && b.className.toString().indexOf('--stop') !== -1) { b.click(); return { ok: true }; }
  return { ok: false, err: '未处于生成中' };
})()
""", timeout=30)
        if post is None:
            post = {"done": False, "reason": "user-stopped"}
        post["stopped"] = True

    if post is None:
        post = {"done": False, "reason": "timeout"}

    # 收尾快照（老实现在循环后 sleep 1500 再 snap；这里等价保留）
    post["final"] = js("""
(() => {
  const v = document.querySelector('.cr-message-list-viewport');
  const agents = v ? Array.from(v.querySelectorAll('.cr-agent')) : [];
  const last = agents[agents.length - 1];
  const stEl = last ? last.querySelector('.cr-agent__processing-status') : null;
  const b = document.querySelector('button.cr-send-button');
  const t = v ? (v.innerText || '') : '';
  const q = t.match(/(额度已用尽|购买加量包|429)/);
  return { nAg: agents.length,
           proc: v ? !!v.querySelector('.cr-agent--processing') : false,
           len: t.length,
           status: stEl ? (stEl.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 22) : '',
           stop: b ? b.className.toString().indexOf('--stop') !== -1 : false,
           quota: q ? q[0] : '' };
})()
""", timeout=40)
    post["log"] = (st or {}).get("log")

    out["run"] = post
    out["ok"] = bool(post.get("done"))
    # 额度用尽要说清楚，别让它混在普通的 ok:false 里
    if post.get("reason") == "quota-exhausted":
        out["quota_exhausted"] = True
        out["err"] = ("该账号额度已用尽（%s）——AI 没有响应，任务不会计分；"
                      "需要等额度恢复或购买加量包。重试无意义。" % post.get("quota"))
    out["convoAfter"] = js("(() => convoCount())()", timeout=30)
    if delete_after:
        # 只删「本次新增的那条」。绝不用「侧边栏第一条」——切换账号后侧边栏会
        # 延迟重绘，读到的第一条可能是上一个账号/用户自己的会话。
        after_titles = stable_task_titles()
        new = [t for t in (after_titles or []) if t not in set(before_titles or [])]
        out["created_title"] = new[0] if len(new) == 1 else None
        out["new_titles"] = new
        # 先切首页解除选中态（刚发完消息的会话处于选中态，删除按钮被禁用）
        js("(async () => { await openNewTask(); await sleep(600); return true; })()", timeout=60)
        if len(new) == 1:
            # 2026-09-20 用户实锤误删：老 deleteConvo(title) 用 includes 模糊匹配，
            # 侧栏有同名/同前缀旧会话时删掉的总是最上面那条（=用户的/最新的），
            # 早期的反而留着堆积。改为「任务区第一条 + 标题核对一致」才动手。
            out["deleted"] = delete_new_task(new[0])
        else:
            out["deleted"] = {"ok": False,
                              "err": "本次新增会话数=%d，拒绝删除以免误删" % len(new)}
    return out


# --------------------------------------------------------------------------- #
# 跨域 iframe（资料库 = space-panel-iframe，origin 是 www.workbuddy.cn）
#
# 它在 CDP 里是**独立的 "iframe" 类型调试目标**（OOPIF），必须直连它自己的 ws。
# 直连之后：Runtime.evaluate 直接跑在 iframe 里；
# Input.dispatchMouseEvent 的坐标也变成**相对 iframe 视口**，不用再叠父页面偏移。
# --------------------------------------------------------------------------- #
def iframe_cdp(url_substr="workbuddy.cn"):
    return C.connect_target(url_substr=url_substr, type_="iframe")


def eval_in_iframe(js_expr, url_substr="workbuddy.cn", timeout=90):
    """在跨域 iframe（如资料库）里执行 JS，返回 byValue 结果。"""
    try:
        cdp, _p = iframe_cdp(url_substr)
    except C.CdpError:
        return {"err": "找不到 %s 的 iframe 调试目标（面板没打开？）" % url_substr}
    try:
        r = cdp.call("Runtime.evaluate", {
            "expression": js_expr, "awaitPromise": True,
            "returnByValue": True, "userGesture": True,
        }, timeout=timeout)
        if r.get("exceptionDetails"):
            d = r["exceptionDetails"]
            desc = (d.get("exception") or {}).get("description") or d.get("text")
            return {"err": "iframe 内 JS 抛错：%s" % str(desc)[:300]}
        return (r.get("result") or {}).get("value")
    finally:
        cdp.close()


def mouse_click_in_iframe(js_expr, url_substr="workbuddy.cn", timeout=30):
    """点击跨域 iframe 内的元素（坐标相对 iframe 视口，无需换算）。"""
    try:
        cdp, _p = iframe_cdp(url_substr)
    except C.CdpError:
        return {"ok": False, "err": "找不到 iframe 调试目标"}
    try:
        rect = cdp.evaluate(
            "(function(){var e=%s; if(!e) return null;"
            " if (e.scrollIntoView) e.scrollIntoView({block:'center', behavior:'instant'});"
            " var r=e.getBoundingClientRect();"
            " var cx=r.left+r.width/2, cy=r.top+r.height/2;"
            " var top=document.elementFromPoint(cx,cy);"
            " return {x:cx, y:cy, w:Math.round(r.width), h:Math.round(r.height),"
            "         hit: !!(top && (top===e || e.contains(top) || top.contains(e)))};})()"
            % js_expr, timeout=timeout)
        if not rect:
            return {"ok": False, "err": "iframe 内找不到元素"}
        if rect["w"] < 2 or rect["h"] < 2:
            return {"ok": False, "err": "iframe 内元素不可见", "rect": rect}
        x, y = rect["x"], rect["y"]
        cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y,
                                              "button": "none"}, timeout=15)
        time.sleep(0.12)
        cdp.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y,
                                              "button": "left", "clickCount": 1}, timeout=15)
        time.sleep(0.09)
        cdp.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y,
                                              "button": "left", "clickCount": 1}, timeout=15)
        time.sleep(0.5)
        return {"ok": True, "rect": rect}
    finally:
        cdp.close()


def iframe_scroll(js_expr="document.scrollingElement", url_substr="workbuddy.cn",
                  step=600, wait=0.4, max_steps=60):
    """在 iframe 内分步滚动（模拟真人阅读到底）。返回滚动轨迹。"""
    try:
        cdp, _p = iframe_cdp(url_substr)
    except C.CdpError:
        return {"err": "找不到 iframe 调试目标"}
    try:
        before = cdp.evaluate("(function(){var e=%s;return e?Math.round(e.scrollTop):null;})()"
                              % js_expr, timeout=20)
        trace = []
        for _ in range(max_steps):
            r = cdp.evaluate(
                "(function(){var e=%s; if(!e) return null;"
                " var max = e.scrollHeight - e.clientHeight;"
                " e.scrollTop = Math.min(e.scrollTop + %d, Math.max(0,max));"
                " return {top: Math.round(e.scrollTop), max: Math.round(max),"
                "         sh: e.scrollHeight, ch: e.clientHeight};})()" % (js_expr, step),
                timeout=25)
            if not isinstance(r, dict):
                break
            trace.append(r["top"])
            time.sleep(wait)
            if r["max"] <= 0 or r["top"] >= r["max"]:
                break
        after = cdp.evaluate("(function(){var e=%s;return e?Math.round(e.scrollTop):null;})()"
                             % js_expr, timeout=20)
        return {"before": before, "after": after, "steps": len(trace), "trace": trace[-6:]}
    finally:
        cdp.close()


# --------------------------------------------------------------------------- #
# 会话（任务）清理 —— 用户要求：积分领取完成后把任务删掉，不留记录
# --------------------------------------------------------------------------- #
def conversations():
    """列出侧边栏当前的任务会话。"""
    return js("(() => convoList())()", timeout=30)


def delete_conversation(title, force=False):
    """删除标题包含 title 的会话（More → 删除任务 → 确认删除）。

    ⚠️ 2026-09-20 起自动流程**不要再用这个**（includes 模糊匹配会误删同名会话，
    用户实锤「删的总是现在的、早期的留着堆积」）。自动流程一律走
    `delete_new_task()`（任务区第一条 + 标题核对一致才删）。
    本函数保留给 CLI `del <关键字>` 和清理脚本（用户明确点名时）用。

    force=True 时**跳过 PROTECT_TITLES 保护名单**——只给「用户已明确点名要删」
    的清理脚本用（如 _purge_all.py）；自动流程一律用默认 force=False。
    「当前正在使用的会话」无论 force 与否都删不掉。
    """
    return js("(async () => await deleteConvo(%s, %s))()"
              % (json.dumps(title), "true" if force else "false"), timeout=90)


def delete_new_task(expected_title):
    """删「本次刚创建、置顶在任务区第一条」的会话 —— 自动流程专用。

    与 delete_conversation 的区别：只看任务区第一条，且标题必须与 expected_title
    互相前缀匹配才动手，对不上就拒绝 —— 宁可留着不删，绝不猜着删。
    """
    if not expected_title:
        return {"ok": False, "err": "无 expected_title，拒绝删除"}
    return js("(async () => await deleteNewTask(%s))()" % json.dumps(expected_title),
              timeout=90)


def reset_team_summon_suppress():
    """清掉「团队召唤确认框」的抑制标记（2026-09-20 破案）。

    根因：驱动器跑授权流程（勾「我已知悉并确认」→「继续使用」）后，客户端把
    `agent-ui.expert-center.team-summon-confirm.suppress.<uid>` 写成 true ——
    此后所有团队召唤**跳过确认框** → 协作授权流程没走 → 团队协作不启动
    （nAg=1 降级单专家）→ Expert_team_use_3 永远不计分。8 个账号全中。
    修复：召唤团队**前**清掉全部 suppress 键，让确认框恢复弹出、授权流程走完整。
    localStorage 是 per-origin 全局存储、键按 uid 区分账号，所以在当前登录账号
    的页面里即可清掉所有账号的键，无需逐号切换。
    """
    return js("""
(() => {
  const kill = [];
  for (let i = window.localStorage.length - 1; i >= 0; i--) {
    const k = window.localStorage.key(i);
    if (/^agent-ui\\.expert-center\\.(team-summon-confirm\\.suppress|finance-risk\\.suppress)/.test(k)) {
      window.localStorage.removeItem(k);
      kill.push(k);
    }
  }
  return { ok: true, removed: kill };
})()
""", timeout=30)


def delete_top_task():
    """删掉「任务」区最新的一条会话（自动化刚建的那条）。"""
    return js("(async () => await deleteTopTask())()", timeout=90)


def top_task_title():
    return js("(() => topTaskTitle())()", timeout=30)


def task_titles():
    """「任务」区当前全部标题。"""
    return js("(() => taskTitles())()", timeout=30)


def stable_task_titles(gap=2.5, tries=6):
    """等侧边栏稳定后再取标题（避免读到重绘中的旧列表）。"""
    prev = None
    for _ in range(tries):
        cur = task_titles()
        if prev is not None and cur == prev:
            return cur
        prev = cur
        time.sleep(gap)
    return prev


def cleanup(titles=None):
    """删除所有由自动化生成的会话（默认按模板名单匹配），保留用户自己的会话。"""
    names = list(titles or TEMPLATE_NAMES)
    out = {"deleted": [], "failed": [], "protected": []}
    for n in names:
        r = delete_conversation(n)
        if r.get("ok"):
            out["deleted"].append(n)
        elif r.get("err") and "拒绝删除" in r["err"]:
            out["protected"].append(n)
        elif r.get("err") == "侧边栏找不到该会话":
            pass                      # 本来就没有，正常
        else:
            out["failed"].append({"title": n, "err": r.get("err") or r})
        time.sleep(1.2)
    return out


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    cmd = sys.argv[1]
    rest = sys.argv[2:]

    if cmd == "status":
        print(json.dumps(status(), ensure_ascii=False, indent=2))
        return 0

    if cmd == "shot":
        p = rest[0] if rest else "logs/ui.png"
        print(json.dumps(shot(p, full="--full" in rest), ensure_ascii=False))
        return 0

    if cmd == "model":
        print(json.dumps(set_model(rest[0]), ensure_ascii=False))
        return 0

    if cmd == "click":
        print(json.dumps(click_text(rest[0]), ensure_ascii=False))
        return 0

    if cmd == "clear":
        print(json.dumps(clear_input(), ensure_ascii=False))
        return 0

    if cmd == "type":
        if not rest:
            print("用法：type <文字> [--send]")
            return 1
        print(json.dumps(type_text(rest[0], do_send="--send" in rest), ensure_ascii=False))
        return 0

    if cmd == "list":
        print(json.dumps(conversations(), ensure_ascii=False, indent=2))
        return 0

    if cmd == "del":
        if not rest:
            print("用法：del <会话标题关键字>")
            return 1
        print(json.dumps(delete_conversation(rest[0]), ensure_ascii=False))
        return 0

    if cmd == "del-top":
        print(json.dumps(delete_top_task(), ensure_ascii=False))
        return 0

    if cmd == "top":
        print(json.dumps(top_task_title(), ensure_ascii=False))
        return 0

    if cmd == "cleanup":
        names = [x for x in rest[0].split(",") if x] if rest and not rest[0].startswith("--") else None
        print(json.dumps(cleanup(names), ensure_ascii=False, indent=2))
        return 0

    if cmd in ("template", "batch-template"):
        names = ([rest[0]] if cmd == "template"
                 else [x for x in rest[0].split(",") if x] if rest else [])
        model = None
        if "--model" in rest:
            model = rest[rest.index("--model") + 1]
        else:
            model = pick_model_for()   # None = 让 run_task 自动挑最省的（Hy3 → DeepSeek-V4）
        prompt = None
        if "--prompt" in rest:
            prompt = rest[rest.index("--prompt") + 1]
        nowait = "--no-wait" in rest
        delafter = "--keep" not in rest          # 默认跑完就删（不留记录）
        if cmd == "template":
            prompt = prompt or TEMPLATE_PROMPTS.get(names[0])
            if prompt:
                print("=== 任务：%s（模型 %s）===" % (names[0], model_label(model)), flush=True)
                r = run_task(names[0], prompt, model=model,
                             max_wait=60 if nowait else 300, delete_after=delafter)
                print(json.dumps({k: v for k, v in r.items()
                                  if k not in ("run",)}, ensure_ascii=False), flush=True)
                if isinstance(r.get("run"), dict):
                    print("  log: %s" % json.dumps(r["run"].get("log"), ensure_ascii=False),
                          flush=True)
                    print("  final: %s" % json.dumps(r["run"].get("final"), ensure_ascii=False),
                          flush=True)
                return 0 if r.get("ok") else 1
            r = use_template(names[0], model=model, wait=not nowait, prompt=prompt)
            print(json.dumps(r, ensure_ascii=False), flush=True)
            return 0 if r.get("ok") else 1

        # batch：逐个跑，每个都补默认指令
        for n in names:
            p = prompt or TEMPLATE_PROMPTS.get(n) or "用一句话回答即可。"
            print("=== 任务：%s（模型 %s）===" % (n, model), flush=True)
            r = run_task(n, p, model=model, max_wait=60 if nowait else 300,
                         delete_after=delafter)
            print(json.dumps({k: v for k, v in r.items()
                              if k not in ("run",)}, ensure_ascii=False), flush=True)
            if isinstance(r.get("run"), dict):
                print("  final: %s" % json.dumps(r["run"].get("final"), ensure_ascii=False),
                      flush=True)
            if not r.get("ok"):
                print("!! 该任务未完成，停止后续", flush=True)
                return 1
            time.sleep(3)
        return 0

    print("未知子命令：%s" % cmd)
    return 1


if __name__ == "__main__":
    sys.exit(main())
