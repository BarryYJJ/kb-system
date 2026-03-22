#!/usr/bin/env python3
"""
核心覆盖标的 - 股价查询 v4 (最终版)
用法: python3 ~/Desktop/stock_watchlist.py
"""

import yfinance as yf
from mootdx.quotes import Quotes
from datetime import datetime
import pytz

# 股票池
tickers = [
    ("2513.HK", "智谱"),
    ("0100.HK", "MINIMAX-WP"),
    ("1024.HK", "快手-W"),
    ("002415.SZ", "海康威视"),
    ("688111.SH", "金山办公"),
    ("002315.SZ", "焦点科技"),
    ("300628.SZ", "亿联网络"),
    ("300124.SZ", "汇川技术"),
    ("TSM", "台积电"),
    ("NVDA", "英伟达"),
    ("GOOG", "谷歌C"),
    ("688041.SH", "海光信息"),
    ("688256.SH", "寒武纪"),
    ("688795.SH", "摩尔线程"),
    ("688802.SH", "沐曦股份"),
    ("6882.HK", "壁仞科技"),
    ("3887.HK", "HASHKEY HLDGS"),
    ("0863.HK", "OSL集团"),
    ("2598.HK", "连连数字"),
    ("0700.HK", "腾讯控股"),
    ("9999.HK", "网易-S"),
    ("2400.HK", "心动公司"),
    ("603444.SH", "吉比特"),
    ("002555.SZ", "三七互娱"),
    ("002602.SZ", "世纪华通"),
    ("9961.HK", "携程集团-S"),
    ("0780.HK", "同程旅行"),
    ("0696.HK", "中国民航信息网络"),
    ("9899.HK", "网易云音乐"),
    ("1698.HK", "腾讯音乐-SW"),
    ("9988.HK", "阿里巴巴-W"),
    ("3690.HK", "美团-W"),
    ("0772.HK", "阅文集团"),
    ("3896.HK", "金山云"),
    ("TSLA", "特斯拉"),
    ("AAPL", "苹果"),
    ("ADBE", "奥多比"),
    ("PYPL", "Paypal Holdings"),
]

a_codes = ["002415", "688111", "002315", "300628", "300124",
           "688041", "688256", "688795", "688802",
           "603444", "002555", "002602"]

# 新股/数据不稳的股票列表（用info方法）
NEW_OR_UNSTABLE = ["0100.HK", "2513.HK"]  # 新股或刚上市的

def get_a_prices():
    try:
        client = Quotes.factory(market='std')
        df = client.quotes(a_codes)
        result = {}
        for i, row in df.iterrows():
            code = row['code']
            price = row['price']
            last_close = row['last_close']
            change = (price - last_close) / last_close * 100 if last_close != 0 else 0
            result[code] = {'price': price, 'change': change}
        return result
    except Exception as e:
        print(f"A股数据获取失败: {e}")
        return {}

def get_price_info(ticker):
    """用info方法获取价格（更准确，尤其对新股）"""
    try:
        s = yf.Ticker(ticker)
        info = s.info
        if 'currentPrice' in info and info.get('currentPrice'):
            current = info['currentPrice']
            change = info.get('regularMarketChangePercent')
            return current, change
        return None, None
    except:
        return None, None

def get_price_history(ticker):
    """用历史数据获取价格"""
    try:
        s = yf.Ticker(ticker)
        h = s.history(period="5d")
        if len(h) >= 2:
            current = h['Close'].iloc[-1]
            prev = h['Close'].iloc[-2]
            change = (current - prev) / prev * 100
            return current, change
        elif len(h) == 1:
            return h['Close'].iloc[-1], None
        return None, None
    except:
        return None, None

def get_price(ticker, name, a_data):
    if ticker.endswith(".SH") or ticker.endswith(".SZ"):
        code = ticker.replace(".SH", "").replace(".SZ", "")
        if code in a_data:
            price = a_data[code]['price']
            change = a_data[code]['change']
            sign = "+" if change > 0 else ""
            return f"  {name} ({ticker}): {price:.2f}  {sign}{change:.2f}%"
        return f"  {name} ({ticker}): --"
    else:
        # 优先用info方法（新股/不稳的），再用历史方法
        if ticker in NEW_OR_UNSTABLE:
            price, change = get_price_info(ticker)
        else:
            price, change = get_price_history(ticker)
        
        if price:
            if change is not None:
                sign = "+" if change > 0 else ""
                return f"  {name} ({ticker}): {price:.2f}  {sign}{change:.2f}%"
            return f"  {name} ({ticker}): {price:.2f}  --"
        return f"  {name} ({ticker}): --"

