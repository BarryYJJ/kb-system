#!/usr/bin/env python3
"""
持仓2 - 个人模拟盘监控系统
从持仓数据获取实时行情，输出市值、占比、涨跌幅
"""
import sys
import os
from datetime import datetime
import requests

# 设置时区
os.environ['TZ'] = 'Asia/Shanghai'

# 导入数据
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from 持仓2_data import WATCHLIST, FUNDS


def get_hk_price_via_tencent(code):
    """通过腾讯财经接口获取港股价格"""
    # 港股代码格式：hk + 5位数字
    code_str = str(code).zfill(5)
    url = f'https://qt.gtimg.cn/q=hk{code_str}'
    
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.text
            if 'v_pv_none_match' in data:
                return None, None
            
            # 解析数据
            parts = data.split('=')[1].strip('"').split('~')
            if len(parts) > 33:
                current_price = float(parts[3])  # 当前价格
                open_price = float(parts[4])     # 开盘价
                
                # 计算涨跌幅（避免31字段的bug）
                if open_price and open_price > 0:
                    change_pct = ((current_price - open_price) / open_price) * 100
                else:
                    change_pct = 0
                
                return current_price, change_pct
    except Exception as e:
        print(f"获取港股 {code} 失败: {e}")
    
    return None, None


def get_us_stock_price(stock_code):
    """获取美股实时价格"""
    try:
        import yfinance as yf
        ticker = yf.Ticker(stock_code)
        info = ticker.fast_info
        
        price = info.last_price
        prev_close = info.previous_close
        
        if price and prev_close:
            change_pct = ((price - prev_close) / prev_close) * 100
            return price, change_pct
    except Exception as e:
        print(f"获取美股 {stock_code} 失败: {e}")
    
    return None, None


def get_us_market_status():
    """获取美股市场状态"""
    import pytz
    from datetime import datetime, time
    
    try:
        now = datetime.now(pytz.timezone('America/New_York'))
        current_time = now.time()
        weekday = now.weekday()
        
        if weekday >= 5:
            return "休市"
        
        if time(9, 30) <= current_time <= time(16, 0):
            return "盘中"
        elif current_time > time(16, 0):
            return "已收盘"
        elif current_time < time(9, 30):
            return "盘前"
    except:
        pass
    
    return "未知"


def format_hk_code(code):
    """格式化港股代码为5位数字"""
    return str(code).zfill(5)


def main():
    now = datetime.now()
    cn_time = now.strftime("%Y-%m-%d %H:%M")
    
    # 美股状态
    us_status = get_us_market_status()
    
    # 合并股票和基金
    all_holdings = list(WATCHLIST) + list(FUNDS)
    
    # 获取行情
    results = []
    total_market_value_cny = 0
    
    # 汇率
    usd_cny = 7.24
    hkd_cny = 0.92
    
    for code, name, qty, market_type, currency, note in all_holdings:
        if qty <= 0:
            continue
        
        price = None
        change_pct = None
        
        if market_type == "港股":
            price, change_pct = get_hk_price_via_tencent(format_hk_code(code))
        elif market_type == "美股":
            price, change_pct = get_us_stock_price(code)
        
        if price:
            # 计算市值（统一转为人民币）
            if currency == "USD":
                market_value = price * qty * usd_cny
            elif currency == "HKD":
                market_value = price * qty * hkd_cny
            else:
                market_value = price * qty
            
            results.append({
                'code': code,
                'name': name,
                'qty': qty,
                'price': price,
                'change_pct': change_pct,
                'market_value': market_value,
                'currency': currency,
                'market_type': market_type,
                'note': note
            })
            total_market_value_cny += market_value
    
    # 按市值排序
    results.sort(key=lambda x: x['market_value'], reverse=True)
    
    # 涨跌幅统计 - 市值加权平均
    changes = [r for r in results if r['change_pct'] is not None]
    gainers = losers = avg_change = weighted_change = 0
    if changes and total_market_value_cny > 0:
        gainers = sum(1 for r in changes if r['change_pct'] > 0)
        losers = sum(1 for r in changes if r['change_pct'] < 0)
        # 市值加权涨跌幅
        weighted_change = sum(r['change_pct'] * r['market_value'] for r in changes) / total_market_value_cny
    
    # 输出Markdown格式
    print(f"### 持仓2 汇总 ({cn_time})")
    print(f"**总市值**: ¥{int(total_market_value_cny):,} | 持仓: {len(results)}只 | **美股**: {us_status}")
    print(f"**涨跌**: 上涨{gainers}只，下跌{losers}只，平均 **{weighted_change:+.2f}%**")
    print()
    print("```")
    print(f"{'代码':<6} {'证券简称':<10} {'占比':>6} {'涨跌':>8} {'现价':>8} {'持仓':>6}")
    print("-" * 50)
    
    for r in results:
        pct = (r['market_value'] / total_market_value_cny * 100) if total_market_value_cny > 0 else 0
        change_str = f"{r['change_pct']:+.2f}%" if r['change_pct'] else "N/A"
        price_str = f"{r['price']:.2f}" if r['price'] else "N/A"
        print(f"{r['code']:<6} {r['name'][:8]:<8} {pct:>5.1f}% {change_str:>8} {price_str:>8} {r['qty']:>6.0f}")
    
    print("-" * 50)
    print(f"{'合计':<16} {int(total_market_value_cny):>10,}")
    print("```")
    
    # Top5
    if changes:
        changes_sorted = sorted(changes, key=lambda x: x['change_pct'], reverse=True)
        top5 = changes_sorted[:5]
        bottom5 = changes_sorted[-5:]
        
        print(f"**涨幅Top5**: " + " / ".join([f"{r['name'][:4]}{r['change_pct']:+.2f}%" for r in top5]))
        print(f"**跌幅Top5**: " + " / ".join([f"{r['name'][:4]}{r['change_pct']:+.2f}%" for r in bottom5]))


if __name__ == "__main__":
    main()
