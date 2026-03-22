# 2026-03-19 学习笔记：OpenClaw + Claude Code 协作方式

来源：https://x.com/elvissun/status/2025920521871716562
作者：Elvis (@elvissun) — 2x dad, building medialyst.ai

## 核心架构：两层系统

- **OpenClaw（Zoe）** = 编排层，持有业务上下文（客户数据、会议记录、历史决策），负责生成精准 prompt、选择合适的 agent、监控进度、通知人类
- **Codex / Claude Code / Gemini** = 执行层，只看代码，专注于技术实现

**关键洞察**：上下文窗口是零和博弈。填满代码就没空间放业务上下文。两层系统让每个 AI 只加载它需要的东西。通过上下文实现专业化，而不是通过不同模型。

## 8 步工作流

### Step 1: 客户需求 → 与编排层讨论范围
- 会议记录自动同步到 Obsidian vault，无需额外解释
- 编排层做三件事：
  1. 直接操作（如充值 credits）— 编排层有 admin API 权限
  2. 拉取业务数据（如从 prod DB 读客户配置）— 编排层有只读权限，coding agent 永远不会有
  3. 生成详细 prompt → 派发 agent

### Step 2: 派发 Agent
- 每个 agent 有独立的 git worktree（隔离分支）和 tmux session
- 命令示例：
  ```bash
  git worktree add ../feat-xxx -b feat/xxx origin/main
  cd ../feat-xxx && pnpm install
  tmux new-session -d -s "codex-xxx" \
    -c "/path/to/worktree" \
    "$HOME/.codex-agent/run-agent.sh templates gpt-5.3-codex high"
  ```
- 任务注册到 `.clawdbot/active-tasks.json`，完成后更新状态（含 PR 号、CI 状态）
- tmux 比 `claude -p` 好：支持中途干预（`tmux send-keys`）

### Step 3: 监控循环
- cron 每 10 分钟跑一次
- 不直接 poll agent（太贵），而是跑确定性脚本：
  1. 检查 tmux session 是否存活
  2. 检查 tracked branch 上有没有 PR
  3. 检查 CI 状态（gh cli）
  4. 自动重试失败的 agent（最多 3 次）
  5. 只在需要人类关注时才通知

### Step 4: Agent 创建 PR
- agent commit → push → `gh pr create --fill`
- PR 不等于完成，"完成"的定义：
  - PR created
  - Branch synced to main（无 merge conflict）
  - CI passing（lint, types, unit, E2E）
  - 三个 AI reviewer 通过
  - 如果有 UI 变更，必须包含截图

### Step 5: 自动 Code Review
- 三个 reviewer 各有特长：
  - **Codex Reviewer**：边界情况之王，低误报，发现逻辑错误和竞态条件
  - **Gemini Code Assist**：免费，擅长安全和扩展性问题，给具体修复建议
  - **Claude Code Reviewer**：最弱，过于谨慎，基本跳过除非标记 critical
- 都直接在 PR 上发评论

### Step 6: 自动测试
- CI pipeline：lint → TypeScript → unit → E2E → Playwright（preview 环境）
- 新规则：UI 变更必须附截图，否则 CI fail

### Step 7: 人类 Review
- 所有自动化通过后才通知人类
- review 只需 5-10 分钟，很多 PR 看截图就 merge

### Step 8: Merge + 清理
- merge 后 cron 清理孤儿 worktree 和任务注册表

## Ralph Loop V2（增强版反馈循环）

标准 Ralph Loop：拉上下文 → 生成输出 → 评估结果 → 保存学习。问题：每轮 prompt 不变，只是检索到的上下文更好了。

Elvis 的改进：
- agent 失败时，编排层**不重试相同 prompt**
- 而是用业务上下文分析失败原因，写更好的 prompt：
  - agent 上下文不够？→ "只看这三个文件"
  - agent 方向错了？→ "客户要的是 X 不是 Y，这是会议记录"
  - agent 需要澄清？→ "这是客户的邮件和公司介绍"
- 成功模式被记录："这个 prompt 结构适合 billing 功能"，"Codex 需要提前看类型定义"
- 奖励信号：CI pass + 三个 review pass + 人类 merge

## 主动发现工作
编排层不只等任务分配，还会主动找活：
- 早上：扫 Sentry → 发现 4 个新错误 → 派 4 个 agent
- 会议后：扫会议记录 → 标记 3 个客户需求 → 派 3 个 agent
- 晚上：扫 git log → 派 Claude Code 更新 changelog

## 选择 Agent 的经验

| Agent | 擅长 | 使用频率 |
|-------|------|---------|
| Codex | 后端逻辑、复杂 bug、多文件重构，需要跨代码库推理 | 90% |
| Claude Code | 前端、git 操作，权限问题少 | 较少 |
| Gemini | UI 设计感，先生成 HTML/CSS spec 再交给 Claude Code 实现 | 设计任务 |

## 对我们的启发

1. **两层分离是正确的架构**：小八（OpenClaw）持上下文，乌萨奇（Claude Code）写代码
2. **tmux + worktree 是成熟的 agent 隔离方案**：比 `claude -p` 灵活得多
3. **确定性监控脚本**比 AI 轮询便宜得多：检查 tmux 存活、gh cli 查 PR/CI
4. **主动找活**：小八可以在 heartbeat 中主动发现任务
5. **失败重试要改 prompt，不是重试相同 prompt**：用上下文分析失败原因
6. **成功模式要记录**：什么 prompt 结构适合什么类型任务
7. **agent registry 用 JSON 文件就够了**：不需要数据库

## Elvis 的数据

- 94 commits / 天（最高），平均 50
- 7 PRs / 30 分钟
- 成本：Claude ~$100/月，Codex ~$90/月（起步 $20）
- 瓶颈：RAM，16GB 最多 4-5 个并行 agent
- 用途：真实 B2B SaaS（medialyst.ai）
