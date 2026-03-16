# -*- coding: utf-8 -*-
import re
from urllib.parse import urljoin
from datetime import date
from bs4 import BeautifulSoup
from .common import make_session, parse_ymd, norm

TIANJIN_HRSS_URL = "https://hrss.tj.gov.cn/zhengwugongkai/zhengcezhinan/zcjdnew/"

def crawl_tianjin_hrss_policy(target_date: date = None) -> list:
    """
    抓取天津人社局-政策解读
    地址：https://hrss.tj.gov.cn/zhengwugongkai/zhengcezhinan/zcjdnew/
    自动计算目标日期（周一抓上周五，周二~周五抓昨天，周末不抓）。
    """
    session = make_session()
    try:
        resp = session.get(TIANJIN_HRSS_URL, timeout=15)
        resp.encoding = "utf-8"
        if resp.status_code != 200:
            print(f"[TianjinHRSS] HTTP Error {resp.status_code}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        results = []

        # 尝试遍历所有可能的列表项
        # 常见结构 li, div, tr 等，配合日期查找
        # 根据 fetch_webpage 的输出来看，是一个列表形式
        
        # 策略：查找所有 li 或 div 元素，如果包含日期 (YYYY-MM-DD) 且包含 a 标签，则提取
        candidates = soup.find_all(["li", "div", "dd"])
        
        for item in candidates:
            text = item.get_text()
            # 匹配日期 YYYY-MM-DD
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

            a_tag = item.find("a")
            if not a_tag:
                continue
                
            title = norm(a_tag.get_text())
            href = a_tag.get("href")
            
            if not title or not href:
                continue
                
            # 天津人社链接可能是相对路径
            full_url = urljoin(TIANJIN_HRSS_URL, href)
            
            # 去重：检查是否已经存在
            if any(r['url'] == full_url for r in results):
                continue
                
            results.append({
                "title": title,
                "url": full_url,
                "date": article_date
            })

        return results

    except Exception as e:
        print(f"[TianjinHRSS] Crawl error: {e}")
        return []
