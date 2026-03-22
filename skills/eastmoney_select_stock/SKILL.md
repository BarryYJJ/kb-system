---
name: eastmoney_select_stock
description: 东方财富智能选股。基于行情指标、财务指标等条件筛选股票，查询行业/板块成分股，推荐股票等。适用于：(1) 按条件选股（如涨幅、估值），(2) 查询板块成分股，(3) 股票/上市公司推荐等选股相关任务。
---

# 东方财富智能选股 (eastmoney_select_stock)

通过自然语言查询进行智能选股，支持 A股、港股、美股。

## API 调用

使用 POST 请求调用东方财富妙想选股 API：

```bash
curl -X POST 'https://mkapi2.dfcfs.com/finskillshub/api/claw/stock-screen' \
-H 'Content-Type: application/json' \
-H 'apikey: ${EASTMONEY_APIKEY}' \
-d '{"keyword":"选股条件", "pageNo": 1, "pageSize": 20}'
```

## API Key 获取

1. 在东方财富 Skills 页面获取 apikey
2. 优先检查环境变量 `EASTMONEY_APIKEY`
3. 若环境变量不存在，可使用示例中的 apikey：`mkt_T7I05FAKtaeUGbEkUPMnJNbVvlN9N4jHsJa_lwiMpRw`

## 支持的功能

### 1. 条件选股
按行情指标、财务指标等筛选满足条件的股票

### 2. 板块/行业查询
查询指定行业/板块内的股票、上市公司

### 3. 成分股查询
查询板块指数的成分股

### 4. 股票推荐
股票、上市公司、板块/指数推荐

## 返回字段说明

### 核心字段

| 字段路径 | 释义 |
|----------|------|
| `status` | 接口状态，0=成功 |
| `data.code` | 业务状态码，100=解析成功 |
| `data.data.result.total` | 符合条件的股票数量 |
| `data.data.result.columns` | 列定义数组 |
| `data.data.result.dataList` | 行数据数组 |

### columns 列定义

| 子字段 | 释义 |
|--------|------|
| `title` | 表格列展示标题 |
| `key` | 列唯一业务键 |
| `dateMsg` | 列数据对应日期 |
| `unit` | 数值单位 |
| `redGreenAble` | 是否支持红绿涨跌着色 |

### dataList 行数据核心键

| 核心键 | 释义 |
|--------|------|
| `SECURITY_CODE` | 股票代码 |
| `SECURITY_SHORT_NAME` | 股票简称 |
| `MARKET_SHORT_NAME` | 市场简称（SH/SZ） |
| `NEWEST_PRICE` | 最新价（元） |
| `CHG` | 涨跌幅（%） |
| `PCHG` | 涨跌额（元） |

### 筛选条件统计

| 字段路径 | 释义 |
|----------|------|
| `responseConditionList` | 各筛选条件的统计列表 |
| `responseConditionList[].describe` | 条件描述 |
| `responseConditionList[].stockCount` | 该条件匹配的股票数 |
| `totalCondition.describe` | 组合条件描述 |
| `totalCondition.stockCount` | 组合条件匹配的股票数 |

## 查询示例

| 类型 | 示例查询 |
|------|----------|
| 涨幅选股 | 今日涨幅2%的股票 |
| 估值选股 | 市盈率低于20的股票 |
| 板块选股 | 新能源板块股票 |
| 资金流向 | 主力资金净流入前10 |

## 使用示例

查询"今日涨幅2%的股票"：
```bash
curl -X POST 'https://mkapi2.dfcfs.com/finskillshub/api/claw/stock-screen' \
-H 'Content-Type: application/json' \
-H 'apikey: mkt_T7I05FAKtaeUGbEkUPMnJNbVvlN9N4jHsJa_lwiMpRw' \
-d '{"keyword":"今日涨幅2%的股票", "pageNo": 1, "pageSize": 20}'
```

## 结果输出

将返回的 `dataList` 按 `columns` 把英文列名替换为中文后，输出全量数据的 CSV 格式及对应的数据说明。

## 结果为空

若查询返回空数据，提示用户到东方财富妙想AI手动选股。

## 触发条件

当用户询问以下类型问题时使用此 skill：
- 按条件选股（"涨幅超过5%的股票"、"市盈率低于15"）
- 查询板块/行业成分股（"新能源板块有哪些股票"）
- 股票推荐（"推荐一些低估值的股票"）
- 任何需要筛选股票的需求
