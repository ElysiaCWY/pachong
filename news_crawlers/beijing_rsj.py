# -*- coding: utf-8 -*-
import re
import time
from urllib.parse import urljoin
from datetime import date
import requests
from bs4 import BeautifulSoup
from .common import make_session, parse_ymd, norm, mark_income_related

BEIJING_RSJ_URL = "https://rsj.beijing.gov.cn/xxgk/2024zcwj/"

def crawl_beijing_rsj_policy(target_date: date = None) -> list:
    """
    抓取北京市人社局-政策文件
    地址：https://rsj.beijing.gov.cn/xxgk/2024zcwj/
    如果不传 target_date，默认抓取所有（或者抓第一页全部，视需求定）。
    这里主要用于每日抓取指定日期的更新。
    """
    
    session = make_session()
    try:
        resp = session.get(BEIJING_RSJ_URL, timeout=15)
        resp.encoding = "utf-8"  # 显式指定编码，防止乱码
        if resp.status_code != 200:
            print(f"[BeijingRSJ] HTTP Error {resp.status_code}")
            return []
            
        soup = BeautifulSoup(resp.text, "html.parser")
        # 寻找包含文章列表的区域。根据页面结构推断，通常在某个 ul 或 div 下。
        # 这里尝试通过通用特征寻找：含有日期的链接列表
        # 页面结构通常是 ul > li > a 和 span(日期)
        
        results = []
        
        # 观察之前的 fetch_webpage 结果
        # [标题](url)YYYY-MM-DD
        # 这通常意味着 html 结构类似于 <li><a href="...">标题</a><span>YYYY-MM-DD</span></li>
        # 或者日期就在 a 标签后面
        
        # 尝试找到主要的文章列表容器
        # 常见的 class 名: list, news_list, zcwj_list 等
        # 可以在 soup 中搜索所有含有日期的 li
        
        # 遍历所有 li 标签，看是否包含日期格式
        for li in soup.find_all("li"):
            text = li.get_text()
            # 简单正则匹配日期 YYYY-MM-DD
            m = re.search(r"20\d{2}-\d{2}-\d{2}", text)
            if not m:
                continue
                
            date_str = m.group(0)
            article_date = parse_ymd(date_str)
            
            if not article_date:
                continue
                
            # 过滤日期
            if target_date and article_date != target_date:
                continue
                
            a_tag = li.find("a")
            if not a_tag:
                continue
                
            title = norm(a_tag.get_text())
            href = a_tag.get("href")
            
            if not title or not href:
                continue
                
            full_url = urljoin(BEIJING_RSJ_URL, href)
            
            title = mark_income_related(title)

            # 去重或添加到结果
            item = {
                "title": title,
                "url": full_url,
                "date": article_date
            }
            results.append(item)
            
        return results

    except Exception as e:
        print(f"[BeijingRSJ] Crawl error: {e}")
        return []
