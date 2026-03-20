# -*- coding: utf-8 -*-
import re
import json
import time
import random
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from .common import make_session, norm, now_cn

# ===================== 界面新闻：商业 =====================
JIEMIAN_BUSINESS_URL = "https://www.jiemian.com/lists/2.html"
# AJAX 翻页接口：https://www.jiemian.com/index.php?m=lists&a=ajax_news&cid=2&page=2
JIEMIAN_AJAX_URL = "https://www.jiemian.com/index.php?m=lists&a=ajax_news&cid=2&page={page}"
MAX_PAGES = 10  # 增加翻页深度

def parse_jiemian_time(text: str) -> datetime:
    """
    解析界面新闻的时间格式。
    常见格式：
    1. "10分钟前", "1小时前"
    2. "昨天 12:34"
    3. "2026-03-19 12:34"
    4. "03-19 12:34" (假设当年)
    """
    text = (text or "").strip()
    if not text:
        return None
    
    now = now_cn().replace(tzinfo=None)
    
    try:
        # 1. 相对时间
        if "分钟前" in text:
            mins = int(re.search(r"(\d+)", text).group(1))
            return now - timedelta(minutes=mins)
        if "小时前" in text:
            hours = int(re.search(r"(\d+)", text).group(1))
            return now - timedelta(hours=hours)
        if "昨天" in text:
            # 昨天 HH:MM
            m = re.search(r"(\d{1,2}):(\d{2})", text)
            if m:
                yesterday = now.date() - timedelta(days=1)
                return datetime(yesterday.year, yesterday.month, yesterday.day, int(m.group(1)), int(m.group(2)))
            else:
                # 仅显示昨天
                return datetime(now.year, now.month, now.day) - timedelta(days=1)
        if "今天" in text:
            # 今天 HH:MM
            m = re.search(r"(\d{1,2}):(\d{2})", text)
            if m:
                return datetime(now.year, now.month, now.day, int(m.group(1)), int(m.group(2)))
            else:
                return datetime(now.year, now.month, now.day)
        
        # 2. 绝对时间
        # 2026-03-19 15:30
        if re.match(r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}", text):
            return datetime.strptime(text, "%Y-%m-%d %H:%M")
        
        # 03/19 15:30
        if re.match(r"\d{2}/\d{2}\s+\d{2}:\d{2}", text):
            dt = datetime.strptime(text, "%m/%d %H:%M")
            return dt.replace(year=now.year)
            
        # 03-19 15:30 (当前年份)
        if re.match(r"\d{2}-\d{2}\s+\d{2}:\d{2}", text):
            dt = datetime.strptime(text, "%m-%d %H:%M")
            return dt.replace(year=now.year)
            
        # 2026/03/19
        if re.match(r"\d{4}/\d{2}/\d{2}", text):
             return datetime.strptime(text, "%Y/%m/%d")

    except Exception:
        pass
    return None

def extract_items_from_soup(soup, seen, results, cutoff_time):
    """
    从 BeautifulSoup 对象中提取新闻项。
    返回本页是否包含有效时间内的文章 (True/False)。
    """
    # 界面新闻列表结构
    # 优先找标准的 .news-view, .item-news
    items = soup.find_all("div", class_=lambda x: x and ("news-view" in x or "item-news" in x))
    
    # 如果没找到，尝试更宽泛的 .news-header
    if not items:
        # Fallback
        items = soup.find_all("div", class_="news-header")
        
    found_recent = False
    
    for item in items:
        # 找链接和标题
        a = item.find("a", href=True)
        if not a:
            continue
            
        href = a.get("href", "").strip()
        if not href or href.startswith("javascript"):
            continue
        if href in seen:
            continue
            
        title = norm(a.get_text())
        if not title:
            # 有时候标题在 title 属性里，或者里面的 h3/p 标签
            t_tag = item.find(["h3", "h4", "p"], class_=lambda x: x and "title" in x)
            if t_tag:
                 title = norm(t_tag.get_text())
            elif a.get("title"):
                 title = norm(a.get("title"))
                 
        if not title or len(title) < 5:
            continue

        if not href.startswith("http"):
            href = "https://www.jiemian.com" + href

        # 过滤视频
        if "/video/" in href:
            continue
            
        # 找时间
        # 1. 优先找 class 含 date/time 的标签
        time_tag = item.find(class_=lambda x: x and ("date" in x or "time" in x or "meta" in x))
        pub_time = None
        
        if time_tag:
             pub_time = parse_jiemian_time(time_tag.get_text())

        # 2. 如果没找到，尝试在全文里正则搜
        if not pub_time:
             text = item.get_text(" ", strip=True)
             # 增加对 "今天", "昨天" 及 "MM/DD HH:MM" 的正则支持
             # 注意：需要把 [昨今]天 ... 放在前面或也匹配到
             # 格式："今天 14:00", "昨天 10:00", "2024/03/12", "03/12 14:00"
             m = re.search(r"(\d{4}/\d{2}/\d{2}|\d{2}/\d{2}\s\d{2}:\d{2}|\d{2}-\d{2}\s\d{2}:\d{2}|\d+分钟前|\d+小时前|[昨今]天\s*\d{1,2}:\d{2})", text)
             if m:
                 pub_time = parse_jiemian_time(m.group(1))

        # 24h 过滤
        if pub_time:
            if pub_time >= cutoff_time:
                seen.add(href)
                results.append({
                    "title": title,
                    "url": href,
                    "source": "jiemian_business",
                    "time": pub_time.strftime("%Y-%m-%d %H:%M")
                })
                found_recent = True
            # 如果时间有了，但比cutoff早，说明这篇旧了。
            # 但列表里可能混排，所以不能单纯通过一篇就break，但可以用 found_recent 标记本页是否有新文章
        else:
            # 如果实在没时间，跳过
            pass
            
    return found_recent

