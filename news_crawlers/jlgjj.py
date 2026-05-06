# -*- coding: utf-8 -*-
import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, now_cn, norm, parse_ymd, mark_income_related


JLGJJ_INDEX_URL = "http://www.jlgjj.gov.cn/zcfg/gfxwj/"


def _page_url(page_no: int) -> str:
    if page_no <= 1:
        return JLGJJ_INDEX_URL
    return urljoin(JLGJJ_INDEX_URL, f"index_{page_no - 1}.html")


def _parse_page(html: str, page_url: str) -> list[dict]:
    soup = BeautifulSoup(html or "", "html.parser")
    results: list[dict] = []

    for row2 in soup.select("ul.list > li > ul > li.row2.txtL"):
        a_tag = row2.find("a", href=True)
        if not a_tag:
            continue

        href = (a_tag.get("href") or "").strip()
        if not href or not href.endswith(".html"):
            continue

        title = norm(a_tag.get_text(" ", strip=True))
        if not title:
            continue

        full_url = urljoin(page_url, href)
        date_text = ""
        row_container = row2.parent
        if row_container:
            row1 = row_container.find("li", class_="row1")
            if row1:
                date_text = norm(row1.get_text(" ", strip=True))
        if not date_text:
            m = re.search(r"(20\d{2}-\d{2}-\d{2})", norm(row2.get_text(" ", strip=True)))
            if m:
                date_text = m.group(1)

        results.append(
            {
                "title": mark_income_related(title),
                "url": full_url,
                "date": parse_ymd(date_text) if date_text else None,
                "source": "jlgjj_gfxwj",
            }
        )

    return results


def crawl_jlgjj_policy(current_time: datetime | None = None, max_pages: int = 6) -> list[dict]:
    """抓取吉林市住房公积金管理中心政策文件板块。"""
    _ = current_time or now_cn()
    session = make_session()
    results: list[dict] = []
    seen_urls: set[str] = set()

    for page_no in range(1, max_pages + 1):
        page_url = _page_url(page_no)
        try:
            resp = session.get(page_url, timeout=15)
            resp.encoding = resp.apparent_encoding or "utf-8"
            if resp.status_code != 200:
                break
        except Exception as e:
            print(f"[JLGJJ] Crawl error(p{page_no}): {e}")
            break

        page_items = _parse_page(resp.text, page_url)
        if not page_items:
            break

        page_has_new = False
        for item in page_items:
            if item["url"] in seen_urls:
                continue
            seen_urls.add(item["url"])
            results.append(item)
            page_has_new = True

        if page_no > 1 and not page_has_new:
            break

    results.sort(key=lambda x: (x["date"] or now_cn().date(), x["title"]), reverse=True)
    return results
