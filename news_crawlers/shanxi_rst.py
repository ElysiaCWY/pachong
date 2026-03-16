# -*- coding: utf-8 -*-
import re
from urllib.parse import urljoin
from datetime import date, datetime
from bs4 import BeautifulSoup
from .common import make_session, parse_ymd, norm

SHANXI_RST_URL = "https://rst.shanxi.gov.cn/zwyw/zcfg/bmwj/"

def crawl_shanxi_rst_policy(target_date: date = None) -> list:
    """
    抓取山西人社厅-部门文件
    地址：https://rst.shanxi.gov.cn/zwyw/zcfg/bmwj/
    自动计算目标日期（周一抓上周五，周二~周五抓昨天，周末不抓）。
    """
    session = make_session()
    try:
        resp = session.get(SHANXI_RST_URL, timeout=15)
        resp.encoding = "utf-8"
        if resp.status_code != 200:
            print(f"[ShanxiRST] HTTP Error {resp.status_code}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        results = []

        # 尝试遍历所有可能的列表项
        # 页面结构通常是 li 包含 a 和 span(日期)
        # 根据 fetch_webpage 结果，日期格式为 YYYY.MM.DD
        
        candidates = soup.find_all("li")
        
        for item in candidates:
            text = item.get_text()
            # 匹配日期 YYYY.MM.DD
            m = re.search(r"(\d{4})\.(\d{2})\.(\d{2})", text)
            if not m:
                continue
            
            # 构造日期字符串 YYYY-MM-DD 以便 parse_ymd 解析，或者直接构造 date 对象
            y, m_str, d_str = m.groups()
            article_date = date(int(y), int(m_str), int(d_str))
                
            # 过滤日期
            if target_date and article_date != target_date:
                continue

            a_tag = item.find("a")
            if not a_tag:
                continue
                
            title = norm(a_tag.get_text())
            href = a_tag.get("href")
            
            if not title or not href:
                continue
                
            full_url = urljoin(SHANXI_RST_URL, href)
            
            # 去重
            if any(r['url'] == full_url for r in results):
                continue
                
            results.append({
                "title": title,
                "url": full_url,
                "date": article_date
            })

        return results

    except Exception as e:
        print(f"[ShanxiRST] Crawl error: {e}")
        return []
