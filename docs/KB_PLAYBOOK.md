# 📘 知识库处理手册（Knowledge Base Playbook）

> **受众**：本手册主要供 OpenClaw AI Agent 阅读。如果你是开发者/用户，请先阅读 README.md 的快速开始部分。手册中的群 ID（YOUR_INVESTMENT_GROUP_ID / YOUR_PERSONAL_GROUP_ID）需要替换为你的实际飞书群 ID。

本手册是小八自己执行知识库处理的操作指南。当收到来自知识库群的消息时，小八直接按本手册执行全部技术流程（提取 → 入库 → 验证），无需委派其他工具。

---

## 一、群组路由

| 群 ID | 知识库 | BRV 工作目录 | 总结风格 |
|--------|--------|-------------|---------|
| YOUR_INVESTMENT_GROUP_ID | AI投研知识库 | ~/.openclaw/workspace/knowledge_bases/ai_research | 投研风格 |
| YOUR_PERSONAL_GROUP_ID | 个人知识库 | ~/.openclaw/workspace/knowledge_bases/personal | 个人风格 |

收到消息后，第一步根据群 ID 确定 BRV_ROOT，后续所有 kb.py 命令先 cd 到对应目录。

---

## 二、内容类型识别

按优先级判断：

1. PDF → 附带 .pdf 文件
2. 图片 → 附带 .jpg/.png/.jpeg/.webp/.heic 文件
3. 链接 → 文本含 http:// 或 https://
4. 长文字 → 以上都不是的纯文本

---

## 三、处理管道

### 管道 A：PDF

1. 文件路径在 ~/.openclaw/media/inbound/ 下。

2. 提取文字：
```
python3 -c "import pymupdf; doc = pymupdf.open('PDF路径'); text = '\n\n'.join([page.get_text() for page in doc]); print(text if len(text.strip()) > 100 else 'SCAN_PDF')"
```

3. 如果输出正常文字 → 即为 FULL_TEXT → 跳转【存储与总结】

4. 如果输出 SCAN_PDF（扫描件）→ 每页转图片：
```
python3 -c "import pymupdf; doc = pymupdf.open('PDF路径'); [page.get_pixmap(dpi=300).save(f'/tmp/kb_processing/pdf_pages/page_{i}.png') for i, page in enumerate(doc)]; print(f'共 {len(doc)} 页')"
```
然后逐页 OCR：
```
bash ~/.openclaw/workspace/kb-system/scripts/ocr_dual.sh /tmp/kb_processing/pdf_pages/page_0.png
```
按页码拼接所有 OCR 结果 = FULL_TEXT → 跳转【存储与总结】

5. 处理完清理：rm -f /tmp/kb_processing/pdf_pages/page_*.png

---

### 管道 B：图片

1. 文件路径在 ~/.openclaw/media/inbound/ 下。

2. 执行 OCR：
```
bash ~/.openclaw/workspace/kb-system/scripts/ocr_dual.sh "图片路径"
```

3. OCR 输出 = FULL_TEXT → 跳转【存储与总结】

4. 如果输出 [OCR_ERROR] → 返回用户：⚠️ 图片文字识别失败，请检查图片清晰度。

---

### 管道 C：链接

#### 识别链接类型：
- bilibili.com 或 b23.tv → B站（C-1）
- xiaohongshu.com 或 xhslink.com → 小红书（C-2）
- 其他 → 通用网页（C-3）

#### C-1：B站视频
```
# 第一步：获取视频标题和描述，作为 whisper 提示词
yt-dlp --dump-json "URL" > /tmp/bilibili_info.json
TITLE=$(python3 -c "import json; print(json.load(open('/tmp/bilibili_info.json')).get('title', ''))")
DESC=$(python3 -c "import json; print(json.load(open('/tmp/bilibili_info.json')).get('description', '')[:200])")
PROMPT="以下是一段中文视频。标题：$TITLE。内容：$DESC"

# 第二步：下载音频
yt-dlp -x --audio-format wav -o "/tmp/kb_processing/audio/bilibili.%(ext)s" "URL"

# 第三步：转写
whisper /tmp/kb_processing/audio/bilibili.wav --model medium --language zh --initial_prompt "$PROMPT" --output_dir /tmp/kb_processing/whisper_output/
cat /tmp/kb_processing/whisper_output/bilibili.txt
```
转录文本 = FULL_TEXT → 跳转【存储与总结】
完成后：rm -f /tmp/kb_processing/audio/bilibili.* /tmp/kb_processing/whisper_output/bilibili.*

#### C-2：小红书（xiaohongshu.com / xhslink.com）