def crawl_jiemian_business():
    """
    抓取界面新闻-商业板块的文章标题与链接。
    只返回24小时内发布的新闻。
    支持翻页（AJAX）。
    """
    s = make_session()
    # 增加 Referer 和 X-Requested-With 防止反爬
    s.headers.update({
        "Referer": JIEMIAN_BUSINESS_URL,
        "X-Requested-With": "XMLHttpRequest"
    })
    
    results = []
    seen = set()
    now = now_cn().replace(tzinfo=None)
    cutoff_time = now - timedelta(hours=24)
    
    # === Page 1: HTML ===
    print(f"[Jiemian] Crawling page 1...")
    try:
        r = s.get(JIEMIAN_BUSINESS_URL, timeout=15)
        r.encoding = "utf-8"
        # 界面新闻第一页是直接HTML
        soup = BeautifulSoup(r.text, "html.parser")
        has_recent = extract_items_from_soup(soup, seen, results, cutoff_time)
        
        # 只要第一页没有任何最近文章，认为后面更没有了
        if not has_recent:
            print("[Jiemian] Page 1 has no recent items. Stopping.")
            return results
            
    except Exception as e:
        print(f"[Jiemian] Fetch page 1 fail: {e}")
        return []

    # === Page 2+: AJAX ===
    for page in range(2, MAX_PAGES + 1):
        url = JIEMIAN_AJAX_URL.format(page=page)
        print(f"[Jiemian] Crawling page {page}: {url}")
        
        try:
            time.sleep(random.uniform(0.5, 1.5))
            r = s.get(url, timeout=15)
            
            # 调试：查看返回是否正常
            if r.status_code != 200:
                print(f"[Jiemian] Page {page} status {r.status_code}. Stopping.")
                break
                
            # 返回通常是 Json: { "rs": "HTML...", "code": 1 ... }
            html_snippet = ""
            try:
                # 尝试解析 JSON
                data = r.json()
                if isinstance(data, dict) and "rs" in data:
                    html_snippet = data["rs"]
                elif isinstance(data, str):
                    # 有时候直接返回字符串？
                    html_snippet = data
                    
            except ValueError:
                # 不是 JSON，可能是直接返回了 HTML
                # 检查是否包含 HTML 标签特征
                if "<div" in r.text or "<html" in r.text:
                    html_snippet = r.text
                else:
                    print(f"[Jiemian] Page {page} not JSON and not HTML. Content start: {r.text[:100]!r}")
                    break
            
            if not html_snippet:
                print(f"[Jiemian] Page {page} empty content. Stopping.")
                break
                
            soup = BeautifulSoup(html_snippet, "html.parser")
            has_recent = extract_items_from_soup(soup, seen, results, cutoff_time)
            
            if not has_recent:
                print(f"[Jiemian] Page {page} has no recent items. Stopping.")
                break
            
        except Exception as e:
            print(f"[Jiemian] Fetch page {page} fail: {e}")
            break

    print(f"[Jiemian] Collected {len(results)} items within 24h.")
    # 调试：如果没有收集到任何东西，打印前几个未通过的 items 以便排查
    # (省略)

    return results
