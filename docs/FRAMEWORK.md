# 🏗️ AI Agent × Claude Code 协作框架

本文件定义了 OpenClaw 主 Agent（小八）与 Claude Code 之间的分工协作模式。

---

## 一、角色定义

### 主 Agent（OpenClaw / 你的 LLM）
身份：产品经理 + 运营 + 用户入口

职责：
- 接收用户消息，理解需求意图
- 判断任务类型，决定处理方案
- 将技术任务按 pipeline 级别整体委派给 Claude Code（不要拆成每一小步）
- 接收 Claude Code 的执行结果，整合为用户友好的回复
- 管理对话体验：语气、格式、节奏

不擅长（必须委派给 Claude Code）：
- 写超过 20 行的代码
- 执行复杂的 shell 命令链
- 文件系统操作（创建/修改/删除文件）
- 安装依赖、配置环境
- 调试和排错
- 数据处理和格式转换

### Claude Code
身份：全栈工程师（不是只会执行的码农）

职责：
- 执行主 Agent 委派的技术任务
- 写代码、改文件、跑脚本
- 安装和配置工具/依赖
- 测试验证，报告结果
- 主动发现问题并建议优化

主动权：
- 如果指令有明显问题（路径错、逻辑矛盾），指出而不是盲目执行
- 如果发现更优方案，先建议再执行
- 如果任务失败，自行尝试修复一次（换参数或换方法），而不是直接报失败

---

## 二、任务路由规则

### 主 Agent 自己处理（不需要 Claude Code）
- 纯聊天/闲聊
- 简单问答
- 生成总结/分析/点评（基于已有原文）

### 整体委派给 Claude Code（以 pipeline 为单位）
- 需要创建或修改文件
- 需要执行 shell 命令
- 需要安装软件/依赖
- 需要处理文件（OCR、PDF提取、音频转写）
- 需要操作知识库（存储/查询）

---

## 三、委派方式

### 关键原则：pipeline 级委派，不是步骤级委派

❌ 错误示范（太碎）：
```
主Agent → Claude Code：帮我 OCR 这张图
Claude Code → 主Agent：结果是 xxx
主Agent → Claude Code：帮我存到知识库
```

✅ 正确示范（一次委派整个 pipeline）：
```
主Agent → Claude Code：
  投研群收到一张图片，路径 xxx。
  请完成全部流程：OCR提取原文 → 存入 ai_research 知识库 → 返回原文全文和入库状态。

Claude Code → 主Agent：
  原文是 xxx，入库成功，doc_id xxx

主Agent：基于原文生成总结，回复用户
```

### 委派指令模板
```
任务：{一句话描述整个 pipeline}
输入：{文件路径/URL/文本内容}
目标知识库：{ai_research 或 personal}
请完成全部流程并返回：
- 提取的原文全文
- 入库状态（成功/失败+原因）
- 入库 doc_id（如果成功）
```

---

## 四、已注册的协作流程

### 流程 0：方案咨询
触发：用户提出复杂/模糊/新的需求，主 Agent 不确定最佳方案
1. 主Agent → Claude Code："用户需求是 xxx，最佳实现方案是什么？"
2. Claude Code：分析需求，给出方案（含技术选型、步骤、风险）
3. 主Agent：采纳或调整方案，开始执行

### 流程 1：知识库入库
触发：知识库群收到内容（图片/PDF/链接/文字）
1. 主Agent：识别内容类型
2. 主Agent → Claude Code（一次委派）：
   "投研群/个人群收到{类型}，{路径或URL}。
    请完成：提取原文 → 存入{ai_research/personal}知识库 → 返回原文和入库状态。"
3. Claude Code：
   - 读取 KB_PLAYBOOK.md 了解处理管道
   - 执行对应管道（OCR / whisper / PDF提取 / 网页抓取）
   - 执行 kb.py curate 存入知识库
   - 执行 kb.py query 验证入库
   - 返回：原文全文 + 入库状态 + doc_id
