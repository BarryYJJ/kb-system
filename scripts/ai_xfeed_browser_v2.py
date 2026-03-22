#!/usr/bin/env python3
"""
X AI新闻 Browser Snapshot 解析器 v2 (方案B - Python 负责解析)

用法:
  1. agent 用 browser 工具打开 X 页面，取 snapshot，把文本写到文件
  2. 运行此脚本解析并输出飞书格式

  直接从文件:
    python3 ai_xfeed_browser_v2.py /tmp/x_snapshot.txt [--session 早间]

  从 stdin:
    cat /tmp/x_snapshot.txt | python3 ai_xfeed_browser_v2.py

  调试模式（输出 JSON）:
    python3 ai_xfeed_browser_v2.py /tmp/x_snapshot.txt --json

监控账号:
  sama (Sam Altman), elonmusk (Elon Musk), AndrewYNg (Andrew Ng),
  DrJimFan (Jim Fan/NVIDIA), cdixon (Chris Dixon/a16z),
  ylecun (Yann LeCun), karpathy (Andrej Karpathy), GaryMarcus, fchollet
"""

import sys
import re
import json
import argparse
from datetime import datetime, timezone, timedelta
from typing import Optional

# ── 监控账号（小写比较）────────────────────────────────────────────────────────
WATCHED_ACCOUNTS = {
    'sama', 'elonmusk', 'andrewng', 'drjimfan', 'cdixon',
    'ylecun', 'karpathy', 'garymarcus', 'fchollet',
    # 常见拼写变体
    'andrewyang', 'jimfan',
}

# Elon 限制最多出现1条
ELON_LIMIT = 1
# 总条数上限
MAX_TWEETS = 7

# ── 解析器 ────────────────────────────────────────────────────────────────────

def parse_x_snapshot(text: str) -> list:
    """
    解析 X (Twitter) 页面 snapshot 文本，提取推文列表。

    X 页面 snapshot 的典型格式（可能随版本变化）：

      @sama · 2h
      Sam Altman
      Tweet content here with #tags @mentions
      1,234 Reposts  5,678 Likes  2.3M Views

    策略：先用 @handle 作为分隔符切块，每块单独解析。
    """
    # 策略1：以 @handle 为锚点切分
    tweets = _parse_by_handle_anchors(text)

    # 策略2：备用 - 按时间戳模式切分
    if not tweets:
        tweets = _parse_by_time_anchors(text)

    # 去重（内容相同的）
    seen, unique = set(), []
    for t in tweets:
        key = t['content'][:60].lower().strip()
        if key and key not in seen:
            seen.add(key)
            unique.append(t)

    return unique


def _parse_by_handle_anchors(text: str) -> list:
    """用 @handle 标记切分文本，逐块解析推文。"""
    # 匹配行首或行中的 @handle 位置
    splits = list(re.finditer(r'(?:^|\n)(@\w{1,50})\s*(?:·|\||\n)', text, re.MULTILINE))

    if not splits:
        # 也尝试没有分隔符的情况
        splits = list(re.finditer(r'(?:^|\n)(@\w{1,50})\b', text, re.MULTILINE))

    if not splits:
        return []

    tweets = []
    for i, m in enumerate(splits):
        start = m.start()
        end = splits[i + 1].start() if i + 1 < len(splits) else len(text)
        section = text[start:end].strip()
        t = _parse_section(section)
        if t:
            tweets.append(t)

    return tweets


def _parse_by_time_anchors(text: str) -> list:
    """备用：按时间戳（2h / Mar 8）定位推文块。"""
    tweets = []
    time_pattern = re.compile(r'\b(\d+[hm]s?)\b|\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d+\b')
    positions = [(m.start(), m.group()) for m in time_pattern.finditer(text)]

    for idx, (pos, ts) in enumerate(positions):
        end = positions[idx + 1][0] if idx + 1 < len(positions) else min(pos + 500, len(text))
        pre = text[max(0, pos - 300):pos]
        post = text[pos:end]

        handles = re.findall(r'@(\w+)', pre)
        if not handles:
            continue
        handle = handles[-1]

        if handle.lower() not in WATCHED_ACCOUNTS:
            continue

        content = _clean_content(post)
        if len(content) > 15:
            tweets.append({
                'handle': handle,
                'time': ts,
                'content': content[:300],
                'engagement': {},
                'score': 0,
            })

    return tweets


