# 零依赖脚本 · Buddy 加油站 API 链路

仅用 Python 标准库，读取本机登录态后直接调用官方接口：

```bash
python scripts/buddy_gas_station.py                 # 签到 + 盲盒 + 猫猫旅行（全自动闭环）
python scripts/buddy_gas_station.py --check-only    # 只查询，不领取、不派遣
python scripts/buddy_gas_station.py --list-accounts # 列出 config 里的账号
python scripts/buddy_gas_station.py --account account_e
```

退出码：0 成功；1 业务失败；2 登录态失效（需重新登录客户端）。

安全约束：只读取登录态文件；输出不打印 Token；不做付费写操作。
