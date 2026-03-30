Telegram 双机器人结算与对账系统开发规范1. 项目概述与技术架构本项目旨在开发一套基于 Telegram 的双端机器人系统，用于商户资金的结算入账、代付扣款、实时 U 价（USDT）换算及自动化财务报表生成。系统必须保证资金计算的绝对准确性及高并发场景下的数据一致性。编程语言: Python 3.11+ (强制使用严格的类型注解 Type Hints)核心框架: aiogram 3.x (纯异步 Telegram Bot 框架，支持多 Bot 实例同开)数据库: PostgreSQL 14+ (处理高并发与事务隔离)ORM 框架: SQLAlchemy 2.0 (异步模式 asyncpg) + Alembic (数据迁移)部署方式: Docker + Docker Compose2. 核心数学模型与业务逻辑在系统代码中，所有的资金计算必须封装为独立的服务类，并严格按照以下公式执行。为避免浮点数精度丢失，底层存储和计算需统一将金额放大 100 倍（以“分”为单位计算），仅在展示时转为正常金额。

结算入账逻辑商户网关结算金额到达后，系统需扣除 6.5% 的服务佣金（包含网关及各方分润），计算商户实际可用余额：$$S_{可用} = S_{结算} \times (1 - 6.5\%)$$2.2 代付扣款逻辑商户发起代付申请时，需在申请金额基础上额外加收 1% 的预留手续费（给渠道方），系统实际扣除金额为：$$D_{扣款} = P_{申请} \times (1 + 1\%)$$安全断言：执行扣款前，必须校验 $S_{可用} \ge D_{扣款}$。
结余换汇 (回 U) 逻辑系统根据管理端设置的实时 U 价，计算当前可用余额可下发的 USDT 数量：$$USDT_{下发} = \frac{S_{可用}}{Rate_{USDT}}$$3. 数据库结构设计 (Schema)AI 生成模型时需基于 SQLAlchemy 2.0 的 Mapped 和 mapped_column 声明式语法。表名 (Table)字段 (Columns)说明system_configkey (String, PK), value (String), updated_at (DateTime)存储全局变量，如 U_RATE。merchantsid (Integer, PK), merchant_name (String), tg_chat_id (BigInteger, Unique), balance (BigInteger)记录商户基础信息和实时可用余额。transactionsid (UUID, PK), merchant_id (FK), tx_type (String: settle/payout), amount (BigInteger), fee (BigInteger), created_at (DateTime)资金流水表，用于生成结算对账单。

4. 机器人指令与路由设计

4.1 管理机器人 (Admin Bot - 仅限内部群/管理员使用)权限控制：通过中间件 (Middleware) 拦截非白名单 user_id 的请求。/uset [汇率]：更新 system_config 表中的 U 价，并返回更新成功提示。/settle [商户标识] [金额]：开启数据库事务，增加对应商户的结算流水。按公式计算可用余额并累加到 merchants.balance。跨 Bot 调用：触发 Notify Bot 向该商户的 tg_chat_id 发送入账通知。/report [商户标识]：汇总当日 transactions 表数据，按模板生成并输出结算对账单。

4.2 通知机器人 (Notify Bot - 部署在商户群)/u：读取 system_config 中的实时汇率并返回。/代付 [金额]：开启带有悲观锁 (SELECT ... FOR UPDATE) 的数据库事务。检查商户余额是否充足。扣除代付本金及 1% 手续费，写入流水。返回扣款详情及最新账内余额。/回款 [金额]：根据公式计算并返回预估下发的 USDT 数量（纯查询，不扣款）。

5. 并发控制与防风控策略 (核心重点)开发时必须实现以下安全机制：数据库悲观锁：在处理 /代付 指令的 SQLAlchemy 事务中，必须对 merchants 表对应行加锁（with_for_update()），防止快速连续请求导致的超扣现象。指令防抖 (Rate Limiting)：在 aiogram 中编写拦截器（Middleware），同一个商户群内，3 秒内不允许连续发起两次 /代付 操作。金额格式化处理：输入解析需支持剥离千分位逗号（如 500,000 需正则处理为 500000），输出统一携带千分位逗号并保留合理小数位。


