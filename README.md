# Buddy 加油站 · 成长计划自动执行与账号管理

> ⚠️ **项目已拆分（2026-09-21）**：原仓库曾同时包含「自动签到」与「抖音/快手自动发布」两类功能，
> 现已拆分为两个**互相独立**的仓库：
> - **本项目 `buddy-auto`（即本仓库）** —— 仅保留 **WorkBuddy 客户端自动签到 + 成长任务 + 领积分 + 出行奖励**，
>   所有与自动发布相关的代码、配置、素材均已迁移至独立项目 **`buddy-publish`**，本仓库不再包含任何发布逻辑。
> - **`buddy-publish`** —— 抖音 / 快手自动发布 + 竖屏演示视频制作（独立仓库，见 `D:\workbuddy\buddy-publish`）。
> 本次拆分同时修复了两个 Bug：① UI「停止任务」请求 404（未注册 `stop` 动作）；
> ② 一键全自动切号后界面停在旧账号导致普通任务（如 `template_5`）进度恒为 0（已改为切号后 `reload=True`）。

零依赖 Python 程序（只用标准库 + 本地网页），为多个微信号各自独立完成
**Buddy 加油站每日签到**、**成长计划任务（接取 + 领取）**，按配置时间循环执行，
逐次记录成败原因，异常时弹系统提醒。程序只做两件事：只读本机 WorkBuddy 登录态、
请求 workbuddy.cn 官方接口；不含任何账号密码，token 只在本地且输出脱敏。

---

## 零、项目上下文（换人 / 换工具继续开发，先看这一节）

> 这一节是需求与实现的事实来源，读完即可直接接手，不需要重新描述需求。

### 0.1 需求

| 编号 | 需求 | 实现位置 | 状态 |
|---|---|---|---|
| R1 | 对所有已录入账号，遍历签到与成长任务列表，筛选未完成/未领取的，串行可控逐一执行并领取积分 | `tasks.run_tasks` + `auto_buddy.cmd_run` | 已实现 |
| R2 | 执行前校验任务状态，跳过已领取 / 已过期 / 已锁定 / 进度未完成的，不重复提交、不漏领 | `tasks.normalize` / `run_tasks` 的 skip 分支 | 已实现 |
| R10 | 每处理完一个账号输出积分余额，取不到要明确报错；全部跑完汇总「账号标识 / 执行前 / 执行后 / 增量」 | `tasks.run_tasks` 的 balance 字段 + `auto_buddy.cmd_run` 汇总段 | 已实现 |
| R11 | 自动识别并跳过需付费/充值的任务（如「公益专家」需捐款），标记「已跳过（需付费）」，绝不执行、绝不扣费 | `tasks.detect_paid` + `config.paid_tasks` | 已实现 |
| R3 | 单个任务失败不影响其它任务 | `run_tasks` 内每个任务独立 try/except，失败只记日志 | 已实现 |
| R4 | 页面按账号分组展示成长任务，按已完成/未完成分组，含任务名、状态、可得积分、累计已获积分 | `ui.html: taskBox/taskRows` + `/api/state` | 已实现 |
| R5 | 展示数据与自动执行结果一致，执行后回写刷新 | 执行末尾重新 `fetch_tasks` 回写 `logs/tasks_state.json`，页面每次 `load()` 重新拉取 | 已实现 |
| R6 | 新账号登录后自动入库并纳入自动执行 | `core.auto_sync_accounts` + `server.watch_new_accounts`（30s 巡检）+ `auto_buddy.py --sync` | 已实现 |
| R7 | 点击账号即切换过去并加载其任务数据 | `/api/switch` + `ui.switchTo`，`allow_write_client_auth=true` 时连客户端登录态一起切 | 已实现 |
| R8 | 错误处理、失败重试、并发控制（串行）、结构化日志 | `tasks._retry`、`tasks.SERIAL_LOCK`、`logs/tasks.jsonl` | 已实现 |
| R9 | 接口异常 / 登录态失效有明确降级与提示 | `auth_error` → `auth_expired` → 气泡提醒 + 页面 need_login 提示 | 已实现 |

### 0.2 模块职责（不要交叉写代码）

```
auto_buddy.py  调度与数据层：配置读写、凭证、签到、账号增删改、CLI（--run/--sync/--ui/...）
tasks.py       成长任务引擎：拉列表、判定、接取、领取、串行锁、重试、结构化日志、状态回写
server.py      HTTP 层：只做路由与转发，业务逻辑一律调用上面两个模块
ui.html        展示层：无框架，fetch /api/state 后渲染
notify_toast.py Windows 气泡提醒（ctypes Win32）
```

