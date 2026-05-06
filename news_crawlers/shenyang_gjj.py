# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, mark_income_related, now_cn, norm, parse_ymd


SHENYANG_GJJ_ZCFG_INDEX = "https://sygjj.shenyang.gov.cn/zcfg/"
SHENYANG_GJJ_ZCFG_PAGE_FMT = "https://sygjj.shenyang.gov.cn/zcfg/index_{page}.html"

ARTICLE_URL_RE = re.compile(r"^https?://sygjj\.shenyang\.gov\.cn/zcfg/\d{6}/t\d+_\d+\.html$")
DATE_RE = re.compile(r"20\d{2}[-/\.]\d{1,2}[-/\.]\d{1,2}")


def _extract_page_items(page_url: str, html: str, now: datetime, since_date) -> tuple[list[dict], datetime | None]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[dict] = []
    newest_dt: datetime | None = None

    for a in soup.select("a.list-right-con-text[href]"):
        href = norm(a.get("href") or "")
        if not href:
            continue

        full_url = urljoin(page_url, href)
        if not ARTICLE_URL_RE.match(full_url):
            continue

        spans = a.find_all("span")
        title = norm(spans[0].get_text(" ", strip=True) if spans else a.get_text(" ", strip=True))
        if not title:
            continue

        date_text = norm(spans[-1].get_text(" ", strip=True) if len(spans) >= 2 else a.get_text(" ", strip=True))
        m = DATE_RE.search(date_text)
        if not m:
            continue

        d = parse_ymd(m.group(0).replace("/", "-").replace(".", "-"))
        if not d:
            continue

        dt = datetime(d.year, d.month, d.day, tzinfo=now.tzinfo)
        if dt > now:
            continue

        if newest_dt is None or dt > newest_dt:
            newest_dt = dt

        # 列表日期仅到天，按日期窗口近似近24小时。
        if dt.date() < since_date:
            continue

        items.append(
            {
                "title": mark_income_related(title),
                "url": full_url,
                "date": dt.date(),
                "source": "shenyang_gjj_zcfg",
            }
        )

    return items, newest_dt


def crawl_shenyang_gjj_policy(current_time: datetime | None = None, max_pages: int = 8) -> list[dict]:
    """抓取沈阳住房公积金“政策法规”近24小时条目（标题+链接）。"""
    now = current_time or now_cn()
    since_date = (now - timedelta(hours=24)).date()

    s = make_session()
    results: list[dict] = []
    seen_urls: set[str] = set()

    for page in range(1, max_pages + 1):
        page_url = SHENYANG_GJJ_ZCFG_INDEX if page == 1 else SHENYANG_GJJ_ZCFG_PAGE_FMT.format(page=page)

        try:
            r = s.get(page_url, timeout=20)
            r.encoding = r.apparent_encoding or "utf-8"
            if r.status_code != 200:
                break
        except Exception as e:
            print(f"[ShenyangGJJ] fetch failed(page={page}): {e}")
            break

        page_items, newest_dt = _extract_page_items(page_url, r.text, now, since_date)
        if not page_items and newest_dt is None:
            if page == 1:
                print("[ShenyangGJJ] no policy entries found on index page")
            break

        for it in page_items:
            if it["url"] in seen_urls:
                continue
            seen_urls.add(it["url"])
            results.append(it)

        if newest_dt and newest_dt.date() < since_date:
            break

    results.sort(key=lambda x: (x["date"], x["title"]), reverse=True)
    return results
