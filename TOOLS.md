# TOOLS.md - 工具与环境配置

Skills 定义工具"怎么用"，本文件记录你的"具体配置"——环境特有的参数、路径、密钥等。

---

## Notion

- API Key: `<NOTION_API_KEY>`

---


## OCR 工具

| 工具 | 推荐度 | 快捷命令 | 备注 |
|------|--------|---------|------|
| RapidOCR | ✅ 首选 | `ocr-rapid 图片路径` | 准确率>98%，支持中英文 |
| macOS Vision OCR | ❌ 不推荐 | `ocr-vision 图片路径` | 漏字严重 |
| DeepSeek OCR (MLX) | ⏸ 暂放 | Web UI: http://localhost:5001 | 模型下载失败，待解决 |

### 路径
- RapidOCR：`~/.openclaw/workspace/skills/RapidOCR/`，Python 环境：`~/Desktop/rapidocr_venv/`
- macOS Vision OCR：`~/.openclaw/workspace/skills/macos-vision-ocr/.build/release/macos-vision-ocr`
- OCR 双引擎脚本：`~/.openclaw/workspace/scripts/ocr_dual.sh`

---

## VPN

- 软件：**Clash Party**（mihomo-party）
- 配置文件：`~/Library/Application Support/mihomo-party/profiles/19ce026e109.yaml`
- iCloud 中国区例外规则已配置：`*.icloud.com.cn` / `*.caldav.icloud.com.cn` / `*.mobileicloud.com.cn`

---


## 内容读取方法

### 微信公众号（优先级）
1. **优先**：browser 工具（反爬虫，curl/web_fetch 失败时用）
   ```
   browser(action="open", url="链接")
   browser(action="snapshot")
   ```
2. **备选**：Agent Reach MCP 工具

### 摘录查询方式
- ❌ 错误：`grep "摘录"` → 只能匹配含"摘录"字样的行
- ✅ 正确：`grep -n "2026-03-04"` → 匹配特定日期所有记录
- 原因：摘录标题格式是 `## 2026-03-04 - 来源名`，不一定含"摘录"二字

---

## 知识库脚本

```bash
# 存入知识库
python3 ~/.openclaw/workspace/scripts/kb.py curate --kb {ai_research|personal} --title "标题" --source "来源" --content "内容"

# 查询
python3 ~/.openclaw/workspace/scripts/kb.py query --kb {ai_research|personal} --question "问题"

# 最近入库
python3 ~/.openclaw/workspace/scripts/kb.py recent --kb {ai_research|personal}
```

---

## 持仓监控脚本

| 持仓 | 脚本 | 数据文件 |
|------|------|---------|
| 核心覆盖标的（38只） | `~/Desktop/stock_watchlist.py` | `~/Desktop/stock_watchlist_data.py` |
| 持仓2（12只） | `~/.openclaw/workspace/持仓2/持仓2_watchlist.py` | `~/.openclaw/workspace/持仓2/持仓2_data.py` |

- 港股数据：腾讯财经接口（qt.gtimg.cn）
- 美股数据：yfinance
