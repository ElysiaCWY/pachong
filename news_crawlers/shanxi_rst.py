# -*- coding: utf-8 -*-
import re
from urllib.parse import urljoin
from datetime import date, timedelta
from bs4 import BeautifulSoup
from .common import make_session, norm, mark_income_related

SHANXI_RST_URL = "https://rst.shanxi.gov.cn/zwyw/zcfg/bmwj/"

def crawl_shanxi_rst_policy(target_date: date = None) -> list:
    """
    抓取山西人社厅-部门文件
    地址：https://rst.shanxi.gov.cn/zwyw/zcfg/bmwj/
    传入 target_date 时按单日抓取；未传入时默认抓取前一天发布内容。
    """
    if target_date is None:
        target_date = date.today() - timedelta(days=1)

    def should_keep(article_date: date) -> bool:
        return article_date == target_date

    def parse_total_pages(soup: BeautifulSoup) -> int:
        text = soup.get_text(" ", strip=True)
        m = re.search(r"共\s*(\d+)\s*页", text)
        if not m:
            return 1
        try:
            return max(1, int(m.group(1)))
        except Exception:
            return 1

    session = make_session()
    try:
        first_resp = session.get(SHANXI_RST_URL, timeout=15)
        first_resp.encoding = "utf-8"
        if first_resp.status_code != 200:
            print(f"[ShanxiRST] HTTP Error {first_resp.status_code}")
            return []

        first_soup = BeautifulSoup(first_resp.text, "html.parser")
        total_pages = parse_total_pages(first_soup)
        results = []
        seen_urls = set()

        for page_index in range(total_pages):
            page_url = SHANXI_RST_URL if page_index == 0 else urljoin(SHANXI_RST_URL, f"index_{page_index}.shtml")
            resp = first_resp if page_index == 0 else session.get(page_url, timeout=15)
            if page_index > 0:
                resp.encoding = "utf-8"
                if resp.status_code != 200:
                    print(f"[ShanxiRST] HTTP Error {resp.status_code} @ {page_url}")
                    continue

            soup = first_soup if page_index == 0 else BeautifulSoup(resp.text, "html.parser")

            # 尝试遍历所有可能的列表项
            # 页面结构通常是 li 包含 a 和日期(YYYY.MM.DD)
            candidates = soup.find_all("li")
            page_oldest_date = None

            for item in candidates:
                text = item.get_text()
                # 匹配日期 YYYY.MM.DD
                m = re.search(r"(\d{4})\.(\d{2})\.(\d{2})", text)
                if not m:
                    continue

                y, m_str, d_str = m.groups()
                try:
                    article_date = date(int(y), int(m_str), int(d_str))
                except ValueError:
                    continue

                if page_oldest_date is None or article_date < page_oldest_date:
                    page_oldest_date = article_date

                # 过滤日期
                if not should_keep(article_date):
                    continue

                a_tag = item.find("a")
                if not a_tag:
                    continue

                title = norm(a_tag.get_text())
                href = a_tag.get("href")

                if not title or not href:
                    continue
                
                title = mark_income_related(title)

                full_url = urljoin(page_url, href)

                # 去重
                if full_url in seen_urls:
                    continue

                seen_urls.add(full_url)
                results.append({
                    "title": title,
                    "url": full_url,
                    "date": article_date
                })

            # 列表按时间倒序发布，若当前页最早日期已早于目标日期，后续页可提前结束
            if page_oldest_date and page_oldest_date < target_date:
                break

        results.sort(key=lambda x: x["date"], reverse=True)
        return results

    except Exception as e:
        print(f"[ShanxiRST] Crawl error: {e}")
        return []
