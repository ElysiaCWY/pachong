# -*- coding: utf-8 -*-
import os
import re
from datetime import date
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from .common import make_session, norm, target_prev_workday, now_cn, parse_ymd

# ===================== 国家税务总局：税务新闻 =====================
CHINATAX_NEWS_URL = "https://www.chinatax.gov.cn/chinatax/n810219/n810724/common_list_swxw.html"

def crawl_chinatax():
    """
    抓取国家税务总局-税务新闻，仅抓昨天（或指定日期）发布的内容。
    """
    # 复用日期设置
    override = parse_ymd(os.getenv("CHINATAX_TARGET_DATE"))
    today = now_cn().date()
    # 默认抓 yesterday
    target = override or target_prev_workday(today)

    s = make_session()
    try:
        r = s.get(CHINATAX_NEWS_URL, timeout=15)
        r.encoding = "utf-8" # 通常是 utf-8
    except Exception as e:
        print(f"Chinatax fetch fail: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    results = []
    seen = set()

    # 页面结构通常是列表，包含链接和日期
    # 例如: <ul class="list"><li><a href="...">标题</a><span>2023-10-12</span></li></ul>
    # 或者直接查找所有含有日期的元素
    
    # 查找所有链接
    links = soup.find_all("a", href=True)
    for a in links:
        url = urljoin(CHINATAX_NEWS_URL, a["href"])
        title = norm(a.get_text())
        
        if not title:
            continue
            
        # 在这行里找日期
        # 往往日期在 a 标签的 parent 里，或者 prev/next sibling
        row_text = ""
        if a.parent:
            row_text = a.parent.get_text(" ", strip=True)
        
        # 匹配日期 YYYY-MM-DD 或 YYYY年MM月DD日
        m = re.search(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})", row_text)
        if not m:
            continue
            
        y, mo, d = map(int, m.groups())
        dt = date(y, mo, d)
        
        # 只要昨天的
        if dt == target:
            if url not in seen:
                # 简单过滤：税务总局网站内链接
                if "chinatax.gov.cn" in url or url.startswith("/"):
                    seen.add(url)
                    results.append({"title": title, "url": url, "date": dt})

    return results
