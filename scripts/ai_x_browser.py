#!/usr/bin/env python3
"""
X AI新闻 Browser抓取 - 方案A&B整合版
功能：
- 方案A：改进的 Cron payload（内联处理逻辑）
- 方案B：模块化处理（browser抓 → 文件 → Python解析）

用法：
  python3 ai_x_browser.py --mode=a --accounts sama,elonmusk
  python3 ai_x_browser.py --mode=b --accounts sama,elonmusk
  python3 ai_x_browser.py --test  # 测试解析
"""

import os
import re
import json
import hashlib
import argparse
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── 配置 ──────────────────────────────────────────────────────────────────────
CACHE_FILE = os.path.expanduser("~/.openclaw/workspace/scripts/.ai_x_seen.json")
DATA_FILE = "/tmp/x_feed_raw.json"

ACCOUNTS = {
    "sama": "Sam Altman (OpenAI)",
    "elonmusk": "Elon Musk",
    "AndrewYNg": "Andrew Ng",
    "DrJimFan": "Jim Fan (NVIDIA)",
    "cdixon": "Chris Dixon (a16z)",
    "karpathy": "Andrej Karpathy",
    "ylecun": "Yann LeCun",
}

# ── 工具函数 ──────────────────────────────────────────────────────────────────
def url_to_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:12]

def load_cache() -> set:
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE) as f:
                data = json.load(f)
            cutoff = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
            fresh = {k: v for k, v in data.items() if v >= cutoff}
            return set(fresh.keys())
        except Exception:
            pass
    return set()

def save_cache(seen_ids: set):
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    existing = {}
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE) as f:
                existing = json.load(f)
        except Exception:
            pass
    for sid in seen_ids:
        existing[sid] = now
    cutoff = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    fresh = {k: v for k, v in existing.items() if v >= cutoff}
    with open(CACHE_FILE, "w") as f:
        json.dump(fresh, f)

# ── 解析函数 ──────────────────────────────────────────────────────────────────
def parse_tweet_text(text: str) -> list:
    """从 snapshot 文本中解析推文"""
    tweets = []
    
    # 移除多余空白
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    
    # 模式1: @username · 时间 · 内容
    pattern1 = r'@(\w+)\s*·\s*(\d+[hms]?)\s*·\s*(.+?)(?:\s*·\s*([\d.K]+))?$'
    
    # 模式2: username (带括号时间)
    pattern2 = r'@?(\w+)\s*\(?(\d+[hms])\)?[:\s]+(.+)$'
    
    current_tweet = {}
    
    for line in lines:
        # 跳过无关行
        if any(skip in line.lower() for skip in ['reply', 'repost', 'share', 'bookmark', 'more']):
            continue
        
        m1 = re.match(pattern1, line)
        m2 = re.match(pattern2, line)
        
        if m1:
            if current_tweet:
                tweets.append(current_tweet)
            current_tweet = {
                'account': m1.group(1),
                'time': m1.group(2),
                'content': m1.group(3).strip(),
                'engagement': m1.group(4) or '',
            }
        elif m2:
            if current_tweet:
                tweets.append(current_tweet)
            current_tweet = {
                'account': m2.group(1),
                'time': m2.group(2),
                'content': m2.group(3).strip(),
                'engagement': '',
            }
        elif current_tweet and 'content' in current_tweet:
            # 多行内容拼接
            current_tweet['content'] += ' ' + line
    
    if current_tweet:
        tweets.append(current_tweet)
    
    return tweets

def filter_ai_tweets(tweets: list) -> list:
    """过滤AI相关内容"""
    ai_keywords = [
        'ai', 'llm', 'gpt', 'model', 'agent', 'neural', 'training',
        'inference', 'openai', 'anthropic', 'google', 'meta',
        'intelligence', 'reasoning', 'benchmark', 'research',
        'agi', 'robot', 'autonomous', 'grok', 'chatgpt', 'claude',
        'gemini', 'deepmind', 'nvidia', 'chip', 'compute',
    ]
    
    filtered = []
    for t in tweets:
        content = t.get('content', '').lower()
        # 不过滤太短的内容（可能是重要短讯）
        if len(content) < 20:
            filtered.append(t)
        elif any(kw in content for kw in ai_keywords):
            filtered.append(t)
    
    return filtered

def parse_engagement(eng: str) -> float:
    """解析热度数值"""
    if not eng:
        return 0
    eng = eng.upper().replace(',', '')
    if 'K' in eng:
        return float(eng.replace('K', '')) * 1000
    if 'M' in eng:
        return float(eng.replace('M', '')) * 1000000
    try:
        return float(eng)
    except:
        return 0