**2026-06-30 更新**：默认走 MediaCrawler 工程管道，不再用浏览器 snapshot 手搓翻页。该链路已实测支持：正文/元数据 → Markdown、图片下载 → OCR → Markdown、视频下载 → ffmpeg → Whisper medium 转写 → Markdown。

首选命令：
```
/opt/homebrew/bin/python3 ~/.hermes/workspace/scripts/kb.py xhs \
  --kb ai_research \
  --url "用户发的小红书链接" \
  --whisper-model medium
```

个人知识库则把 `--kb ai_research` 改成 `--kb personal`。如只想先快速入库正文、跳过重媒体：加 `--no-images --no-video`。

支持度与限制：
- 最稳：`xhslink.com/o/...` 或 `xiaohongshu.com/discovery/item/<note_id>?xsec_token=...` 这类 App 分享详情链接。
- 不稳：裸 `/explore/<id>`、搜索页、主页、过期 token、风控/验证码页。
- 公开视频/图文详情链接可先空 Cookie；批量搜索、评论、主页、私密或限制内容大概率需要登录态。
- MediaCrawler 可能把 WebP 内容保存成 `.jpg`，管道会先用 ffmpeg 转 PNG 再 OCR。
- 视频转写默认 Whisper `medium`，比 `tiny/small` 更适合中文和技术词。

底层位置：
- MediaCrawler checkout：`~/.hermes/workspace/mediacrawler_test/MediaCrawler`
- 媒体持久化目录：`~/.hermes/workspace/xhs_media/<timestamp>/`，避免 Markdown 引用被删除的临时文件
- research-kb extractor：`/Users/yjj/projects/monorepo/research-kb/src/research_kb/extractors/xiaohongshu.py`
- Hermes 入口：`~/.hermes/workspace/scripts/kb.py xhs`

失败处理：
1. 如果提示 MediaCrawler 不存在，设置 `RESEARCH_KB_MEDIACRAWLER_DIR` 或重新 clone/sync。
2. 如果 OCR 缺依赖，管道会自动尝试 `~/.openclaw/workspace/scripts/ocr_dual.sh`；仍失败时正文和视频文本照常入库，并在 Markdown 里保留处理警告。
3. 如果视频转写失败，检查 `ffmpeg`、`whisper` 和 `~/.cache/whisper/medium.pt`；失败不应阻断正文入库。
4. 如果 URL 被风控或 token 过期，明确告知用户“链接失效/被风控”，不要包装成抓取成功。

#### C-3：通用网页

第一步：用 browser 工具打开链接（微信文章用 browser）：
```
browser(action="open", profile="openclaw", url="URL")
browser(action="snapshot", targetId="上一步返回的targetId")
```
如果成功获取有意义的内容 → 将内容作为 FULL_TEXT → 跳转【存储与总结】

第二步：jina.ai 降级：
```
curl -s "https://r.jina.ai/{URL}" > /tmp/kb_processing/web_content.txt
```
如果获取到有意义的内容（文件大小 > 500 字节）→ 将内容作为 FULL_TEXT → 跳转【存储与总结】

第三步：直接抓取原始 HTML 并清洗（最终降级）：
```
curl -sL "URL" | python3 -c "import sys, re; html = sys.stdin.read(); html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL); html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL); html = re.sub(r'<[^>]+>', '\n', html); text = re.sub(r'\n{3,}', '\n\n', html); text = re.sub(r' {2,}', ' ', text); print(text.strip())"
```
结果 = FULL_TEXT → 跳转【存储与总结】

---

### 管道 D：长文字

用户文本 = FULL_TEXT → 跳转【存储与总结】

---

## 四、存储与总结

### 4.1 存入本地知识库

直接执行以下命令：

python3 ~/.openclaw/workspace/kb-system/scripts/kb.py curate \
  --kb {ai_research 或 personal} \
  --title "{根据内容自动生成的标题}" \
  --source "{来源类型} | {URL 或 用户直接发送}" \
  --content "{FULL_TEXT 的完整内容}" \
  --type "{pdf / image_ocr / video / xiaohongshu / webpage / text}"

执行后验证：
python3 ~/.openclaw/workspace/kb-system/scripts/kb.py query \
  --kb {ai_research 或 personal} \
  --question "{用标题关键词检索}"

根据实际执行结果，在总结中如实报告：
- curate 成功且 query 检索到 → 📍 入库状态：✅ 成功 | doc_id: {id} | 已验证可检索
- curate 成功但 query 未检索到 → 📍 入库状态：⚠️ 已执行，验证未检索到
- curate 失败 → 📍 入库状态：❌ 失败 | {错误信息}

