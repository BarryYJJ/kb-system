# OpenClaw 项目结构文档

> 生成时间: 2026-03-07
> 版本: 基于当前安装版本

## 项目概览

OpenClaw 是一个开源的 AI 助手框架，支持多渠道接入（飞书、Discord、Telegram、WhatsApp 等）和插件扩展。

---

## 核心目录结构

```
openclaw/
├── dist/                    # 编译后的 JavaScript 代码
├── docs/                    # 项目文档
├── extensions/              # 渠道扩展插件
├── node_modules/            # 依赖包
├── skills/                  # 技能扩展
├── assets/                  # 静态资源
├── LICENSE                  # 开源许可证
├── CHANGELOG.md             # 更新日志
├── README.md                # 项目说明
├── package.json             # npm 配置
└── openclaw.mjs             # 入口文件
```

---

## 核心模块详解

### 1. extensions/ - 渠道扩展

支持的消息/通话渠道：

| 渠道 | 说明 |
|------|------|
| `feishu` | 飞书 |
| `discord` | Discord |
| `telegram` | Telegram |
| `whatsapp` | WhatsApp |
| `signal` | Signal |
| `slack` | Slack |
| `googlechat` | Google Chat |
| `imessage` | iMessage |
| `irc` | IRC |
| `line` | LINE |
| `matrix` | Matrix |
| `msteams` | Microsoft Teams |
| `nostr` | Nostr |
| `twitch` | Twitch |
| `zalo` | Zalo |

**其他扩展：**
- `acpx` - ACP 协议支持
- `phone-control` - 手机控制
- `voice-call` - 语音通话
- `memory-core` / `memory-lancedb` - 记忆存储
- `llm-task` - LLM 任务处理

### 2. skills/ - 技能扩展

内置技能（54个）：

**效率工具：**
- `apple-notes` - Apple Notes 管理
- `apple-reminders` - Apple 提醒事项
- `things-mac` - Things 3 任务管理
- `obsidian` - Obsidian 笔记
- `notion` - Notion 集成

**开发者工具：**
- `github` - GitHub CLI 集成
- `gh-issues` - GitHub Issues 管理
- `coding-agent` - 代码开发代理（Codex/Claude Code）
- `skill-creator` - 技能创建工具

**媒体处理：**
- `summarize` - 内容摘要
- `video-frames` - 视频帧提取
- `openai-whisper` - 语音转文字
- `peekaboo` - macOS UI 自动化

**其他：**
- `weather` - 天气查询
- `blogwatcher` - 博客监控
- `gemini` - Gemini CLI
- `wacli` - WhatsApp CLI

### 3. dist/ - 编译输出

编译后的代码，按功能模块分包：

- `daemon-cli.js` - 守护进程 CLI
- `gateway-cli.js` - 网关 CLI
- `cron-cli.js` - 定时任务 CLI
- `tui-cli.js` - 终端 UI
- `node-cli.js` - 节点 CLI
- `control-ui/` - Web 控制界面

**bundled/ - 内置插件：**
- `session-memory` - 会话记忆
- `command-logger` - 命令日志
- `boot-md` - 启动引导
- `bootstrap-extra-files` - 额外引导文件

**plugin-sdk/ - 插件 SDK：**

| 模块 | 功能 |
|------|------|
| `discord` | Discord 集成 |
| `feishu` | 飞书集成 |
| `whatsapp` | WhatsApp 集成 |
| `telegram` | Telegram 集成 |
| `memory` | 记忆系统 |
| `config` | 配置管理 |
| `security` | 安全模块 |
| `web` | Web 服务 |
| `node-host` | 节点托管 |
| `providers` | LLM 提供商 |
| `media-understanding` | 媒体理解 |
| `terminal` | 终端集成 |
| `agents` | 代理系统 |

### 4. docs/ - 文档

项目文档目录。

---

## 配置文件

OpenClaw 配置通常位于：
- `~/.openclaw/config.json` - 主配置
- `~/.openclaw/workspace/` - 工作区

---

## 常用命令

```bash
# 启动网关
openclaw gateway start

# 查看状态
openclaw status

# 定时任务
openclaw cron ...

# 更新
openclaw update run
```

---

## 扩展开发

可通过以下方式扩展 OpenClaw：

1. **开发新渠道扩展** - 在 `extensions/` 下创建新插件
2. **开发新技能** - 在 `skills/` 下创建技能
3. **配置插件** - 修改 `config.json` 中的 plugins 字段

---

*此文档由 OpenClaw 自动生成*
