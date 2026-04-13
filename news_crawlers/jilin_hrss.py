# -*- coding: utf-8 -*-
import re
from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, norm, mark_income_related


JILIN_HRSS_POLICY_URL = "https://hrss.jl.gov.cn/flfg/dfxfggz2017/"


def _parse_page_count(soup: BeautifulSoup) -> int:
    text = soup.get_text(" ", strip=True)
    m = re.search(r"总数\s*(\d+)\s*页", text)
    if not m:
        return 1
    try:
        return max(1, int(m.group(1)))
    except Exception:
        return 1


def crawl_jilin_hrss_policy(target_date: date = None) -> list[dict]:
    """
    抓取吉林省人社厅-地方法规政策板块。
    传入 target_date 时按单日抓取；未传入时抓取全部分页标题链接。
    """
    session = make_session()
    try:
        first_resp = session.get(JILIN_HRSS_POLICY_URL, timeout=15)
        first_resp.encoding = first_resp.apparent_encoding or "utf-8"
        if first_resp.status_code != 200:
            print(f"[JilinHRSS] HTTP Error {first_resp.status_code}")
            return []

        first_soup = BeautifulSoup(first_resp.text, "html.parser")
        total_pages = _parse_page_count(first_soup)
        results = []
        seen_urls = set()

        for page_index in range(total_pages):
            page_url = JILIN_HRSS_POLICY_URL if page_index == 0 else urljoin(JILIN_HRSS_POLICY_URL, f"index_{page_index}.html")
            resp = first_resp if page_index == 0 else session.get(page_url, timeout=15)
            if page_index > 0:
                resp.encoding = resp.apparent_encoding or "utf-8"
                if resp.status_code != 200:
                    print(f"[JilinHRSS] HTTP Error {resp.status_code} @ {page_url}")
                    continue

            soup = first_soup if page_index == 0 else BeautifulSoup(resp.text, "html.parser")
            page_oldest_date = None

            for li in soup.find_all("li"):
                text = norm(li.get_text(" ", strip=True))
                m = re.search(r"(20\d{2}-\d{2}-\d{2})", text)
                if not m:
                    continue

                try:
                    article_date = date.fromisoformat(m.group(1))
                except ValueError:
                    continue

                if page_oldest_date is None or article_date < page_oldest_date:
                    page_oldest_date = article_date

                if target_date and article_date != target_date:
                    continue

                a_tag = li.find("a", href=True)
                if not a_tag:
                    continue

                title = norm(a_tag.get_text(" ", strip=True))
                href = (a_tag.get("href") or "").strip()
                if not title or not href:
                    continue

                full_url = urljoin(page_url, href)
                if full_url in seen_urls:
                    continue

                seen_urls.add(full_url)
                title = mark_income_related(title)
                results.append({"title": title, "url": full_url, "date": article_date, "source": "jilin_hrss_policy"})

            if target_date and page_oldest_date and page_oldest_date < target_date:
                break

        results.sort(key=lambda x: (x["date"], x["title"]), reverse=True)
        return results
    except Exception as e:
        print(f"[JilinHRSS] Crawl error: {e}")
        return []
