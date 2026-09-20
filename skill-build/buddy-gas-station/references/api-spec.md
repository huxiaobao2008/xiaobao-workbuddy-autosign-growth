# 接口规格（实测提取 · 2026-09）

## 一、登录态

| 项 | 值 |
|---|---|
| 文件 | `%LOCALAPPDATA%\CodeBuddyExtension\Data\Public\auth\workbuddy-desktop.info` |
| 字段 | `auth.accessToken`（JWT）、`auth.domain`（实测 `www.workbuddy.cn` / `www.codebuddy.cn`）、`auth.refreshToken` |
| 请求头 | `Authorization: Bearer <token>`、`Content-Type: application/json`、可选 `X-Refresh-Token` |

登录态约 60 天需重新登录；失效时唯一解法是客户端重新登录。

## 二、签到（域名用 `auth.domain`，带 `/v2`）

| 用途 | 方法 | 路径 |
|---|---|---|
| 查状态 | POST | `/v2/billing/meter/checkin-activity-status` |
| 领取 | POST | `/v2/billing/meter/daily-checkin` |

- 成功：`code=0`，返回 `credit` / `streak_days` / `total_credits` / `end_time`。
- **已签到返回 `code=10001`**（HTTP 400）——幂等，不是错误，不要重试。
- 必须用 POST：GET 探测会 404。

## 三、成长中心（域名固定 `www.workbuddy.cn`，**不带 /v2**）

| 用途 | 方法 | 路径 |
|---|---|---|
| 能量余额 | GET | `/activity/growth/energy` |
| 盲盒配额 | GET | `/activity/growth/buddy/quota` |
| 开盲盒 | POST | `/activity/growth/buddy/open` |
| 伙伴列表 | GET | `/activity/growth/buddy/list` |
| 伙伴信息 | GET | `/activity/growth/buddy/info` |
| 旅行状态 | GET | `/activity/growth/buddy/travel/status` |
| 旅行配置 | GET | `/activity/growth/buddy/travel/config` |
| 领到达奖励 | POST | `/activity/growth/buddy/travel/claim` |
| 派猫猫 | POST | `/activity/growth/buddy/travel/depart` |
| 任务清单 | GET | `/v2/activity/growth/tasks` |
| 领取任务奖励 | POST | `/activity/growth/tasks/{code}/claim` |
| 活跃日历 | GET | `/activity/growth/heatmap` |
| 连续天数 | GET | `/activity/growth/streak` |

关键字段：

- `quota`：`balance`（能量余额）、`cost_per_open`（单次消耗）、`affordable`（当前可开次数）、`max_open_count`。
- `travel/status`：`state` = `idle` / `traveling` / `arrived`；`daily_limit_reached`；`reward_credit`；`arrive_at`。
- `travel/depart` 请求体 `{"location_id": N}`，地点 1–4（咖啡馆 / 商场店铺 / 健身房 / 古镇客栈），
  收益区间相同（随机 1–4 小时、5–10 积分）。
- 接口仅需 Bearer Token，无需设备指纹。

端点来源：成长中心前端 bundle（`growthSpace` 模块）与 `app.asar` 双向核对。

## 四、重要边界

- **成长任务进度无法纯 API 刷**：进度由服务端检测真实产品使用事件得出，
  客户端没有任何上报接口；桌面端会话 `conversationOrigin=local`，云端 API 造不出来。
- 云端会话链路（`POST /console/as/conversations/` + ACP）**只能点亮活跃/连续天数，
  不会推进成长任务进度**（换模型、改 origin 都试过，无效）。
- 旅行无召回接口，只能等到达后自动领取；`arrived` 状态不会丢积分。
- 盲盒能量不足、旅行达每日上限时：只跳过，不发写请求。
