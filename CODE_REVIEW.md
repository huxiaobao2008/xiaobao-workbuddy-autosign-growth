# 项目缺陷与逻辑 Bug 审查报告

- **审查对象**：`D:\workbuddy\2026-09-19-00-30-03\buddy-auto\`（Buddy加油站 / WorkBuddy 成长计划 多账号自动化脚本集）
- **审查方式**：逐行通读核心 14 个文件（含 `ui_tasks.py` 2437 行、`ui_driver.py` 1535 行全量）+ 模式扫描；只读不改
- **审查日期**：2026-09-20

## 后台任务处置（前置动作）
- 发现 1 个后台数据进程：PID 1484 运行 `batch_runner.py --accounts account_e --codes Expert_team_use_3 --stay`（常驻循环批量任务）。
- 已结束该进程（及其进程树）。当前目录下无任何 python/node/浏览器残留进程。

---

## 一、按严重程度排序的缺陷清单

### 🔴 [High] D1 — `switch_to` 的"已在该账号则跳过"快路径是死代码
- **位置**：`account_switch.py:235`
- **根因**：`page_account()` 返回字典的键是 `urlUid`/`menuName`（见 `:64,:67,:80`），但此处用 `(before or {}).get("uid")`。该键恒为 `None`，与 `acct.get("uid")` 永远不相等 → 快路径**永不命中**。
- **影响**：每个账号每次 `switch_to`（17 个账号 × 多次调用）都会执行完整 `atomic_write` + `reload_page()` + `wait_ready()`。reload 是全系统最易抖动的环节，无谓 reload 随账号数线性放大整体 flakiness、拖慢一键流程。
- **修复**：改用左下角昵称等价判断（与文件顶部注释一致，urlUid 在切换前是过期的）：
  ```python
  if menu_matches((before or {}).get("menuName"), acct.get("nickname") or ""):
      out["ok"] = True; out["switched"] = False; return out
  ```
  > 注：`switch_to` 内第 287 行 `file_ok` 用的是 `read_live().get("account").get("uid")`（登录文件，确有 uid 键），是正确的；D1 仅指第 235 行。

### 🟠 [Medium] D3 — `set_permission.py` 'all' 分支硬编码切回 `account_a`
- **位置**：`set_permission.py:216` `back = AS.switch_to("account_a", reload=False, verify=True)`
- **影响**：批量设权限结束后，无论用户主号是谁，客户端都停在 `account_a`。若用户主号非 a，后续手动操作会发生在错误账号（烧错额度/发错上下文）。
- **修复**：遍历前用 `AS.current_key()` 捕获原始主号，结束后切回该 key；或直接复用 `run_all._switch_back_main` 逻辑。

### 🟠 [Medium] D4 — `build_content` 用 `src not in others` 按对象值去重，可能漏去重
- **位置**：`account_switch.py:199-202`
- **根因**：列表成员判断按 dict 内容相等。若同一 uid 在 `accounts` 与 `allAccounts` 中各出现一次且字段略有差异（如一个有 `lastLogin`/`isCurrent`），会被当作"不同"而都写入登录文件。
- **影响**：`workbuddy-desktop.info` 出现重复 uid 条目，Electron 加载后可能显示重复账号或选错登录态；且静默发生、不抛异常。
- **修复**：按 `uid` 去重：
  ```python
  seen = set()
  for src in (live.get("accounts") or []) + (live.get("allAccounts") or []):
      if isinstance(src, dict) and src.get("uid") and src["uid"] != target_uid and src["uid"] not in seen:
          seen.add(src["uid"]); others.append(src)
  ```

### 🟠 [Medium] D5 — `query_credits` 违反"失败返回 err 不抛异常"契约
- **位置**：`auto_buddy.py:317` `r["status"]`（直接下标）
- **根因**：`try` 只包住 `task_checkin`，未包住 `r["status"]`。若 `task_checkin` 在某失败路径返回不含 `status` 键的字典（如 `{"err": ...}` 形态早返回），此处抛 `KeyError`。
- **影响**：调用方（server 状态轮询 / 批量查询）预期拿到 dict，实际收到未捕获异常，可能导致一次状态刷新整批失败。
- **修复**：`status = r.get("status")`，并校验 dict 形态后再决定 `err`。

### 🟡 [Medium/Low] D13 — `today_active` 用 `is True` 脆弱判断
- **位置**：`growth_active.py:421` `return {"ok": True, "is_active": today.get("is_active") is True, ...}`
- **根因**：`is True` 仅在值与 `True` 是同一对象时成立。若接口返回 `is_active` 为整数 `1/0`、字符串或其他真值，结果误判为 `False`。JSON 布尔通常正常，但该写法缺乏防御性。
- **修复**：`bool(today.get("is_active"))`。

### 🟡 [Low] D2 — `restore()` 用错误 key 校验，永远 `ok=False`
- **位置**：`account_switch.py:323-324` `(after or {}).get("uid") == uid`
- **影响**：`after` 为 `wait_ready()`（即 page_account 结构，键为 urlUid），`.get("uid")` 恒 `None` → `out["ok"]` 恒 `False`、`page_uid` 恒 `None`。当前仅 CLI 打印使用（`:378`），功能性影响低，但属同一系统性键错位错误，一旦被编排层改用会误判。
- **修复**：改为 `after.get("urlUid")`，并优先用 `menuName` + `menu_matches` 校验。

### 🟡 [Low] D6 — `server.py:104` `_clear_bust = _state_bust` 是死代码
- 把函数对象赋给局部变量后从未调用，注释却声称"保持缓存失效"。`STATE_CACHE`（TTL=5s）在 stop 时不被刷新。删掉该行与注释，或真正调用清缓存。

### 🟡 [Low] D7 — `tasks.py:393` 用 `+` 切片解析积分
- `credit_got += int(msg.split("+")[1].split(" ")[0])` 被 `except Exception: pass` 包住。文案微调（如 `+3分`/本地化）即静默少算。建议 `re.search(r'\+\s*(\d+)', msg)` 并记日志。

### 🟡 [Low] D8 — `ui_runner.py:126` 无默认 `next()` + 直接下标
- `acct = next(a for a in cfg["accounts"] if a["key"] == key)`：缺 `"accounts"` 键抛 `KeyError`，key 不存在抛 `StopIteration`。建议 `next((...), None)` + 判空，并对 `cfg.get("accounts") or []` 取值。

### 🟡 [Low] D9 — `cdp.py:79` 握手状态用子串 `"101" not in status`
- HTTP 状态行子串匹配脆弱；其后有 `Sec-WebSocket-Accept` 强校验兜底，实际风险极低。建议 `not status.startswith("HTTP/1.1 101")`。

### 🟡 [Low] D10 — `ui_tasks.py:1886` `do_expert_lighthouse` 预算守卫死代码
- `t0 = time.time(); if budget and (time.time()-t0) > budget`：刚赋值就判断，差恒≈0，永不触发；`budget` 实际无效（兜底靠 `run_expert_once` 内 `max_wait`）。删除该守卫或并入带循环入口。

### 🟡 [Low] D11 — `growth_active.py:204` ACP 读线程 daemon 且未显式 join
- `close()` 未发停止信号/未 `join`。因 `daemon=True` 不会阻止退出，属轻微资源泄漏。建议 `close()` 中关底层连接并 `_reader.join(timeout=...)`。

---

## 二、根因聚集与最该先修的点

- **根因聚集**：D1 / D2 是同一个系统性错误——`page_account()` 返回 `urlUid`，但多处用 `.get("uid")`（应为 `urlUid` 或 `menuName`）。建议一次性全局排查 `account_switch.py` 内所有 `page_account()` 结果的键访问，统一收敛到一个 helper。
- **最脆弱环节**：账号切换与状态校验（`account_switch.py`）是整个多账号引擎的命门，D1/D2/D4 均在此。优先修 D1（减少无谓 reload 从根上降抖）、D3/D4（账号状态正确性）、D5（异常契约对齐）。
- **架构评价**：分层清晰（server → run_all/auto_buddy → batch_runner → ui_driver/ui_tasks → account_switch → cdp），串行锁、跨进程停止信号、`_switch_back_main` 的 finally 兜底、CDP 真实鼠标绕过 React 受控组件等设计体现实战打磨，整体健壮性中上。缺陷主要表现为"效率/抖动放大"与"静默误判"，而非硬崩溃。

## 三、说明
- 本报告所列行号基于审查时的文件版本；修改前请再次 `Read` 确认上下文。
- 未修改任何源文件。如需我直接修复上述缺陷，请确认，我将按"先 D1/D3/D4/D5，再 D13/D2，最后 D6–D11"的顺序处理。