约定：新增能力优先加在 `tasks.py`（任务类）或 `auto_buddy.py`（账号/调度类），
`server.py` 只加薄薄一层 action，`ui.html` 只加渲染与按钮。

### 0.3 真实接口清单（已核实，勿臆造）

```
POST /v2/billing/meter/checkin-activity-status     签到状态（含 total_credits / streak）
POST /v2/billing/meter/daily-checkin               领取签到（已签返回 code=10001）
GET  /v2/activity/growth/tasks                     成长任务列表 ★
POST /activity/growth/tasks/accept                 接取任务  body {task_codes:[...]}
POST /activity/growth/tasks/{code}/claim           领取任务奖励
GET  /v2/activity/growth/profile                   成长档案（level / completed / total）
GET  /v2/activity/growth/buddy/info                成长伙伴
POST /v2/activity/growth/buddy/travel/claim        伙伴出行到达奖励
```
来源：桌面端 `app.asar` + 官网 usercenter 前端产物 `growthSpace-*.js` 双向核对。
注意：tasks 用 `/v2` 前缀，accept/claim **不带** `/v2`；反过来会 404。
非 `/v2` 的 web 专属接口（energy/badges/streak/travel-status）在桌面鉴权下 404，未使用。

### 0.4 任务状态机

```
not_accepted --accept--> accepted --(进度达标)--> in_progress/completed --claim--> claimed
```
- `claimed` 视为已完成；`locked` / `valid_end` 已过 → 跳过
- 进度未达标（如 1/5）→ 跳过并提示「需先在客户端完成该操作」，程序不会伪造进度
- claim 返回 `already_claimed` / `task not completed` → 按「跳过」处理，不算失败、不重试

### 0.5 已知边界与限制

- 任务分三类：
  1. 可自动完成（接取即达标）；
  2. 需真人操作（创建画布、召唤专家等）—— 程序只接取、在进度达标时领取，
     **不伪造操作**，页面显示「待完成」；
  3. **需付费/捐款**（如「公益专家」需完成 1 次捐款）—— 硬跳过，程序绝不触碰、绝不扣费。
- 积分有两个口径：
  - **积分余额** = Buddy加油站积分（签到接口 `total_credits`），官方只暴露这一个余额接口；
    成长任务领取的积分计入成长账户、无公开余额接口，所以「增量」在已签到时可能是 0，属正常。
  - **本次任务获得积分** 单独统计，不会漏报；页面上的「待领积分」= 未完成任务的可得积分合计。
- 写回客户端登录态（真正让客户端换号）默认关闭：`allow_write_client_auth=false`。
  开启后会备份原文件再覆盖 `workbuddy-desktop.info`，**需重启客户端才生效**。
- 定时：WorkBuddy 自动化每天 08:00 跑 `--sync --run`；OS 级计划任务需自己跑
  `--install-scheduler`（沙箱禁用了 schtasks.exe）。

---

## 一、当前配置

| 账号 key | 备注 | 昵称 | UID | 每天执行时间 |
|---|---|---|---|---|
| `account_a` | 主号·邻家 | A༺邻家༻私人定制改装洗美工作室 | `c1b34955…58ad` | 08:00 |
| `account_b` | 副号·小宝 | 小宝·觉醒之旅 | `648cced2…f1f` | 08:05 |
| `account_c` | 18347426898 | 18347426898 | `a4371605…c1fb` | 08:00 |
| `account_d` | 15598157728 | 15598157728 | `5cee3cc7…b6c4` | 08:00 |
| `account_e` | 乡下人 | 乡下人 | `0d33254f…cc1e` | 08:00 |
| `account_f` | 15661172224 | 15661172224 | `935f3d08…3ba4` | 08:00 |

（后四个是后来在网页界面里从「已登录账号」一键加进来的，不需要就在界面里点「移除」或「停用」。）

自动执行的任务（每个账号独立开关）：
1. **每日签到** — `POST /v2/billing/meter/daily-checkin`，先查状态再领，已签自动跳过，幂等不重复。
2. **成长伙伴状态** — `GET /v2/activity/growth/buddy/info`，同步成长伙伴（当前两号均为「暴富喵 UR」）。
3. **出行到达奖励** — `POST /v2/activity/growth/buddy/travel/claim`，伙伴出行到达时自动领积分；未到达返回 `not arrived yet`，记为「跳过」而非失败。

> 接口路径已从本机客户端 `app.asar` 源码核实，不是猜的。

---

## 二、文件结构

