# -*- coding: utf-8 -*-
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from .common import make_session, norm, now_cn, target_prev_workday

# ===================== 动脉网：指定栏目 =====================
VBDATA_URL = "https://www.vbdata.cn/articleList?category=2992"

def parse_vbdata_time(text: str) -> datetime:
    """
    解析动脉网时间，支持：
    - "1小时前"
    - "1天前"
    - "2026-03-19"
    """
    if not text:
        return None
    s = norm(text)
    
    # 1. 相对时间
    now = now_cn().replace(tzinfo=None)
    
    if "分钟前" in s:
        m = re.search(r"(\d+)\s*分钟前", s)
        if m:
            minutes = int(m.group(1))
            return now - timedelta(minutes=minutes)
    elif "小时前" in s:
        m = re.search(r"(\d+)\s*小时前", s)
        if m:
            hours = int(m.group(1))
            return now - timedelta(hours=hours)
    elif "天前" in s:
        m = re.search(r"(\d+)\s*天前", s)
        if m:
            days = int(m.group(1))
            return now - timedelta(days=days)
    
    # 2. 绝对日期 YYYY-MM-DD
    m_date = re.search(r"(\d{4}-\d{2}-\d{2})", s)
    if m_date:
        try:
            return datetime.strptime(m_date.group(1), "%Y-%m-%d")
        except:
            pass
            
    return None

def crawl_vbdata():
    """
    抓取动脉网指定栏目文章。
    只返回24小时内发布的新闻。
    """
    s = make_session()
    try:
        r = s.get(VBDATA_URL, timeout=15)
        r.encoding = r.apparent_encoding or "utf-8"
        html = r.text
    except Exception as e:
        print(f"VBData fetch fail: {e}")
        return []

    soup = BeautifulSoup(html, "html.parser")
    results = []
    seen = set()
    
    # 过滤时间：最近 24 小时
    now = now_cn().replace(tzinfo=None)
    cutoff = now - timedelta(hours=24)

    # 动脉网列表项结构通常包含标题链接和时间
    # 观察 fetch_webpage 结果，结构可能是:
    # <li class="list-item"> ... <span class="date">...</span> ... <a class="title">...</a> ... </li>
    # 或者类似的 div 结构
    
    # 策略：查找所有可能的列表项容器
    # 我们可以直接查找包含 href 的 a 标签，然后找附近的日期
    
    # 也可以查找 class 包含 "date" 或 "time" 的元素，或者直接匹配日期格式的文本
    
    # 根据 fetch_webpage 的 markdown 结构：
    # 李佳英1 天前
    # [](...) 时讯 [标题](url)
    
    # 这暗示日期在标题之前。
    # 我们遍历所有的 a 标签，找到链接符合 /1519... (数字ID) 的
    
    links = soup.find_all("a", href=True)
    
    for a in links:
        href = a["href"]
        # 链接通常是 https://www.vbdata.cn/1519068428 或 /1519068428
        # 匹配数字 ID 结尾
        if not re.search(r"/\d+$", href):
            continue
            
        title = norm(a.get_text())
        if len(title) < 5:
            continue
            
        url = urljoin(VBDATA_URL, href)
        if url in seen:
            continue
            
        # 找日期
        # 日期通常在 a 标签的父级容器中的某个位置，或者前一个兄弟节点
        # 我们可以尝试在 a 标签的 parent 以及 parent 的 parent 中找日期文本
        
        found_date = None
        container = a.parent
        for _ in range(3): # 向上找3层
            if not container:
                break
            
            # 在容器内找文本
            text_nodes = container.stripped_strings
            for txt in text_nodes:
                # 跳过标题本身 (如果遍历到了)
                if txt in title: 
                    continue
                
                dt = parse_vbdata_time(txt)
                if dt:
                    found_date = dt
                    break
            
            if found_date:
                break
            container = container.parent
            
        if not found_date:
            continue
            
        # 检查时间是否在24小时内
        # 注意：如果是 "1天前"，通常认为可能稍微超过24小时，但如果是昨天发布的也算
        # 这里严格一点，如果是 parse 出来的 exact timestamp 比较 cutoff
        # 如果是 date object (from YYYY-MM-DD), set time to 00:00
        
        is_recent_date = False
        
        # 如果日期包含具体时间（时:分），直接比较
        # parse_vbdata_time 对于相对时间返回的是带时分秒的，对于 YYYY-MM-DD 返回的是 00:00:00
        
        if found_date >= cutoff:
            is_recent_date = True
        else:
            # 特殊处理：如果是 00:00:00 (即只提取到日期)，而日期就是今天或昨天，则保留
            # 比如 cutoff 是 今天 09:00，文章是 昨天 00:00， 实际上 < 24h 也不一定
            # 我们放宽一点：如果是今天或昨天的日期，都保留
            if found_date.hour == 0 and found_date.minute == 0:
                if found_date.date() >= (now.date() - timedelta(days=1)):
                    is_recent_date = True
            
        if not is_recent_date:
            continue

        seen.add(url)
        results.append({
            "title": title,
            "url": url,
            "published_at": found_date.strftime("%Y-%m-%d %H:%M"),
            "source": "vbdata"
        })
            
    # 按时间倒序
    results.sort(key=lambda x: x["published_at"], reverse=True)
    return results
