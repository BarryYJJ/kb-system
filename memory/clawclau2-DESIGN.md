# ClawClau v2 — Architecture Design

> 小八调度 agent swarm 的下一代编排层

## 核心理念

OpenClaw (小八) 是编排层 (orchestrator)，持有业务上下文。Agent (乌萨奇) 只看代码，各司其职。Context windows 是零和博弈——不要混用。

## v1 vs v2 对比

| 能力 | v1 | v2 |
|------|----|----|
| Agent 类型 | Claude Code only | Claude Code + Codex |
| 工作目录隔离 | 共享目录（冲突风险）| git worktree 每任务独立分支 |
| Steering | tmux send-keys（但 -p 模式无效）| 两种模式：steerable / print |
| 自动 Retry | 无 | 最多3次，每次改进 prompt |
| Definition of Done | 无 | 自定义检查脚本 |
| 日志格式 | stream-json（只支持 claude）| stream-json (claude) + plain (codex) |
| 进度汇报 | --interval（v1.4 才修复）| 内置，稳定 |
| 代码质量 | 多次 patch，混乱 | 从头设计，清晰分层 |

---

## 架构概览

```
┌─────────────────────────────────────────────────┐
│                   小八 (orchestrator)             │
│   持有业务上下文，决定任务类型、prompt、DoD         │
└────────────────────┬────────────────────────────┘
                     │ spawn.sh / retry.sh
         ┌───────────┼───────────┐
         ▼           ▼           ▼
   [Claude Code]  [Codex]   [Future: Gemini]
   tmux session  tmux session
   git worktree  git worktree
         │           │
         ▼           ▼
   stream-json     plain text
     log file      log file
         │           │
         └─────┬─────┘
               ▼
         active-tasks.json  ← source of truth
               │
         check.sh / monitor
         result.sh
         steer.sh
         kill.sh
         retry.sh
```

---

## 组件设计

### 1. Registry (`active-tasks.json`)

每个任务的完整生命周期记录：

```json
{
  "id": "refactor-auth",
  "agent": "claude",
  "mode": "print",
  "tmuxSession": "cc-refactor-auth",
  "prompt": "Refactor src/auth.ts to use JWT",
  "workdir": "/home/user/project",
  "agentWorkdir": "/home/user/.openclaw/worktrees/refactor-auth",
  "log": "/home/user/.openclaw/.clawclau2/logs/refactor-auth.json",
  "model": "claude-opus-4-5",
  "startedAt": 1742000000000,
  "timeout": 600,
  "status": "running",
  "completedAt": null,
  "worktree": "/home/user/.openclaw/.clawclau2/worktrees/refactor-auth",
  "branch": "clawclau/refactor-auth",
  "retryCount": 0,
  "maxRetries": 3,
  "parentTaskId": null,
  "doneCheck": "/path/to/done-check.sh",
  "steerLog": [
    { "at": 1742000100000, "message": "Focus on the login flow first" }
  ]
}
```

**Status lifecycle:**
```
pending → running → done
                 → failed       (session ended, log empty or DoD check failed)
                 → timeout      (exceeded timeout)
                 → killed       (manual)
                 → retrying     (auto retry triggered)
```

### 2. Agent 选择策略

| 任务类型 | 推荐 Agent | 原因 |
|---------|-----------|------|
| 后端逻辑、复杂 bug、多文件重构 | `codex` | 更擅长推理和代码理解 |
| 前端、git 操作、文件操作 | `claude` | 权限问题少，更快 |
| 需要中途纠正方向 | `claude --steerable` | 支持 tmux 交互 |
| 长时间任务（>10分钟）| `codex` | 更稳定 |

### 3. 两种运行模式

**Print 模式（默认）**
- 命令：`claude -p --output-format stream-json --verbose --include-partial-messages`
- 优点：实时 stream-json 日志，文本提取精确
- 缺点：不支持中途 steering（stdin 非交互）
- 适合：明确任务，不需要中途纠正

**Steerable 模式（`--steerable`）**
- 命令：`claude --dangerously-skip-permissions`（交互式）
- 日志：`tmux pipe-pane` 捕获原始终端输出
- 优点：支持 `steer.sh` 中途注入消息
- 缺点：日志含 ANSI 转义码，需额外清洗
- 适合：需要中途纠正，或不确定任务范围的探索型任务

**Codex 模式**
- 命令：`codex --approval-mode full-auto`
- 日志：纯文本（非 stream-json）
- Steering：通过 tmux send-keys 发送消息

### 4. Git Worktree 隔离

