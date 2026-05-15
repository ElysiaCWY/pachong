# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from urllib.parse import urljoin
import re

from bs4 import BeautifulSoup

from .common import make_session, mark_income_related, now_cn, norm, parse_ymd


ANSHAN_GJJ_ZWGK_INDEX = "https://asgjj.anshan.gov.cn:1433/zwgk/index.jhtml"


def _page_url(page_no: int) -> str:
    if page_no <= 1:
        return ANSHAN_GJJ_ZWGK_INDEX
    return f"https://asgjj.anshan.gov.cn:1433/zwgk/index_{page_no}.jhtml"


def _extract_page_items(page_url: str, html: str, now: datetime, since_date) -> tuple[list[dict], bool]:
    soup = BeautifulSoup(html or "", "html.parser")
    items: list[dict] = []
    hit_older = False

    for li in soup.select("div.ejyright-grayboxcon ul li"):
        a_tag = li.select_one("a[href]")
        date_tag = li.select_one("span.spantime")
        if not a_tag or not date_tag:
            continue

        title = norm(a_tag.get("title") or a_tag.get_text(" ", strip=True))
        href = norm(a_tag.get("href") or "")
        if not title or not href:
            continue

        dt = parse_ymd(date_tag.get_text(" ", strip=True))
        if not dt:
            continue
        if dt > now.date():
            continue
        if dt < since_date:
            hit_older = True
            continue

        items.append(
            {
                "title": mark_income_related(title),
                "url": urljoin(page_url, href),
                "date": dt,
                "source": "anshan_gjj_zwgk",
            }
        )

    return items, hit_older


def crawl_anshan_gjj_zwgk(current_time: datetime | None = None, max_pages: int = 13) -> list[dict]:
    """抓取鞍山市住房公积金管理中心信息公开栏目，仅保留近24小时内条目。"""
    now = current_time or now_cn()
    since_date = (now - timedelta(hours=24)).date()

    session = make_session()
    results: list[dict] = []
    seen_urls: set[str] = set()

    for page_no in range(1, max_pages + 1):
        page_url = _page_url(page_no)
        try:
            resp = session.get(page_url, timeout=20)
            resp.encoding = resp.apparent_encoding or "utf-8"
            if resp.status_code != 200:
                break
        except Exception as e:
            print(f"[AnshanGJJ] fetch failed(page={page_no}): {e}")
            break

        page_items, hit_older = _extract_page_items(page_url, resp.text, now, since_date)
        if not page_items and page_no == 1:
            break

        for it in page_items:
            if it["url"] in seen_urls:
                continue
            seen_urls.add(it["url"])
            results.append(it)

        if hit_older:
            break

    results.sort(key=lambda x: (x["date"], x["title"]), reverse=True)
    return results