#!/usr/bin/env python3
"""
AI新闻 RSS 抓取脚本
来源：TechCrunch AI + The Decoder + AI News + MarkTechPost
特性：去重、过滤纯AI内容、输出飞书格式
用法：python3 ai_news_rss.py [--hours 24] [--max 8] [--session 早间|午间|晚间]
"""

import sys
import os
import json
import hashlib
import argparse
import re
from datetime import datetime, timezone, timedelta
from xml.etree import ElementTree as ET
import subprocess
import urllib.request
import urllib.parse

# ── 持仓配置 ─────────────────────────────────────────────────────────────────
# 读取核心覆盖标的和持仓2
def load_watchlists():
    """加载持仓列表"""
    tickers = set()
    
    # 核心覆盖标的
    try:
        sys.path.insert(0, os.path.expanduser("~/Desktop"))
        from stock_watchlist_data import WATCHLIST as WL1
        for s in WL1:
            t = s.get("ticker", "")
            if t:
                # 简化ticker
                ticker = t.replace(".HK", "").replace(".SH", "").replace(".SZ", "").replace("-WP", "").replace("-W", "")
                tickers.add(ticker.upper())
                # 添加中文名
                tickers.add(s.get("name", "").upper())
    except Exception as e:
        print(f"加载核心标的失败: {e}")
    
    # 持仓2
    try:
        sys.path.insert(0, os.path.expanduser("~/.openclaw/workspace/持仓2"))
        from 持仓2_data import WATCHLIST as WL2
        for s in WL2:
            if isinstance(s, tuple) and len(s) >= 2:
                ticker = str(s[0]).zfill(5)  # 港股5位
                tickers.add(ticker)
                tickers.add(s[1].upper())  # 证券简称
    except Exception as e:
        print(f"加载持仓2失败: {e}")
    
    return tickers

# 预加载持仓
WATCHLIST_TICKERS = load_watchlists()
print(f"已加载 {len(WATCHLIST_TICKERS)} 个持仓标的")

def check_relevant(ticker: str, title: str, desc: str) -> bool:
    """检查新闻是否与持仓相关"""
    text = f"{ticker} {title} {desc}".upper()
    for t in WATCHLIST_TICKERS:
        if t in text:
            return True
    return False

# ── 翻译函数 ─────────────────────────────────────────────────────────────────
def translate_to_chinese(text: str) -> str:
    """翻译英文到中文（使用免费翻译API）"""
    if not text or len(text) < 5:
        return text
    
    # 尝试用 MyMemory 免费 API
    try:
        url = "https://api.mymemory.translated.net/get"
        params = urllib.parse.urlencode({
            "q": text[:500],  # 限制长度
            "langpair": "en|zh-CN"
        })
        req = urllib.request.Request(f"{url}?{params}")
        req.add_header("User-Agent", "Mozilla/5.0")
        with urllib.request.urlopen(req, timeout=5) as response:
            result = json.loads(response.read().decode())
            if result.get("responseStatus") == 200:
                return result.get("responseData", {}).get("translatedText", text)
    except Exception:
        pass
    return text

# ── 配置 ──────────────────────────────────────────────────────────────────────
CACHE_FILE = os.path.expanduser("~/.openclaw/workspace/scripts/.ai_news_seen.json")

RSS_SOURCES = [
    {
        "name": "TechCrunch AI",
        "url": "https://techcrunch.com/feed/?cat=artificial-intelligence",
        "ai_only": True,   # 本身就是AI分类，无需过滤
    },
    {
        "name": "The Decoder",
        "url": "https://the-decoder.com/feed/",
        "ai_only": True,
    },
    {
        "name": "AI News",
        "url": "https://www.artificialintelligence-news.com/feed/",
        "ai_only": True,
    },
    {
        "name": "MarkTechPost",
        "url": "https://www.marktechpost.com/feed/",
        "ai_only": True,
    },
]