如果 FULL_TEXT 超过 50000 字符，kb.py 会自动分段处理，不需要手动切分。

**可选元数据参数**（能判断时尽量补全，写入 frontmatter 便于后续检索）：
`--directions "算力,大模型"`、`--tags`、`--tickers`、`--companies "Credo,STM"`、`--quality A/B/C`、`--language zh`、`--privacy private`、`--ai-initial-view-summary "一句话 AI 初步判断"`。均为逗号分隔或短字符串，省略即用默认值。

**新版 Markdown 备份格式（重要）**：

- 机器可读元数据统一写入文件顶部的 YAML **frontmatter**（`doc_id / kb / title / directions / source_type / source / ingested_at / updated_at / language / quality / tags / tickers / companies / ai_initial_view_summary / privacy / content_hash / attachment_refs`）。
- 正文**不再**重复写 `**来源** / **类型** / **入库时间**` 元信息块，也不写分隔线；正文只保留结构化小节：`核心摘要`、`来源事实与关键数据`、`AI初步判断(小八)`、`原始OCR全文` 等。
- 助手的判断类小节标题一律使用 **`## AI初步判断(小八)`**（旧的 `小八投研判断 / 小八判断 / 投研判断(小八)` 会被自动归一化），明确这是 AI 参考意见而非用户结论。
- `doc_id` 形如 `kb_<知识库>_<时间戳>_<内容哈希前8位>`。若把带旧元信息块的正文传入，kb.py 会保守移除开头重复块，但绝不删除正文中的来源事实。

### 4.2 总结格式

#### 投研知识库（YOUR_INVESTMENT_GROUP_ID）：
```
📊 投研知识入库完成
📌 标题：{标题}
📂 来源：{类型} | {URL或文件名}
🕐 入库时间：{YYYY-MM-DD HH:MM}
📍 入库状态：{根据 kb.py curate + kb.py query 的实际执行结果填写，不是固定文字}

🔑 核心要点：
1. {要点1 — 优先数据、趋势、结论}
2. {要点2}
3. {要点3} （3-5个，每个1-2句）

📈 投资视角：
• 行业/赛道：{行业}
• 关键数据：{数字、百分比、指标}
• 信号判断：{利好/利空/中性} — {原因}

💡 值得深挖的点：
• {线索；没有则省略此节}

🗣️ 说人话的一句话总结：{大白话，像跟朋友吃饭聊天一样}
```

#### 个人知识库（YOUR_PERSONAL_GROUP_ID）：
```
📝 知识入库完成
📌 标题：{标题}
📂 来源：{类型} | {URL或文件名}
🕐 入库时间：{YYYY-MM-DD HH:MM}
📍 入库状态：{根据 kb.py curate + kb.py query 的实际执行结果填写，不是固定文字}

💡 内容摘要： {3-5句话，自然简洁}

🔖 关键知识点：
• {知识点1}
• {知识点2}
• {知识点3}

🗣️ 说人话的一句话总结：{大白话}
```

---

## 五、特殊指令

| 用户输入 | 操作 |
|---------|------|
| "查询：" / "查" / "搜：" 开头 | python3 ~/.openclaw/workspace/kb-system/scripts/kb.py query --kb {ai_research/personal} --question "问题"，组织为自然语言回答 |
| "最近入库" / "最近记录" | python3 ~/.openclaw/workspace/kb-system/scripts/kb.py recent --kb {ai_research/personal} |

---

## 六、错误处理

失败时返回：
```
⚠️ 处理遇到问题
📋 内容类型：{类型}
🔧 失败步骤：{步骤}
❌ 错误信息：{描述}
🔄 建议：{操作建议}
```

- OCR 双引擎都失败 → 建议检查图片清晰度
- 链接无法访问 → 建议检查是否需要登录
- PDF + OCR 都失败 → 报错
- kb.py curate 失败 → 仍返回总结，标注 ⚠️ 入库失败
- whisper 失败 → 提示可能无音频
- yt-dlp 失败 → 提示链接可能失效

---

## 七、补充

1. 附件路径：~/.openclaw/media/inbound/（首次使用需创建：`mkdir -p ~/.openclaw/media/inbound`）
2. OCR 脚本：~/.openclaw/workspace/kb-system/scripts/ocr_dual.sh
3. 处理完清理 /tmp/kb_processing/ 临时文件
4. 多条消息逐条处理、逐条返回
5. 长视频（>1小时）先回复"正在转录中请稍等"
6. 每次处理默默自检：类型判断→正确管道→FULL_TEXT非空→入库→正确风格总结→最后一行是说人话总结→清理临时文件
