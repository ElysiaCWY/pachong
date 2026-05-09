# -*- coding: utf-8 -*-
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, mark_income_related, now_cn, norm


CANGZHOU_GJJ_INDEX = "https://gjj.cangzhou.gov.cn/gjj/c121054/listDisplaySelf.shtml"
ARTICLE_RE = re.compile(r"^https?://gjj\.cangzhou\.gov\.cn/gjj/c121054/\d{6,}\.shtml$")
DATE_RE = re.compile(r"(20\d{2}-\d{2}-\d{2})")


def _page_url(page_no: int) -> str:
    if page_no <= 1:
        return CANGZHOU_GJJ_INDEX
    return f"https://gjj.cangzhou.gov.cn/gjj/c121054/listDisplaySelf_{page_no}.shtml"


def _parse_page_items(page_url: str, html: str, now: datetime, since_date) -> tuple[list[dict], bool]:
    soup = BeautifulSoup(html or "", "html.parser")
    results: list[dict] = []
    newest_date = None
    has_older_item = False

    for li in soup.select("ul.infolist li"):
        a = li.find("a", href=True)
        if not a:
            continue

        href = norm(a.get("href") or "")
        if not href:
            continue

        full_url = urljoin(page_url, href)
        if not ARTICLE_RE.match(full_url):
            continue

        title = norm(a.get_text(" ", strip=True) or a.get("title") or "")
        if not title:
            continue

        li_text = norm(li.get_text(" ", strip=True))
        m = DATE_RE.search(li_text)
        if not m:
            continue

        dt = datetime.strptime(m.group(1), "%Y-%m-%d")
        if now.tzinfo is not None:
            dt = dt.replace(tzinfo=now.tzinfo)

        if dt > now:
            continue

        if newest_date is None or dt > newest_date:
            newest_date = dt

        if dt.date() < since_date:
            has_older_item = True
            continue

        results.append(
            {
                "title": mark_income_related(title),
                "url": full_url,
                "date": dt,
                "source": "cangzhou_gjj_announcement",
            }
        )

    return results, has_older_item


def crawl_cangzhou_gjj_announcement(current_time: datetime | None = None, max_pages: int = 6) -> list[dict]:
    """抓取沧州公积金通知公告，仅保留近24小时内发布的标题和链接。"""
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
            print(f"[CangzhouGJJ] fetch failed(page={page_no}): {e}")
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

    results.sort(key=lambda x: (x.get("date") or now, x.get("title", "")), reverse=True)
    return results