# AI关键词（用于过滤非AI源的文章）
AI_KEYWORDS = [
    "AI", "artificial intelligence", "machine learning", "deep learning",
    "LLM", "GPT", "Claude", "Gemini", "language model", "neural network",
    "OpenAI", "Anthropic", "Google DeepMind", "Meta AI", "xAI",
    "ChatGPT", "Copilot", "agent", "chatbot", "transformer",
    "diffusion", "generative", "foundation model", "AGI",
]

# ── 工具函数 ──────────────────────────────────────────────────────────────────
def url_to_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:12]

def load_cache() -> set:
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE) as f:
                data = json.load(f)
            # 只保留最近7天的记录
            cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
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
    # 更新已见列表
    for sid in seen_ids:
        existing[sid] = now
    # 只保留最近7天
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    fresh = {k: v for k, v in existing.items() if v >= cutoff}
    with open(CACHE_FILE, "w") as f:
        json.dump(fresh, f)

def fetch_url(url: str, timeout: int = 15) -> bytes:
    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", str(timeout),
             "-A", "Mozilla/5.0 (compatible; RSS reader)",
             url],
            capture_output=True,
            timeout=timeout + 5  # 总体超时
        )
        if result.returncode != 0:
            raise RuntimeError(f"curl failed: {result.stderr.decode()}")
        return result.stdout
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"curl timeout after {timeout}s")

def parse_rss(xml_bytes: bytes, source_name: str, ai_only: bool) -> list:
    """解析RSS XML，返回文章列表"""
    items = []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        return []

    # 处理命名空间
    ns = {
        'dc': 'http://purl.org/dc/elements/1.1/',
        'content': 'http://purl.org/rss/1.0/modules/content/',
    }

    channel = root.find('channel')
    if channel is None:
        return []

    for item in channel.findall('item'):
        title_el = item.find('title')
        link_el = item.find('link')
        desc_el = item.find('description')
        pub_el = item.find('pubDate')
        dc_creator = item.find('dc:creator', ns)

        title = title_el.text.strip() if title_el is not None and title_el.text else ""
        link = link_el.text.strip() if link_el is not None and link_el.text else ""
        desc = desc_el.text or "" if desc_el is not None else ""
        pub_date = pub_el.text.strip() if pub_el is not None and pub_el.text else ""
        author = dc_creator.text.strip() if dc_creator is not None and dc_creator.text else ""

        if not title or not link:
            continue

        # 清理 description 中的 HTML 标签
        desc_clean = re.sub(r'<[^>]+>', '', desc).strip()
        desc_clean = re.sub(r'\s+', ' ', desc_clean)
        desc_clean = desc_clean[:200] + "..." if len(desc_clean) > 200 else desc_clean

        # 解析发布时间
        pub_dt = None
        if pub_date:
            for fmt in [
                "%a, %d %b %Y %H:%M:%S %z",
                "%a, %d %b %Y %H:%M:%S %Z",
            ]:
                try:
                    pub_dt = datetime.strptime(pub_date, fmt)
                    if pub_dt.tzinfo is None:
                        pub_dt = pub_dt.replace(tzinfo=timezone.utc)
                    break
                except ValueError:
                    continue

        # AI关键词过滤（非纯AI源才需要）
        if not ai_only:
            combined = (title + " " + desc_clean).lower()
            if not any(kw.lower() in combined for kw in AI_KEYWORDS):
                continue

        items.append({
            "id": url_to_id(link),
            "title": title,
            "link": link,
            "desc": desc_clean,
            "pub_dt": pub_dt,
            "author": author,
            "source": source_name,
        })

    return items

def format_pub_time(pub_dt) -> str:
    if pub_dt is None:
        return ""
    # 转成 GMT+8
    cst = timezone(timedelta(hours=8))
    local = pub_dt.astimezone(cst)
    return local.strftime("%m/%d %H:%M")

