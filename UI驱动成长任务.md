# 用 CDP 驱动客户端完成成长任务（实测可用）

成长任务的进度由服务端检测「真实产品使用事件」得出，**纯 API 刷不动**。
唯一可行路径是驱动桌面客户端本体做真实操作。本目录的 `ui_driver.py` 就是这个驱动器。

## 一、前置

1. 客户端带调试端口启动：双击 `restart-cdp.cmd`（端口 9222）。
   **必须由 WorkBuddy 之外的进程启动**（资源管理器双击即可）——
   会话内 spawn 的子进程都活在 kill-on-close 的 Windows Job 里，命令一结束就被连带杀掉。
2. 客户端**必须登录目标任务所属账号**。UI 驱动只能作用于当前登录账号；
   多账号不用手动切换，用 `account_switch.py` / `batch_runner.py` 自动切（见第八节）。
3. 确认 `python cdp.py info` 能看到页面。
4. **窗口必须可见**（否则一切都会「看起来像坏了」，见下面「一·零」）。

## 一·零：窗口被隐藏 = 万恶之源（2026-09-19 血泪）

Chromium 在窗口被完全遮挡 / 远程会话断开 / 锁屏时，会把页面判定为 `hidden`。
症状**极隐蔽**，会被误判成「页面有 bug」，实则只是窗口不可见：

| 症状 | 真实原因 |
|---|---|
| 页面内的 `await sleep(2500)` 实际跑了 **47 秒**（慢 ~19 倍），驱动脚本必然 CDP 超时 | 隐藏页面的定时器被重度节流 |
| 专家列表 `暂无内容` / `.ec-expert-grid` 高度 0 / 渲染 0 张卡 | react-virtuoso 拿不到容器高度，不渲染任何 item |
| reload、换分类、等 120s 全都无效 | 不是前端状态问题，重载也没用 |

**诊断一行搞定**：

```python
python -c "import ui_driver as U, json; print(U.js('(()=>({hidden:document.hidden,vis:document.visibilityState}))()'))"
```

`hidden: true` 就是它。

**修复**：`Emulation.setFocusEmulationEnabled {enabled:true}` 可强制拉回 `visible`。
关键注意：**焦点模拟是按 CDP 连接生效的**，而本项目每次操作都新建连接，
所以已经固化在 `cdp.connect()` / `cdp.connect_target()` 里（见 `cdp.unhide()`），
不需要每次手动设。**不要删掉这段**。

窗口真的最小化时，另外用 `python win_focus.py WorkBuddy`（ctypes 调 Win32
`ShowWindow(SW_RESTORE)`）恢复——bash 内禁止 powershell，所以用 ctypes。

## 一·补：多账号怎么切（已实现）

客户端是单账号的，界面里没有「切换账号」按钮（只有「退出登录」）。
切换 = **原子替换登录态文件**，不用重启客户端：

```
%LOCALAPPDATA%\CodeBuddyExtension\Data\Public\auth\workbuddy-desktop.info
```

```bash
python account_switch.py --who              # 当前登录谁（看界面昵称，别看 URL）
python account_switch.py --list             # 可切换清单 + 凭证剩余天数
python account_switch.py --to account_b     # 切（自动备份 + 校验）
python account_switch.py --restore          # 回滚到上次切换前
```

**关键结论（实测）**：客户端**每次请求都会重读登录文件**，所以
**不需要 `Page.reload`** —— 写入后界面昵称和侧边栏会自己变过来。
不 reload 的好处是：我自己（当前会话）就跑在同一个客户端里，reload 会打断自己的界面。

**校验只能看左下角 `.user-menu-trigger` 的昵称**：URL 里的 `accountSnapshot`
是**页面加载时**生成的快照，不 reload 的切换不会更新它，拿它判断会误判「切换失败」。
而且昵称重绘有延迟（连续快切时尤其明显），所以校验必须**轮询等待**，不能读一次就下结论。

## 二、一条命令跑一个任务

```bash
python ui_driver.py template 幻灯片                 # 默认：Hy3（0.00x 免费）+ 跑完自动删会话
python ui_driver.py template 幻灯片 --model GLM-5.2 # 指定模型（夜猫子这类点名模型的任务）
python ui_driver.py template 幻灯片 --keep          # 保留会话，不删
python ui_driver.py batch-template 幻灯片,深度研究    # 连做多个
```

内部序列：新建任务 → 清空输入框 →（可选）选模型 → 点「+」选模板 → 补一句指令
→ 发送 → 轮询到对话结束 →（默认）删掉自己刚建的那条会话。