```bash
# spawn 时创建
git -C "$REPO_ROOT" worktree add "$WORKTREE_PATH" -b "clawclau/$TASK_ID"

# 任务完成后（可选：保留 for PR review）
git -C "$REPO_ROOT" worktree remove "$WORKTREE_PATH" --force
```

多个并发 agent 在不同 branch 工作，互不干扰。主目录 clean，随时可切换。

### 5. 监控策略（Monitoring）

**不 poll agent，100% 确定性：**
1. `tmux has-session` → 判断 session 是否存活
2. `jq` 读 `active-tasks.json` → 获取任务元数据
3. `wc -c` 检查 log 文件大小变化 → 判断是否有新输出
4. `gh pr list` → 检查 PR 创建（DoD 检查）
5. 超时：`$NOW_MS - startedAt > timeout * 1000`

后台 monitor（`spawn.sh` 内嵌）：
```
while tmux has-session; do sleep 5; done
→ session 结束后检查 log
→ 运行 doneCheck 脚本（如有）
→ 更新 registry status
→ openclaw system event 通知
```

### 6. 自动 Retry + Prompt 改进

```
任务失败 → retry.sh 读取失败原因（从 log 提取）
         → 若 retryCount < maxRetries:
           - 创建新任务 ID（${original}-retry-${n}）
           - 设置 parentTaskId = original
           - 用改进后的 prompt 派发
           - retryCount++
         → 若 retryCount >= maxRetries: 通知失败
```

Retry prompt 改进方式：
1. 附加失败原因摘要（从 log 提取最后200字符）
2. 附加之前的 steering 历史
3. 明确指出"上次失败原因是 X，这次请注意 Y"

### 7. Definition of Done (DoD)

`--done-check <script>` 指定一个可执行脚本：
```bash
#!/bin/bash
# $1=task-id, $2=log-file, $3=workdir
# 返回 0 = done, 非0 = not done
# 示例：检查 PR 是否创建
gh pr list --head "clawclau/$1" --json number | jq 'length > 0'
```

内置 DoD 检查器（未来可扩展）：
- `--done-check pr` → 检查 PR 是否创建
- `--done-check ci` → 检查 CI 是否通过
- `--done-check file:<path>` → 检查文件是否存在/修改

### 8. stream-json 文本提取

优先级（Claude print 模式）：
1. `result` 事件的 `.result` 字段（任务完成后的完整输出）
2. 最后一条 `assistant` 事件的 `.message.content[].text`（累积文本）
3. 所有 `text_delta` 片段拼接（实时流）

Codex 日志：直接读取，strip ANSI 转义码。

---

## 目录结构

```
$CC_HOME/                       # 默认 ~/.openclaw/.clawclau2/
├── active-tasks.json           # 任务注册表
├── logs/
│   ├── task-id.json            # Claude stream-json log
│   └── task-id.txt             # Codex plain text log
├── prompts/
│   ├── task-id.txt             # 原始 prompt
│   └── task-id-wrapper.sh      # 生成的 wrapper 脚本
└── worktrees/
    └── task-id/                # git worktree（如启用）
```

---

## 脚本 API

### spawn.sh
```
spawn.sh [OPTIONS] <task-id> "<prompt>" [workdir]

Options:
  --agent <claude|codex>    agent 类型 (default: claude)
  --steerable               启用交互式模式（支持 steering）
  --worktree                在独立 git worktree 中运行
  --branch <name>           worktree branch 名 (default: clawclau/<id>)
  --timeout <sec>           超时秒数 (default: 600)
  --interval <sec>          进度汇报间隔 (default: 0 = off)
  --max-retries <n>         最大重试次数 (default: 3)
  --done-check <script>     DoD 检查脚本路径
  --model <name>            模型名称
```

### check.sh
```
check.sh [task-id]           # 查看单个任务或列出所有任务
```

### result.sh
```
result.sh <task-id>          # 从 log 提取可读文本结果
```

### steer.sh
```
steer.sh <task-id> "<message>"   # 中途纠正 agent 方向
```

### kill.sh
```
kill.sh <task-id> [--cleanup-worktree]   # 终止任务
```

### retry.sh
```
retry.sh <task-id> ["<improved prompt>"]  # 改进 prompt 后重试
```

---

## 设计原则

1. **Registry is truth**: 所有状态变更先写 registry，再操作
2. **Fail fast**: 参数错误立即退出，不继续执行
3. **Idempotent where possible**: check/result 可以多次调用无副作用
4. **No polling**: 监控通过状态读取，不轮询 agent
5. **Clean worktrees**: 任务结束后 worktree 可选清理，不泄漏
6. **Prompt as file**: prompt 写入文件，避免 shell 转义地狱
