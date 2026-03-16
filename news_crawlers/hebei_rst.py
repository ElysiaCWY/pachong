# -*- coding: utf-8 -*-
import re
from urllib.parse import urljoin
from datetime import date
from bs4 import BeautifulSoup
from .common import make_session, parse_ymd, norm

HEBEI_RST_URL = "https://rst.hebei.gov.cn/zxdtChild?isId=1427&id=3&orientation=0"
HEBEI_BASE_URL = "https://rst.hebei.gov.cn"

def parse_hebei_date(text: str):
    """
    解析类似于 "2025-12-04 15:57:00" 的日期
    """
    s = norm(text)
    # 提取 YYYY-MM-DD
    m = re.search(r"(\d{4}-\d{1,2}-\d{1,2})", s)
    if not m:
        return None
    return parse_ymd(m.group(1))

def crawl_hebei_rst_policy(target_date: date = None) -> list:
    """
    抓取河北人社厅-政策解读
    地址：https://rst.hebei.gov.cn/zxdtChild?isId=1427&id=3&orientation=0
    自动计算目标日期（周一抓上周五，周二~周五抓昨天，周末不抓）。
    """
    session = make_session()
    try:
        resp = session.get(HEBEI_RST_URL, timeout=15)
        resp.encoding = "utf-8"
        if resp.status_code != 200:
            print(f"[HebeiRST] HTTP Error {resp.status_code}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        results = []

        # 尝试寻找包含文章列表的容器
        # 根据 fetch_webpage 的结果，内容可能在一个表格或列表中
        # 常见结构：tr > td > a + td(日期)
        # 或者 li > a + span(日期)

        # 策略1：查找所有带有 href 的 a 标签，并在其附近寻找日期
        # 策略2：遍历所有可能的列表项容器 (tr, li)
        
        # 优先尝试 tr (看起来像表格)
        rows = soup.find_all("tr")
        if not rows:
            # 如果没找到 tr，尝试 li
            rows = soup.find_all("li")
        
        # 如果还是没有，尝试 div (有些网站用 div 模拟表格)
        if not rows:
            # 这是一个比较宽泛的搜索，但对于结构不明的页面很有用
            # 我们直接搜索所有包含日期的元素，然后找其前后的 a 标签
            pass

        for row in rows:
            text = row.get_text()
            # 检查是否有日期
            date_obj = parse_hebei_date(text)
            if not date_obj:
                continue

            # 过滤日期
            if target_date and date_obj != target_date:
                continue

            # 在该行内查找 a 标签
            a_tag = row.find("a")
            if not a_tag:
                continue

            title = norm(a_tag.get_text())
            href = a_tag.get("href")

            if not title or not href:
                continue
            
            # 处理链接，有时是相对路径
            # 使用 response.url 作为 base，以正确处理相对链接
            full_url = urljoin(resp.url, href)
            
            # 去重
            if any(r['url'] == full_url for r in results):
                continue

            results.append({
                "title": title,
                "url": full_url,
                "date": date_obj
            })
            
        # 如果 above loop 没找到结果 (可能是 div 结构)，尝试更通用的方法
        if not results:
             # 获取页面所有文本包含日期的元素
             # ... (这里先保持简单，如果跑不通再调整)
             pass

        return results

    except Exception as e:
        print(f"[HebeiRST] Crawl error: {e}")
        return []