## 三、模型选择原则（用户要求：只准免费/最省，GLM-5.2 只给点名任务）

- 默认挑**积分最少或免费**的：`Hy3`（限时免费 0.00x）→ 备选 `Deepseek-V4.1-Flash`（0.03x），
  前者不可用时**自动退到后者**。
- 只有任务**点名模型**时才用点名的：`Model_chat_GLM5.2` → GLM-5.2（每个账号只用一次）。
- 不要一律用一个模型；`Hy4 preview` 会触发频率限制，避开。
- 代码里对应 `CHEAP_MODELS` / `TASK_MODEL_RULES` / `AVOID_MODELS` / `pick_model_for()`。

**⚠️ 这条曾经完全失效（白烧积分）—— 别改回去：**

老代码在 `run_task` 里写的是 `if (model) pickModel(...)`，而**所有 UI 驱动器
（专家 / 灵感 / 设计创意）都传 `model=None`** → 整段「选模型」被跳过 → 客户端沿用它
**自己当前选中的模型**（往往就是 GLM-5.2）。也就是说"最省积分"写在注释里、跑起来没生效。

现在的约定（集中在 `ui_driver.run_task`，驱动器不用管）：

| 传入 | 含义 |
| --- | --- |
| `model=None`（默认） | 自动按 `CHEAP_MODELS` **依次回退**（Hy3 → DeepSeek-V4.1-Flash） |
| `model="X"` | 只用 X，拿不到就报错 |
| `model=""` | 明确「不碰模型选择器」（逃生口，特殊场景才用） |

候选全部失败时**响亮报错并中止**，绝不静默滑回贵模型 —— 宁可重跑，也不要悄悄花钱。
`pick_model_for(code)` 现在只对点名任务返回名字，其余返回 `None`；执行结果里的
`out["model_used"]` 会写明**实际用上的模型**，事后可核对。

## 四、删会话（用户要求：领完积分后删掉，不留记录）

- `run_task(delete_after=True)`（CLI 默认开启）：跑完立刻删掉刚建的那条。
- 删除不会让任务进度倒退——进度是**服务端事件计数**，实测删掉会话后 `template_5` 仍为原值。
- 顺序必须是**先领积分、后删会话**（用户原话「把积分领取完成以后 把任务删除掉」）。
- 保护名单 `PROTECT_TITLES`：用户自己的会话（本对话 + 他的创作任务）任何自动删除都不得碰。

## 五、踩过的坑（照抄即可，别重踩）

| # | 现象 | 原因 / 对策 |
|---|------|-------------|
| 1 | 改 `innerText` / dispatch input 输入框没反应 | 编辑器是 **Slate 受控组件**。用 `Input.insertText` 打字、`Input.dispatchKeyEvent`(Ctrl+A→Backspace) 清空 |
| 2 | 只发模板标签，任务不计数 | AI 会反问「你想要什么」并把会话挂成**「待确认」**，对话没完成。**必须补一句 prompt** |
| 3 | 读到错误的 `--stop` / 一直在跳的计时器 | WorkBuddy 会把视图**切回活跃会话**（用户自己那个）。此时 querySelector 命中的是它，不是目标对话 → 整个序列必须**一条命令连贯跑完**，中途别插别的操作 |
| 4 | 完成判定误判 | 不能只看发送按钮 `--stop`（等用户回答时也不消失）。可靠信号：`.cr-message-list-viewport` 内最后一个 `.cr-agent` 的 `.cr-agent--processing` 消失，且结构（气泡数/文本长度）连续 4 拍不变 |
| 5 | 删不掉刚建的会话 | 刚发完消息的会话处于**「选中」态**，归档按钮禁用。先点一次「新建任务」切首页解除选中 |
| 6 | 找不到靠后的模板（生活小知识等） | 模板行横向滚动且**只渲染约 8 个**，更靠后的拿不到。优先用前 8 个 |
| 7 | `.cmd` 双击乱码 | 批处理必须**纯 ASCII + CRLF**（cmd.exe 按 GBK 解码中文会切行） |
| 8 | 切换账号后「切回主号」误报失败 | 校验用了 URL 的 `accountSnapshot`（**页面快照，切换后不更新**）。只认界面昵称，且要轮询等待重绘 |
| 9 | 快速连续切账号时读到**上一个账号**的昵称/会话列表 | 侧边栏和昵称都是延迟重绘的。切完要等界面昵称对上目标账号，**再做任何读写** |
| 10 | 误删用户的会话 | 旧实现按「侧边栏第一条」当自己的会话去删；列表一滞后就会删到用户的。现改为**跑前拍快照、跑后只删新增的那条**（`taskTitles()` 快照差集），新增数≠1 就拒绝删除 |
| 11 | 删会话报「侧边栏找不到该会话」 | 同样是列表滞后。删之前先 `stable_task_titles()` 等列表稳定 |
| 12 | 夜猫子涨了、`Model_chat_GLM5.2` 却不涨 | 夜间窗口内 GLM-5.2 的使用被归到「夜猫子」活动，不记到「体验模型」。GLM-5.2 相关任务按时间分开跑：**白天**刷 Model_chat，**23:00–08:00** 刷 black_cat |

