#!/usr/bin/env python3
"""
AI大V 推文抓取脚本（X/Twitter）
策略：依次尝试多个 Nitter 实例的 RSS，全部失败则输出诊断信息
特性：去重、时间过滤、输出飞书格式
用法：python3 ai_xfeed.py [--hours 12] [--max 10]

监控账号：
  sama (Sam Altman), elonmusk, AndrewYNg, DrJimFan, cdixon,
  ylecun (Yann LeCun), karpathy, sama, GaryMarcus
"""

import sys
import os
import json
import hashlib
import argparse
import re
import time
from datetime import datetime, timezone, timedelta
from xml.etree import ElementTree as ET
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
import signal

# ── 配置 ──────────────────────────────────────────────────────────────────────
CACHE_FILE = os.path.expanduser("~/.openclaw/workspace/scripts/.ai_xfeed_seen.json")

# 监控账号列表（按重要性排序，马斯克放在最后，减少占比）
# 分类：OpenAI系 > AI学术界 > 业界/产品 > 投资界
ACCOUNTS = [
    # ===== OpenAI 系 =====
    "sama",        # Sam Altman (OpenAI CEO)
    "karpathy",    # Andrej Karpathy
    "ilyasut",     # Ilya Sutskever
    "sbands",      # Sam Bowman
    
    # ===== AI 学术界 =====
    "AndrewYNg",   # Andrew Ng (DeepLearning.AI)
    "ylecun",      # Yann LeCun (Meta AI)
    "fchollet",    # François Chollet (Google)
    "GaryMarcus",  # Gary Marcus
    "Goodfellow_Ian", # Ian Goodfellow
    
    # ===== 业界/产品 =====
    "DrJimFan",    # Jim Fan (NVIDIA AI)
    "JensenHuang", # Jensen Huang (NVIDIA CEO)
    "demishassabis", # Demis Hassabis (DeepMind)
    "JeffDean",    # Jeff Dean (Google)
    "dario_amodei", # Dario Amodei (Anthropic CEO)
    "jackclark",   # Jack Clark (Anthropic)
    "Arthur_Mensch", # Arthur Mensch (Mistral AI CEO)
    
    # ===== 投资界 =====
    "cdixon",      # Chris Dixon (a16z)
    "pmddom",      # Patrick McDonnell
    "smtx",        # SemiAnalysis
    "swyx",        # AI Engineer
    
    # ===== 其他AI大V =====
    "elonmusk",    # Elon Musk (xAI) - 放在最后
]

# Nitter 实例列表（按稳定性排序，只保留最可靠的）
# 定期检查更新：https://github.com/zedeus/nitter/wiki/Instances
# 减少实例数量，超时时间缩短，提升稳定性
NITTER_INSTANCES = [
    "nitter.privacydev.net",  # 最稳定
    "nitter.tiekoetter.com",  # 备用
]

# 并发控制
MAX_WORKERS = 5  # 最多同时获取5个账号
ACCOUNT_TIMEOUT = 8  # 单账号超时（秒）

# AI 关键词（过滤非AI推文，设为空列表则不过滤）
AI_FILTER_KEYWORDS = [
    "AI", "LLM", "GPT", "model", "agent", "neural", "training",
    "inference", "OpenAI", "Anthropic", "Google", "Meta AI",
    "intelligence", "reasoning", "benchmark", "research",
    "paper", "release", "launch", "announcement",
    "AGI", "robot", "autonomous",
]
# 设为 False 则不过滤（抓所有推文）
ENABLE_AI_FILTER = False

# ── 工具函数 ──────────────────────────────────────────────────────────────────
def url_to_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:12]

def load_cache() -> set:
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE) as f:
                data = json.load(f)
            cutoff = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
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
    cutoff = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    fresh = {k: v for k, v in existing.items() if v >= cutoff}
    with open(CACHE_FILE, "w") as f:
        json.dump(fresh, f)