# ── 主逻辑 ────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="AI新闻RSS抓取")
    parser.add_argument("--hours", type=int, default=24, help="抓取最近N小时的文章")
    parser.add_argument("--max", type=int, default=8, help="最多输出N条")
    parser.add_argument("--session", type=str, default="", help="推送场次（早间/午间/晚间）")
    parser.add_argument("--no-dedup", action="store_true", help="不去重（调试用）")
    args = parser.parse_args()

    cutoff = datetime.now(timezone.utc) - timedelta(hours=args.hours)
    seen_ids = set() if args.no_dedup else load_cache()
    all_articles = []
    source_errors = []

    for source in RSS_SOURCES:
        try:
            xml_bytes = fetch_url(source["url"])
            articles = parse_rss(xml_bytes, source["name"], source.get("ai_only", False))
            # 时间过滤：只保留 cutoff 之后的
            fresh = []
            for a in articles:
                if a["pub_dt"] is not None and a["pub_dt"] < cutoff:
                    continue
                if a["id"] in seen_ids:
                    continue
                fresh.append(a)
            all_articles.extend(fresh)
        except Exception as e:
            source_errors.append(f"{source['name']}: {e}")

    # 按发布时间倒序
    def sort_key(a):
        return a["pub_dt"] or datetime.min.replace(tzinfo=timezone.utc)

    all_articles.sort(key=sort_key, reverse=True)

    # 去重（相同标题）
    seen_titles = set()
    deduped = []
    for a in all_articles:
        title_key = re.sub(r'\s+', ' ', a["title"].lower().strip())
        if title_key not in seen_titles:
            seen_titles.add(title_key)
            deduped.append(a)

    # 截取 top N
    output = deduped[:args.max]

    # 更新缓存
    if not args.no_dedup:
        new_ids = seen_ids | {a["id"] for a in output}
        save_cache(new_ids)

    # ── 输出 ──────────────────────────────────────────────────────────────────
    now_cst = datetime.now(timezone(timedelta(hours=8)))
    session_label = f"【{args.session}】" if args.session else ""
    header = f"📰 {session_label}AI新闻 {now_cst.strftime('%m/%d %H:%M')}"

    if not output:
        print(header)
        print("\n暂无最新AI新闻（过去{}小时内无新文章）".format(args.hours))
        if source_errors:
            print("\n部分数据源异常：" + "；".join(source_errors))
        return

    # 翻译标题和摘要，检查持仓相关
    relevant_news = []
    other_news = []
    for a in output:
        a["title_cn"] = translate_to_chinese(a["title"])
        a["desc_cn"] = translate_to_chinese(a["desc"]) if a["desc"] else ""
        # 检查是否与持仓相关
        if check_relevant("", a["title"], a["desc"]):
            a["relevant"] = True
            relevant_news.append(a)
        else:
            a["relevant"] = False
            other_news.append(a)
    
    # 持仓相关的放前面
    output = relevant_news + other_news
    
    lines = [header, ""]
    
    # 先输出持仓相关
    if relevant_news:
        lines.append("【持仓相关新闻】")
        for i, a in enumerate(relevant_news, 1):
            time_str = format_pub_time(a["pub_dt"])
            time_tag = f" [{time_str}]" if time_str else ""
            lines.append(f"{i}. {a['title_cn']}{time_tag}")
            if a["desc_cn"]:
                lines.append(f"   {a['desc_cn']}")
            lines.append(f"   链接：{a['link']}")
            lines.append(f"   来源：{a['source']}")
            lines.append("")
    
    # 再输出其他新闻
    if other_news:
        if relevant_news:
            lines.append("【其他AI新闻】")
        for i, a in enumerate(other_news, len(relevant_news) + 1):
            time_str = format_pub_time(a["pub_dt"])
            time_tag = f" [{time_str}]" if time_str else ""
            lines.append(f"{i}. {a['title_cn']}{time_tag}")
            if a["desc_cn"]:
                lines.append(f"   {a['desc_cn']}")
            lines.append(f"   链接：{a['link']}")
            lines.append(f"   来源：{a['source']}")
            lines.append("")

    if source_errors:
        lines.append("⚠️ 部分源异常：" + "；".join(source_errors))

    print("\n".join(lines))


if __name__ == "__main__":
    main()
