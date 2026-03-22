# Designing AI agents to resist prompt injection

**来源**: 网页 | OpenAI

**类型**: webpage

**入库时间**: 2026-03-12T19:53:33.902113

---

Designing AI agents to resist prompt injection

作者：Thomas Shadwell, Adrian Spänu
发布时间：2026年3月11日
来源：OpenAI Security

核心观点：

AI agents are increasingly able to browse the web, retrieve information, and take actions on a user's behalf. Those capabilities are useful, but they also create new ways for attackers to try to manipulate the system.

These attacks are often described as prompt injection: instructions placed in external content in an attempt to make the model do something the user did not ask for. In our experience, the most effective real-world versions of these attacks increasingly resemble social engineering more than simple prompt overrides.

That shift matters. If the problem is not just identifying a malicious string, but resisting misleading or manipulative content in context, then defending against it cannot rely only on filtering inputs. It also requires designing the system so that the impact of manipulation is constrained, even if some attacks succeed.

Prompt injection is evolving

Early prompt injection type attacks could be as simple as editing a Wikipedia article to include direct instructions to AI agents visiting it. As models have become smarter, they have also become less vulnerable to this kind of suggestion and we have observed that prompt injection-style attacks have responded by including elements of social engineering.

Email example of prompt injection:

A 2025 example of a prompt injection attack on ChatGPT reported to OpenAI by external security researchers. In testing, it worked 50% of the time with the user prompt deep research on emails from today.

Within the wider AI security ecosystem it has become common to recommend techniques such as AI firewalling in which an intermediary between the AI agent and the outside world attempts to classify inputs into malicious prompt injection and regular inputs—but these fully developed attacks are not usually caught by such systems.

Social engineering and AI agents

As real-world prompt injection attacks developed in complexity, we found that the most effective offensive techniques leveraged social engineering tactics. Rather than treating these prompt injection attacks with social engineering as a separate or entirely new class of problem, we began to view it through the same lens used to manage social engineering risk on human beings in other domains.

In this way, we can imagine the AI agent as existing in a similar three-actor system as a customer service agent. The agent wants to act on behalf of their employer, but they are continuously exposed to external input that may attempt to mislead them. The customer support agent, human or AI, must have limitations placed on their capabilities to limit the downside risk inherent to existing in such a malicious environment.

This mindset has informed a robust suite of countermeasures we have deployed that uphold the security expectations of our users.

How this informs our defenses in ChatGPT

In ChatGPT, we combine this social engineering model with more traditional security engineering approaches such as source-sink analysis.

In that framing, an attacker needs both a source, or a way to influence the system, and a sink, or a capability that becomes dangerous in the wrong context. For agentic systems, that often means combining untrusted external content with an action such as transmitting information to a third party, following a link, or interacting with a tool.

Our goal is to preserve a core security expectation for users: potentially dangerous actions, or transmissions of potentially sensitive information, should not happen silently or without appropriate safeguards.

Attacks we see developed against ChatGPT most often consist of attempting to convince the assistant it should take some secret information from a conversation and transmit it to a malicious third-party. In most of the cases we are aware of, these attacks fail because our safety training causes the agent to refuse. For those cases in which the agent is convinced, we have developed a mitigation strategy called Safe Url which is designed to detect when information the assistant learned in the conversation would be transmitted to a third-party.

This same mechanism applies to navigations and bookmarks in Atlas, and searches and navigations in Deep Research. ChatGPT Canvas and ChatGPT Apps take a similar approach, allowing the agent to create and use functional applications—these run in a sandbox that is able to detect unexpected communications and ask the user for their consent.

Looking ahead

Safe interaction with the adversarial outside world is necessary for fully autonomous agents. When integrating an AI model with an application system, we recommend asking what controls a human agent should have in a similar situation and implementing those. We expect that a maximally intelligent AI model will be able to resist social engineering better than a human agent, but this is not always feasible or cost-effective depending on the application.

We continue to explore the implications of social engineering against AI models and defenses against it and incorporate our findings both into our application security architectures and the training we put our AI models through.