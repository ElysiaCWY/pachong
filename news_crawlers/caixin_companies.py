# -*- coding: utf-8 -*-
import requests
import re
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from .common import make_session, norm, now_cn

# ===================== 财新网：公司 =====================
CAIXIN_COMPANIES_URL = "https://companies.caixin.com/"

def parse_caixin_time(s: str) -> datetime:
    """
    解析类似 "2026年03月19日 12:34" 的时间字符串
    """
    if not s:
        return None
    try:
        # 尝试匹配完整时间
        m = re.search(r"(\d{4})年(\d{2})月(\d{2})日\s*(\d{2}):(\d{2})", s)
        if m:
            dt_str = f"{m.group(1)}-{m.group(2)}-{m.group(3)} {m.group(4)}:{m.group(5)}"
            return datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
        
        # 尝试匹配仅日期（如列表页可能省略时间）
        m_date = re.search(r"(\d{4})年(\d{2})月(\d{2})日", s)
        if m_date:
             dt_str = f"{m_date.group(1)}-{m_date.group(2)}-{m_date.group(3)}"
             return datetime.strptime(dt_str, "%Y-%m-%d")
             
        return None
    except Exception:
        return None

def crawl_caixin_companies():
    """
    抓取财新网-公司板块的文章标题与链接。
    只返回24小时内发布的新闻。
    """
    s = make_session()
    try:
        r = s.get(CAIXIN_COMPANIES_URL, timeout=15)
        r.encoding = r.apparent_encoding or "utf-8"
        html = r.text
    except Exception as e:
        print(f"Caixin Companies fetch fail: {e}")
        return []

    soup = BeautifulSoup(html, "html.parser")
    results = []
    seen = set()
    now = now_cn().replace(tzinfo=None)

    links = soup.find_all("a", href=True)
    
    for a in links:
        href = a.get("href", "").strip()
        # 宽松匹配URL，允许后面有参数
        if not re.search(r"caixin\.com/\d{4}-\d{2}-\d{2}/\d+\.html", href):
            continue
            
        url = href
        # 去重
        if url in seen:
            continue
            
        title = norm(a.get_text())
        if not title or len(title) < 5:
            continue
            
        time_found = None
        text_for_check = ""
        
        # 1. 在父级容器中找时间
        parent = a.parent
        for _ in range(3):
            if not parent:
                break
            text = parent.get_text(" ", strip=True)
            text_for_check = text
            dt = parse_caixin_time(text)
            if dt:
                time_found = dt
                break
            parent = parent.parent
            
        is_from_url = False
        # 2. URL 提取日期兜底
        if not time_found:
            m_url = re.search(r"/(\d{4})-(\d{2})-(\d{2})/", url)
            if m_url:
                dt_str = f"{m_url.group(1)}-{m_url.group(2)}-{m_url.group(3)}"
                try:
                    time_found = datetime.strptime(dt_str, "%Y-%m-%d")
                    is_from_url = True
                except:
                    pass
        
        if not time_found:
            continue
            
        # 判定是否在24h内
        # case A: 精确时间 (time_found has H:M)
        # case B: 仅日期 (time_found H:M is 00:00), 且 is_from_url is True OR text didn't contain 00:00
        
        should_keep = False
        delta = now - time_found
        
        # 判断 time_found 是否包含有效时分
        # 如果 is_from_url 为 True，肯定只有日期
        # 如果 is_from_url 为 False，但 hour=0 minute=0，可能是真的0点，也可能是 parse_caixin_time 只匹配到日期
        # parse_caixin_time 逻辑：如果匹配到 H:M 就返回带时分的，否则返回 00:00
        
        has_time_part = True
        if is_from_url:
            has_time_part = False
        elif time_found.hour == 0 and time_found.minute == 0:
            # 检查原文是否真的写了 00:00
            if "00:00" not in text_for_check:
                has_time_part = False
        
        if has_time_part:
            # 精确对比 24 小时
            if timedelta(seconds=0) <= delta <= timedelta(hours=24):
                should_keep = True
        else:
            # 只有日期：只要是今天或昨天
            # delta.days: 0 (today), 1 (yesterday)
            # note: delta = now - today_00_00 -> if now is today 12:00, delta is 12h (days=0)
            # if now is tomorrow 12:00, delta is 36h (days=1)
            # if item is yesterday 00:00, now is today 12:00 -> delta = 36h (days=1)
            # So if days <= 1, it implies today or yesterday
            if delta.days <= 1 and delta.days >= 0:
                should_keep = True
                
        if should_keep:
            seen.add(url)
            results.append({
                "title": title, 
                "url": url, 
                "source": "caixin_companies",
                "time": time_found.strftime("%Y-%m-%d %H:%M")
            })

    return results
