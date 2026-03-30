# 支持的 Telegram 命令说明

本文档列出当前双机器人（管理端 / 商户端）**已实现且可用**的全部命令。命令名均为**英文**，符合 Telegram 标准 Bot Command 格式。

---

## 管理机器人（Admin Bot）

在内部管理群使用，需配置环境变量 `ADMIN_BOT_TOKEN`。**不进行用户 ID 白名单校验**（任何能向该机器人发消息的用户均可触发管理命令，请务必通过群权限与 Token 保管控制访问面）。

| 命令 | 语法 | 说明 |
|------|------|------|
| `/uset` | `/uset <rate>` | 更新系统内的实时 USDT 汇率（写入 `system_config` 的 `U_RATE`）。示例：`/uset 7.20` |
| `/settle` | `/settle <merchant_identifier> <amount>` | 对指定商户做**结算入账**：按规则扣除 6.5% 佣金后增加可用余额，并写入流水；同时由通知机器人向该商户绑定的群发送入账通知。商户标识可为**商户名称**或**数字型商户 id**。金额支持千分位，如 `500,000`。示例：`/settle shop_a 100,000` |
| `/report` | `/report <merchant_identifier>` | 生成该商户**当日**（按服务器时区的日历日）结算与代付汇总，并显示当前余额及按当前 U 价估算的可回 U 数量。示例：`/report shop_a` |

---

## 通知机器人（Notify Bot）

部署在商户群，需配置 `NOTIFY_BOT_TOKEN`。群内发送命令时，系统按**当前群的 `chat_id`** 在表 `merchants` 中查找对应商户（`tg_chat_id` 需事先与群一致）。

| 命令 | 语法 | 说明 |
|------|------|------|
| `/u` | `/u` | 查询当前系统配置的 USDT 汇率（`U_RATE`）。 |
| `/payout` | `/payout <amount>` | **代付扣款**：在数据库事务内对商户行加锁查询（`with_for_update()`）；SQLite 下行级锁语义与 PostgreSQL 不同，单库文件场景下仍能保证写入串行化。校验余额后按「申请金额 + 1% 预留手续费」扣款并写流水。同一商户群 **3 秒内** 不可连续发起两次 `/payout`。金额支持千分位。示例：`/payout 10,000` |
| `/quote` | `/quote <amount>` | **仅查询**：将输入金额视为本币金额，按当前 U 价估算可下发的 USDT 数量，**不修改余额**。示例：`/quote 50,000` |

---

## 金额与格式

- 金额可为整数或小数；支持千分位逗号，例如 `1,234,567.89`。
- 系统内部以「分」为单位（金额 × 100 的整数）存储与计算；机器人回复中会格式化为带千分位、两位小数的展示。

---

## 部署与数据前提

- 数据库为 **SQLite**，需先执行迁移：`alembic upgrade head`（启动前请保证 `DATABASE_URL` 中数据库文件所在目录存在；程序会对 SQLite 路径自动创建父目录）。
- 使用 `/settle`、`/report` 前，目标商户须在表 `merchants` 中存在，且 `merchant_name` 或 `id` 与参数一致。
- 使用 `/payout`、`/u`、`/quote` 前，当前群须在 `merchants.tg_chat_id` 中绑定为该商户群。

---

## 环境变量（运维对照）

| 变量 | 用途 |
|------|------|
| `ADMIN_BOT_TOKEN` | 管理机器人 Token |
| `NOTIFY_BOT_TOKEN` | 通知机器人 Token |
| `DATABASE_URL` | 异步 SQLite 连接串，例如 `sqlite+aiosqlite:///./data/app.db`（本地）或 `sqlite+aiosqlite:////app/data/app.db`（Docker 挂载数据目录时） |
| `DEFAULT_U_RATE` | 首次读取汇率且库中无配置时的默认 U 价 |