## 五·补：一条命令跑一个账号（多账号编排）

`batch_runner.py` = 「切账号 → 按任务类型逐个推到达标 → 领取 → 切回」一次跑完。
**必须整条命令一次跑完**，中途不能插别的操作。

```bash
python batch_runner.py --accounts account_d                                  # 默认跑能自动完成的三类
python batch_runner.py --accounts account_b,account_c --codes black_cat    # 只跑夜猫子
python batch_runner.py --accounts account_e --codes template_5,black_cat
python batch_runner.py --accounts account_d --dry                          # 只看计划不动手
```

自动执行策略（其余任务需要人工在客户端操作，不在自动范围）：

| code | 条件 | 做法 |
|------|------|------|
| `template_5` | 用 5 个**不同**模板各发一次 | 循环 `run_task(模板, 一句话指令)`，每次查进度，达标即停 |
| `Model_chat_GLM5.2` | 新建对话 + GLM-5.2 | `run_task(use_template=False, model="GLM-5.2")` |
| `black_cat` | 23:00–08:00 + GLM-5.2，每天 1 次 | 同上，只在夜间窗口跑 |

**一条模板 = +1 进度**（实测）。夜间跑 GLM-5.2 会被算到 `black_cat` 上。

## 六、常用命令

```bash
python task_status.py account_a            # 只读：任务矩阵（删除前后核对进度用）
python task_status.py account_a --grep template_5
python ui_driver.py list                   # 侧边栏会话
python ui_driver.py del-top                # 删最新一条
python ui_driver.py cleanup "标题A,标题B"    # 按标题批量删
python check_convos.py                     # 逐账号列会话（核对有没有残留/误删）
python check_convos.py account_f --del 标题关键字   # 删指定残留
python verify_convos.py account_d          # 带 reload 强制刷新的核对（慢但最准）
python auto_buddy.py --run --account account_a --force   # 接取/领取（含已完成的积分）
```

## 八、其余界面类任务（ui_tasks.py 的驱动器）

`ui_tasks.py` = 「不在对话里」的那些任务的驱动器。每条都是**一次完整动作**
（进页面 → 点到位 → 触发事件 → 回首页），调用方负责切账号与领取积分。

| code | 界面 | 关键动作 | 已验证 |
|------|------|----------|--------|
| `automation_1` | 定时任务 | 添加 → 名称 → 提示词(Slate) → 频率改到未来 → 确定 → 权限二次确认 | ✅ |
| `Library_read` | 资料库 | 侧边栏开面板 → 跨域 iframe 打开文档 → 滚到底 | ✅ |
| `Hp_Appearance` | 设置·外观 | 用户菜单 → 外观 → 点「和平精英激战金秋」卡片 | ✅ |
| `Buddy_App` / `Buddy_App_QQ` | 发现应用 | 点「企鹅教师助手 → 进入」**一次点击同时完成两个任务** | ✅ |
| `expert_5` | 专家中心 | 专家 tab → 召唤 →（**必须再发一句话**） | ✅ |
| `Expert_lighthouse` | 专家中心 | 搜索框输入「轻量云」→ 召唤「腾讯轻量云专家」→ 发一句 | ✅ |
| `Expert_team_use_3` | 专家中心 | 专家团 tab → 召唤 → **积分提醒弹层要勾选 + 继续使用** → 发一句 | 见下 |
| `create_canvas` | 首页·设计创意 | 场景 pill → 快捷动作 → **示例提示词** → 发送 | ✅ |
| `playbook_prompt` | 灵感 | 侧边栏「灵感」→ 案例卡片 → 做同款 → 替换 → 发送 | ✅ |
| `skill_1` | 专家·技能·连接器 | 技能 tab → 试用一个技能 | 6 个号都已完成 |

### 专家中心（expert_5 / Expert_team_use_3 / Expert_lighthouse）

