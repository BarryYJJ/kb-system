---
name: eastmoney_financial_search
description: 东方财富金融资讯搜索。基于东方财富妙想搜索能力搜索金融资讯（研报、新闻、公告、政策解读等），用于获取时效性信息或特定事件信息。适用于：(1) 个股最新资讯/研报查询，(2) 板块/主题新闻，(3) 宏观/风险分析，(4) 大盘异动解读等金融场景信息检索。
---

# 东方财富资讯搜索 (eastmoney_financial_search)

根据用户问句搜索相关金融资讯，获取与问句相关的资讯信息（研报、新闻、解读等）。

## API 调用

使用 POST 请求调用东方财富妙想搜索 API：

```bash
curl -X POST --location 'https://mkapi2.dfcfs.com/finskillshub/api/claw/news-search' \
--header 'Content-Type: application/json' \
--header 'apikey: ${EASTMONEY_APIKEY}' \
--data '{"query":"用户问句"}'
```

## API Key 获取

1. 在东方财富 Skills 页面获取 apikey
2. 优先检查环境变量 `EASTMONEY_APIKEY`
3. 若环境变量不存在，可使用示例中的 apikey：`mkt_T7I05FAKtaeUGbEkUPMnJNbVvlN9N4jHsJa_lwiMpRw`

## 问句示例

| 类型 | 示例问句 |
|------|----------|
| 个股资讯 | 格力电器最新研报、贵州茅台机构观点 |
| 板块/主题 | 商业航天板块近期新闻、新能源政策解读 |
| 宏观/风险 | A股具备自然对冲优势的公司 汇率风险、美联储加息对A股影响 |
| 综合解读 | 今日大盘异动原因、北向资金流向解读 |

## 返回字段说明

| 字段路径 | 释义 |
|----------|------|
| `title` | 信息标题，高度概括核心内容 |
| `secuList` | 关联证券列表，含代码、名称、类型 |
| `secuList[].secuCode` | 证券代码（如 002475） |
| `secuList[].secuName` | 证券名称（如立讯精密） |
| `secuList[].secuType` | 证券类型（股票/债券） |
| `trunk` | 信息核心正文/结构化数据块 |

## 使用示例

搜索"立讯精密资讯"：
```bash
curl -X POST 'https://mkapi2.dfcfs.com/finskillshub/api/claw/news-search' \
-H 'Content-Type: application/json' \
-H 'apikey: mkt_T7I05FAKtaeUGbEkUPMnJNbVvlN9N4jHsJa_lwiMpRw' \
-d '{"query":"立讯精密"}'
```

## 触发条件

当用户询问以下类型问题时使用此 skill：
- 查询特定股票的最新资讯、研报、机构观点
- 查询板块/主题相关新闻或政策解读
- 询问宏观因素对A股的影响
- 询问大盘异动、资金流向等综合解读
- 任何需要金融时效性信息的查询
