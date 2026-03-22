# NVIDIA 不做对手做铠甲：NemoClaw 为什么选择站在 OpenClaw 背后

---

3月16日，GTC 2026。

黄仁勋穿着他标志性的皮衣走上台，在长达两小时的主题演讲里塞满了芯片、机器人和各种"one more thing"。但真正让开发者社区炸锅的，是一个叫 **NemoClaw** 的东西。

不是新模型，不是新芯片，而是一个安全平台。

更准确地说，NVIDIA 把开源项目 OpenClaw 拿过来，在外面包了一层企业级安全壳，然后免费送出去。

这个操作，值得好好聊聊。

---

## 先说背景：OpenClaw 怎么了？

OpenClaw 是过去一年里最火的开源 AI Agent 项目之一。它的原创作者 Peter Steinberger 在今年2月15日加入了 OpenAI，项目随即转交给基金会运营。Sam Altman 公开表示，OpenClaw 将继续作为独立的开源项目存在。

换句话说，OpenClaw 现在处于一个微妙的状态——创始人走了，社区还在，但缺一个有实力的"靠山"。

NVIDIA 就是在这个时间点切进来的。

---

## NemoClaw 到底是什么？

很多人第一反应是：NVIDIA 要做自己的 Agent 框架了？

不是。NemoClaw 不是 OpenClaw 的竞品，而是 OpenClaw 的**安全增强层**。

架构分三层，非常清晰：

**第一层：Nemotron 模型。** NVIDIA 自家的开源模型家族，默认搭配的是 `nemotron-3-super-120b-a12b`（后面会专门聊这个模型）。

**第二层：OpenShell 运行时。** 这是核心。Agent 所有操作都在隔离沙箱里执行，底层用 K3s（轻量版 Kubernetes）跑在 Docker 容器里。支持 YAML 声明式策略，不重启即可热加载。凭证不落盘，通过环境变量注入。甚至内置了一个实时终端 UI，长得像 k9s。

不止 OpenClaw，它还支持 Claude Code、OpenCode、Codex 等主流 Agent。

**第三层：NVIDIA Agent Toolkit。** 一键安装分发层，把 OpenClaw + Nemotron + OpenShell 打包成开箱即用的整体。

整个项目 Apache 2.0 开源，GitHub 上已经放出来了（NVIDIA/NemoClaw 和 NVIDIA/OpenShell）。

---

## 四层安全防护，这才是重点

Agent 安全是今年最热的话题之一。当 AI Agent 拥有执行代码、调用 API、读写文件的能力后，"安全"就不再是锦上添花，而是刚需。

NemoClaw 的 OpenShell 设计了四层防护：

**网络层：** 默认阻止所有出站连接。没错，默认全封。需要什么放行什么，精确到 HTTP 方法和路径级别，运行时可以热更新。

**文件系统层：** Agent 只能读写指定路径，创建沙箱时就锁死。想偷偷读个 `/etc/passwd`？门都没有。

**进程层：** 阻止提权和危险系统调用，底层用的是 Linux 的 Landlock + seccomp + netns 三件套。这是内核级别的隔离，不是应用层的花架子。

**推理层：** 所有 API 调用被劫持到受控后端。Agent 以为自己在调外部 API，实际上中间有一层代理在监控和过滤。

四层叠在一起，思路很明确：**不信任 Agent 的任何行为，一切权限都需要显式授予。**

这和传统软件安全的"最小权限原则"一脉相承，但落地到 AI Agent 场景里，确实是目前我见过最完整的方案之一。

---

## Nemotron 3 Super：免费的才是最贵的

聊完安全，得说说模型本身。

Nemotron 3 Super 的参数量是 120B，但因为采用了 MoE（混合专家）架构，每次推理只激活 12.7B。底层架构叫 NemotronH，是 Mamba 和 Transformer 的混合体。

性能呢？几组数据：

- **PinchBench**（OpenClaw Agent 评测）：85.6%，同类开源模型第一，超过 Claude Opus 4.5 和 Kimi 2.5
- **SWE-Bench Verified**：60.47%，开源第一
- **RULER 1M**（长上下文）：91.75%，开源第一
- **DeepResearch Bench**：排名第一
- **API 推理速度**：442 tok/s，全平台第二快

Artificial Analysis Intelligence Index 给了 36 分。

但最炸裂的是价格——**完全免费**。通过 OpenRouter 或 build.nvidia.com 调用，零成本。