- 入口：侧边栏 `button.conversation-list-tab-button`「专家·技能·连接器」。
- 页内：`.ec-list-tab` 是**列表切换**（`专家` / `专家团`）；`.um-tab` 是**板块切换**
  （`专家` / `技能` / `连接器`）——两者别搞混。
- 卡片：`article.ec-expert-card`，召唤按钮 `.ec-card-summon-btn`。
- 分类：`.ec-category-tab`（全部 / 腾讯专家 / …）；搜索框 `.ec-search-wrapper input`。
- **只召唤不计分**（实测）：召唤只是把专家预填进输入框（还带一段引导语），
  服务端只在**真正产生一次专家对话**时才计数。所以必须 `keep_input=True` 保留预填内容，
  再补一句很短的话发出去。验证：expert_5 由 1/5 → 2/5 立刻 +1。
- 专家团召唤会弹 `.ec-team-summon-confirm-overlay`「积分消耗提醒」：
  先点 `label.ec-confirm-dialog-checkbox`，再点 `[data-track-id=expert_team_confirm_continue]`。
- 单次专家/专家团对话的**实际积分消耗约 0.4–0.6**（提示词很短，Hy3 免费），成本可忽略。
- **流程必须分步**（`_expert_steps()` + `run_task(pre_steps=..., pre_gap=[...])`）：
  JS 只负责「点击后立刻返回」，等待全部交给 Python 的 `time.sleep`。
  曾经把整条流程塞进一次 JS 调用 → 必然超时，原因就是「一·零」里的窗口隐藏节流。
  分步还顺带把失败点定位得很清楚（`out["pre_steps"]` 是每步的返回值数组）。

**⚠️ Expert_team_use_3 长期 0/3 的真根因（2026-09-19 找到，别重踩）：**

现象极具迷惑性：驱动器「跑完了」、`out["sent"]=true`、会话也建了也删了，但进度**永远 0/3**。

真因是**专家中心没挂载完**：`EXPERT_ENTER_STEP` 点完侧边栏**立刻 return**，而专家中心
是整页视图、首屏很重，6s 的间隔常常不够 → 后续步骤报「专家中心没加载出来」+「卡片列表为空」
→ **而 `run_task` 不会因为前置步骤失败就停下**，于是它照样把 prompt 发进一个普通对话：
任务不计分（根本不是那个功能）、白建一条会话、日志还看不出错。

修法三件套（缺一不可）：

1. `EXPERT_ENTER_STEP` 点完**轮询等 `.ec-list-tab` 出现**（最多 20s）再返回；
   `EXPERT_SUMMON_STEP` 的卡片轮询从 16 次提到 30 次。
2. `run_task(pre_must_ok=True)`：**任何一步 `ok=false` 就中止，绝不往下发消息**。
   专家 / 灵感流程都已开启。这是通用闸门 —— 任何"先点 UI 再发消息"的任务都该开。
3. 实测：切「专家团」tab ✅ → 真正召唤出「MVP开发专家团」（12 张卡）→ chip 带上引导语
   「我想从零做一个团队协作工具」→ 发送 → 会话建成 → 干净删除 ✅，且 `model_used="Hy3"`。

顺带说明：专家团不一定会弹积分确认框（实测「MVP开发专家团」就没弹），
`EXPERT_CONFIRM_*` 两步在没有弹窗时返回 `{ok:true, dialog:false}`，属正常。

### 设计创意（create_canvas）

- 场景 pill `.wb-scene-tabs__pill`（日常办公 / 代码开发 / **设计创意**）→ `U.setScene()`。
- 切到设计创意后出现快捷动作 `button.quick-actions__item`：
  视觉海报 / 运营海报 / PPT设计 / 生成图片 / 生成视频 / 品牌设计 / **网站设计** / 移动端App /
  设计系统 / Web App / 图标&插画。
- 点快捷动作**只会塞一个标签**（如「网站设计」），直接发送 AI 会反问 → 会话挂「待确认」、
  任务不计数。**必须再点一个示例提示词** `button.quick-actions-sub__item`
  （网站设计 → AI趋势官网 / 球鞋文化网站 / 粗野主义网站），它会把完整需求填进输入框。
- 输入框里已有草稿时，点快捷动作/示例词会弹「输入框里有你写的内容 … 替换」→ 要点「替换」。

### 灵感（playbook_prompt）

- 侧边栏「更多 · 灵感」是二级入口，真正可点的是 `.conversation-list-tab-button-sub`「灵感」。
- 页面上出现 `.wb-related-playbooks__card` 案例卡片（点侧边栏「灵感」后首页也会显示这一条）。
- 流程：点卡片 → 右侧详情面板 → 点「做同款」→ 弹「替换」确认框 → 点「替换」→ 输入框被
  完整提示词填满 → 发送。