# ── 方案A: 生成改进的 Cron payload ──────────────────────────────────────────
def generate_cron_payload_a(accounts: list) -> str:
    """生成方案A的 Cron payload（内联处理）"""
    account_str = ",".join(accounts)
    
    payload = f"""推送X AI新闻（方案A）

**重要：在消息开头添加当前日期和时间，格式如：2026-03-10 20:06**

用 browser 工具打开 X 搜索页面：
```
https://x.com/search?q=from:{accounts[0]}+OR+from:{accounts[1]}+AI&f=live
```

等待页面加载完成（等待3秒）：
用 browser action=act 发送 keys=["PageDown"] 滚动页面，重复2次

用 snapshot 抓取页面内容，然后解析：

1. **提取推文**：用正则匹配 @username · 时间 · 内容 格式
2. **过滤AI内容**：保留包含AI关键词的推文
3. **排序**：按热度（点赞/观看数）倒序
4. **去重**：与缓存对比（2天）
5. **截断**：内容超过150字则截断

**输出格式**：
```
🐦 X AI动态 03/10 20:06

1. @sama [2h]
   内容摘要...
   ❤️ 12.5K

2. @elonmusk [4h]
   内容摘要...
   ❤️ 45K
...
```

**关注账号**：{account_str}

**AI关键词**：ai, llm, gpt, model, agent, openai, anthropic, nvidia, grok, chatgpt

目标群：oc_033200a2287a2b7fe4f952513242b665

更新缓存文件：~/.openclaw/workspace/scripts/.ai_x_seen.json
"""
    return payload

# ── 方案B: 生成独立处理脚本 ─────────────────────────────────────────────────
def generate_script_b():
    """生成方案B的独立处理脚本"""
    script = '''#!/usr/bin/env python3
"""
X AI新闻 Browser抓取 - 方案B（模块化处理）
用法：
1. browser 抓取页面 → 保存到 /tmp/x_feed_raw.txt
2. 运行此脚本解析并输出

示例 Cron payload:
  用 browser 打开 X 搜索页面...
  用 snapshot 抓取内容保存
  然后运行: python3 ~/.openclaw/workspace/scripts/ai_x_parse.py --input /tmp/x_feed_raw.txt
"""

import sys
import os
import re
import json
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path

CACHE_FILE = os.path.expanduser("~/.openclaw/workspace/scripts/.ai_x_seen.json")

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE) as f:
                data = json.load(f)
            cutoff = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
            fresh = {k: v for k, v in data.items() if v >= cutoff}
            return set(fresh.keys())
        except:
            pass
    return set()

def save_cache(seen_ids):
    now = datetime.now(timezone.utc).isoformat()
    existing = {}
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE) as f:
                existing = json.load(f)
        except:
            pass
    for sid in seen_ids:
        existing[sid] = now
    cutoff = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    fresh = {k: v for k, v in existing.items() if v >= cutoff}
    with open(CACHE_FILE, "w") as f:
        json.dump(fresh, f)

def parse_tweets(text):
    tweets = []
    lines = [l.strip() for l in text.split("\\n") if l.strip()]
    
    pattern1 = r'@(\\w+)\\s*·\\s*(\\d+[hms]?)\\s*·\\s*(.+?)(?:\\s*·\\s*([\\d.K]+))?$'
    pattern2 = r'@?(\\w+)\\s*\\(?(\\d+[hms])\\)?[:\\s]+(.+)$'
    
    current = {}
    for line in lines:
        if any(skip in line.lower() for skip in ["reply", "repost", "share", "bookmark", "more"]):
            continue
        m1 = re.match(pattern1, line)
        m2 = re.match(pattern2, line)
        if m1:
            if current: tweets.append(current)
            current = {"account": m1.group(1), "time": m1.group(2), "content": m1.group(3).strip(), "engagement": m1.group(4) or ""}
        elif m2:
            if current: tweets.append(current)
            current = {"account": m2.group(1), "time": m2.group(2), "content": m2.group(3).strip(), "engagement": ""}
        elif current and "content" in current:
            current["content"] += " " + line
    if current: tweets.append(current)
    return tweets

def filter_ai(tweets):
    keywords = ["ai", "llm", "gpt", "model", "agent", "neural", "openai", "anthropic", "nvidia", "grok", "chatgpt", "reasoning", "agi"]
    filtered = []
    for t in tweets:
        content = t.get("content", "").lower()
        if len(content) < 20 or any(kw in content for kw in keywords):
            filtered.append(t)
    return filtered

def format_output(tweets, seen_ids):
    now = datetime.now(timezone(timedelta(hours=8)))
    lines = [f"🐦 X AI动态 {now.strftime('%m/%d %H:%M')}", ""]
    
    # 过滤 + 排序
    tweets = filter_ai(tweets)
    tweets.sort(key=lambda t: parse_engagement(t.get("engagement", "")), reverse=True)
    
    if not tweets:
        return "\\n".join(lines) + "\\n暂无AI相关动态"
    
    new_ids = set()
    for i, t in enumerate(tweets[:8], 1):
        tweet_id = hashlib.md5((t["account"] + t["content"][:50]).encode()).hexdigest()[:12]
        if tweet_id in seen_ids:
            continue
        new_ids.add(tweet_id)
        
        content = t["content"]
        if len(content) > 150:
            content = content[:147] + "..."
        
        lines.append(f"{i}. @{t['account']} [{t['time']}]")
        lines.append(f"   {content}")
        if t.get("engagement"):
            lines.append(f"   ❤️ {t['engagement']}")
        lines.append("")
    
    if new_ids:
        save_cache(seen_ids | new_ids)
    
    return "\\n".join(lines)

def parse_engagement(eng):
    if not eng: return 0
    eng = eng.upper().replace(",", "")
    if "K" in eng: return float(eng.replace("K", "")) * 1000
    if "M" in eng: return float(eng.replace("M", "")) * 1000000
    try: return float(eng)
    except: return 0

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", "-i", default="/tmp/x_feed_raw.txt")
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"错误: 文件不存在 {args.input}")
        print("请先用 browser 抓取页面内容保存到此文件")
        sys.exit(1)
    
    with open(args.input) as f:
        text = f.read()
    
    seen_ids = load_cache()
    tweets = parse_tweets(text)
    print(format_output(tweets, seen_ids))

if __name__ == "__main__":
    main()
'''
    return script

