# -*- coding: utf-8 -*-
import re
import time
import random
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from .common import make_session, norm, now_cn

# ===================== 中国金融信息网：独家 =====================
CNFIN_DJ_URL = "https://www.cnfin.com/dj/index.html"
CNFIN_DJ_PAGE_URL = "https://www.cnfin.com/dj/index_{page}.html"
MAX_PAGES = 10 

def parse_cnfin_time(text: str) -> datetime:
    """
    解析时间格式，例如：2026-03-06 19:16:29
    """
    text = (text or "").strip()
    if not text:
        return None
    
    try:
        if re.match(r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}", text):
            return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
        if re.match(r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}", text):
            return datetime.strptime(text, "%Y-%m-%d %H:%M")
        # 备用：YYYY-MM-DD
        if re.match(r"\d{4}-\d{2}-\d{2}", text):
             return datetime.strptime(text, "%Y-%m-%d")
    except Exception:
        pass
    return None

def crawl_cnfin_dj():
    """
    抓取中国金融信息网-独家板块的文章标题与链接。
    只返回24小时内发布的新闻。
    """
    s = make_session()
    results = []
    seen = set()
    now = now_cn().replace(tzinfo=None)
    cutoff_time = now - timedelta(hours=24)
    
    # === Page 1 ~ MAX_PAGES ===
    for page in range(1, MAX_PAGES + 1):
        if page == 1:
            url = CNFIN_DJ_URL
        else:
            url = CNFIN_DJ_PAGE_URL.format(page=page)
            
        print(f"[CNFIN] Crawling page {page}: {url}")
        
        try:
            if page > 1:
                time.sleep(random.uniform(0.5, 1.5))
                
            r = s.get(url, timeout=15)
            r.encoding = r.apparent_encoding or "utf-8"
            
            if r.status_code != 200:
                print(f"[CNFIN] Page {page} status {r.status_code}. Stopping.")
                break
                
            soup = BeautifulSoup(r.text, "html.parser")
            
            # 定位列表容器
            # 这里的结构是 <div class="zxlist-text-cont"> 父级通常是列表项
            # 直接找 .zxlist-text-cont 比较方便
            items = soup.find_all("div", class_="zxlist-text-cont")
            
            if not items:
                print(f"[CNFIN] Page {page} has no items. Stopping.")
                break
                
            found_recent = False
            
            for item in items:
                try:
                    h3 = item.find("h3")
                    if not h3:
                        continue
                    a = h3.find("a", href=True)
                    if not a:
                        continue
                        
                    href = a["href"].strip()
                    title = norm(a.get_text())
                    
                    if not title or len(title) < 5:
                        continue
                        
                    # 补全链接
                    # 这里的 href 通常是 //www.cnfin.com/...
                    if href.startswith("//"):
                        href = "https:" + href
                    elif not href.startswith("http"):
                        href = urljoin(CNFIN_DJ_URL, href)
                        
                    if href in seen:
                        continue
                        
                    # 找时间
                    time_div = item.find("div", class_="ui-publish")
                    pub_time = None
                    if time_div:
                        pub_time = parse_cnfin_time(time_div.get_text())
                    
                    if not pub_time:
                         # 尝试在文本里搜索日期
                         txt = item.get_text()
                         m = re.search(r"(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})", txt)
                         if m:
                             pub_time = parse_cnfin_time(m.group(1))
                             
                    if pub_time:
                        if pub_time >= cutoff_time:
                            seen.add(href)
                            results.append({
                                "title": title,
                                "url": href,
                                "source": "cnfin_dj",
                                "time": pub_time.strftime("%Y-%m-%d %H:%M")
                            })
                            found_recent = True
                        else:
                            # 遇到旧新闻，但页面内可能有乱序（虽然置顶通常在最前）
                            # 一般这类网站按时间倒序，遇到第一篇旧闻，后面大概率都是旧闻
                            # 但为了保险起见，本页继续找，下一页再判断 found_recent
                            pass
                except Exception as e:
                    print(f"[CNFIN] Parse item error: {e}")
                    continue
            
            # 如果整页都没有新文章，停止翻页
            if not found_recent:
                print(f"[CNFIN] Page {page} has no recent items. Stopping.")
                break
                
        except Exception as e:
            print(f"[CNFIN] Fetch page {page} fail: {e}")
            break

    print(f"[CNFIN] Collected {len(results)} items within 24h.")
    return results
