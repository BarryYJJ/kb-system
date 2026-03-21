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
bash ~/.openclaw/workspace/scripts/ocr_dual.sh /tmp/kb_processing/pdf_pages/page_0.png
```
按页码拼接所有 OCR 结果 = FULL_TEXT → 跳转【存储与总结】

5. 处理完清理：rm -f /tmp/kb_processing/pdf_pages/page_*.png

---

### 管道 B：图片

1. 文件路径在 ~/.openclaw/media/inbound/ 下。

2. 执行 OCR：
```
bash ~/.openclaw/workspace/scripts/ocr_dual.sh "图片路径"
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

**2026-03-13 更新**：使用 browser 工具替代 MCP 容器，不再依赖 Docker。

**执行分工**：
- 简单图文（1-3张图）：直接处理
- 复杂图文（需翻页）或批量：委派给 Claude Code 执行

处理分三个阶段：获取信息 → 判断类型并深度提取 → 入库。

##### 阶段一：用 browser 打开链接

1. 用户发送小红书链接（支持两种格式）：
   - 短链接：`http://xhslink.com/o/xxx`
   - 完整链接：`https://www.xiaohongshu.com/explore/xxx?xsec_token=xxx`

2. 用 browser 工具打开（profile: openclaw）：
```
browser(action="open", profile="openclaw", url="用户发的链接")
```

3. 获取页面内容：
```
browser(action="snapshot", targetId="上一步返回的targetId")
```

4. 解析内容（从 snapshot 结果提取）：
   - 标题：在 `generic > link` 找到笔记标题
   - 作者：找到作者昵称和头像
   - 正文：正文内容在 `generic > text` 中
   - 标签：提取 `#tag` 格式的链接
   - 互动数据：点赞、收藏、评论数
   - 图片数量：如 `1/5` 表示共5张图片
   - 视频标识：如果有视频图标或视频播放器 → 视频

##### 阶段二：判断类型并深度提取

【图文笔记处理】

**自动翻页逻辑**：
1. 首次 snapshot 后，从内容中提取图片数量（如 `1/5` → 共5张）
2. 循环翻页：对于第 2 到 N 张图片：
   - 查找翻页箭头元素（ref 格式如 `e145`）
   - 点击翻页箭头
   - snapshot 获取新内容
   - 解析新增的图片文字
3. 合并所有页面的内容

示例代码：
```
# 获取图片数量
import re
match = re.search(r'(\d+)/(\d+)', snapshot_text)
if match:
    current_page = int(match.group(1))
    total_pages = int(match.group(2))
    
# 自动翻页
for page in range(current_page + 1, total_pages + 1):
    # 找翻页箭头并点击
    browser(action="act", targetId="xxx", request={"kind": "click", "ref": "箭头ref"})
    time.sleep(1)
    # 获取新内容
    new_snapshot = browser(action="snapshot", targetId="xxx")
    # 解析新页面的文字
```

2. 图片 OCR（如需要）：
   - 从 snapshot 中提取图片 URL（可选，如果页面文字不够）
   - 或用 RapidOCR 处理截图

3. 合并 FULL_TEXT：
```
FULL_TEXT = "标题: xxx\n作者: xxx\n发布时间: xxx\n互动: xxx赞 xxx收藏 xxx评论\n\n--- 正文 ---\n" + 正文内容 + "\n\n--- 标签 ---\n" + 标签列表
```

【视频笔记处理】

1. 用 snapshot 获取页面文字内容：
   - 视频笔记的正文也会显示在页面上
   - 评论区的精彩评论也会被抓取

2. FULL_TEXT：
```
FULL_TEXT = "标题: xxx\n作者: xxx\n发布时间: xxx\n互动: xxx赞 xxx收藏 xxx评论\n\n--- 正文 ---\n" + 页面文字内容 + "\n\n--- 热门评论 ---\n" + 评论内容
```

⚠️ **视频转写说明**：目前暂无完美方案获取视频语音。如需转写，请：
- 方案A：从 App 保存视频到本地 → 用 whisper 转写
- 方案B：仅入库文字内容（正文+评论）

##### 阶段三：入库

FULL_TEXT 准备好后 → 跳转到【存储与总结】

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

python3 ~/.openclaw/workspace/scripts/kb.py curate \
  --kb {ai_research 或 personal} \
  --title "{根据内容自动生成的标题}" \
  --source "{来源类型} | {URL 或 用户直接发送}" \
  --content "{FULL_TEXT 的完整内容}" \
  --type "{pdf / image_ocr / video / xiaohongshu / webpage / text}"

执行后验证：
python3 ~/.openclaw/workspace/scripts/kb.py query \
  --kb {ai_research 或 personal} \
  --question "{用标题关键词检索}"

根据实际执行结果，在总结中如实报告：
- curate 成功且 query 检索到 → 📍 入库状态：✅ 成功 | doc_id: {id} | 已验证可检索
- curate 成功但 query 未检索到 → 📍 入库状态：⚠️ 已执行，验证未检索到
- curate 失败 → 📍 入库状态：❌ 失败 | {错误信息}

如果 FULL_TEXT 超过 50000 字符，kb.py 会自动分段处理，不需要手动切分。

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
| "查询：" / "查" / "搜：" 开头 | python3 ~/.openclaw/workspace/scripts/kb.py query --kb {ai_research/personal} --question "问题"，组织为自然语言回答 |
| "最近入库" / "最近记录" | python3 ~/.openclaw/workspace/scripts/kb.py recent --kb {ai_research/personal} |

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
2. OCR 脚本：~/.openclaw/workspace/scripts/ocr_dual.sh
3. 处理完清理 /tmp/kb_processing/ 临时文件
4. 多条消息逐条处理、逐条返回
5. 长视频（>1小时）先回复"正在转录中请稍等"
6. 每次处理默默自检：类型判断→正确管道→FULL_TEXT非空→入库→正确风格总结→最后一行是说人话总结→清理临时文件
