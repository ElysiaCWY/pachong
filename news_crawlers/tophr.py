# -*- coding: utf-8 -*-
import os
import re
from datetime import date
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from .common import make_session, norm, parse_ymd, now_cn, target_prev_workday

# ===================== 企业新闻：第一资源 =====================
TOPHR_NEWS_URL = "http://www.tophr.net/news/newslist.asp?id=23"

def crawl_tophr():
    """
    抓取第一资源网站新闻，仅抓昨天（或指定 SINA_TARGET_DATE）发布的内容。
    """
    # 复用财经新闻的日期设置
    override = parse_ymd(os.getenv("SINA_TARGET_DATE"))
    today = now_cn().date()
    # 默认抓 yesterday
    target = override or target_prev_workday(today)

    s = make_session()
    try:
        r = s.get(TOPHR_NEWS_URL, timeout=15)
        # 第一资源是 ASP 网站，通常是 GB2312/GBK
        r.encoding = "gb2312"
    except Exception as e:
        print(f"TopHR fetch fail: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    results = []
    seen = set()

    # 简单粗暴遍历所有可能有日期的链接
    # 页面结构类似: <li><a href="...">标题</a>[2026-3-11]</li>
    # 或者 <td class="news_title"><a ...>...</a></td><td class="news_time">[2026-3-11]</td>
    # 这里用正则做宽泛匹配
    # 寻找所有含有 href 的 a 标签
    links = soup.find_all("a", href=True)
    for a in links:
        url = urljoin(TOPHR_NEWS_URL, a["href"])
        title = norm(a.get_text())
        
        # 必须有标题且链接包含 /news/
        if not title or "/news/" not in url:
            continue
            
        # 尝试在 a 标签的父级或周围寻找日期 [YYYY-M-D]
        # 很多时候日期就在后面
        # 扩大搜索范围：看这一行的文本
        row_text = ""
        if a.parent:
            row_text = a.parent.get_text(" ", strip=True)
            if a.parent.parent: # 再往上一层保险点 (tr/li)
                 row_text += " " + a.parent.parent.get_text(" ", strip=True)
        
        # 匹配日期 [2026-3-11] 或 [2026-03-11]
        m = re.search(r"\[(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})", row_text)
        if not m:
            continue
            
        y, mo, d = map(int, m.groups())
        dt = date(y, mo, d)
        
        # 只要昨天的
        if dt == target:
            if url not in seen:
                seen.add(url)
                results.append({"title": title, "url": url, "date": dt})

    return results
