# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, mark_income_related, now_cn, norm, parse_ymd


YUNNAN_HRSS_CHANNELS = {
    "yunnan_notice": "https://hrss.yn.gov.cn/NewsLsit.aspx?ClassID=558",
    "yunnan_policy": "https://hrss.yn.gov.cn/NewsLsit.aspx?ClassID=560",
}


def _page_url(index_url: str, page_no: int) -> str:
    if page_no <= 1:
        return index_url
    joiner = "&" if "?" in index_url else "?"
    return f"{index_url}{joiner}page={page_no}"


def _parse_item_date(text: str):
    date_obj = parse_ymd(norm(text))
    if not date_obj:
        return None
    return datetime(date_obj.year, date_obj.month, date_obj.day, tzinfo=now_cn().tzinfo)


def _extract_page_items(page_url: str, html: str, now: datetime, since_date):
    soup = BeautifulSoup(html, "html.parser")
    items = []
    newest_dt = None

    for li in soup.select("ul.infoList > li"):
        a_tag = li.find("a", href=True)
        span_tag = li.find("span")
        if not a_tag or not span_tag:
            continue

        title = norm(a_tag.get("title") or a_tag.get_text(" ", strip=True))
        href = norm(a_tag.get("href") or "")
        dt = _parse_item_date(span_tag.get_text(" ", strip=True))
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
                "source": "yunnan_hrss_policy",
            }
        )

    return items, newest_dt


def crawl_yunnan_hrss_policy(current_time: datetime | None = None, max_pages: int = 20) -> list[dict]:
    """抓取云南省人社厅指定两个栏目标题和链接，仅保留近24小时内条目。"""
    now = current_time or now_cn()
    if now.tzinfo is None:
        now = now.replace(tzinfo=now_cn().tzinfo)
    since_date = (now - timedelta(hours=24)).date()

    session = make_session()
    results: list[dict] = []
    seen_urls: set[str] = set()

    for _, index_url in YUNNAN_HRSS_CHANNELS.items():
        first_page_url = _page_url(index_url, 1)
        first_page_first_url = None

        for page_no in range(1, max_pages + 1):
            page_url = _page_url(index_url, page_no)
            try:
                resp = session.get(page_url, timeout=20)
                resp.encoding = resp.apparent_encoding or "utf-8"
                if resp.status_code != 200:
                    break
            except Exception as e:
                print(f"[YunnanHRSS] fetch failed(page={page_no}): {e}")
                break

            page_items, newest_dt = _extract_page_items(page_url, resp.text, now, since_date)
            if not page_items and newest_dt is None:
                break

            if page_no == 1 and page_items:
                first_page_first_url = page_items[0]["url"]
            elif page_no > 1 and first_page_first_url and page_items and page_items[0]["url"] == first_page_first_url:
                # 某些页面对 page 参数不敏感，重复首条时直接停止，避免重复抓取。
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