- **点「灵感」会让首页导航**：页面一导航，同一次 JS 调用里剩下的 `await` 就永远回不来
  （CDP 一直等到超时）。所以这段必须用 `run_task(pre_steps=[...])`，每步一次独立调用。
- **更好的做法**：首页本来就自带同款卡片，直接点首页的 `.wb-related-playbooks__card`，
  **完全绕开导航** —— 这也是 `do_playbook_prompt(via_home=True)`（默认）的做法。

**⚠️ 坑 1（致命且完全静默）：常量漏了尾部的 `()`**

`PB_SIDE` / `PB_SAME` / `PB_REPLACE` 当初只写了**函数定义**、没写尾部的 `()`，
而 `js()` 内部是 `return await (<code>)` → await 一个函数对象 → 序列化成 `{}`。
结果：**「做同款」从来没被点过**，`steps` 里那三项都是 `{}`，却不报任何错。
（`PB_CARD` 因为被 `_pb_card_step()` 包了一层自调用才没事 —— 这也解释了
为什么"有的步骤好、有的不好"，当时还以为只是导航时序问题，白查了很久。）

修法：统一用 `_fn(src, *args)` 包成自调用，**别裸传常量给 `js()`**。
同一条经验适用于所有一次性 JS：要么自调用、要么用 `_fn` 包。

**⚠️ 坑 2：这个任务要等对话**真正跑完**才计数**

首页 4 张卡片重量差别很大：

| idx | 卡片 | 体感 |
| --- | --- | --- |
| 0 | 八十二亿之后：全球人口结构与趋势图志 | **最重**，实测生成一次 8~10 分钟 |
| 1 | 养老退休规划方案 | 中 |
| 2 | 《思考，快与慢》精读笔记卡 | **最轻**（默认用这张） |
| 3 | 新产品上市 GTM 发布计划一页纸 | 中 |

- `batch_runner.PB_CASE = 2` 挑最轻的，省十几分钟。
- `do_playbook_prompt` 的 `max_wait` 默认已提到 **900**。
- `run_task` 现在把 `out["sent"]`（消息已发出）和 `out["ok"]`（生成结束）**分开报** ——
  别再把"还在跑"当成"流程坏了"。

## 九、多账号一次跑完（含界面类任务）

```bash
python batch_runner.py --accounts account_d,account_e,account_f --codes ui    # 只跑界面类
python batch_runner.py --accounts account_d,account_e,account_f --codes all   # 两类都跑
```

`Buddy_App` 与 `Buddy_App_QQ` 是同一个动作，两个都在列表里时只跑一次。
`run_code` 对每个 code 有 try/except，单个任务炸掉不会带走整批。

**跑完必须领积分**（"做完"只是变成待领取，不领不到账）：

```bash
python claim_all.py              # 所有账号
python claim_all.py account_e    # 指定账号
```

`batch_runner` 收尾会领**该账号全部可领项**（不只 `--codes` 里那些），
所以顺带能把历史积压一起清掉。

## 十、按要求不执行的任务（black_cat）

用户明确要求：**「夜猫子」black_cat 所有账号都不刷**（要连续 3 个晚上，奖励还是 Buddy 不是积分）。

做成了**配置级开关**，别硬编码回代码里：

```json
"skip_tasks": { "codes": ["black_cat"], "keywords": [] }
```

生效层次：`tasks.py` 的 `detect_skip()` → `normalize()` 里 `claimable=False`、
`accept_needed=False`、状态显示「已跳过（按要求不执行）」→ `run_tasks` 走 `skip_required` 分支；
`batch_runner` 另有 `_skip_codes()` 守卫，默认 `--codes` 与 `all` 都不再含它，
**即使显式写进 `--codes` 也会被拒**。删掉 `config.json` 里这个 code 即可恢复。

## 十一、其余已知情况

- `Expert_team_use_3`：**已修好**（见「八 · 专家中心」的根因说明），0/3 的账号可以正常刷。
- `Expert_Philanthropy`（需捐款）：永远跳过，绝不接取/领取。
- `skill_1`：现有 6 个账号都已完成，未单独写驱动器。
- `Model_chat_GLM5.2`：**必须白天跑**（夜间会被夜猫子吃掉）。a/b/c 已完成，d/e/f 待白天补。
- 其余任务 a/b/c 三个号已全部完成；d/e/f 还差界面类的那几项，用上面的 `--codes ui` 补。