def _parse_section(section: str) -> Optional[dict]:
    """解析单个推文段落，提取结构化数据。"""
    lines = [l.strip() for l in section.split('\n') if l.strip()]
    if not lines:
        return None

    # 第一行应含 @handle
    handle_match = re.search(r'@(\w+)', lines[0])
    if not handle_match:
        return None
    handle = handle_match.group(1)

    if handle.lower() not in WATCHED_ACCOUNTS:
        return None

    # 提取时间戳
    time_str = _extract_time(lines)

    # 提取互动数据（likes / views / reposts）
    engagement = _extract_engagement('\n'.join(lines))

    # 提取正文内容（去掉 handle行、互动行、UI按钮行）
    content = _extract_content(lines)

    if not content or len(content) < 10:
        return None

    return {
        'handle': handle,
        'time': time_str,
        'content': content,
        'engagement': engagement,
        'score': _calc_score(engagement),
    }


def _extract_time(lines: list) -> str:
    """从行列表中提取时间戳。"""
    time_re = re.compile(
        r'\b(\d+[hm]s?|\d+\s*hours?|\d+\s*min(?:utes?)?)\b'
        r'|\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d+\b'
        r'|\b(\d{1,2}/\d{1,2})\b'
    )
    for line in lines[:6]:
        m = time_re.search(line)
        if m:
            return m.group(0)
    return ''


# 要跳过的行模式（UI 元素、互动按钮等）
_SKIP_PATTERNS = [
    re.compile(r'^@\w+'),                                          # @handle
    re.compile(r'^\d[\d,.]*(K|M|B)?\s+(Likes?|Views?|Reposts?|Replies?|Bookmarks?)', re.I),
    re.compile(r'^(Like|Repost|Reply|Bookmark|Share|More|Follow|Verified)\s*$', re.I),
    re.compile(r'^·\s*\d+[hms]'),                                  # · 2h
    re.compile(r'^\d+[hm]\s*$'),                                   # 2h alone
    re.compile(r'^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d+$'),
    re.compile(r'^(Trending|Show more|Load more|Following|Followers)\b', re.I),
    re.compile(r'^\d+\s*(Following|Followers)', re.I),
    re.compile(r'^X$'),                                            # X 品牌 logo 文字
]


def _extract_content(lines: list) -> str:
    """从行列表中提取正文内容，过滤掉 UI 元素。"""
    content_lines = []
    for i, line in enumerate(lines):
        if i == 0:  # 第一行是 @handle 所在行，跳过 handle 部分
            # 如果这行除了 handle 还有其他内容，保留
            cleaned = re.sub(r'@\w+\s*[·|]?\s*\d*[hm]?s?\s*', '', line).strip()
            if cleaned and len(cleaned) > 3 and not re.match(r'^\s*[·|]\s*$', cleaned):
                content_lines.append(cleaned)
            continue

        skip = False
        for pat in _SKIP_PATTERNS:
            if pat.match(line):
                skip = True
                break
        if not skip and line:
            content_lines.append(line)

    content = ' '.join(content_lines[:12])
    content = re.sub(r'\s{2,}', ' ', content).strip()
    return content


def _clean_content(text: str) -> str:
    """清理文本中的 UI 元素，得到正文。"""
    text = re.sub(r'[\d.,]+(K|M|B)?\s+(Likes?|Views?|Reposts?|Replies?)', '', text, flags=re.I)
    text = re.sub(r'\b(Like|Repost|Reply|Bookmark|Share|Follow)\b', '', text, flags=re.I)
    text = re.sub(r'\b\d+[hm]\b', '', text)
    text = re.sub(r'\s{2,}', ' ', text)
    return text.strip()


def _extract_engagement(text: str) -> dict:
    """从文本中提取互动数据。"""
    engagement = {}
    metrics = {
        'likes': re.compile(r'([\d,.]+(K|M|B)?)\s+Likes?', re.I),
        'views': re.compile(r'([\d,.]+(K|M|B)?)\s+Views?', re.I),
        'reposts': re.compile(r'([\d,.]+(K|M|B)?)\s+Reposts?', re.I),
        'replies': re.compile(r'([\d,.]+(K|M|B)?)\s+Repl(?:y|ies)', re.I),
        'bookmarks': re.compile(r'([\d,.]+(K|M|B)?)\s+Bookmarks?', re.I),
    }
    # 也匹配纯数字+单位在行首（如 "1,234" 后面跟换行然后 "Likes"）
    for key, pat in metrics.items():
        m = pat.search(text)
        if m:
            engagement[key] = m.group(1)

    # 也尝试逆序格式（数字在前，无空格）
    if not engagement:
        for key, label in [('likes', 'Likes?'), ('views', 'Views?'), ('reposts', 'Reposts?')]:
            m = re.search(r'([\d,.]+(K|M|B)?)\s*\n\s*' + label, text, re.I)
            if m:
                engagement[key] = m.group(1)

    return engagement