```
buddy-auto/
├─ auto_buddy.py          主程序：调度、凭证、签到、账号管理、CLI
├─ tasks.py               成长任务引擎：接取/领取、串行锁、重试、结构化日志、状态回写
├─ config.json            配置：账号、执行时间、提醒、重试、自动入库  ← 日常只改这个
├─ server.py              本地网页服务（接口层，复用 auto_buddy / tasks）
├─ ui.html                网页管理界面：账号列表 / 添加 / 切换 / 任务分组 / 积分
├─ notify_toast.py        Windows 原生气泡提醒（ctypes 调用，无 PowerShell 依赖）
├─ accounts/
│   ├─ account_a.cred.json   各账号凭证快照（勿外传）
│   └─ …
├─ logs/
│   ├─ runs.jsonl         每次账号级执行的完整记录
│   ├─ tasks.jsonl        任务级结构化日志：账号 / 任务 / 步骤 / 状态 / 原因
│   ├─ tasks_state.json   最新任务快照（执行后回写，页面以此为准）
│   ├─ latest.json        最近一次执行结果
│   ├─ summary.txt        最近一次执行的人类可读汇总
│   ├─ alerts.log         告警记录
│   └─ scheduler.log      计划任务调用时的标准输出
└─ README.md              本文档（含需求上下文，见第零节）
```

---

## 三、日常命令

```bash
cd D:\workbuddy\2026-09-19-00-30-03\buddy-auto
set PY=C:\Users\Administrator\.workbuddy\binaries\python\versions\3.13.12\python.exe

%PY% auto_buddy.py --list          # 看两个账号状态和最近执行结果
%PY% auto_buddy.py --check --run --force   # 体检：只查询，不领取
%PY% auto_buddy.py --run --force   # 立刻跑一次（忽略时间窗）
%PY% auto_buddy.py --run --account account_b --force   # 只跑副号
%PY% auto_buddy.py --discover      # 扫描本机所有登录态（找账号用）
%PY% auto_buddy.py --notify-test   # 测试提醒通道

# 账号管理（网页界面里也能做，等价）
%PY% auto_buddy.py --add <UID>     # 把本机某个登录态账号加入列表
%PY% auto_buddy.py --remove <KEY>  # 从列表移除（凭证文件保留）
%PY% auto_buddy.py --disable <KEY> # 停用 / --enable 启用
%PY% auto_buddy.py --capture-all   # 一键续期所有还能抓到的凭证
%PY% auto_buddy.py --sync            # 扫登录态，新账号自动入库（--sync --run 可连用）
%PY% auto_buddy.py --ui              # 启动网页管理界面（默认 http://127.0.0.1:8765）
```

---

## 四、任务自动执行流程（签到 + 成长任务）

一次 `--run` 对每个启用账号串行做四件事（`config.json` 里可单独关）：

1. **每日签到** `checkin`：先查状态，今日未签才领取，已签跳过
2. **成长任务清单** `growth_tasks`（核心）：
   - 拉 `GET /v2/activity/growth/tasks`
   - **先判付费**：命中 `paid_tasks` 名单或文案关键词（捐款/公益/充值…）→ 标记
     「已跳过（需付费）」，不接取、不领取、不产生任何扣费
   - 其余逐个判定：`已领取/已锁定/已过期` → 跳过；`未接取` → accept；进度达标 → claim；
     进度未达标 → 跳过并说明「需先在客户端完成」
   - 每个任务独立 try/except，一个失败不中断其它；账号级异常也不会中断整轮
   - 执行完**重新拉一次列表**回写 `logs/tasks_state.json`，页面展示的就是这份
3. **成长伙伴状态** `growth_info`
4. **出行到达奖励** `growth_travel_claim`

**积分余额输出**：
- 每个账号处理完立刻输出 `积分余额：执行前 → 执行后（增量 ±N）`；
  取不到余额时**明确报错** `! 积分余额获取失败：<原因>`，不会静默跳过
- 全部跑完输出汇总表：`账号标识 / 执行前 / 执行后 / 增量`
- 口径说明：这里的「积分余额」= Buddy加油站积分（官方唯一暴露的余额口径，
  来自签到接口 `total_credits`）；成长任务领取的积分计入成长账户、无公开余额接口，
  所以增量只反映签到变化，任务获得的积分会单独列出 `本次任务领取 +N 积分`

