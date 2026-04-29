# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, mark_income_related, now_cn, norm, parse_ymd


XIZANG_HRSS_INDEX = "https://hrss.xizang.gov.cn/zwgk/xzgfxwj/"
XIZANG_HRSS_PAGE_FMT = "https://hrss.xizang.gov.cn/zwgk/xzgfxwj/index_{page}.html"


def _page_url(page_no: int) -> str:
    if page_no <= 1:
        return XIZANG_HRSS_INDEX
    return XIZANG_HRSS_PAGE_FMT.format(page=page_no - 1)


def _parse_item_date(text: str):
    date_obj = parse_ymd(norm(text))
    if not date_obj:
        return None
    return datetime(date_obj.year, date_obj.month, date_obj.day, tzinfo=now_cn().tzinfo)


def _extract_page_items(page_url: str, html: str, now: datetime, since_date):
    soup = BeautifulSoup(html, "html.parser")
    items = []
    newest_dt = None

    for item in soup.select("div.gl-list-item"):
        a_tag = item.select_one("a.nm[href]")
        date_tag = item.select_one("div.date")
        if not a_tag or not date_tag:
            continue

        title = norm(a_tag.get("title") or a_tag.get_text(" ", strip=True))
        href = norm(a_tag.get("href") or "")
        dt = _parse_item_date(date_tag.get_text(" ", strip=True))
        if not title or not href or not dt:
            continue
        if dt > now:
            continue

        if newest_dt is None or dt > newest_dt:
            newest_dt = dt

        if dt.date() < since_date:
            continue

        items.append(
            {
                "title": mark_income_related(title),
                "url": urljoin(page_url, href),
                "date": dt.date(),
                "source": "xizang_hrss_policy",
            }
        )

    return items, newest_dt


def crawl_xizang_hrss_policy(current_time: datetime | None = None, max_pages: int = 20) -> list[dict]:
    """抓取西藏自治区人社厅行政规范性文件栏目标题和链接，仅保留近24小时内条目。"""
    now = current_time or now_cn()
    if now.tzinfo is None:
        now = now.replace(tzinfo=now_cn().tzinfo)
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
            print(f"[XizangHRSS] fetch failed(page={page_no}): {e}")
            break

        page_items, newest_dt = _extract_page_items(page_url, resp.text, now, since_date)
        if not page_items and newest_dt is None:
            break

        for item in page_items:
            if item["url"] in seen_urls:
                continue
            seen_urls.add(item["url"])
            results.append(item)

        if newest_dt and newest_dt.date() < since_date:
            break

    results.sort(key=lambda x: (x["date"], x["title"]), reverse=True)
    return results