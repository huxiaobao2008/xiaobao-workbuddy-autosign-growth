#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多账号「能自动完成」的成长任务批量执行器

背景：UI 驱动只能作用于客户端**当前登录**的账号。所以每个账号都要
「切换 → 驱动 UI → 领取 → 切回」。**整条命令必须一次跑完**，
中途不能插别的操作（会打断视图/会话归属）。

本脚本处理三类「主流程」任务（模板/模型/夜猫子）：

  template_5          使用 5 个不同模板并发起对话
                      -> 每个「不同模板」+1，用 run_task(模板, 指令)
  Model_chat_GLM5.2   新建对话并用 GLM-5.2 成功对话一次
                      -> run_task(无模板, GLM-5.2)
  black_cat           夜间 23:00-次日 08:00，新建对话用 GLM-5.2，每天 1 次、累计 3 天
                      -> 同 Model_chat，但只在夜间窗口且每天只试 1 次

以及「需要在别的界面点」的任务（驱动器在 ui_tasks.py，用 --codes ui 一把跑完）：

  expert_5 / Expert_team_use_3 / Expert_lighthouse   专家中心（召唤本身不计分，要发一句话）
  create_canvas        设计创意模式（快捷动作 + 示例提示词）
  playbook_prompt      灵感案例「做同款」
  Library_read         资料库文档读完
  Hp_Appearance        和平精英主题
  Buddy_App / Buddy_App_QQ   发现应用 → 企鹅教师助手（一次点击同时完成两个）
  automation_1         创建 1 个自动化任务（跑完删掉）
  skill_1              技能页试用一个技能

用法：
    python batch_runner.py --accounts account_d
    python batch_runner.py --accounts account_d,account_e,account_f
    python batch_runner.py --accounts account_d --codes template_5
    python batch_runner.py --accounts account_d --codes ui          # 只跑界面类任务
    python batch_runner.py --accounts account_d --codes all         # 两类都跑
    python batch_runner.py --accounts account_d --no-claim --keep
    python batch_runner.py --accounts account_d --dry

参数：
    --accounts  逗号分隔的账号 key（按序跑）
    --codes     逗号分隔的任务 code；也接受 ui（只界面类）/ all（全部）
                （默认 template_5,Model_chat_GLM5.2,black_cat）
    --templates template_5 用的模板池（默认内置 14 个模板名）
    --no-claim  跑完不领取
    --keep      跑完不删会话（默认跑完即删）
    --stay      跑完不切回原账号（默认切回）
    --dry       只打印计划，不切账号不动 UI
