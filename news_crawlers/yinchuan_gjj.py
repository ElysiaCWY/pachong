# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, mark_income_related, now_cn, norm, parse_ymd


YINCHUAN_GJJ_INDEX = "https://gjj.yinchuan.gov.cn/zcfg.htm"


def _page_url(page_no: int) -> str:
    if page_no <= 1:
        return YINCHUAN_GJJ_INDEX
    return f"https://gjj.yinchuan.gov.cn/zcfg/{page_no}.htm"


def _extract_date(text: str):
    text = norm(text)
    if not text:
        return None

    m = re.search(r"20\d{2}-\d{2}-\d{2}", text)
    if not m:
        return None
    return parse_ymd(m.group(0))


def _extract_page_items(page_url: str, html: str, now: datetime, since_date):
    soup = BeautifulSoup(html or "", "html.parser")
    items: list[dict] = []
    newest_date = None

    for a_tag in soup.find_all("a", href=True):
        href = norm(a_tag.get("href") or "")
        if not href:
            continue

        full_url = urljoin(page_url, href)
        if "gjj.yinchuan.gov.cn/info/1025/" not in full_url:
            continue
        if not full_url.lower().endswith((".htm", ".html")):
            continue

        title = norm(a_tag.get("title") or a_tag.get_text(" ", strip=True))
        if not title or len(title) < 6:
            continue
        if title in {"首页", "上页", "下页", "尾页"}:
            continue

        parent_text = norm(a_tag.parent.get_text(" ", strip=True)) if a_tag.parent else ""
        date_obj = _extract_date(a_tag.get("title") or parent_text)
        if not date_obj:
            continue

        if newest_date is None or date_obj > newest_date:
            newest_date = date_obj

        if date_obj < since_date:
            continue

        items.append(
            {
                "title": mark_income_related(title),
                "url": full_url,
                "date": date_obj,
                "source": "yinchuan_gjj_policy",
            }
        )

    return items, newest_date


def crawl_yinchuan_gjj_policy(current_time: datetime | None = None, max_pages: int = 3) -> list[dict]:
    """抓取银川住房公积金管理中心政策法规栏目，仅保留近24小时内条目。"""
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
        except Exception as e:
            print(f"[YinchuanGJJ] fetch failed(page={page_no}): {e}")
            break

        if resp.status_code != 200:
            break

        page_items, newest_date = _extract_page_items(page_url, resp.text, now, since_date)
        if not page_items and newest_date is None:
            if page_no == 1:
                print("[YinchuanGJJ] no policy entries found on index page")
            break

        for item in page_items:
            if item["url"] in seen_urls:
                continue
            seen_urls.add(item["url"])
            results.append(item)

        if newest_date and newest_date < since_date:
            break

    results.sort(key=lambda x: (x["date"], x["title"]), reverse=True)
    return results