#!/usr/bin/env python3
"""
X AI新闻 - Browser抓取后处理脚本
用法：在获取到 browser snapshot 后，用此脚本解析输出
"""

import sys
import re
from datetime import datetime, timezone, timedelta

# 示例输入（从 browser snapshot 获取的原始文本）
SAMPLE_INPUT = """
# 从 snapshot 提取的推文数据示例
# 格式：账号名|时间|内容|热度
sama|2h|I just announced GPT-4.5 and GPT-5 roadmap. We're focusing on reasoning and safety.|12.5K
elonmusk|4h|Grok 3 is now live. Biggest compute cluster ever trained.|45K
AndrewYNg|6h|New course on AI agents just launched. Link in bio.|8.2K
DrJimFan|1h|NVIDIA DGX Cloud now available. AI factories are here.|6.7K
cdixon|3h|Software 3.0 is happening. AI-native apps are the future.|5.1K
"""

def parse_tweets(raw_text: str) -> list:
    """解析 browser snapshot 提取的推文数据"""
    tweets = []
    
    # 尝试多种模式匹配
    patterns = [
        # 模式1: @username · 时间 · 内容 · 热度
        r'@(\w+)\s*·\s*(\d+h|\d+m|\d+s)?\s*·\s*(.+?)\s*·\s*([\d.K]+)',
        # 模式2: username 时间
        r'^(\w+)\s+(\d+h|\d+m):\s+(.+)$',
    ]
    
    lines = raw_text.strip().split('\n')
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        
        # 简单解析：尝试提取关键信息
        # 格式: 账号|时间|内容|热度
        parts = line.split('|')
        if len(parts) >= 3:
            tweets.append({
                'account': parts[0].strip(),
                'time': parts[1].strip(),
                'content': parts[2].strip(),
                'engagement': parts[3].strip() if len(parts) > 3 else '',
            })
    
    return tweets

def format_output(tweets: list, session: str = "") -> str:
    """格式化输出"""
    now = datetime.now(timezone(timedelta(hours=8)))
    header = f"🐦 X AI动态 {now.strftime('%m/%d %H:%M')}"
    if session:
        header = f"🐦【{session}】X AI动态 {now.strftime('%m/%d %H:%M')}"
    
    if not tweets:
        return header + "\n\n暂无最新AI动态"
    
    lines = [header, ""]
    
    # 按热度排序
    def parse_engagement(t):
        eng = t.get('engagement', '0')
        if 'K' in eng:
            return float(eng.replace('K', '')) * 1000
        return 0
    
    tweets.sort(key=parse_engagement, reverse=True)
    
    for i, t in enumerate(tweets[:8], 1):  # 最多8条
        lines.append(f"{i}. @{t['account']} [{t['time']}]")
        # 内容太长则截断
        content = t['content']
        if len(content) > 150:
            content = content[:147] + "..."
        lines.append(f"   {content}")
        if t.get('engagement'):
            lines.append(f"   ❤️ {t['engagement']}")
        lines.append("")
    
    return "\n".join(lines)

def main():
    # 从 stdin 读取（或者传入文件）
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            raw = f.read()
    else:
        raw = sys.stdin.read()
    
    tweets = parse_tweets(raw)
    print(format_output(tweets))

if __name__ == "__main__":
    main()