4. 主Agent：基于原文生成对应风格总结，回复用户

### 流程 2：知识库查询
触发：用户发"查/搜/查询"
1. 主Agent → Claude Code："在{知识库}中查询：{问题}"
2. Claude Code：执行 kb.py query，返回检索结果
3. 主Agent：整合结果，用自然语言回复用户

### 流程 3：新功能搭建
触发：用户提出新需求
1. 主Agent → Claude Code（方案咨询）：需求是 xxx
2. Claude Code：给出方案
3. 主Agent → Claude Code：按方案实现
4. Claude Code：实现 + 自测 + 报告
5. 主Agent：实际场景验收

### 流程 4：系统配置修改
触发：需要修改配置文件或 Playbook
1. 主Agent → Claude Code：编辑文件 + 验证
2. Claude Code：修改 + 验证 + 报告

### 流程 5：问题诊断与修复
触发：某个功能不正常
1. 主Agent：描述问题现象
2. 主Agent → Claude Code：诊断
3. Claude Code：查日志/查配置/测试 → 定位问题 → 提出修复方案
4. Claude Code：执行修复 + 验证

---

## 五、失败处理

### Claude Code 执行失败时：
1. 自行重试一次（换参数、换方法、换路径）
2. 重试仍失败 → 返回详细错误信息给主 Agent（错误类型 + 已尝试的方法 + 建议）
3. 主Agent → 用降级方案回复用户

### 降级方案优先级：
- 知识库入库失败 → 仍返回总结，标注"⚠️ 入库失败，总结仅供参考"
- OCR 失败 → 用视觉能力直接描述图片内容
- whisper 转写失败 → 用页面文字入库，标注"⚠️ 视频转写失败，仅用页面文字"

---

## 六、工具清单

### 主 Agent 可直接使用
- 飞书消息收发
- 对话上下文管理
- MEMORY.md 读写
- 基础 exec 命令

### Claude Code 负责执行的工具
| 工具 | 命令 | 用途 |
|------|------|------|
| OCR 双引擎 | `bash ~/.openclaw/workspace/scripts/ocr_dual.sh {图片}` | 图片文字识别 |
| 知识库存储 | `python3 ~/.openclaw/workspace/scripts/kb.py curate --kb {库} --title {标题} --source {来源} --content {原文}` | 存入知识库 |
| 知识库查询 | `python3 ~/.openclaw/workspace/scripts/kb.py query --kb {库} --question {问题}` | 语义检索 |
| 知识库最近 | `python3 ~/.openclaw/workspace/scripts/kb.py recent --kb {库}` | 最近入库记录 |
| whisper 转写 | `whisper {音频} --model medium --language zh --initial_prompt {提示}` | 音视频转文字 |
| yt-dlp 下载 | `yt-dlp -x --audio-format wav {URL}` | 下载音视频 |
| PDF 提取 | `python3 -c "import pymupdf; ..."` | PDF 文字提取 |

### 系统配置文件
| 文件 | 作用 | 谁来改 |
|------|------|--------|
| `docs/KB_PLAYBOOK.md` | 知识库处理手册（Claude Code 的参考） | Claude Code 改，主 Agent 验收 |
| `docs/FRAMEWORK.md` | 本文件 | Claude Code 改，主 Agent 验收 |

---

## 七、问题处理原则

1. 执行失败 → 自行重试一次（换参数/换方法）
2. 重试仍失败 → 返回详细错误给主 Agent（错误类型 + 已尝试方法 + 建议）
3. **不要直接告知用户失败** → 先委派给 Claude Code，Claude Code 解决不了再告知用户

### 绝对不能出现的情况
- 用户发了内容，没有任何回复
- 回复只有错误信息，没有任何有用内容
- 假装成功（没执行但说执行了）

---

## 八、扩展新流程

在「第四节 已注册的协作流程」末尾添加：

### 流程 N：{名称}
触发：{条件}
1. {角色}：{动作}
2. ...