**付费任务配置**（`config.json`）：
```jsonc
"paid_tasks": {
  "codes": ["Expert_Philanthropy"],     // 显式名单：体验「公益专家」（需完成1次捐款）
  "keywords": ["捐款","捐赠","公益","付费","充值","支付","购买","消费","下单","开通会员","¥"]
}
```
接口本身**不返回**费用字段，所以靠「显式名单 + 文案关键词」双重判定；发现新的付费任务，
把 task_code 加进 `codes` 即可，永久生效。命中后 `claimable`/`accept_needed` 都会被置 false，
页面显示红色「需付费」标签 + 置灰的「已跳过（需付费）」按钮。

**最终输出结构**（命令行 `--run`，网页里对应同样的字段）：
```
===== 积分汇总（账号标识 / 执行前 / 执行后 / 增量） =====
  account_a(主号·邻家)     400 → 400  (+0)
  ……
===== 任务明细（完成 / 跳过 / 失败） =====
  账号 account_a  完成 15/18  领取 0  接取 0  跳过付费 1  跳过其它 2  失败 0
      [跳过·需付费] 体验「公益专家」（Expert_Philanthropy）：命中付费任务名单
      [失败] xxx：失败原因          ← 有才列
```

控制与容错：
- **串行**：`tasks.SERIAL_LOCK` 全局一把锁，CLI / 网页 / 定时任务共用；
  拿不到锁直接返回「已有执行在进行中」，不会并发打接口
- **不中断**：单个任务失败 → 记进 `failed_tasks` 继续下一个任务；
  单个账号异常 → 记成「账号级异常」继续下一个账号
- **重试**：只有网络异常（-1）与 5xx 才重试，`retry.attempts` 默认 2 次、退避 2 秒；
  业务错误（4xx 带 msg）不重试，避免重复提交／重复扣费
- **不重复提交**：已领取一律跳过；claim 返回 `already_claimed` 也按跳过处理
- **结构化日志** `logs/tasks.jsonl`，每行一条：
  `ts / date / account / nickname / task / task_title / step(fetch|balance|accept|claim|skip|skip_paid|error) / status / reason`

---

## 五、网页管理界面（列表 / 添加 / 切换 / 任务 / 积分）

```bash
%PY% auto_buddy.py --ui          # 加 --port 8766 换端口
```

启动后自动打开浏览器；只监听 `127.0.0.1`，页面和接口都不含 token。

**上半区「已登录账号」** —— 从本机登录态实时读取（含历史备份文件），列出昵称、手机号、UID、
登录态剩余天数，以及**该账号的积分**（累计 / 连续天数 / 今日是否已签）。
- 还没加入列表的账号：右侧「添加」按钮，点一下写入 `config.json` 并自动抓凭证
- 已加入的：按钮置灰显示「已添加 · account_x」，不可重复添加
- 登录态为空 / 文件损坏 / 目录不存在：给出对应的空状态或黄色提示条，不会白屏

**下半区「账号列表」** —— 就是 `config.json` 的内容，每行展示**该账号的积分**（累计 / 连续 /
今日是否已签）、成长任务完成度、凭证剩余天数、执行时间；操作列四个按钮：
- **执行**：立刻跑该账号的签到 + 成长任务
- **登录/续期**：该账号的**独立登录入口**。本机还留着它的登录态就直接续上（不用扫码）；
  没有就明确提示「请先打开客户端扫码登录」，`need_login` 会让页面弹出对应指引
- **停用/启用**：临时把某个号从定时任务里摘出去
- **移除**：从列表删掉（凭证文件保留，不误删）

**点击账号行 = 切换到该账号**（行会高亮并标「当前」），下方展开它的成长任务面板：
- 任务按 **未完成 / 已完成** 分组，每行显示任务名、状态、进度、`可得积分`，
  并按状态给按钮：`接取` / `领取` / `已领取`（置灰）/ `待完成`（置灰）
- 面板顶部显示 `已完成 x/y`、成长`等级`、`待领积分`，以及「执行本账号」
- 再点一次该行可收起面板
- 想让客户端也跟着换号：把 `config.json` 的 `allow_write_client_auth` 改成 `true`，
  切换时会备份并写入客户端登录态文件（**需重启客户端生效**）；默认关闭，只切程序内的当前账号

**顶部按钮**：一键执行全部 / 一键续期全部凭证 / 打开客户端登录 / 扫描新账号 / 刷新。
顶部三个数字是账号数、今日已签数、累计积分合计。

**新账号自动入库**：网页服务启动时会扫一次，随后每 30 秒巡检一次本机登录态；
出现配置里没有的新账号就自动加入列表（enabled + 全任务开关）并抓取凭证，直接纳入自动执行。
也可用顶部「扫描新账号」或命令行 `--sync` 手动触发。

接口（同一套数据读写，前端只是壳）：
`GET /api/state`；
`POST /api/add | remove | toggle | run | capture | capture-all | open-client | task | switch | sync`。

