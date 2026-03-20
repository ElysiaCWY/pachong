# -*- coding: utf-8 -*-
import re
from datetime import datetime
from bs4 import BeautifulSoup
from .common import make_session, norm, now_cn, target_prev_workday

# ===================== 同花顺：非上市公司 =====================
THSI_UNLISTED_URL = "https://news.10jqka.com.cn/fssgsxw_list/"
MAX_PAGES = 50  # 增加页数以应对当日新闻较多的情况

def crawl_thsi_unlisted():
    """
    抓取同花顺-非上市公司新闻。
    只爬取前一天（工作日逻辑，如果是周一则抓上周五）发布的。
    """
    s = make_session()
    
    # 确定目标日期：同 others，使用 prev_workday
    # 如果今天是周三(19)，prev_workday是周二(18)
    today = now_cn().date()
    target_date = target_prev_workday(today)
    
    print(f"[THSI] Target Date: {target_date} (Previous Workday)")
    print(f"[THSI] Start crawling items...")
    
    results = []
    seen = set()
    
    # 遍历页面
    # URL 模式:
    # 首页: https://news.10jqka.com.cn/fssgsxw_list/
    # 第2页: https://news.10jqka.com.cn/fssgsxw_list/index_2.shtml
    
    for page in range(1, MAX_PAGES + 1):
        if page == 1:
            url = THSI_UNLISTED_URL
        else:
            url = f"{THSI_UNLISTED_URL}index_{page}.shtml"
            
        try:
            r = s.get(url, timeout=15)
            # 同花顺以前是gbk，现在部分页面可能是utf-8
            # 让 requests 自动检测
            r.encoding = r.apparent_encoding 
        except Exception as e:
            print(f"[THSI] Fetch page {page} fail: {e}")
            break
            
        soup = BeautifulSoup(r.text, "html.parser")
        
        # 查找列表项
        container = soup.find("div", class_="list-con")
        items = []
        if container:
            items = container.find_all("li")
        
        if not items:
            span_titles = soup.find_all("span", class_="arc-title")
            for sp in span_titles:
                parent = sp.parent
                if parent and parent.name == "li":
                    if parent not in items:
                        items.append(parent)
        
        # print(f"[THSI] Page {page}: found {len(items)} items.")

        if not items:
            # 如果连续很多页没找到，可能到底了
            if page > 5:
                break
            pass
            
        for li in items:
            # 提取标题
            a = li.find("a", href=True)
            if not a:
                t_span = li.find("span", class_="arc-title")
                if t_span:
                    a = t_span.find("a", href=True)
            
            if not a:
                continue
                
            href = a.get("href", "").strip()
            title = norm(a.get_text())
            
            if not title:
                continue
                
            # 提取日期
            d_span = li.find("span", class_="arc-date")
            date_text = ""
            if d_span:
                date_text = d_span.get_text().strip()
            
            # 尝试解析日期 "MM月DD日"
            match_date = re.search(r"(\d{1,2})月(\d{1,2})日", date_text)
            news_date = None
            
            if match_date:
                m_month = int(match_date.group(1))
                m_day = int(match_date.group(2))
                curr_year = today.year
                if today.month == 1 and m_month == 12:
                    curr_year -= 1
                
                try:
                    news_date = datetime(curr_year, m_month, m_day).date()
                except:
                    pass
            
            # 如果没找到 date_text，尝试从 URL 提取: /20260319/
            if not news_date:
                m_url = re.search(r"/(\d{4})(\d{2})(\d{2})/", href)
                if m_url:
                    try:
                        news_date = datetime(int(m_url.group(1)), int(m_url.group(2)), int(m_url.group(3))).date()
                    except:
                        pass
            
            if news_date:
                # 只有等于 target_date (昨天) 才收录
                if news_date == target_date:
                    if href not in seen:
                        seen.add(href)
                        results.append({
                            "title": title,
                            "url": href,
                            "source": "thsi_unlisted",
                            "time": f"{news_date} {date_text}"
                        })
                elif news_date < target_date:
                    print(f"[THSI] Found older date {news_date} < {target_date}, stopping crawl.")
                    return results
                else:
                    # 日期比较新（今天），继续找
                    pass
            else:
                pass

    print(f"[THSI] Total collected: {len(results)}")
    return results