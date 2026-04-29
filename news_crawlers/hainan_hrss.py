# -*- coding: utf-8 -*-
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, mark_income_related, now_cn, norm, parse_ymd


HAINAN_HRSS_BASE = "https://hrss.hainan.gov.cn/hrss/0503/"
HAINAN_HRSS_INDEX = "https://hrss.hainan.gov.cn/hrss/0503/list3.shtml?ddtab=true"


def _page_url(page_no: int) -> str:
    if page_no <= 1:
        return HAINAN_HRSS_INDEX
    return urljoin(HAINAN_HRSS_BASE, f"list3_{page_no}.shtml?ddtab=true")


def _parse_page_count(html: str) -> int:
    match = re.search(r"createPageHTML\('page_div',\s*(\d+),\s*1,'list3','shtml',\d+\)", html)
    if not match:
        return 1
    try:
        return max(1, int(match.group(1)))
    except Exception:
        return 1


def _clean_title(text: str) -> str:
    title = norm(text)
    return re.sub(r"^[·•\s]+", "", title)


def _parse_date(text: str):
    date_obj = parse_ymd(norm(text))
    if not date_obj:
        return None
    return datetime(date_obj.year, date_obj.month, date_obj.day, tzinfo=now_cn().tzinfo)


def _extract_page_items(page_url: str, html: str, now: datetime, since_date):
    soup = BeautifulSoup(html, "html.parser")
    items = []
    hit_older = False

    for card in soup.select("div.list-right_title.fon_1"):
        container = card.parent
        a_tag = card.find("a", href=True)
        if not a_tag:
            continue

        title = _clean_title(a_tag.get("title") or a_tag.get_text(" ", strip=True))
        href = norm(a_tag.get("href") or "")
        container_text = container.get_text(" ", strip=True) if container else card.get_text(" ", strip=True)
        date_match = re.search(r"(20\d{2}-\d{2}-\d{2})", container_text)
        dt = _parse_date(date_match.group(1) if date_match else "")

        if not title or not href or not dt:
            continue
        if dt > now:
            continue
        if dt.date() < since_date:
            hit_older = True
            continue

        items.append(
            {
                "title": mark_income_related(title),
                "url": urljoin(page_url, href),
                "date": dt.date(),
                "source": "hainan_hrss_policy",
            }
        )

    return items, hit_older


def crawl_hainan_hrss_policy(current_time: datetime | None = None, max_pages: int | None = None) -> list[dict]:
    """抓取海南省人社厅部门文件标题和链接，仅保留近24小时内条目。"""
    now = current_time or now_cn()
    if now.tzinfo is None:
        now = now.replace(tzinfo=now_cn().tzinfo)
    since_date = (now - timedelta(hours=24)).date()

    session = make_session()
    try:
        first_resp = session.get(HAINAN_HRSS_INDEX, timeout=20)
        first_resp.encoding = first_resp.apparent_encoding or "utf-8"
        if first_resp.status_code != 200:
            print(f"[HainanHRSS] HTTP Error {first_resp.status_code}")
            return []
    except Exception as e:
        print(f"[HainanHRSS] fetch failed: {e}")
        return []

    page_count = _parse_page_count(first_resp.text)
    if max_pages is not None:
        page_count = min(page_count, max_pages)

    results = []
    seen_urls = set()

    for page_no in range(1, page_count + 1):
        page_url = _page_url(page_no)
        if page_no == 1:
            html = first_resp.text
        else:
            try:
                resp = session.get(page_url, timeout=20)
                resp.encoding = resp.apparent_encoding or "utf-8"
                if resp.status_code != 200:
                    break
                html = resp.text
            except Exception as e:
                print(f"[HainanHRSS] fetch failed(page={page_no}): {e}")
                break

        page_items, hit_older = _extract_page_items(page_url, html, now, since_date)
        for item in page_items:
            if item["url"] in seen_urls:
                continue
            seen_urls.add(item["url"])
            results.append(item)

        if hit_older:
            break

    results.sort(key=lambda x: (x["date"], x["title"]), reverse=True)
    return results