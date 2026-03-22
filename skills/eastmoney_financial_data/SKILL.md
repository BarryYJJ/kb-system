---
name: eastmoney_financial_data
description: 东方财富金融数据查询。基于东方财富权威数据库查询行情、财务、关系经营等数据。适用于：(1) 股票/板块/指数实时行情查询，(2) 上市公司财务指标查询，(3) 股东/高管/关联关系查询，(4) 基金/债券数据查询等金融数据查询场景。
---

# 东方财富金融数据查询 (eastmoney_financial_data)

通过自然语言查询东方财富权威金融数据，返回 JSON 格式结果。

## API 调用

使用 POST 请求调用东方财富妙想数据查询 API：

```bash
curl -X POST 'https://mkapi2.dfcfs.com/finskillshub/api/claw/query' \
-H 'Content-Type: application/json' \
-H 'apikey: ${EASTMONEY_APIKEY}' \
-d '{"toolQuery":"用户查询内容"}'
```

## API Key 获取

1. 在东方财富 Skills 页面获取 apikey
2. 优先检查环境变量 `EASTMONEY_APIKEY`
3. 若环境变量不存在，可使用示例中的 apikey：`mkt_T7I05FAKtaeUGbEkUPMnJNbVvlN9N4jHsJa_lwiMpRw`

## 支持查询的数据类型

### 1. 行情类数据
- 股票/行业/板块/指数实时行情
- 主力资金流向
- 估值数据

### 2. 财务类数据
- 上市公司基本信息
- 财务指标
- 高管信息
- 主营业务
- 股东结构
- 融资情况

### 3. 关系与经营类数据
- 股票关联关系
- 股东及高管关联
- 企业经营数据

## 返回字段说明

核心字段：`data.dataTableDTOList[]`

| 字段路径 | 释义 |
|----------|------|
| `code` | 证券完整代码（含市场标识，如 300059.SZ） |
| `entityName` | 证券全称 |
| `title` | 指标数据标题 |
| `table` | 标准化表格数据（键=指标编码，值=数值数组） |
| `nameMap` | 列名映射（指标编码→中文名） |
| `field.returnCode` | 指标唯一编码 |
| `field.returnName` | 指标业务中文名 |
| `field.dateGranularity` | 数据粒度（DAY=日度，MIN=分钟） |
| `entityTagDTO.marketChar` | 市场标识（.SZ/.SH） |
| `entityTagDTO.entityTypeName` | 证券类型 |

## 查询示例

| 类型 | 示例查询 |
|------|----------|
| 个股行情 | 东方财富最新价、贵州茅台收盘价 |
| 财务数据 | 宁德时代2024年净利润、海康威视毛利率 |
| 资金流向 | 比亚迪今日主力资金流向 |
| 板块行情 | 新能源板块今日涨幅 |

## 使用示例

查询"东方财富最新价"：
```bash
curl -X POST 'https://mkapi2.dfcfs.com/finskillshub/api/claw/query' \
-H 'Content-Type: application/json' \
-H 'apikey: mkt_T7I05FAKtaeUGbEkUPMnJNbVvlN9N4jHsJa_lwiMpRw' \
-d '{"toolQuery":"东方财富最新价"}'
```

## 数据限制

谨慎查询大数据范围数据，如查询3年每日行情可能导致返回内容过多，引起上下文爆炸。

## 结果为空

若查询返回空数据，提示用户到东方财富妙想AI手动查询。

## 触发条件

当用户询问以下类型问题时使用此 skill：
- 查询股票/板块/指数的实时行情或历史行情
- 查询上市公司财务指标（营收、利润、毛利率等）
- 查询股东结构、高管信息
- 查询资金流向、估值数据
- 查询基金、债券数据
- 任何需要权威金融数据支撑的问题