对比一下：GLM-5 Turbo 要 $1.2/$4 per MTok，Claude Opus 4.6 要 $5/$25 per MTok。Nemotron 3 Super 直接把价格打到了零。

本地部署的话需要 64GB 内存起步，Mac 用户可以跑 MLX 9-bit 量化版。

---

## NVIDIA 在下什么棋？

到这里，整个故事的商业逻辑已经很清楚了。

NVIDIA 没有做 OpenClaw 的竞品，没有 fork 一份自己搞，甚至没有把 OpenClaw 收编进自己的体系。它选择了一个更聪明的位置：**做安全层，做基础设施，做铠甲**。

这套打法，一点都不陌生。

**CUDA。**

CUDA 免费吗？免费。CUDA 赚钱吗？不直接赚。但 CUDA 锁定了整个 GPU 计算生态，所有人都在 CUDA 上写代码，所有人都得买 NVIDIA 的卡。

NemoClaw 的逻辑一模一样：

> 基础工具免费 → 开发者用起来 → 生态做大 → 企业需要安全合规 → 卖 GPU 和云服务。

安全合作方的名单也说明了问题：CrowdStrike、Cisco、Microsoft Security。这些都是企业安全领域的顶级玩家。NVIDIA 不是自己做安全咨询，而是拉着安全巨头一起建生态。

模型免费、安全框架免费、工具链免费——但你要跑起来，要么上 NVIDIA 的云，要么买 NVIDIA 的卡。

黄仁勋不说，但谁都明白。

---

## OpenClaw 的"管道化"风险

不过，对 OpenClaw 社区来说，这件事没那么简单。

一个开源项目被大厂包在里面当"内核"用，好处是曝光度和用户量暴增，坏处是**可能被管道化**——变成别人产品里的一个组件，失去独立品牌和话语权。

以前大家可能还会担心"被收编"的风险。但 Peter 已经去了 OpenAI，OpenClaw 在基金会手里，NVIDIA 要收编也没人可以谈。所以收编不太可能发生。

真正的风险是管道化。

当用户说"我用的是 NemoClaw"而不是"我用的是 OpenClaw"的时候，后者的品牌认知就在被稀释。当 NVIDIA 的安全层和工具链变成事实标准，OpenClaw 的替代成本就接近于零——换一个 Agent 框架进去，NemoClaw 照样跑。

这对 OpenClaw 社区来说，是一个需要认真对待的问题。

当然，反过来看，一个创始人已经离开、由基金会运营的开源项目，能被 NVIDIA 选中做底层，本身也是一种认可。至少在当下，这比被遗忘强得多。

---

## 还有哪些要注意的？

最后说几个现实问题。

NemoClaw 目前是 **Alpha 阶段**，NVIDIA 自己都说"expect rough edges"。翻译成人话就是：会有 bug，会有坑，生产环境别急着上。

**只支持 Linux。** Mac 和 Windows 用户暂时别想了。考虑到底层是 K3s + Docker + Landlock + seccomp 这一套 Linux 内核安全机制，短期内跨平台基本不现实。

对于想尝鲜的开发者，建议开个 Linux 虚拟机或者云实例试试。对于企业用户，等到 Beta 再评估不迟。

---

## 写在最后

GTC 2026 上有很多大新闻，但 NemoClaw 可能是最被低估的一个。

它表面上是一个安全工具，背后是 NVIDIA 对 AI Agent 生态的一次战略卡位。不做 Agent，做 Agent 的安全层；不做应用，做应用的基础设施。免费开放，生态共建，最后靠算力收割。

这是 CUDA 的剧本，在 Agent 时代的重演。

而对于整个行业来说，NemoClaw 释放的信号也很清楚：**AI Agent 的安全问题，已经从"要不要做"进入了"怎么做"的阶段。** 当 NVIDIA 亲自下场做安全框架的时候，说明这件事已经不是学术讨论，而是工程现实。

至于 OpenClaw，它正站在一个十字路口：被大厂赋能的同时，也在被大厂定义。

这条路往哪走，基金会和社区需要想清楚。

---

*NemoClaw 和 OpenShell 均已在 GitHub 开源（Apache 2.0），感兴趣的读者可以搜索 NVIDIA/NemoClaw 和 NVIDIA/OpenShell 查看。Nemotron 3 Super 模型可通过 OpenRouter 或 build.nvidia.com 免费使用。*