"""
import datetime
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import auto_buddy as core     # noqa: E402
import tasks as T             # noqa: E402
import account_switch as AS   # noqa: E402
import ui_driver as U         # noqa: E402
import ui_tasks as UT         # noqa: E402


# --------------------------------------------------------------------------- #
# ★ A7（2026-09-20 核验缺陷 #7 + 用户要求「不再重复试」）：团队尝试**永久账本**。
#   会话列表可以被清（用户已要求清空），但「这个号试过哪些团队、结果如何」必须
#   落盘留存 —— 试过且没计分的团队不再重试，候选池空了就如实报「需人工接手」，
#   绝不盲试。恢复重试的办法：删掉 logs/team_state.json 里对应账号的 attempts。
# --------------------------------------------------------------------------- #
def _team_state_file():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "team_state.json")


def _load_team_state():
    try:
        with open(_team_state_file(), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _record_team_attempt(key, entry):
    p = _team_state_file()
    st = _load_team_state()
    st.setdefault(key, {}).setdefault("attempts", []).append(entry)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


# 需要「在别的界面点」的任务 -> 由 ui_tasks.py 里的驱动器负责
UI_CODES = (
    "expert_5", "Expert_team_use_3", "Expert_lighthouse",
    "create_canvas", "playbook_prompt", "Library_read",
    "Hp_Appearance", "Buddy_App", "Buddy_App_QQ", "automation_1", "skill_1",
    "open_blindbox",
)

# --------------------------------------------------------------------------- #
# 「已验证跑通」的任务集合 —— 用户明确要求：**以后就只用这些去做**
#
# 依据（2026-09-19 核验，`task_status.py` 全账号实数）：
#   a/b/d/e/f/c 六个账号上，下面每一个 code 都是「已领取」= 真的跑通过。
#   这就是成功经验，别再拿没验证过的东西去撞。
#
# 默认只跑这份名单（`--codes` 的 all/ui/proven 都指它）。
# --------------------------------------------------------------------------- #
PROVEN_CODES = [
    "template_5", "Model_chat_GLM5.2",
    "create_canvas", "playbook_prompt", "Library_read", "Expert_lighthouse",
    "Hp_Appearance", "Buddy_App", "Buddy_App_QQ", "automation_1", "skill_1",
    "expert_5",
]

# 排除在自动流程之外的任务（要跑必须**显式**写 code）：
#   Expert_team_use_3 —— 要求「3 个**不同**团队」，实测多数团队不计分；
#                        盲试 11 个账号 × 12 队 × 3 分钟 = 白烧 5 小时，用户已明令停掉。
#   open_blindbox     —— 未线上验证过。
#   black_cat         —— 用户点名不执行（config.skip_tasks）。
#   Expert_Philanthropy —— 付费（config.paid_tasks）。
EXCLUDED_CODES = ["Expert_team_use_3", "open_blindbox", "black_cat", "Expert_Philanthropy"]

# 桌面端自动化**做不到**的任务（服务端仍列为未完成，但客户端没有任何路径能推进）：
#   wb_wechat_oa_subscribe_task —— 关注官方公众号，需微信扫码，外部动作
# 这类任务每次都发起 = 白烧额度/时间，直接跳过并如实标注。
UNAUTOMATABLE_CODES = ["wb_wechat_oa_subscribe_task"]

# 是否允许跑付费任务（默认否；用户显式开 --confirm-paid 才跑）
def _paid_allowed():
    return os.environ.get("BR_CONFIRM_PAID", "") not in ("", "0", "false", "False")


# playbook_prompt 用首页第几张灵感卡片（0 起）。挑最轻的那张，省十几分钟。
PB_CASE = 2

# Buddy_App 与 Buddy_App_QQ 是**同一个动作**：点「发现应用 → 企鹅教师助手 → 进入」
# 会同时完成两个任务，所以两个 code 只跑一次（按 appear 顺序去重）。
BUDDY_PAIR = ("Buddy_App", "Buddy_App_QQ")

# template_5 用的模板池：按「短、便宜、必定有答复」排序，够 5 个即可（多给几个容错）
TEMPLATE_POOL = [
    "幻灯片", "产品管理", "深度研究", "金融服务", "个人工作台",
    "生活小知识", "工作技巧", "旅游攻略", "帮我写作", "日常翻译",
    "最新新闻", "文档处理", "数据分析及可视化", "视频生成",
]

# 每个 code 的默认模型名（任务点名了模型才用点名模型）
CODE_MODEL = {
    "Model_chat_GLM5.2": "GLM-5.2",
    "black_cat": "GLM-5.2",
}

CHAT_PROMPT = "用一句话回答：今天几号？只给答案。"


# --------------------------------------------------------------------------- #
def fetch_map(key):
    """拉某账号的全部任务 -> {code: task}；返回 (map, err)。"""
    cfg = core.load_config()
    acct = next((a for a in cfg["accounts"] if a["key"] == key), None)
    if not acct:
        return {}, "配置里没有账号 %s" % key
    cred, err = core.load_cred(acct)
    if err:
        return {}, "凭证不可用：%s" % err
    lst, err = T.fetch_tasks(cred, cfg)
    if err:
        return {}, err
    return {t["code"]: t for t in lst}, ""


def prog(key, code):
    m, err = fetch_map(key)
    if err:
        return None, None, "err:" + err
    t = m.get(code)
    if not t:
        return None, None, "not_found"
    p = t.get("progress") or {}
    return p.get("current"), p.get("target"), t.get("status")


def done(key, code):
    cur, tgt, st = prog(key, code)
    if st == "claimed" or st == "completed":
        return True
    return bool(cur is not None and tgt and cur >= tgt)


def in_night(dt=None):
    """夜猫子窗口：23:00 - 次日 08:00。"""
    h = (dt or datetime.datetime.now()).hour
    return h >= 23 or h < 8


# --------------------------------------------------------------------------- #
def _compact(r, keys):
    """从驱动器返回值里挑出关键字段，避免把整段 run 日志塞进报告。"""
    if not isinstance(r, dict):
        return r
    ks = list(keys) + ["yielded", "stopped"]
    return {k: r.get(k) for k in ks if k in r}


def _is_yielded(rec):
    """这条记录是不是「给用户让路」导致的没跑。

    让路是**可恢复**的（不是真失败），必须在账号收尾阶段重跑一次，
    否则用户看到的账就是「这个号少做了 2 个任务」而日志里只有一行 err。
    """
    try:
        s = json.dumps(rec, ensure_ascii=False)
    except Exception:
        s = str(rec)
    return ("已让路" in s) or ('"yielded": true' in s)


def _skip_codes():
    """用户点名「不执行」的 task code（config.json 的 skip_tasks.codes）。"""
    try:
        blk = (core.load_config() or {}).get("skip_tasks") or {}
        return {c for c in (blk.get("codes") or []) if c}
    except Exception:
        return set()


def _remaining_actionable(acc, cfg):
    """该账号还剩哪些「能推进」的成长任务（付费/过期/锁定/桌面端做不到的不算）。

    返回 (remaining_list, summary, err)。
    """
    try:
        cred, err = core.load_cred(acc)
        if not cred:
            return [], None, err or "无凭证"
        tl, e2 = T.fetch_tasks(cred, cfg)
        if e2:
            return [], None, e2
        s = T.summarize(tl)
        rest = []
        for t in tl:
            p = t.get("progress") or {}
            if t.get("status") in ("claimed", "completed"):
                continue
            if p.get("target") and (p.get("current") or 0) >= p["target"]:
                continue
            # 服务端就做不到的：付费/过期/锁定；以及桌面端没路径的（关注公众号等）
            if t.get("paid") or t.get("expired") or t.get("locked"):
                continue
            if t.get("code") in UNAUTOMATABLE_CODES:
                continue
            rest.append(t)
        return rest, s, ""
    except Exception as e:
        return [], None, "%s: %s" % (type(e).__name__, str(e)[:120])


def account_ready_for_cleanup(acc, cfg):
    """是否满足「可以清理会话」的前提（用户 2026-09-21 定的规则）：

    1) 该账号的成长任务**全部完成**（仅剩付费/过期/锁定/桌面端做不到的不算遗留）；
    2) 没有待领积分（pending_credit == 0）—— 积分没拿到就删会话 = 白跑。

    返回 (ready: bool, reason: str)
    """
    rest, s, err = _remaining_actionable(acc, cfg)
    if err:
        return False, "无法确认任务状态（%s），不清理" % err
    if s and int(s.get("pending_credit") or 0) > 0:
        return False, "还有可领积分 %s，不清理" % s.get("pending_credit")
    if rest:
        return False, "还有 %d 项未完成（%s），不清理" % (
            len(rest), "、".join(str(t.get("title"))[:10] for t in rest[:4]))
    return True, "成长任务已完成且无可领积分"


def _cleanup_team_convs(log=None):
    """删掉当前账号里由专家团任务产生的会话（标题命中自动化指纹）。

    与「跑团队时绝不删会话」那条规则不冲突：那条是为了保留「用过哪些团队」的账本；
    本函数的调用前提由 `account_ready_for_cleanup` 把关——**任务全部完成、
    积分全部到手之后**才清（用户 2026-09-21 定），绝不是开头就删。
    """
    say = log or (lambda *a, **k: None)
    removed, failed = [], []
    # ⚠️ 指纹必须**截断安全**：侧边栏标题会被客户端截断，
    #    "…执行规则：如果上面的任务需要我提供材料…" 常被砍成 "…执行规则"，
    #    用长指纹会一条都匹配不到（2026-09-21 实测）。用短指纹「执行规则」。
    #    绝不能用 TEAM_LEDGER_SIGNS 的特征词去删 —— 用户自己开的会话
    #    （如 "分析这个CSV文件…"）也会命中，会误删用户的东西。
    FINGERPRINTS = ["执行规则"]
    try:
        titles = U.task_titles() or []
    except Exception as e:
        say("    清理跳过：读会话列表失败 %s" % str(e)[:80])
        return removed
    for t in titles:
        if not any(f in (t or "") for f in FINGERPRINTS):
            continue
        try:
            U.delete_conversation(t, force=False)
            removed.append(t[:30])
        except Exception:
            failed.append(t[:30])
    if failed:
        say("    清理失败 %d 条（受保护或当前使用中）" % len(failed))
    return removed


def _run_ui_code(key, code, cur, tgt, do_delete, log):
    """跑「需要在别的界面点」的那几类任务（驱动器都在 ui_tasks.py）。"""
    if code == "expert_5":
        need = max(0, (tgt or 5) - (cur or 0))
        if need <= 0:
            return {"skipped": "已达标"}
        log("    还需召唤 %d 位专家（召唤后发一句话才计数）" % need)
        r = UT.do_expert_5(need=need, start=int(cur or 0), verbose=False,
                           delete_after=do_delete)
        return {"ok": bool(r.get("ok")), "n_ok": r.get("n_ok"),
                "runs": [(x.get("expert") or "")[:18] for x in (r.get("runs") or [])]}

    if code == "Expert_team_use_3":
        need = max(0, (tgt or 3) - (cur or 0))
        if need <= 0:
            return {"skipped": "已达标"}
        # 用户要求「完成任务时务必看好」：**每一轮都核对服务端进度增量**，
        # 没涨就换下一个候选团队重试。理由（2026-09-19 实测）：
        #   专家团只有「团队真的把这一轮说完（客户端标已完成）」才计分，
        #   而不同团队差别极大 —— 独董会这类"给一张起手卡就收尾"的会 130s 完成并 +1；
        #   MVP开发专家团/游戏工作室这类多阶段长流程的跑 8 分钟也不结束、永远 0。
        #   以前是「召唤完就当成功」，于是长期 0/3 还查不出原因。
        #   候选顺序按"会不会自己收尾"的经验排 —— #6 独董会 实测能计分
        #   （2026-09-19：account_e 1/3 → 2/3，一轮 ~130s）。
        # ⚠️ 服务端 desc 原文：「切换至「专家团」，召唤并使用 **3 个不同的专家团队**」
        #   → 必须是**不同的**团队，同一个团队用第二次**不计分**。
        #   2026-09-19 实测：account_e 用 #6 独董会 1/3→2/3 只成功过一次；
        #   再跑 #6 就 +0（nAg=1、done=True、无额度报错）。所以这里只做「试不同团队」，
        #   **不做任何"复用同一个团队"的优化**（试过一版，方向是错的）。
        #
        # 每轮记录 nAg（参与对话的 agent 数）：nAg=1 = 团队压根没成立
        #   （点完弹窗里的「召唤专家团」弹窗直接关、没有「使用提醒」确认框，
        #     实测 `dialogs: []`、`ackKnown: []`），这类注定 +0。
        #   有这个字段才能一眼区分「团队没成立」和「成立了但不计分」。
        # 候选顺序 = **从简单到重**（用户点名的原则：「简单任务别老挑那些要你补材料的专家」）：
        #   6  独董会          给一张起手卡就收尾，自包含，实测 ~130s 能计分
        #   7/0/2 软件工坊/MVP/游戏工作室（账本里几乎没出现过的冷门候选）
        #   —— 下面这些**要你提供东西**或已实测重复，放最后（4 要素材、11 要题目/数据、3 要持仓）
        # ⚠️ 2026-09-20 18:20 改版教训：服务端会整表更换专家团卡片名单/顺序，静态下标
        #    必然过期错位（旧表 idx=7=软件工坊，实际点成产品战略团队；idx=2 点成已用过的
        #    交易分析团队 → 必 +0）。候选一律以**运行时真实名单**为准、按名字召唤，
        #    TEAM_PREFERRED 只决定尝试顺序；不在真实名单里的名字自动跳过。
        live_cards = UT.list_team_cards()
        if not live_cards:
            return {"code": code,
                    "error": "读不到专家团真实卡片名单（DOM 探测失败），拒绝按旧下标盲试"}
        cands = ([n for n in UT.TEAM_PREFERRED if n in live_cards]
                 + [n for n in live_cards if n not in UT.TEAM_PREFERRED])
        _order = os.environ.get("BR_TEAM_ORDER", "").strip()
        if _order:
            _names = [x.strip() for x in _order.split(",") if x.strip()]
            if _names:
                cands = ([n for n in _names if n in live_cards]
                         + [n for n in cands if n not in _names])
                log("    [候选] 用 BR_TEAM_ORDER 指定的顺序：%s" % _names)
            else:
                log("    [候选] BR_TEAM_ORDER 解析失败，用默认顺序")
        # ⚠️ 2026-09-20 用户实锤：必须**先剔除账本里已经用过的团队** ——
        #    服务端要求「3 个不同的专家团队」，重复必 +0，盲试纯烧积分。
        #    ledger_used_teams() 读任务区会话标题 + chip 实测映射反推已用团队。
        used_teams, titles = UT.ledger_used_teams()
        _before = len(cands)
        cands = [n for n in cands if n not in used_teams]
        log("    账本：%d 条会话 → 已用团队 %s；候选 %d→%d 个 %s"
            % (len(titles), sorted(used_teams) or "(无)", _before, len(cands), cands))
        if not cands:
            return {"ok": False, "err": "账本显示全部团队都已用过，无新团队可试（已用 %s）" % sorted(used_teams),
                    "progress": "%s/%s" % (cur, tgt), "teams": []}
        # ★ A7：叠加「历史尝试」永久账本（logs/team_state.json）—— 会话列表可清，
        #   试过没计分的团队**不再重试**；候选池空 = 如实报「需人工接手」，绝不盲试。
        #   注：改版前按错误下标记的历史团队名（如"软件工坊"）在真实名单里已不存在，
        #   会自然失效，不会误伤新候选。
        _state = _load_team_state().get(key, {})
        _tried = {a.get("team") for a in (_state.get("attempts") or []) if a.get("team")}
        _b2 = len(cands)
        cands = [n for n in cands if n not in _tried]
        if _tried:
            log("    历史尝试账本：已试过 %s；候选 %d→%d 个" % (sorted(_tried), _b2, len(cands)))
        if not cands:
            return {"ok": False,
                    "err": ("没有可试的新团队：账本已用 %s + 历史已试 %s → 该账号在自动化下无法继续，"
                            "需人工接手（确认要重试请删 logs/team_state.json 中该账号的 attempts）"
                            % (sorted(used_teams), sorted(_tried))),
                    "progress": "%s/%s" % (cur, tgt), "teams": []}
        tried, gained_total = [], 0
        # ★ 账号硬闸：本轮必须在 key 这个账号下执行（昵称对不上 → 拒绝跑，防烧错号额度）
        acct_nick = next((a.get("nickname") for a in (core.load_config().get("accounts") or [])
                          if a.get("key") == key), None)
        _now_nick = UT.current_account_name()
        if acct_nick and not (_now_nick and str(acct_nick) in str(_now_nick)):
            log("    [账号闸] 当前登录=%s，期望=%s → 拒绝执行（可能刚切号未生效）"
                % (_now_nick, acct_nick))
            return {"code": code, "error": "账号核对失败：当前=%s 期望=%s" % (_now_nick, acct_nick)}
        # 本账号专家团总预算（秒）：防止「一个团队卡 8 分钟 × 12 个候选 ≈ 1.5 小时」
        # 把整个账号乃至后续账号全拖死（用户原话：不能因为一个号做不完就卡住其它号）。
        # team_first_reply=False（2026-09-20 实测改判）：专家团必须等团队把这一轮说完
        # 才计分 —— 首回复就收工删会话会把团队打断（account_e 连 5 个团队全 nAg=1、+0）。
        # max_wait=300 等团队自然收尾，独董会 ~130s；600s 预算够试 2 个团队。
        team_t0 = time.time()
        # 1800 = 允许串行尝试 2 个 900s 级别的多阶段团队（600s 会在第一个团队跑完后就耗尽）
        TEAM_BUDGET = int(os.environ.get("BR_TEAM_BUDGET", "1800"))
        log("    还需 %d 个**不同**专家团；逐个候选试，每轮核对进度增量（预算 %.0fs，等整轮收尾）" % (need, TEAM_BUDGET))
        for team_name in cands:
            # 用户按了「停止任务」就立刻收手 —— 别再一个个团队试下去
            if U.stop_requested():
                log("    [停止] 收到停止指令，中止专家团尝试")
                break
            if time.time() - team_t0 > TEAM_BUDGET:
                log("    [预算] 专家团已达 %.0fs 预算，中止剩余候选" % TEAM_BUDGET)
                break
            c0, _, _ = prog(key, code)
            if c0 is None:
                # A6（核验缺陷 #6）：一次查询失败只重试一次、仍失败就**跳过这个候选**，
                # 不再像老代码那样 break 掉整轮（一次 API 抖动 = 整号不干活）。
                time.sleep(4)
                c0, _, _ = prog(key, code)
                if c0 is None:
                    log("    [进度查询失败] 跳过候选 [%s]（API 抖动），继续下一个" % team_name)
                    continue
            if not tgt or c0 >= tgt:
                break
            r = UT.run_expert_once(kind="team", idx=0, team_name=team_name, prompt="",
                                   max_wait=1500,   # 财税合规类 6 阶段长流程 900s 不够；超时未完成会被记历史永久排除
                                   # ⚠️ 专家团**绝不删会话**（2026-09-20 用户实锤）：
                                   # 会话标题就是「用过哪些团队」的唯一账本，跑完删掉
                                   # 等于销毁证据 → 下一轮账本为空 → 又重复试同一个团队
                                   # （服务端要求 3 个**不同**团队，重复必 +0）。
                                   # 让路/让用户随后自己清，自动化不碰。
                                   delete_after=False,
                                   team_first_reply=False,
                                   expect_nick=acct_nick)
            c1, t1, _ = prog(key, code)
            # prog 查询偶发返回 None（API 抖动）：把 None 当「查询失败」处理，
            # 不累计 delta（2026-09-20 实测 #10 曾把 None 算成 -2 污染 gained）。
            if c1 is None:
                delta = 0
            else:
                delta = c1 - (c0 or 0)
            gained_total += delta
            # A7：本轮尝试落盘（永久账本：试过什么、结果如何，清会话也丢不掉）。
            # ⚠️ 两类**不算尝试**：①「给用户让路」的跳过——根本没召唤过；②前置步骤
            #   失败（sent=false）——多为客户端瞬时抖动（确认框没点掉等），记进去会把
            #   好团队永久拉黑（2026-09-20 18:32 腾讯自选股被误拉黑实测）。
            #   让路候选留给收尾阶段的补跑机制。
            if "已让路" not in (r.get("err") or "") and r.get("sent"):
                _record_team_attempt(key, {
                    "at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "team": team_name,
                    "sent": bool(r.get("sent")),
                    "reason": (r.get("run") or {}).get("reason"),
                    "delta": delta, "scored": bool(delta and delta > 0),
                    "err": (r.get("err") or "")[:120]})
            nags = [x.get("nAg") for x in ((r.get("run") or {}).get("log") or [])
                    if isinstance(x, dict) and x.get("nAg") is not None]
            tried.append({"team": team_name, "delta": delta, "nAg": max(nags) if nags else None,
                          "sent": bool(r.get("sent")),
                          "reason": (r.get("run") or {}).get("reason"),
                          "created": r.get("created_title"),
                          "deleted": bool((r.get("deleted") or {}).get("ok")),
                          # 失败原因：pre_steps 挂了 / 发送失败 / 选模型失败都要能一眼看到，
                          # 否则只有 nAg=None 一个信号，查不出卡在哪一步（2026-09-20 教训）。
                          "err": (r.get("err") or "")[:160],
                          "pre_err": ((r.get("pre") or {}).get("err") or "")[:160],
                          "model": r.get("model_used") or r.get("model")})
            log("    团队[%s] 进度 %s → %s（%+d）nAg=%s%s"
                % (team_name, c0, c1, delta, tried[-1]["nAg"],
                   ("  err=" + tried[-1]["err"]) if tried[-1]["err"] else ""))
        c1, t1, _ = prog(key, code)
        ok = bool(c1 is not None and t1 and c1 >= t1)
        # ★ 宽限轮询（2026-09-21 实锤）：团队会话在驱动退出后仍会在客户端里继续
        #   跑完并**延迟计分** —— g 号财税合规被判 +0 后深夜自己计分到账。
        #   判失败前先宽限等待（默认 300s，env BR_TEAM_GRACE 可调），
        #   别把「慢」误报成「失败」。
        if not ok and not U.stop_requested():
            grace = int(os.environ.get("BR_TEAM_GRACE", "300"))
            log("    进度未变，宽限等待 %ds 看延迟计分..." % grace)
            g_deadline = time.time() + grace
            while time.time() < g_deadline:
                if U.stop_requested():
                    log("    [停止] 宽限等待中收到停止指令")
                    break
                time.sleep(30)
                c1, t1, _ = prog(key, code)
                if c1 is not None and t1 and c1 >= t1:
                    ok = True
                    log("    [宽限] 延迟计分到账，进度 %s/%s" % (c1, t1))
                    break
        if ok:
            # 清理前必须过闸：**该账号成长任务全部完成 + 无可领积分**才清
            # （用户 2026-09-21 定：完成并拿到积分之后再删，不是开头就删）。
            try:
                _cfg = core.load_config()
                _acc = next((a for a in (_cfg.get("accounts") or [])
                             if a.get("key") == key), None)
                ready, why = (account_ready_for_cleanup(_acc, _cfg)
                              if _acc else (False, "配置里没有该账号"))
            except Exception as e:
                ready, why = False, "状态检查异常：%s" % str(e)[:80]
            if ready:
                removed = _cleanup_team_convs(log)
                log("    %s → 清理会话 %d 条" % (why, len(removed)))
            else:
                log("    不清理：%s" % why)
        return {"ok": ok, "progress": "%s/%s" % (c1, t1), "gained": gained_total,
                "teams": tried,
                "err": None if ok else "试过 %d 个团队都未推进，详见 teams" % len(tried)}

    if code == "Expert_lighthouse":
        log("    搜索并召唤「腾讯轻量云」专家")
        r = UT.do_expert_lighthouse(verbose=False, delete_after=do_delete)
        return {"ok": bool(r.get("ok")), "runs": r.get("runs")}

    if code == "create_canvas":
        log("    设计创意 → 快捷动作 → 示例提示词 → 发送")
        r = UT.do_create_canvas(verbose=False, delete_after=do_delete)
        return _compact(r, ["ok", "action", "suggestion", "promptLen", "preErr",
                            "created", "runDone", "deleted", "err"])

    if code == "playbook_prompt":
        log("    灵感 → 做同款 → 替换 → 发送（第 %d 张卡片）" % (PB_CASE + 1))
        # 首页 4 张卡片：0 全球人口可视化(重，实测要 8 分钟) / 1 养老退休规划 /
        # 2 读书精读笔记卡(最轻) / 3 GTM 一页纸。挑轻的卡片 = 少等十几分钟，
        # 任务只要求「体验 1 款优秀案例」，不挑内容。
        r = UT.do_playbook_prompt(case_idx=PB_CASE, verbose=False, delete_after=do_delete)
        return _compact(r, ["ok", "sent", "case", "promptLen", "created", "runDone", "deleted", "err"])

    if code == "Library_read":
        log("    打开资料库并读完文档")
        r = UT.do_library_read()
        return _compact(r, ["ok", "doc", "already_open", "err"])

    if code == "Hp_Appearance":
        log("    切到「和平精英激战金秋」主题")
        r = UT.do_hp_appearance(verbose=False)
        return _compact(r, ["ok", "theme", "before", "after", "err"])

    if code in BUDDY_PAIR:
        log("    发现应用 → 企鹅教师助手 → 进入（一个动作同时完成 Buddy_App 与 Buddy_App_QQ）")
        r = UT.do_buddy_app("企鹅教师助手")
        return _compact(r, ["ok", "clicked", "authorized", "err"])

    if code == "automation_1":
        log("    创建 1 个自动化任务（跑完删掉，不留记录）")
        r = UT.do_automation_1_and_clean()
        return _compact(r, ["ok", "name", "created", "err"])

    if code == "skill_1":
        fn = getattr(UT, "do_skill_1", None)
        if not fn:
            return {"skipped": "skill_1 驱动器未实现（现有 6 个账号该任务都已完成）"}
        log("    技能页试用一个技能")
        r = fn(verbose=False)
        return _compact(r, ["ok", "skill", "err"])

    if code == "open_blindbox":
        log("    打开已解锁的「限定款 Buddy 盲盒」")
        r = UT.do_open_blindbox(verbose=False)
        return _compact(r, ["ok", "skipped", "enter", "open", "err"])

    return {"skipped": "该 code 没有自动执行策略"}


def run_code(key, code, templates, do_delete, log, deadline=None, stop=None):
    """跑一个 code 直到达标（或跑不动）。返回该 code 的执行记录。

    deadline：账号级时间预算（Unix 时间戳）。若已超期，直接跳过本 code，
    确保单账号总时长可控 —— 即使某个 UI 任务内部兜底失效，也不会拖垮整个一键流程。
    stop：可调用对象，返回 True 表示用户点了「停止任务」→ 立刻收手不跑新任务。
    """
    rec = {"code": code, "runs": []}

    if stop and stop():
        rec["skipped"] = "收到停止指令，跳过"
        return rec

    if deadline and time.time() > deadline:
        rec["skipped"] = "超出账号时间预算，跳过"
        log("    超出账号时间预算，跳过")
        return rec

    # 用户点名「不执行」的任务（配置 skip_tasks.codes，默认含 black_cat）：
    # 即使被显式写进 --codes 也拒绝执行，免得误刷。
    if code in _skip_codes():
        rec["skipped"] = "按要求不执行（config.json 的 skip_tasks）"
        log("    按要求不执行，跳过")
        return rec

    # 桌面端做不到的任务（需外部动作）→ 跳过，别每次都发起白烧额度
    if code in UNAUTOMATABLE_CODES:
        rec["skipped"] = "桌面端无法完成（需外部动作），跳过"
        log("    桌面端无法完成（需外部动作），跳过")
        return rec

    cur, tgt, st = prog(key, code)
    rec["before"] = {"current": cur, "target": tgt, "status": st}
    if cur is not None and tgt and cur >= tgt:
        rec["skipped"] = "已达标"
        return rec

    # 服务端标记的不可执行状态：付费（未确认）/ 已过期 / 已锁定 → 一律跳过
    _m, _err = fetch_map(key)
    _t = (_m or {}).get(code) or {}
    if _t.get("paid") and not _paid_allowed():
        rec["skipped"] = "付费任务，未开 BR_CONFIRM_PAID → 跳过"
        log("    付费任务，跳过")
        return rec
    if _t.get("expired") or _t.get("locked"):
        rec["skipped"] = "已过期/已锁定，跳过"
        log("    已过期/已锁定，跳过")
        return rec

    if code == "template_5":
        need = tgt if (tgt and cur is not None) else 5
        left = need - (cur or 0)
        pool = list(templates)
        log("    template_5 需再跑 %d 个不同模板" % left)
        i = 0
        while left > 0 and i < len(pool):
            if stop and stop():
                log("        [停止] 收到停止指令，中止模板循环")
                rec["stopped"] = True
                break
            tpl = pool[i]
            i += 1
            pr = U.TEMPLATE_PROMPTS.get(tpl) or "用一句话回答即可。"
            log("      [%d] 模板「%s」..." % (i, tpl))
            t0 = time.time()
            r = U.run_task(tpl, pr, model=U.pick_model_for("template_5"),
                           max_wait=240, delete_after=do_delete)
            c2, t2, _ = prog(key, code)
            gained = None if (c2 is None or cur is None) else (c2 - cur)
            rec["runs"].append({"template": tpl, "ok": r.get("ok"),
                                "secs": round(time.time() - t0, 1),
                                "created": r.get("created_title"),
                                "deleted": (r.get("deleted") or {}).get("ok"),
                                "progress_after": c2, "gained": gained})
            log("        ok=%s %.0fs 进度 %s/%s 增%s" % (r.get("ok"), time.time() - t0,
                                                        c2, t2, gained))
            if c2 is not None:
                cur = c2
                left = (t2 or need) - (c2 or 0)
            if gained == 0:
                log("        ! 本次没涨进度，可能该模板已用过，继续下一个")

    elif code in ("Model_chat_GLM5.2", "black_cat"):
        if code == "black_cat" and not in_night():
            rec["skipped"] = "不在夜间窗口（23:00-08:00）"
            log("    不在夜间窗口，跳过")
            return rec
        want = CODE_MODEL[code]
        # 关键：如果模型选择器里**已经**是目标模型，pickModel 会走 already 分支、
        # 不产生「选择模型」这个动作，任务可能因此不计次。
        # 所以先切到一个别的模型，再切回目标模型，保证动作真实发生。
        reset = U.set_model(U.CHEAP_MODELS[0])
        rec["model_reset"] = reset
        log("    先把模型切到 %s（制造真实切换），再切回 %s" % (U.CHEAP_MODELS[0], want))
        log("    %s：新建 %s 对话 1 次" % (code, want))
        t0 = time.time()
        r = U.run_task("", CHAT_PROMPT, model=want,
                       max_wait=240, delete_after=do_delete, use_template=False, stop=stop)
        c2, t2, _ = prog(key, code)
        rec["runs"].append({"ok": r.get("ok"), "secs": round(time.time() - t0, 1),
                            "created": r.get("created_title"),
                            "deleted": (r.get("deleted") or {}).get("ok"),
                            "prepare": (r.get("prepare") or {}),
                            "typed": (r.get("typed") or {}).get("ok"),
                            "progress_after": c2})
        log("      ok=%s %.0fs 进度 %s/%s" % (r.get("ok"), time.time() - t0, c2, t2))
    elif code in UI_CODES:
        t0 = time.time()
        rec.update(_run_ui_code(key, code, cur, tgt, do_delete, log))
        rec["secs"] = round(time.time() - t0, 1)
    else:
        rec["skipped"] = "该 code 没有自动执行策略"

    c2, t2, st2 = prog(key, code)
    rec["after"] = {"current": c2, "target": t2, "status": st2}
    return rec


def run_account(key, codes, templates, do_claim, do_delete, dry, log, deadline=None, stop=None):
    out = {"account": key, "codes": codes, "records": []}
    cfg = core.load_config()
    acct = next((a for a in cfg["accounts"] if a["key"] == key), None)
    if not acct:
        out["err"] = "配置里没有账号 %s" % key
        return out
    out["label"] = acct.get("label")

    if not dry:
        # ★ 修复 2026-09-21「普通任务进度 0/5、手动切号后才开始做」：
        #   旧写法 reload=False 只靠登录文件 uid 判成功，但客户端**界面会话还停在旧账号**
        #   （ui_driver.run_task 注释已证实：刚切完账号时侧边栏仍是上一个账号的列表），
        #   于是 template_5/Model_chat 的对话被建到旧账号下、目标账号进度恒为 0。
        #   这里必须 reload=True + verify=True，让渲染进程真正落到目标账号再做 UI 驱动。
        #   switch_to 默认就是 reload=True，自动化流程此前显式关掉是这次回归的根源。
        sw = AS.switch_to(key, reload=True, verify=True)
        out["switch"] = sw
        out["switch_menu_pending"] = bool(sw.get("menu_pending"))
        log("  [切] -> %s ok=%s 界面=%s%s" % (key, sw.get("ok"),
                                           (sw.get("after") or {}).get("menu"),
                                           "（界面待刷新）" if sw.get("menu_pending") else ""))
        if not sw.get("ok"):
            out["err"] = "切换失败"
            return out

    # 前置「接取 + 领取」：新账号的任务多半还是 not_accepted，
    # **不接取的话进度根本不计**（白板账号 i~q 之前就是卡在这）。
    # 先跑一遍让所有任务进入 accepted/in_progress，顺带把已完成的先领了；
    # 跑完 UI 后再领一次（下面的 do_claim），两边都覆盖到。
    if not dry and do_claim:
        res0 = T.run_account_tasks(acct, cfg)
        out["pre_accept"] = {"reason": res0.get("reason"),
                             "accepted": res0.get("summary", {}).get("accepted"),
                             "claimed": res0.get("summary", {}).get("claimed"),
                             "credit_got": res0.get("credit_got")}
        log("  [接取] %s | 接取 %s 个 / 领取 %s 个"
            % (res0.get("reason"), res0.get("summary", {}).get("accepted"),
               res0.get("summary", {}).get("claimed")))

    # Buddy_App 与 Buddy_App_QQ 由同一次点击完成：两个都在列表里时只跑一次，
    # 代表 code 取「还没达标的那个」（都达标则两个都跳过）。
    codes = list(codes)
    if all(c in codes for c in BUDDY_PAIR):
        todo = [c for c in BUDDY_PAIR if not done(key, c)]
        pos = min(codes.index(c) for c in BUDDY_PAIR)
        codes = [c for c in codes if c not in BUDDY_PAIR]
        if todo:
            codes.insert(pos, todo[0])

    for code in codes:
        if stop and stop():
            log("  [停止] 收到停止指令，跳过剩余任务")
            out["stopped"] = True
            break
        if deadline and time.time() > deadline:
            log("  [预算] 账号时间预算已到，剩余任务跳过")
            break
        log("  [任务] %s" % code)
        try:
            out["records"].append(run_code(key, code, templates, do_delete, log,
                                           deadline=deadline, stop=stop))
        except Exception as e:
            # 单个任务炸掉不能带走整批：记下来继续跑下一个 code / 下一个账号。
            log("    !! %s 异常：%s: %s" % (code, type(e).__name__, str(e)[:160]))
            out["records"].append({"code": code, "error": "%s: %s" % (type(e).__name__, str(e)[:200])})

    # 第一轮跑完，把「因为让路给用户而没跑成」的任务挑出来补跑一次。
    # 让路是设计行为（用户正在打字时绝不抢输入框），但**不能白丢**：
    # 以前 account_m/n/o/q 就是这样各少了 create_canvas / playbook_prompt 两项。
    yielded = [r.get("code") for r in out["records"] if _is_yielded(r)]
    yielded = [c for c in yielded if c in codes]
    if yielded and not (stop and stop()):
        log("  [补跑] 上一轮因让路给用户跳过 %d 个：%s" % (len(yielded), ",".join(yielded)))
        out["retry_codes"] = yielded
        for code in yielded:
            if stop and stop():
                log("  [停止] 收到停止指令，补跑中止")
                out["stopped"] = True
                break
            if deadline and time.time() > deadline:
                log("  [预算] 账号时间预算已到，补跑跳过")
                break
            log("  [任务·补跑] %s" % code)
            try:
                out["records"].append(run_code(key, code, templates, do_delete, log,
                                               deadline=deadline, stop=stop))
            except Exception as e:
                log("    !! %s 异常：%s: %s" % (code, type(e).__name__, str(e)[:160]))
                out["records"].append({"code": code,
                                       "error": "%s: %s" % (type(e).__name__, str(e)[:200])})

    if do_claim and not dry:
        log("  [领取] ...")
        res = T.run_account_tasks(acct, cfg)
        out["claim"] = {"status": res.get("status"), "reason": res.get("reason"),
                        "credit_got": res.get("credit_got"),
                        "claimed": res.get("summary", {}).get("claimed")}
        log("    %s | 本次领取 %s 积分" % (res.get("reason"), res.get("credit_got")))

    m, err = fetch_map(key)
    if not err:
        out["final"] = {
            "done": sum(1 for t in m.values() if t.get("done")),
            "total": len(m),
            "profile_level": None,
        }
    return out


def main():
    argv = sys.argv[1:]

    def opt(name, default=None):
        if name in argv:
            i = argv.index(name)
            if i + 1 < len(argv):
                return argv[i + 1]
        return default

    if not argv or "--help" in argv or "-h" in argv:
        print(__doc__)
        return 0

    keys = [x for x in (opt("--accounts", "") or "").split(",") if x]
    if not keys:
        print(__doc__)
        return 1
    raw_codes = opt("--codes", "proven")
    if raw_codes.strip() in ("proven", "PROVEN", "已验证", "ui", "UI", "all", "ALL", "全部"):
        # ui / all / proven 一律 = **只跑已验证的名单**（用户要求「以后就只用这些去做」）。
        # 想跑没验证过的（如 Expert_team_use_3）必须显式写出来。
        code_list = list(PROVEN_CODES)
    else:
        code_list = [x for x in raw_codes.split(",") if x]
    codes = code_list
    templates = [x for x in (opt("--templates", "") or "").split(",") if x] or TEMPLATE_POOL
    do_claim = "--no-claim" not in argv
    do_delete = "--keep" not in argv
    stay = "--stay" in argv
    dry = "--dry" in argv

    def log(m):
        print(m, flush=True)

    log("账号：%s   任务：%s" % (keys, codes))
    log("夜间窗口(23:00-08:00)：%s" % ("是" if in_night() else "否"))

    main_key, main_menu = AS.current_key()
    log("客户端当前账号：%s (界面=%s)" % (main_key, main_menu))

    # 每账号时间预算（秒）：兜底防止「某个号某个 UI 任务内部兜底失效 / 一直 processing」
    # 把整个账号乃至后续所有账号全拖死 —— 用户原话：不能因为一个号做不完就卡住其它号。
    # 到了预算，该账号剩余任务整体跳过（run_account 在每轮任务开始前检查 deadline）。
    # 注意：单个长任务内部（如专家团）另有自己的 TEAM_BUDGET 兜底，这里只卡「账号总时长」。
    ACCOUNT_BUDGET_SECS = int(os.environ.get("BR_ACCOUNT_BUDGET", "1200"))

    report = {"accounts": [], "main_before": main_key, "main_menu": main_menu}
    try:
        for k in keys:
            log("\n===== %s =====" % k)
            deadline = time.time() + ACCOUNT_BUDGET_SECS
            report["accounts"].append(
                # 把「停止任务」信号接进去：以前 stop=None → run_code 里的
                # `if stop and stop()` 形同虚设，只有 run_task 内部看得到停止标志，
                # 账号级循环/任务级循环都停不下来（用户投诉过）。
                run_account(k, codes, templates, do_claim, do_delete, dry, log,
                            deadline=deadline, stop=U.stop_requested))
    finally:
        if not dry and not stay and main_key and main_key not in keys:
            back = AS.switch_to(main_key, reload=False)
            report["switch_back"] = {"ok": back.get("ok"),
                                     "menu": (back.get("after") or {}).get("menu")}
            log("\n[切回] %s ok=%s 界面=%s" % (main_key, back.get("ok"),
                                              (back.get("after") or {}).get("menu")))
        elif not dry:
            log("\n[切回] 无需（主号已在目标列表内或 --stay）")

    print("\n=== 汇总 ===")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