def _parse_num(s: str) -> float:
    """把 '4.5K' / '1,234' / '2M' 转成 float。"""
    s = s.replace(',', '').strip()
    if s.endswith('K'):
        return float(s[:-1]) * 1_000
    if s.endswith('M'):
        return float(s[:-1]) * 1_000_000
    if s.endswith('B'):
        return float(s[:-1]) * 1_000_000_000
    try:
        return float(s)
    except ValueError:
        return 0.0


def _calc_score(engagement: dict) -> float:
    """加权热度分：likes×5 + reposts×3 + views×0.01。"""
    likes = _parse_num(engagement.get('likes', '0'))
    views = _parse_num(engagement.get('views', '0'))
    reposts = _parse_num(engagement.get('reposts', '0'))
    replies = _parse_num(engagement.get('replies', '0'))
    return likes * 5 + reposts * 3 + views * 0.01 + replies * 2


# ── 格式化输出 ─────────────────────────────────────────────────────────────────

def format_output(tweets: list, session: str = '') -> str:
    """格式化推文列表为飞书发送格式。"""
    now = datetime.now(timezone(timedelta(hours=8)))
    session_label = f"【{session}】" if session else ""
    header = f"🐦 {session_label}X AI动态  {now.strftime('%m/%d %H:%M')}"

    if not tweets:
        return (
            header + "\n\n"
            "⚠️ 未能从 snapshot 提取到推文\n"
            "可能原因：\n"
            "  1. 页面未完全加载（需要等待后再 snapshot）\n"
            "  2. 未登录 X（需要先登录）\n"
            "  3. snapshot 格式与解析器不匹配\n"
        )

    # 排序：Elon 优先1条放最前，其他按热度降序
    elon = [t for t in tweets if t['handle'].lower() == 'elonmusk']
    others = sorted(
        [t for t in tweets if t['handle'].lower() != 'elonmusk'],
        key=lambda t: t['score'],
        reverse=True,
    )

    selected = others[:MAX_TWEETS - (1 if elon else 0)]
    if elon:
        selected = [elon[0]] + selected  # Elon 插到最前

    lines = [header, ""]

    for i, t in enumerate(selected, 1):
        time_tag = f" [{t['time']}]" if t['time'] else ""
        lines.append(f"{i}. @{t['handle']}{time_tag}")

        content = t['content']
        if len(content) > 200:
            content = content[:197] + "..."
        lines.append(f"   {content}")

        # 互动数据
        eng = t['engagement']
        parts = []
        if eng.get('likes'):
            parts.append(f"❤️ {eng['likes']}")
        if eng.get('views'):
            parts.append(f"👁 {eng['views']}")
        if eng.get('reposts'):
            parts.append(f"🔁 {eng['reposts']}")
        if parts:
            lines.append(f"   {' · '.join(parts)}")

        lines.append("")

    lines.append(f"—— 共 {len(selected)} 条 ——")
    return "\n".join(lines)


# ── 主函数 ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="X Browser Snapshot 解析器 v2",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("input_file", nargs='?', help="snapshot 文件路径（不传则读 stdin）")
    parser.add_argument("--session", default="", help="时段标签：早间/午间/收盘/晚间")
    parser.add_argument("--json", action="store_true", dest="output_json",
                        help="输出 JSON 格式（调试用）")
    parser.add_argument("--max", type=int, default=MAX_TWEETS, help=f"最多输出条数（默认 {MAX_TWEETS}）")
    args = parser.parse_args()

    if args.input_file:
        with open(args.input_file, 'r', encoding='utf-8', errors='replace') as f:
            raw = f.read()
    else:
        raw = sys.stdin.read()

    tweets = parse_x_snapshot(raw)

    if args.output_json:
        print(json.dumps(tweets, ensure_ascii=False, indent=2, default=str))
    else:
        global MAX_TWEETS
        MAX_TWEETS = args.max
        print(format_output(tweets, session=args.session))


if __name__ == "__main__":
    main()