def fetch_url(url: str, timeout: int = 6) -> bytes:
    """带超时控制的 curl 请求"""
    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", str(timeout),
             "-L",   # follow redirects
             "-A", "Mozilla/5.0 (compatible; RSS reader)",
             url],
            capture_output=True,
            timeout=timeout + 2  # 进程级超时缓冲
        )
        if result.returncode != 0:
            raise RuntimeError(f"curl exit {result.returncode}")
        return result.stdout
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"timeout after {timeout}s")

def try_fetch_nitter_rss(account: str, timeout_per_instance: int = 5) -> tuple:
    """
    依次尝试所有 Nitter 实例，返回 (xml_bytes, instance_used)
    全部失败则抛出异常
    """
    errors = []
    for instance in NITTER_INSTANCES:
        url = f"https://{instance}/{account}/rss"
        try:
            data = fetch_url(url, timeout=timeout_per_instance)
            # 简单验证是否是有效 RSS
            if b"<rss" in data or b"<?xml" in data:
                if b"<item>" in data or b"<item " in data:
                    return data, instance
                else:
                    errors.append(f"{instance}: empty feed (no items)")
            else:
                errors.append(f"{instance}: not RSS")
        except Exception as e:
            errors.append(f"{instance}: {str(e)[:40]}")
    raise RuntimeError("All Nitter instances failed:\n" + "\n".join(f"  {e}" for e in errors))

def fetch_account_tweets(account: str, cutoff: datetime) -> tuple:
    """单账号抓取（带超时），返回 (tweets, error_msg)"""
    try:
        # 单账号总超时 20 秒
        xml_bytes, instance = try_fetch_nitter_rss(account, timeout_per_instance=5)
        tweets = parse_nitter_rss(xml_bytes, account, instance)
        fresh = [t for t in tweets
                 if t["pub_dt"] is None or t["pub_dt"] >= cutoff]
        return fresh, None
    except Exception as e:
        return [], str(e).split("\n")[0]

def parse_nitter_rss(xml_bytes: bytes, account: str, instance: str) -> list:
    """解析 Nitter RSS，返回推文列表"""
    tweets = []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return []

    channel = root.find('channel')
    if channel is None:
        return []

    for item in channel.findall('item'):
        title_el = item.find('title')
        link_el = item.find('link')
        pub_el = item.find('pubDate')
        desc_el = item.find('description')

        title = title_el.text.strip() if title_el is not None and title_el.text else ""
        link = link_el.text.strip() if link_el is not None and link_el.text else ""
        pub_date = pub_el.text.strip() if pub_el is not None and pub_el.text else ""
        desc = desc_el.text or "" if desc_el is not None else ""

        if not title or not link:
            continue

        # 清理 HTML
        desc_clean = re.sub(r'<[^>]+>', '', desc).strip()
        desc_clean = re.sub(r'\s+', ' ', desc_clean)

        # 推文内容优先用 desc（更完整），title 作为摘要
        content = desc_clean if desc_clean and len(desc_clean) > len(title) else title
        content = content[:280] + "..." if len(content) > 280 else content

        # 解析发布时间
        pub_dt = None
        if pub_date:
            for fmt in [
                "%a, %d %b %Y %H:%M:%S %z",
                "%a, %d %b %Y %H:%M:%S %Z",
                "%a, %d %b %Y %H:%M:%S GMT",
            ]:
                try:
                    pub_dt = datetime.strptime(pub_date, fmt)
                    if pub_dt.tzinfo is None:
                        pub_dt = pub_dt.replace(tzinfo=timezone.utc)
                    break
                except ValueError:
                    continue

        # 转为 x.com 链接（替换 nitter 域名）
        x_link = re.sub(r'https?://[^/]+/', 'https://x.com/', link)

        # AI 关键词过滤
        if ENABLE_AI_FILTER:
            combined = content.lower()
            if not any(kw.lower() in combined for kw in AI_FILTER_KEYWORDS):
                continue

        tweets.append({
            "id": url_to_id(link),
            "account": account,
            "content": content,
            "link": x_link,
            "pub_dt": pub_dt,
            "source_instance": instance,
        })

    return tweets

