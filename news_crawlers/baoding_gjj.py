# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, mark_income_related, now_cn, norm, parse_ymd


BAODING_GJJ_INDEX = "https://bdgjj.baoding.gov.cn/zxwj/index.jhtml"
ARTICLE_RE = re.compile(r"^https?://bdgjj\.baoding\.gov\.cn(?::80)?/zxwj/\d+\.jhtml$")


def _page_url(page_no: int) -> str:
    if page_no <= 1:
        return BAODING_GJJ_INDEX
    return f"https://bdgjj.baoding.gov.cn/zxwj/index_{page_no}.jhtml"


def _parse_page_items(page_url: str, html: str, now: datetime, since_date) -> tuple[list[dict], bool]:
    soup = BeautifulSoup(html or "", "html.parser")
    items: list[dict] = []
    newest_date = None
    has_older_item = False

    for li in soup.find_all("li"):
        a = li.find("a", href=True)
        if not a:
            continue

        href = norm(a.get("href") or "")
        if not href:
            continue

        full_url = urljoin(page_url, href)
        if not ARTICLE_RE.match(full_url):
            continue

        title = norm(a.get_text(" ", strip=True))
        if not title:
            continue

        # 日期块通常是：<div class="ejyright-time2">06</div><div class="ejyright-time1">2026-05</div>
        day_text = ""
        ym_text = ""
        time2 = li.select_one(".ejyright-time2")
        time1 = li.select_one(".ejyright-time1")
        if time2:
            day_text = norm(time2.get_text(" ", strip=True))
        if time1:
            ym_text = norm(time1.get_text(" ", strip=True))

        dt = None
        if day_text and ym_text:
            m = re.match(r"^(20\d{2})-(\d{1,2})$", ym_text)
            if m:
                date_text = f"{m.group(1)}-{int(m.group(2)):02d}-{int(day_text):02d}"
                dt = parse_ymd(date_text)

        # 兜底：从整条文本里找日期
        if not dt:
            txt = norm(li.get_text(" ", strip=True))
            m = re.search(r"(20\d{2}-\d{1,2}-\d{1,2})", txt)
            if m:
                dt = parse_ymd(m.group(1))

        if not dt:
            continue

        if dt > now.date():
            continue

        if newest_date is None or dt > newest_date:
            newest_date = dt

        if dt < since_date:
            has_older_item = True
            continue

        items.append(
            {
                "title": mark_income_related(title),
                "url": full_url,
                "date": dt,
                "source": "baoding_gjj_zxwj",
            }
        )

    return items, has_older_item


def crawl_baoding_gjj_zxwj(current_time: datetime | None = None, max_pages: int = 6) -> list[dict]:
    """抓取保定公积金中心文件，仅保留近24小时内发布的标题和链接。"""
    now = current_time or now_cn()
    since_date = (now - timedelta(days=1)).date()
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
            print(f"[BaodingGJJ] fetch failed(page={page_no}): {e}")
            break

        page_items, has_older_item = _parse_page_items(page_url, resp.text, now, since_date)
        if not page_items and page_no == 1:
            break

        for item in page_items:
            if item["url"] in seen_urls:
                continue
            seen_urls.add(item["url"])
            results.append(item)

        if has_older_item:
            break

    results.sort(key=lambda x: (x.get("date") or now.date(), x.get("title", "")), reverse=True)
    return results
