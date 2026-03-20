# -*- coding: utf-8 -*-
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from .common import make_session, norm, now_cn, parse_ymd

# ===================== 财富中文网：商业频道 =====================
FORTUNE_CN_URL = "https://www.fortunechina.com/shangye/"

def crawl_fortune_cn():
    """
    抓取财富中文网-商业频道
    抓取策略：默认抓取昨天的内容（北京时间）。
    """
    s = make_session()
    
    # 确定目标日期：默认昨天
    # 如果有环境变量设置则使用
    now = now_cn().date()
    # 昨天
    target_date = now - timedelta(days=1)
    target_str = target_date.strftime("%Y-%m-%d")

    # 如果需要调试特定日期，可手动覆盖，或使用 common.target_prev_workday 逻辑
    # 这里保持原脚本逻辑：昨天
    
    print(f"[FortuneCN] Target date: {target_str}")

    try:
        r = s.get(FORTUNE_CN_URL, timeout=15)
        r.encoding = "utf-8"
    except Exception as e:
        print(f"FortuneCN fetch fail: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    results = []
    seen = set()

    # 列表抓取逻辑参考原脚本
    # ul.news-list li.news-item
    # h2 -> a
    # div.date -> time
    
    items = soup.select("ul.news-list li.news-item")
    if not items:
        # 尝试备用选择器，财富网有时候结构会变
        items = soup.find_all("div", class_="news-item")
        
    print(f"[FortuneCN] Found candidates: {len(items)}")

    for li in items:
        h2 = li.find(["h2", "h3"])
        a = li.find("a", href=True)
        date_div = li.find("div", class_=lambda x: x and ("date" in x or "time" in x))

        if not a:
            if h2:
                a_in_h2 = h2.find("a", href=True)
                if a_in_h2:
                    a = a_in_h2

        if not a:
            continue

        href = a["href"].strip()
        # 财富网链接有时候是相对路径
        if not href.startswith("http"):
            href = urljoin(FORTUNE_CN_URL, href)
            
        if href in seen:
            continue

        title = ""
        if h2:
             title = norm(h2.get_text())
        else:
             title = norm(a.get_text())
        
        if not title:
             continue

        pub_time_str = ""
        if date_div:
            pub_time_str = date_div.get_text(strip=True)
        
        # 如果没有日期，尝试从链接里提取日期 (例如 .../2026/03/19/...)
        if not pub_time_str:
            m = re.search(r"/(\d{4})[/-](\d{2})[/-](\d{2})/", href)
            if m:
                pub_time_str = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        
        # 过滤日期
        # 原脚本逻辑：必须等于 target_date
        # 财富网日期格式通常是 YYYY-MM-DD
        if pub_time_str:
            # 简单比较字符串即可，假设都是 YYYY-MM-DD
            if pub_time_str == target_str:
                seen.add(href)
                results.append({
                    "title": title,
                    "url": href,
                    "source": "fortune_cn",
                    "time": pub_time_str
                })
            else:
                pass
                # print(f"  Skip date: {pub_time_str} != {target_str}")
        else:
            # 没找到日期，无法判断，跳过
            pass

    print(f"[FortuneCN] Collected {len(results)} items for {target_str}")
    return results
