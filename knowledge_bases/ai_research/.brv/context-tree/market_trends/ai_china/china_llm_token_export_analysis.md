---
title: China LLM Token Export Analysis
tags: []
related: [market_trends/ai_china/ubs_china_ai_expert_call_key_takeaways.md]
keywords: []
importance: 50
recency: 1
maturity: draft
createdAt: '2026-03-09T05:57:14.983Z'
updatedAt: '2026-03-09T05:57:14.983Z'
---
## Raw Concept
**Task:**
Analyze the surge and strategy of Chinese LLM token export

**Changes:**
- Significant market share growth on OpenRouter (2% to 39%)
- Shift from overseas to domestic inference infrastructure for cost efficiency
- Increased domestic compute demand starting from December 2025

**Flow:**
Domestic inference (5090 cards, cheap electricity) -> Low-cost API (1/6 price) -> Global token distribution (OpenRouter, etc.)

**Timestamp:** 2026-03-09

**Author:** Little Bear Team (小熊团队)

## Narrative
### Structure
The strategy relies on domestic high-performance GPUs (5090), low electricity costs, and distilled data to offer aggressive pricing.

### Dependencies
Relies on domestic cloud providers like Volcengine (ByteDance) and Alibaba Cloud. New subsea cables in Southeast Asia are expected to support future bandwidth needs.

### Highlights
Chinese tokens now account for 39% of OpenRouter traffic. The competitive edge is primarily cost (1/6 of global average) rather than raw benchmark performance.

### Rules
Rule 1: Marketing/Front-end infrastructure is overseas, but inference is domestic.
Rule 2: Exported data is primarily coding-related to avoid sensitivity issues.

### Examples
OpenRouter market share jump from 2% to 39% within roughly 15 months.

## Facts
- **api_pricing**: China's LLM API prices are approximately 1/6th of overseas prices. [project]
- **token_market_share**: Chinese model token share on OpenRouter grew from 2% in late 2024 to 39% recently. [project]
- **compute_location**: Inference compute for exported tokens is almost entirely based in China using local power and 5090 GPUs. [environment]
- **inference_latency**: Typical inference response latency is around 100 seconds. [project]
