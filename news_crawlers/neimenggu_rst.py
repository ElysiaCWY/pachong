# -*- coding: utf-8 -*-
import re
from urllib.parse import urljoin
from datetime import date
from bs4 import BeautifulSoup
from .common import make_session, parse_ymd, norm

NEIMENGGU_RST_URL = "https://rst.nmg.gov.cn/zfxxgk/fdzdgknr/?gk=3&cid=14006"
NEIMENGGU_BASE_URL = "https://rst.nmg.gov.cn"

def crawl_neimenggu_rst_policy(target_date: date = None) -> list:
    """
    抓取内蒙古人社厅-政策解读/部门文件
    地址：https://rst.nmg.gov.cn/zfxxgk/fdzdgknr/?gk=3&cid=14005
    自动计算目标日期（周一抓上周五，周二~周五抓昨天，周末不抓）。
    """
    session = make_session()
    try:
        resp = session.get(NEIMENGGU_RST_URL, timeout=15)
        resp.encoding = "utf-8"
        if resp.status_code != 200:
            print(f"[NeimengguRST] HTTP Error {resp.status_code}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        results = []

        # 尝试遍历所有可能的列表项
        # 根据 fetch_webpage 结果，内容可能在一个表格或列表中
        # 常见结构：tr > td > a + td(日期)
        
        # 优先寻找 table tr
        rows = soup.find_all("tr")
        
        for row in rows:
            text = row.get_text()
            # 匹配日期 YYYY-MM-DD
            m = re.search(r"(\d{4}-\d{1,2}-\d{1,2})", text)
            if not m:
                continue
            
            date_str = m.group(1)
            article_date = parse_ymd(date_str)
            
            if not article_date:
                continue
                
            # 过滤日期
            if target_date and article_date != target_date:
                continue

            a_tag = row.find("a")
            if not a_tag:
                continue
                
            title = norm(a_tag.get_text())
            href = a_tag.get("href")
            
            if not title or not href:
                continue
                
            full_url = urljoin(NEIMENGGU_BASE_URL, href)
            
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
        print(f"[NeimengguRST] Crawl error: {e}")
        return []