def parse_engagement(eng: str) -> float:
    if not eng:
        return 0
    eng = eng.upper().replace(',', '')
    if 'K' in eng:
        return float(eng.replace('K', '')) * 1000
    if 'M' in eng:
        return float(eng.replace('M', '')) * 1000000
    try:
        return float(eng)
    except:
        return 0

# ── 主逻辑 ────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="X AI新闻 - 方案A&B")
    parser.add_argument("--mode", choices=["a", "b", "test", "compare"], default="compare")
    parser.add_argument("--accounts", type=str, default="sama,elonmusk,AndrewYNg,DrJimFan,cdixon")
    args = parser.parse_args()
    
    accounts = args.accounts.split(",")
    
    if args.mode == "a":
        print("=" * 60)
        print("方案A: 改进的 Cron payload（内联处理）")
        print("=" * 60)
        print(generate_cron_payload_a(accounts))
        
    elif args.mode == "b":
        print("=" * 60)
        print("方案B: 独立解析脚本")
        print("=" * 60)
        script = generate_script_b()
        script_path = Path(os.path.expanduser("~/.openclaw/workspace/scripts/ai_x_parse.py"))
        script_path.write_text(script)
        print(f"已生成脚本: {script_path}")
        print("\n使用方式：")
        print("1. browser 抓取页面 → 保存到 /tmp/x_feed_raw.txt")
        print("2. 运行: python3 ai_x_parse.py --input /tmp/x_feed_raw.txt")
        
    elif args.mode == "test":
        # 测试解析
        sample = """
@elonmusk · 2h
Grok 3 is now live. Biggest compute cluster ever trained. 🚀
45K
@sama · 4h
We just released GPT-4.5. It's our best model yet for conversation.
12.5K
@AndrewYNg · 6h
New AI agents course is now live. Link in bio. #AI #learning
8.2K
@DrJimFan · 1h
NVIDIA DGX Cloud is now available. AI factories are here.
6.7K
"""
        tweets = parse_tweet_text(sample)
        tweets = filter_ai_tweets(tweets)
        tweets.sort(key=lambda t: parse_engagement(t.get('engagement', '')), reverse=True)
        
        now = datetime.now(timezone(timedelta(hours=8)))
        print(f"🐦 X AI动态 {now.strftime('%m/%d %H:%M')}")
        print()
        for i, t in enumerate(tweets[:5], 1):
            content = t['content']
            if len(content) > 150:
                content = content[:147] + "..."
            print(f"{i}. @{t['account']} [{t['time']}]")
            print(f"   {content}")
            if t.get('engagement'):
                print(f"   ❤️ {t['engagement']}")
            print()
            
    else:  # compare
        print("=" * 60)
        print("方案对比")
        print("=" * 60)
        print("""
┌─────────────┬────────────────────────────────────────────────────────┐
│  方案A      │ 优点：简单，一个 Cron 任务搞定                           │
│ (内联处理)  │ 缺点：解析逻辑难以调试，每次都要改 Cron payload          │
├─────────────┼────────────────────────────────────────────────────────┤
│  方案B      │ 优点：模块化，便于调试优化；解析逻辑独立，易维护        │
│ (模块化)    │ 缺点：多一步文件读写                                    │
└─────────────┴────────────────────────────────────────────────────────┘

推荐：方案B（模块化）
理由：
1. 解析逻辑可以单独测试和优化
2. 出问题容易定位
3. 复用性好（同一个解析脚本可用于不同数据源）
""")
        
        # 生成方案B脚本
        script = generate_script_b()
        script_path = Path(os.path.expanduser("~/.openclaw/workspace/scripts/ai_x_parse.py"))
        script_path.write_text(script)
        print(f"✅ 已生成方案B脚本: {script_path}")

if __name__ == "__main__":
    main()
