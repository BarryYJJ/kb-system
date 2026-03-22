# ClawClau v2 设计参考 — Elvis 的 Agent Swarm 架构

来源：https://x.com/elvissun/status/2025920521871716562

## 核心理念

**OpenClaw 不直接调 coding agent，而是作为编排层。** 小八（orchestrator）管理乌萨奇们（agents），持有业务上下文，派发精准 prompt。

**Context windows 是零和博弈。** agent 只看代码，orchestrator 只看业务。各司其职。

## 关键架构决策

### 1. Agent Spawn
- 每个 agent 用 **git worktree** 隔离（独立分支，互不干扰）
- 在 **tmux session** 中运行（支持中途 steering）
- 支持 Codex 和 Claude Code 两种 agent
- 任务注册到 `.clawdbot/active-tasks.json`

### 2. Agent 选择策略
- **Codex**：后端逻辑、复杂 bug、多文件重构（90%任务）
- **Claude Code**：前端、git 操作（更快、权限问题少）
- **Gemini**：UI 设计（生成 HTML/CSS spec，交给 Claude Code 实现）

### 3. Definition of Done（关键！）
- PR created
- Branch synced to main（无 merge conflicts）
- CI passing（lint, types, unit tests, E2E）
- Code review passed
- Screenshot included（UI 变更必须附截图）

### 4. Automated Code Review
- 三模型交叉 review（Codex + Gemini + Claude Code），各有擅长
- review 结果直接发到 PR comment

### 5. Monitoring（Ralph Loop V2）
- 定时 cron 检查所有 agent 状态
- **不 poll agent**，而是读 JSON registry + 检查 tmux/gitch 状态
- 100% 确定性，极低 token 消耗
- Agent 失败时自动 respawn（最多3次），但**不是同一个 prompt 重试**
- Orchestrator 用业务上下文写更好的 retry prompt

### 6. Prompt 改进循环
- 成功的 prompt pattern 被记录："这种结构适合 billing 功能"
- 失败也记录："Codex 需要 type definitions 提前给"
- 越跑越聪明

## 当前 ClawClau v1 的问题

1. **没有 git worktree 隔离**：多个任务共享同一目录，可能冲突
2. **只支持 Claude Code**：不支持 Codex
3. **没有 steering 能力**：无法中途纠正 agent 方向
4. **日志格式 stream-json 难读**：需要更好的解析
5. **没有自动 retry + prompt 改进**：失败就失败了
6. **没有 code review 自动化**
7. **没有 Definition of Done 概念**
8. **进度汇报还没完全跑通**
