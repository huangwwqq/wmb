# 外贸邦采购商 / 供应商爬虫

抓取 [外贸邦](https://www.52wmb.com/) 的采购商、供应商。登录后按国家统计数量，再按公司拉详情和提单。

公司写入 `public.customs_companies`，提单写入 `customs.trade_info`，`source=wmb`。碳纤维临时任务写入 `public.carbon_fiber_companies`，提单仍进 `customs.trade_info`。

## 接口

国家数量（页面 `build_stats_country`）：

- 采购商 `company_type=0`
- 供应商 `company_type=1`
- `GET /async/common/country/stats`

生产者要「包含邮箱」，所以 `filter_weight=email`。不带这个条件时同一接口是全部公司。

公司列表：`GET /async/company/search/list`

- `search_type`：`1` 公司名，`2` 产品名，`3` HS 编码
- `country`：国家英文小写，例如 `united states`
- 翻页：`start` + `size`，页面每页 30，单次最多约 10000 条

公司详情页签对应：

| 页面 | 接口 |
|---|---|
| 贸易概述 | `/company/detail/trends`、`/company/detail/year/stats` |
| 联系方式 | `POST /async/company/contacts` |
| 进口/出口数据 | `/company/detail/trade` |
| 贸易伙伴 | `/company/detail/partner` |
| HS 编码 | `/company/detail/hs` |
| 采供产品 | `/async/detail/product-list` |
| 贸易区域 | `/company/detail/trade-country` |
| 港口统计 | `/company/detail/port`（`port_type` 0 和 1） |

登录：`POST /async/sign`，表单字段 `user_name`、`password`。

## 任务表

- `public.wmb_task`：国家 + 类型。`type` 1 采购商 / 2 供应商，`flag` 0 未完成 / 1 已完成，`page` 当前页（从 1 开始，未完成时从这一页接着翻）
- `public.wmb_company_task`：公司 id。已存在则忽略

`update_time` 由触发器写入，程序不传。建表脚本：`sql/wmb_task.sql`。

新插入，或采集数量比库里多时，`flag` 改回 0，`page` 改回 1。翻到最后一页，或第一页确实没有数据，才标完成。空页、残页、验证码、频繁、403/429 不算完成，页码停在当前页。

生产者单线程。消费者 3 线程。账号队列冷却 1 秒。

## 服务器

马来西亚那台，和小满同一台。

| 项 | 值 |
|---|---|
| SSH | `ssh root@187.53.135.180` |
| 代码 | `/data/wmb` |
| 虚拟环境 | `/python_env/wmb` |
| Redis | `127.0.0.1:6379` db `2` |
| PostgreSQL | `127.0.0.1:5433` 库 `postgres` |

```bash
source /python_env/wmb/bin/activate
cd /data/wmb/spider
mkdir -p /data/wmb/logs
PY=/python_env/wmb/bin/python

nohup $PY -u account.py          >> /data/wmb/logs/account.out  2>&1 &
nohup $PY -u account_queue.py    >> /data/wmb/logs/queue.out    2>&1 &
nohup $PY -u wmb_consumer.py     >> /data/wmb/logs/consumer.out 2>&1 &
nohup $PY -u wmb_producer.py     >> /data/wmb/logs/producer.out 2>&1 &
nohup $PY -u tmp_carbon_fiber.py >> /data/wmb/logs/carbon.out   2>&1 &
```

生产者每月北京时间 1 号 0 点跑一次。线上 crontab 是 UTC：

```
0 16 28-31 * * [ "$(TZ=Asia/Shanghai date +\%d)" = "01" ] && flock -n /tmp/wmb_producer.lock -c 'cd /data/wmb/spider && /python_env/wmb/bin/python -u wmb_producer.py >> /data/wmb/logs/producer.out 2>&1'
```

库备份沿用这台机器已有的 `htzx-pg-backup`：主库 `5433`，备份库 `5432`，第一天全量，之后增量。`wmb_task` 在同一个 `postgres` 库里，会跟着备份走。

## 目录

```
spider/     登录、账号队列、生产者、消费者、碳纤维临时脚本
curd/       任务表和结果表
parse/      国家码、公司、提单字段映射
common/     PostgreSQL、请求
setting/    连接和参数
sql/        建表
```
