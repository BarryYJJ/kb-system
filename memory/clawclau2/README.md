# ClawClau v2

**Claude Code + Codex agent 编排系统**

小八（orchestrator）管理 agent swarm 的下一代工具。支持 git worktree 隔离、双 agent、中途 steering、智能 retry。

## 快速开始

```bash
# 设置 (可选，默认 ~/.openclaw/.clawclau2/)
export CC_HOME="$HOME/.openclaw/.clawclau2"

# 派发一个 Claude Code 任务
./spawn.sh my-task "Fix the auth bug in src/auth.ts" ~/my-project

# 查看状态
./check.sh

# 查看结果
./result.sh my-task
```

## 脚本

### spawn.sh — 派发任务

```bash
./spawn.sh [OPTIONS] <task-id> "<prompt>" [workdir]

# 选项
--agent <claude|codex>    agent 类型 (default: claude)
--steerable               交互式模式，支持 steer.sh
--worktree                在独立 git worktree 中运行
--branch <name>           worktree 分支名 (default: clawclau/<id>)
--timeout <sec>           超时秒数 (default: 600)
--interval <sec>          进度汇报间隔，0=关闭 (default: 0)
--max-retries <n>         最大重试次数 (default: 3)
--done-check <script>     Definition of Done 检查脚本
--model <name>            模型名称
```

**示例：**

```bash
# 基础任务
./spawn.sh fix-auth "Fix the login bug" ~/project

# Codex + worktree 隔离 + 超时 20 分钟
./spawn.sh refactor-api "Refactor the API layer" ~/project \
  --agent codex --worktree --timeout 1200

# 支持中途纠正 + 进度汇报每 60s
./spawn.sh explore-task "Explore the codebase and identify tech debt" ~/project \
  --steerable --interval 60

# 带 DoD 检查（验证 PR 已创建）
./spawn.sh feature-x "Implement feature X" ~/project \
  --done-check ./examples/done-check-pr.sh
```

### check.sh — 查看状态

```bash
./check.sh              # 列出所有任务
./check.sh my-task      # 查看单个任务详情
```

### result.sh — 获取结果

```bash
./result.sh my-task        # 从 log 提取可读文本
./result.sh my-task --raw  # 输出原始 log 文件
```

### steer.sh — 中途纠正方向

```bash
./steer.sh my-task "Focus on the login flow first, ignore registration for now"
```

注意：仅支持 `--steerable` 模式（Claude 交互式）和 Codex 任务。
Print 模式任务请用 `kill.sh` + `retry.sh`。

### kill.sh — 终止任务

```bash
./kill.sh my-task                          # 终止任务
./kill.sh my-task --cleanup-worktree       # 同时删除 worktree
```

### retry.sh — 改进 prompt 后重试

```bash
./retry.sh my-task                         # 用原 prompt + 失败上下文重试
./retry.sh my-task "Fix the null pointer error in line 42"  # 指定改进 prompt
```

重试任务 ID 格式：`my-task-retry-1`，`my-task-retry-2` 以此类推。

## Agent 选择指南

| 场景 | 推荐 | 理由 |
|------|------|------|
| 后端逻辑、复杂 bug | `--agent codex` | 推理能力强 |
| 前端、git 操作、快速任务 | `--agent claude`（默认）| 更快，权限问题少 |
| 需要中途纠正 | `--steerable` | 支持 steer.sh |
| 大规模重构 | `--agent codex --worktree` | 隔离+安全 |
| 探索型任务 | `--steerable --interval 60` | 可观察+可纠正 |

## 两种运行模式

**Print 模式（默认）**
- `claude -p --output-format stream-json`
- 实时 stream-json 日志，文本提取精确
- 不支持 steer.sh（stdin 非交互）
- 任务明确时使用

**Steerable 模式（`--steerable`）**
- `claude --dangerously-skip-permissions`（交互式）
- 支持 steer.sh 中途注入消息
- 日志为原始终端输出
- 探索型任务或需要中途纠正时使用

## Definition of Done

`--done-check <script>` 指定一个可执行脚本，任务完成后运行：
- 返回 0 = 完成
- 返回非 0 = 失败（触发 retry）

```bash
#!/usr/bin/env bash
# done-check-pr.sh: 验证 PR 是否已创建
# $1=task-id, $2=log-file, $3=workdir
BRANCH="clawclau/$1"
COUNT=$(gh pr list --head "$BRANCH" --json number 2>/dev/null | jq 'length')
[[ "$COUNT" -gt 0 ]]
```

## 任务状态流转

```
pending → running → done
                 → failed       (session 结束，log 空或 DoD 未通过)
                 → timeout      (超过 timeout)
                 → killed       (手动 kill.sh)
                 → retrying     (auto retry 进行中)
```

## 目录结构

```
$CC_HOME/                          # 默认 ~/.openclaw/.clawclau2/
├── active-tasks.json              # 任务注册表（source of truth）
├── logs/
│   ├── task-id.json               # Claude stream-json log
│   └── task-id.txt                # Codex / steerable plain text log
├── prompts/
│   ├── task-id.txt                # 原始 prompt
│   └── task-id-wrapper.sh         # 生成的 wrapper 脚本
└── worktrees/
    └── task-id/                   # git worktree（启用 --worktree 时）
```

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `CC_HOME` | `~/.openclaw/.clawclau2` | 数据目录 |

## 安全说明

- `spawn.sh` 使用 `--dangerously-skip-permissions` — 仅在受信任环境中使用
- Codex 使用 `--approval-mode full-auto` — 无需手动审批每个操作
- Worktree 隔离防止多任务互相干扰主目录

## v1 → v2 迁移

| v1 脚本 | v2 等价 |
|---------|---------|
| `claude-spawn.sh` | `spawn.sh` |
| `claude-check.sh` | `check.sh` |
| `claude-result.sh` | `result.sh` |
| `claude-steer.sh` | `steer.sh` |
| `claude-kill.sh` | `kill.sh` |
| `claude-monitor.sh` | 内嵌到 `spawn.sh` 后台进程 |
| —（新增）| `retry.sh` |

环境变量：`CLAWCLAU_HOME` → `CC_HOME`
