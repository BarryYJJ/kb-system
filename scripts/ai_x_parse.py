#!/usr/bin/env python3
"""
X AI新闻 Browser抓取 - 解析器
功能：从 browser snapshot 解析推文，过滤AI相关内容，输出飞书格式
"""

import sys
import os
import re
import json
import argparse
import hashlib
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta

CACHE_FILE = os.path.expanduser("~/.openclaw/workspace/scripts/.ai_x_seen.json")

# AI关键词
AI_KEYWORDS = [
    "ai", "llm", "gpt", "model", "agent", "neural", "openai", "anthropic",
    "nvidia", "grok", "chatgpt", "reasoning", "agi", "xai", "tesla_ai",
    "deepmind", "meta", "mistral", "claude", "perplexity", "character.ai",
    "transformer", "diffusion", "gpt-", "sora", "dalle", "runway",
    "sam altman", "dario amodei", "jensen huang", "karpathy", "ilyasut",
    "demis has", "jeff dean", "jim fan", "chris dixon", "a16z",
    "robot", "autonomous", "self-driving", "fsd", "optimus", "tesla robot",
    "foundation model", "multimodal", "token", "inference", "training",
    "benchmark", "score", "gpt4", "gpt5", "o1", "o3", "gemini",
]

def translate_to_chinese(text: str) -> str:
    if not text or len(text) < 5:
        return text
    try:
        url = "https://api.mymemory.translated.net/get"
        params = urllib.parse.urlencode({"q": text[:500], "langpair": "en|zh-CN"})
        req = urllib.request.Request(f"{url}?{params}")
        req.add_header("User-Agent", "Mozilla/5.0")
        with urllib.request.urlopen(req, timeout=5) as response:
            result = json.loads(response.read().decode())
            if result.get("responseStatus") == 200:
                return result.get("responseData", {}).get("translatedText", text)
    except Exception:
        pass
    return text

def parse_tweets(text: str) -> list:
    """从 snapshot 文本解析推文"""
    tweets = []
    lines = text.split('\n')
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # 格式1: [Name @handle · time]
        # 例: [Elon Musk @elonmusk · 57m]
        m = re.match(r'\[([^@]+)@(\w+)\s*·\s*(\d+[hm]|\d+h)\]', line)
        if m:
            name = m.group(1).strip()
            handle = m.group(2)
            time_str = m.group(3)
            
            # 收集内容（后续几行直到热度行）
            content_parts = []
            i += 1
            while i < len(lines):
                next_line = lines[i].strip()
                # 热度行: 256 replies, 92 reposts, 1668 likes, 25K views
                if re.match(r'\d+[KkMm]?\s*(replies?|likes?|reposts?|views?)\b', next_line, re.I):
                    engagement = next_line
                    break
                elif next_line.startswith('[') or not next_line:
                    break
                else:
                    content_parts.append(next_line)
                i += 1
            
            content = ' '.join(content_parts).strip()
            if content:
                tweets.append({
                    "account": handle,
                    "time": time_str,
                    "content": content,
                    "engagement": engagement if 'engagement' in dir() else ""
                })
                continue
        
        # 格式2: @username · time · content
        m2 = re.match(r'(@\w+)\s*·\s*(\d+[hm]|\d+h)\s*·\s*(.+)$', line)
        if m2:
            tweets.append({
                "account": m2.group(1).lstrip('@'),
                "time": m2.group(2),
                "content": m2.group(3),
                "engagement": ""
            })
            i += 1
            continue
        
        # 格式3: article "Name @handle time content"
        m3 = re.search(r'article\s+"[^"]+"\s+(@\w+)\s+(\d+\s*(?:hours?|minutes?|days?)\s*ago|Mar\s+\d+)\s+(.+)$', line)
        if m3:
            rest = m3.group(3)
            # 提取热度
            eng_match = re.search(r'(\d+[Kk]?\s*likes?)', rest)
            engagement = eng_match.group(1) if eng_match else ""
            # 去掉热度
            content = re.sub(r'\d+[Kk]?\s*likes?[, ]*\d*[Kk]?\s*views?\s*$', '', rest).strip()
            tweets.append({
                "account": m3.group(1).lstrip('@'),
                "time": m3.group(2),
                "content": content,
                "engagement": engagement
            })
            i += 1
            continue
        
        i += 1
    
    return tweets

def is_ai_related(content: str) -> bool:
    if not content:
        return False
    content_lower = content.lower()
    if len(content) < 30:
        return True
    return any(kw in content_lower for kw in AI_KEYWORDS)

def parse_engagement(eng: str) -> float:
    if not eng:
        return 0
    # 只提取数字+KM单位
    eng = eng.lower()
    # 优先匹配 views 数量
    m = re.search(r'(\d+\.?\d*)([km])?\s*views?', eng)
    if m:
        num = float(m.group(1))
        if m.group(2) == 'k':
            num *= 1000
        elif m.group(2) == 'm':
            num *= 1000000
        return num
    # 备选：匹配 likes
    m = re.search(r'(\d+\.?\d*)([km])?\s*likes?', eng)
    if m:
        num = float(m.group(1))
        if m.group(2) == 'k':
            num *= 1000
        elif m.group(2) == 'm':
            num *= 1000000
        return num
    return 0

def tweet_id(t: dict) -> str:
    return hashlib.md5((t["account"] + t["content"][:50]).encode()).hexdigest()[:12]

def load_cache() -> set:
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE) as f:
                data = json.load(f)
            cutoff = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
            return {k: v for k, v in data.items() if v >= cutoff}.keys()
        except:
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
        except:
            pass
    for sid in seen_ids:
        existing[sid] = now
    cutoff = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    fresh = {k: v for k, v in existing.items() if v >= cutoff}
    with open(CACHE_FILE, "w") as f:
        json.dump(fresh, f)

def format_output(tweets: list, seen_ids: set) -> str:
    now = datetime.now(timezone(timedelta(hours=8)))
    header = f"🐦 X AI动态 {now.strftime('%m/%d %H:%M')}"
    
    tweets = [t for t in tweets if is_ai_related(t.get("content", ""))]
    tweets.sort(key=lambda t: parse_engagement(t.get("engagement", "")), reverse=True)
    
    if not tweets:
        return header + "\n\n暂无AI相关动态"
    
    lines = [header, ""]
    new_ids = set()
    
    for i, t in enumerate(tweets[:8], 1):
        tid = tweet_id(t)
        if tid in seen_ids:
            continue
        new_ids.add(tid)
        
        content = translate_to_chinese(t.get("content", ""))
        if len(content) > 150:
            content = content[:147] + "..."
        
        lines.append(f"{i}. @{t['account']} [{t['time']}]")
        lines.append(f"   {content}")
        if t.get("engagement"):
            lines.append(f"   🔥 {t['engagement']}")
        lines.append("")
    
    if not new_ids:
        return header + "\n\n暂无新动态（已推送过的内容）"
    
    if new_ids:
        save_cache(seen_ids | new_ids)
    
    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(description="X AI新闻解析")
    parser.add_argument("--input", "-i", default=None, help="输入文件路径")
    args = parser.parse_args()
    
    if args.input:
        if not os.path.exists(args.input):
            print(f"错误: 文件不存在 {args.input}")
            sys.exit(1)
        with open(args.input) as f:
            text = f.read()
    else:
        text = sys.stdin.read()
    
    if not text.strip():
        print("错误: 没有输入内容")
        sys.exit(1)
    
    seen_ids = load_cache()
    tweets = parse_tweets(text)
    output = format_output(tweets, seen_ids)
    print(output)

if __name__ == "__main__":
    main()
