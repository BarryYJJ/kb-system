# NemoClaw核心架构解析：企业级AI Agent安全平台

**来源**: text | 用户直接发送

**类型**: text

**入库时间**: 2026-03-17T09:08:45.557172

---

🤖 NemoClaw 是什么
NVIDIA 基于 OpenClaw 打造的企业级 AI Agent 安全平台。不是另起炉灶，而是在 OpenClaw 上面包了一层安全壳。
🔧 核心架构（三层）
- Nemotron：NVIDIA 的开源模型家族，替代默认 LLM，提供企业级推理能力
- OpenShell：隔离沙箱运行时，Agent 的所有操作都在沙箱内执行，数据不外泄
- NVIDIA Agent Toolkit：一键安装，模型 + 运行时 + 安全蓝图打包在一起
🛡️ 解决的核心问题
OpenClaw 爆火之后，企业最大的顾虑是安全：Agent 能访问文件、日历、数据库，万一失控怎么办。NemoClaw 加了策略引擎和沙箱隔离，Agent 该干的事能干，不该碰的数据碰不到。
🤝 安全合作方
CrowdStrike、Cisco、Microsoft Security 都参与了 OpenShell 的安全建设。微软的 NEXT AI 团队已经在用 Nemotron + OpenShell 做对抗性训练，增强运行时防护。
💻 部署方式
- 支持本地和云端
- 硬件：RTX PC、DGX Station、DGX Spark
- 一条命令安装，兼容任何 coding agent
📅 时间线
- 3月10日 Wired 爆料 NVIDIA 在做这个
- 3月16日（今天）Jensen 在 GTC 2026 正式发布
💡 怎么看
本质上 NVIDIA 没有重造 OpenClaw，而是做了"OpenClaw 的企业安全增强包"。这个思路很聪明：不跟 OpenClaw 竞争，而是成为它的安全基础设施层。对于正在观望的企业客户来说，有人给 Agent 加了安全带，落地意愿会大幅提升。