def get_us_market_status():
    beijing_tz = pytz.timezone('Asia/Shanghai')
    now = datetime.now(beijing_tz)
    us_tz = pytz.timezone('US/Eastern')
    us_time = now.astimezone(us_tz)
    us_hour = us_time.hour
    us_min = us_time.minute
    
    if (us_hour > 9 or (us_hour == 9 and us_min >= 30)) and us_hour < 16:
        status = "美股 [开盘中]"
    elif us_hour < 9 or us_hour >= 16:
        status = "美股 [已收盘]" if us_hour >= 6 else "美股 [盘前]"
    else:
        status = "美股 [盘前/盘后]"
    
    return f"美东时间 {us_time.strftime('%H:%M')} ({status})"

# 主程序
print("="*60)
print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M')} GMT+8")
print(get_us_market_status())
print("="*60)
print("核心覆盖标的")
print("-"*60)

a_data = get_a_prices()

for ticker, name in tickers:
    print(get_price(ticker, name, a_data))

print("="*60)

# 统计
results = []
for ticker, name in tickers:
    change = None
    if ticker.endswith(".SH") or ticker.endswith(".SZ"):
        code = ticker.replace(".SH", "").replace(".SZ", "")
        if code in a_data:
            change = a_data[code]['change']
    else:
        if ticker in NEW_OR_UNSTABLE:
            _, change = get_price_info(ticker)
        else:
            _, change = get_price_history(ticker)
    results.append((ticker, name, change))

up_list = [(t, n, c) for t, n, c in results if c and c > 0]
down_list = [(t, n, c) for t, n, c in results if c and c < 0]
up_list.sort(key=lambda x: x[2], reverse=True)
down_list.sort(key=lambda x: x[2])

print("\n点评")
print("-"*60)
print("【涨幅 Top 5】")
for i, (t, n, c) in enumerate(up_list[:5], 1):
    sign = "+" if c > 0 else ""
    print(f"  {i}. {n} ({t}): {sign}{c:.2f}%")

print("\n【跌幅 Top 5】")
for i, (t, n, c) in enumerate(down_list[:5], 1):
    print(f"  {i}. {n} ({t}): {c:.2f}%")

print(f"\n【汇总】\n  上涨 {len(up_list)} 只, 下跌 {len(down_list)} 只")

print("\n【板块分析】")
ai_stocks = ["海光信息", "寒武纪", "摩尔线程", "沐曦股份", "英伟达", "谷歌C", "台积电"]
game_stocks = ["吉比特", "三七互娱", "世纪华通", "心动公司"]
crypto_stocks = ["连连数字", "OSL集团", "HASHKEY HLDGS"]
internet_stocks = ["腾讯控股", "网易-S", "阿里巴巴-W", "美团-W", "快手-W"]
music_stocks = ["网易云音乐", "腾讯音乐-SW", "阅文集团"]
office_stocks = ["金山办公", "焦点科技", "金山云"]
hardware_stocks = ["海康威视", "亿联网络", "汇川技术"]
travel_stocks = ["携程集团-S", "同程旅行", "中国民航信息网络"]
us_stocks = ["特斯拉", "苹果", "奥多比", "Paypal Holdings"]

def print_sector(name, stock_list):
    data = [(t, n, c) for t, n, c in results if n in stock_list]
    up = [(t, n, c) for t, n, c in data if c and c > 0]
    down = [(t, n, c) for t, n, c in data if c and c < 0]
    if up:
        names = ", ".join([n for t, n, c in up])
        print(f"  {name}: 上涨 {len(up)} 只 ({names})")
    elif down:
        names = ", ".join([n for t, n, c in down])
        print(f"  {name}: 下跌 {len(down)} 只 ({names})")
    else:
        print(f"  {name}: --")

print_sector("AI/算力", ai_stocks)
print_sector("游戏", game_stocks)
print_sector("港股通证", crypto_stocks)
print_sector("港股互联网", internet_stocks)
print_sector("音乐", music_stocks)
print_sector("办公/软件", office_stocks)
print_sector("硬件/安防", hardware_stocks)
print_sector("旅行/OTA", travel_stocks)
print_sector("美股", us_stocks)

print("\n" + "="*60)