def format_pub_time(pub_dt) -> str:
    if pub_dt is None:
        return ""
    cst = timezone(timedelta(hours=8))
    local = pub_dt.astimezone(cst)
    return local.strftime("%m/%d %H:%M")

# ── 主逻辑 ────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="AI大V 推文抓取")
    parser.add_argument("--hours", type=int, default=12, help="抓取最近N小时的推文")
    parser.add_argument("--max", type=int, default=10, help="最多输出N条")
    parser.add_argument("--accounts", type=str, default="", help="逗号分隔的账号列表（默认用内置列表）")
    parser.add_argument("--no-dedup", action="store_true", help="不去重")
    parser.add_argument("--no-filter", action="store_true", help="不过滤AI关键词")
    args = parser.parse_args()

    accounts = [a.strip() for a in args.accounts.split(",")] if args.accounts else ACCOUNTS
    cutoff = datetime.now(timezone.utc) - timedelta(hours=args.hours)
    seen_ids = set() if args.no_dedup else load_cache()

    all_tweets = []
    account_errors = {}
    working_instance = None

    # 并发获取（加速）
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(fetch_account_tweets, account, cutoff): account 
                   for account in accounts}
        for future in as_completed(futures, timeout=ACCOUNT_TIMEOUT * 2):
            account = futures[future]
            try:
                tweets, err = future.result()
                if err:
                    account_errors[account] = err
                else:
                    # 去除已见ID
                    fresh = [t for t in tweets if t["id"] not in seen_ids]
                    all_tweets.extend(fresh)
                    if tweets:
                        working_instance = tweets[0].get("source_instance")
            except Exception as e:
                account_errors[account] = str(e)[:50]

    # 按时间排序
    def sort_key(t):
        return t["pub_dt"] or datetime.min.replace(tzinfo=timezone.utc)

    all_tweets.sort(key=sort_key, reverse=True)

    # 去重（相同内容）
    seen_content = set()
    deduped = []
    for t in all_tweets:
        content_key = t["content"][:100].lower()
        if content_key not in seen_content:
            seen_content.add(content_key)
            deduped.append(t)

    output = deduped[:args.max]

    # 更新缓存
    if not args.no_dedup:
        new_ids = seen_ids | {t["id"] for t in output}
        save_cache(new_ids)

    # ── 输出 ──────────────────────────────────────────────────────────────────
    now_cst = datetime.now(timezone(timedelta(hours=8)))
    header = f"🐦 AI 大V 动态 {now_cst.strftime('%m/%d %H:%M')}"

    lines = [header, ""]

    if not output and account_errors:
        # 全部失败
        lines.append("⚠️ X 数据抓取失败（Nitter 实例不可用）")
        lines.append("")
        lines.append("失败账号：" + "、".join(f"@{a}" for a in account_errors.keys()))
        lines.append("")
        lines.append("建议：")
        lines.append("1. 手动更新 NITTER_INSTANCES 列表（查看 https://github.com/zedeus/nitter/wiki/Instances）")
        lines.append("2. 或等待下次推送自动重试")
        print("\n".join(lines))
        return

    if not output:
        lines.append(f"过去 {args.hours}h 内无新推文")
        if working_instance:
            lines.append(f"（使用实例：{working_instance}）")
        print("\n".join(lines))
        return

    if working_instance:
        lines.append(f"数据来源：{working_instance}")
        lines.append("")

    for i, t in enumerate(output, 1):
        time_str = format_pub_time(t["pub_dt"])
        time_tag = f" [{time_str}]" if time_str else ""
        lines.append(f"{i}. @{t['account']}{time_tag}")
        lines.append(f"   {t['content']}")
        lines.append(f"   🔗 {t['link']}")
        lines.append("")

    if account_errors:
        failed = "、".join(f"@{a}" for a in account_errors.keys())
        lines.append(f"⚠️ 部分账号抓取失败：{failed}")

    print("\n".join(lines))


if __name__ == "__main__":
    main()
