# 零依赖脚本 · Buddy 加油站 API 链路

仅用 Python 标准库，读取本机登录态后直接调用官方接口：

```bash
python scripts/buddy_gas_station.py                 # 签到 + 盲盒 + 猫猫旅行（全自动闭环）
python scripts/buddy_gas_station.py --check-only    # 只查询，不领取、不派遣
python scripts/buddy_gas_station.py --list-accounts # 列出 config 里的账号
python scripts/buddy_gas_station.py --account account_e
```

## 信封解密（WorkBuddy 5.6.2+）

新版客户端登录态里 `accessToken` 是 `$wbEncrypted` 加密信封（AES-256-GCM），不能直接当明文发送。
脚本自动探测静态密钥，顺序为：`--atrest-key` 参数 → 环境变量 `WORKBUDDY_ATREST_KEY` →
`../data/atrest.key` → `./data/atrest.key`（32 字节二进制密钥，与用户级 `data/atrest.key` 同源）。
解密成功不落盘，只改内存副本，输出仍不打印 Token。

```bash
python scripts/buddy_gas_station.py --atrest-key /path/to/atrest.key
```

## 退出码

| 退出码 | 含义 |
| --- | --- |
| 0 | 全部步骤成功（含幂等跳过） |
| 1 | 业务失败（需人工查看原因） |
| 2 | 登录态失效（需重新登录客户端） |
| 3 | 凭据是加密信封但缺少/无法匹配静态密钥（重启桌面端生成后重试） |

安全约束：只读取登录态文件；输出不打印 Token；不做付费写操作。
