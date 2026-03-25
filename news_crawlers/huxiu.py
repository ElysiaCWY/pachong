# -*- coding: utf-8 -*-
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, date
from urllib.parse import urljoin
from .common import norm, now_cn, target_prev_workday

# ===================== 虎嗅网 (Huxiu) =====================
HUXIU_NEWS_URL = "https://www.huxiu.com/article/"

def parse_huxiu_time(text: str) -> datetime:
    """
    解析虎嗅与时间相关的文本：
    1. "5分钟前", "1小时前", "3天前"
    2. "2023-10-27 10:20"
    3. "2023-10-27"
    """
    text = (text or "").strip()
    if not text:
        return None
    
    now = now_cn().replace(tzinfo=None)
    
    try:
        # 相对时间
        if "分钟前" in text:
            m = re.search(r"(\d+)\s*分钟前", text)
            if m:
                return now - timedelta(minutes=int(m.group(1)))
        if "小时前" in text:
            m = re.search(r"(\d+)\s*小时前", text)
            if m:
                return now - timedelta(hours=int(m.group(1)))
        if "天前" in text:
            m = re.search(r"(\d+)\s*天前", text)
            if m:
                return now - timedelta(days=int(m.group(1)))
        
        # 绝对时间 YYYY-MM-DD HH:MM
        m_ymd_hm = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{1,2})", text)
        if m_ymd_hm:
            return datetime(
                int(m_ymd_hm.group(1)), 
                int(m_ymd_hm.group(2)), 
                int(m_ymd_hm.group(3)),
                int(m_ymd_hm.group(4)),
                int(m_ymd_hm.group(5))
            )
            
        # 绝对日期 YYYY-MM-DD
        m_ymd = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
        if m_ymd:
             return datetime(int(m_ymd.group(1)), int(m_ymd.group(2)), int(m_ymd.group(3)))
             
    except Exception:
        pass
    return None

def crawl_huxiu(target_date=None, article_max=30):
    """
    抓取虎嗅网最新资讯文章。
    默认抓取 target_date (通常是昨天/今天) 的新闻。
    """
    if target_date is None:
        target_date = target_prev_workday(now_cn().date())
        
    results = []
    seen = set()
    
    print(f"[Huxiu] Start crawling... Target Date: {target_date}")
    
    try:
        session = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.huxiu.com/"
        }
        
        # 使用 verify=False 跳过 SSL 验证以避免证书错误
        resp = session.get(HUXIU_NEWS_URL, headers=headers, timeout=15, verify=False)
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # 查找文章容器
        # 结构通常是: div.article-item-wrap
        items = soup.find_all("div", class_=re.compile(r"article-item-wrap"))
        
        print(f"  -> Found {len(items)} items")
        
        for item in items[:article_max]:
            try:
                # 提取标题与链接
                # <h3 class="channel-title ..."> title </h3>
                # 链接在 h3 的父级或者附近的 a 标签
                h3 = item.find("h3", class_=re.compile("channel-title"))
                if not h3:
                    continue
                
                title = norm(h3.get_text(strip=True))
                
                # 寻找链接
                # 1. 尝试 h3 的父级
                link_el = h3.parent
                if link_el.name != 'a':
                    # 2. 尝试找同一个 item 下的链接
                    link_el = item.find("a", href=True)
                
                if not link_el or not link_el.has_attr('href'):
                    continue
                    
                href = link_el['href']
                full_url = urljoin(HUXIU_NEWS_URL, href)
                
                if full_url in seen:
                    continue
                    
                # 提取时间
                # 时间在 item 文本中，或 class="time"
                # 虎嗅列表页有时直接把时间文本放在某个 span 里，或者和其他信息混在一起
                # 我们先尝试找专门的时间标签
                time_txt = ""
                
                # 尝试找时间相关的 class
                time_el = item.find(class_=re.compile("time|date"))
                if time_el:
                    time_txt = time_el.get_text(strip=True)
                else:
                    # 如果没有明确标签，尝试在整个 item 文本里搜索 "分钟前" 等特征
                    full_txt = item.get_text(strip=True)
                    # 优先匹配相对时间
                    m = re.search(r"(\d+(分钟|小时|天)前)", full_txt)
                    if m:
                        time_txt = m.group(1)
                    else:
                        # 匹配绝对时间 YYYY-MM-DD
                        m2 = re.search(r"(\d{4}-\d{2}-\d{2})", full_txt)
                        if m2:
                            time_txt = m2.group(1)

                dt = parse_huxiu_time(time_txt)
                
                if dt:
                    # 比较日期
                    if dt.date() == target_date:
                        seen.add(full_url)
                        results.append({
                            "title": title,
                            "url": full_url,
                            "date": dt,
                            "source": "huxiu"
                        })
                else:
                    # 如果没解析出时间，但排在很前面，且策略允许，可以考虑作为当天处理？
                    # 暂时严格过滤
                    pass
                    
            except Exception as e:
                # print(f"  -> Item parse error: {e}")
                continue

    except Exception as e:
        print(f"[Huxiu] Error: {e}")
            
    # 按时间倒序
    results.sort(key=lambda x: x["date"], reverse=True)
    return results