---

## 六、改配置（改完不用动代码）

编辑 `config.json`：

```jsonc
"accounts": [
  {
    "key": "account_a",            // 账号标识，命令里用
    "label": "主号·邻家",           // 自己看的备注
    "uid": "c1b34955-...",         // 与凭证绑定，抓错号会报错
    "cred_file": "accounts/account_a.cred.json",
    "enabled": true,               // false = 停用该账号
    "times": ["08:00"],            // 每天执行时间点，可写多个 ["08:00","20:30"]
    "tasks": { "checkin": true, "growth_tasks": true, "growth_info": true, "growth_travel_claim": true }
  }
],
"schedule": {
  "trigger_mode": "daily",         // daily=每天定点；interval=固定间隔循环
  "every_minutes": 60,             // interval 模式下的间隔（最小 30）
  "window_minutes": 25             // 时间点前后多少分钟算"到点"，防计划任务延迟漏跑
},
"auto_add_new_accounts": true,        // 新账号登录即自动入库
  "allow_write_client_auth": false,        // true=切换账号时连客户端登录态一起改（需重启客户端）
  "retry": { "attempts": 2, "backoff_seconds": 2 },   // 仅对网络异常/5xx 重试
},
"alert": {
  "desktop_notify": true,          // 异常弹 Windows 气泡
  "notify_on_success": false,      // 成功也弹（默认关，免打扰）
  "webhook_url": ""                // 可选：异常 POST 到企业微信/钉钉机器人
}
```

---

## 七、定时执行

**现状**：已建 WorkBuddy 定时自动化「Buddy加油站双账号每日自动签到与成长任务」，
每天 08:00 触发，跑完直接在会话里汇报结果。

**想改成操作系统级定时**（不依赖本软件打开）：在你自己的终端里执行一次即可，
程序会按 `config.json` 里所有启用账号的时间点自动注册 Windows 计划任务：

```bash
%PY% auto_buddy.py --install-scheduler   # 注册/刷新
%PY% auto_buddy.py --remove-scheduler    # 删除
```

任务名形如 `WorkBuddyAuto_0800`。时间点改动后重新执行一次 `--install-scheduler` 即可。

---

## 八、换号 / 加号 / 凭证过期

登录态有效期约 60 天，过期后程序会报「登录态失效」并弹提醒。处理：

1. 打开 WorkBuddy 客户端 → 登录目标微信号；
2. `python auto_buddy.py --capture account_a`（抓当前登录态到该账号）；
3. 若该号的历史登录态还在本机，也可指定文件抓取：
   `python auto_buddy.py --capture account_b --from-file "<登录态文件绝对路径>"`
   （先用 `--discover` 看本机存过哪些号）。

**加第三个号**：在 `config.json` 的 `accounts` 里复制一段，填新 key/label/uid，
然后客户端登录那个号执行 `--capture <新key>`。

**切换**：点网页界面里的账号行即可切到该账号并展开它的任务（命令行为 `--add` / `--capture`）。
默认只切「程序内当前账号」；要连客户端一起换号，把 `allow_write_client_auth` 设为 `true`
（会先备份再覆盖客户端登录态文件，重启客户端后生效）。
`enabled: false` 即可停用某个号。

---

## 九、日志与告警

`logs/runs.jsonl` 每行一条完整记录，字段：
`ts / date / account / label / nickname / status(success|skip|fail) / trigger / cred_expiry_days / tasks.{任务}.{status,code,reason}`

举例：
```json
{"ts":"2026-09-19 00:45:13","account":"account_b","status":"success",
 "tasks":{"checkin":{"status":"success","code":"claimed","reason":"签到成功 +100 积分，连续 4 天，累计 300"},
          "growth_travel_claim":{"status":"success","code":"claimed","reason":"出行到达奖励领取成功"}}}
```

`logs/tasks.jsonl` 任务级结构化日志，每行一条：
`ts / date / account / nickname / task(任务码) / task_title / step(fetch|accept|claim|skip|error) / status / reason`

```json
{"ts":"2026-09-19 01:23:46","account":"account_c","task":"create_canvas",
 "task_title":"体验「设计创意模式」","step":"skip","status":"skip","reason":"已领取"}
```

告警触发条件：
- 任一账号任一任务失败 → 气泡提醒 + `logs/alerts.log`
- 凭证剩余不足 7 天 → 提前提醒重新抓取
- 可选 webhook 推送

退出码：`0` 全部成功 / `1` 存在失败 / `2` 凭证失效或缺失。
