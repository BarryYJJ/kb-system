# 📘 知识库处理手册（Knowledge Base Playbook）

本文件包含知识库助手的完整处理流程。当收到来自知识库群的消息时，按本手册执行。

---

## 一、群组路由

| 群 ID | 知识库 | 工作目录 | 总结风格 |
|--------|--------|-------------|---------|
| YOUR_INVESTMENT_GROUP_ID | AI投研知识库 | ~/.openclaw/workspace/knowledge_bases/ai_research | 投研风格 |
| YOUR_PERSONAL_GROUP_ID | 个人知识库 | ~/.openclaw/workspace/knowledge_bases/personal | 个人风格 |

收到消息后，第一步根据群 ID 确定 KB_ROOT，后续所有 kb.py 命令先 cd 到对应目录。

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

1. 提取文字：
```
python3 -c "import pymupdf; doc = pymupdf.open('PDF路径'); text = '\n\n'.join([page.get_text() for page in doc]); print(text if len(text.strip()) > 100 else 'SCAN_PDF')"
```

2. 如果输出正常文字 → 即为 FULL_TEXT → 跳转【存储与总结】

3. 如果输出 SCAN_PDF（扫描件）→ 每页转图片：
```
python3 -c "import pymupdf; doc = pymupdf.open('PDF路径'); [page.get_pixmap(dpi=300).save(f'/tmp/kb_processing/pdf_pages/page_{i}.png') for i, page in enumerate(doc)]; print(f'共 {len(doc)} 页')"
```
然后逐页 OCR：
```
bash scripts/ocr_dual.sh /tmp/kb_processing/pdf_pages/page_0.png
```
按页码拼接所有 OCR 结果 = FULL_TEXT → 跳转【存储与总结】

4. 处理完清理：rm -f /tmp/kb_processing/pdf_pages/page_*.png

---

### 管道 B：图片

1. 执行 OCR：
```
bash scripts/ocr_dual.sh "图片路径"
```

2. OCR 输出 = FULL_TEXT → 跳转【存储与总结】

3. 如果输出 [OCR_ERROR] → 返回用户：⚠️ 图片文字识别失败，请检查图片清晰度。

---

### 管道 C：链接

#### 识别链接类型：
- bilibili.com 或 b23.tv → B站（C-1）
- xiaohongshu.com 或 xhslink.com → 小红书（C-2）
- 其他 → 通用网页（C-3）

#### C-1：B站视频
```bash
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

#### C-2：小红书（xiaohongshu.com / xhslink.com）

处理分三个阶段：获取信息 → 判断类型并深度提取 → 入库。

##### 阶段一：获取帖子基础信息

1. 如果是短链接（xhslink.com），先解析真实URL：
   ```
   REAL_URL=$(curl -sLI -o /dev/null -w '%{url_effective}' "短链接URL")
   ```

2. 用小红书 MCP 工具获取帖子详情：
   - 获取：标题、作者、发布时间、正文文字、标签、点赞/收藏/评论数
   - 获取：帖子类型（视频 or 图文）
   - 获取：如果有图片，获取图片 URL 列表；如果有视频，获取视频 URL

##### 阶段二：判断类型并深度提取

【视频笔记处理】
```bash
# yt-dlp 下载音频（使用完整分享链接，含 token 参数）
yt-dlp -x --audio-format wav -o "/tmp/kb_processing/audio/xhs.%(ext)s" "FULL_URL"

# whisper 转写
KMP_DUPLICATE_LIB_OK=TRUE whisper /tmp/kb_processing/audio/xhs.wav \
  --model medium --language zh --initial_prompt "$PROMPT" \
  --output_dir /tmp/kb_processing/whisper_output/

# 合并
FULL_TEXT = METADATA + 帖子正文 + 视频转写
```

【图文笔记处理】
```bash
# 逐张下载并 OCR
for i in 图片序号; do
  curl -o /tmp/kb_processing/ocr/xhs_img_${i}.jpg "图片URL"
  bash scripts/ocr_dual.sh /tmp/kb_processing/ocr/xhs_img_${i}.jpg
done

# 合并
FULL_TEXT = METADATA + 帖子正文 + 所有图片OCR结果
```

#### C-3：通用网页

```bash
# 第一步：Jina Reader 读取
curl -s "https://r.jina.ai/{URL}" > /tmp/kb_processing/web_content.txt

# 第二步：降级方案（Jina 失败时）
curl -sL "URL" | python3 -c "
import sys, re
html = sys.stdin.read()
html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
html = re.sub(r'<[^>]+>', '\n', html)
text = re.sub(r'\n{3,}', '\n\n', html)
print(text.strip())
"
```

---

### 管道 D：长文字

用户文本 = FULL_TEXT → 跳转【存储与总结】

---

## 四、存储与总结

### 4.1 存入本地知识库

```bash
python3 scripts/kb.py curate \
  --kb {ai_research 或 personal} \
  --title "{根据内容自动生成的标题}" \
  --source "{来源类型} | {URL 或 用户直接发送}" \
  --content "{FULL_TEXT 的完整内容}" \
  --type "{pdf / image_ocr / video / xiaohongshu / webpage / text}"
```

执行后验证：
```bash
python3 scripts/kb.py query \
  --kb {ai_research 或 personal} \
  --question "{用标题关键词检索}"
```

### 4.2 总结格式

#### 投研知识库：
```
📊 投研知识入库完成
📌 标题：{标题}
📂 来源：{类型} | {URL或文件名}
🕐 入库时间：{YYYY-MM-DD HH:MM}
📍 入库状态：{✅ 成功 | ⚠️ 已执行未验证 | ❌ 失败}

🔑 核心要点：
1. {要点1 — 优先数据、趋势、结论}
2. {要点2}
3. {要点3}

📈 投资视角：
• 行业/赛道：{行业}
• 关键数据：{数字、百分比、指标}
• 信号判断：{利好/利空/中性} — {原因}

🗣️ 说人话的一句话总结：{大白话}
```

#### 个人知识库：
```
📝 知识入库完成
📌 标题：{标题}
📂 来源：{类型} | {URL或文件名}
🕐 入库时间：{YYYY-MM-DD HH:MM}
📍 入库状态：{✅ 成功 | ⚠️ 已执行未验证 | ❌ 失败}

💡 内容摘要：{3-5句话}

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
| "查询：" / "查" / "搜：" 开头 | `python3 scripts/kb.py query --kb {库} --question "问题"` |
| "最近入库" / "最近记录" | `python3 scripts/kb.py recent --kb {库}` |

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
- whisper 失败 → 提示可能无音频
- yt-dlp 失败 → 提示链接可能失效
