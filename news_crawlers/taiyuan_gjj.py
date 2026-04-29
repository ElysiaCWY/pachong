# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, now_cn, norm, parse_ymd, mark_income_related


TAIYUAN_GJJ_TZGG_URL = "https://zfgjj.taiyuan.gov.cn/tzgg.html"


def _parse_list(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    items: list[dict] = []

    for li in soup.select("li"):
        date_span = li.find("span")
        a = li.find("a", href=True)
        if not date_span or not a:
            continue

        date_text = norm(date_span.get_text())
        article_date = parse_ymd(date_text)
        if not article_date:
            continue

        href = a.get("href") or ""
        if not href or href.startswith("javascript:"):
            continue

        title = norm(a.get("title") or a.get_text())
        if not title:
            continue

        items.append(
            {
                "title": mark_income_related(title),
                "url": urljoin(TAIYUAN_GJJ_TZGG_URL, href),
                "date": article_date,
                "source": "通知公告",
            }
        )

    seen = set()
    uniq = []
    for it in items:
        key = (it["title"], it["url"], it["date"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(it)
    return uniq


def crawl_taiyuan_gjj_policy(current_time: datetime | None = None, max_pages: int = 5) -> list[dict]:
    """抓取太原住房公积金中心通知公告（近24小时）。"""
    now = current_time or now_cn()
    since = now - timedelta(days=1)
    session = make_session()
    results: list[dict] = []

    for page in range(1, max_pages + 1):
        if page == 1:
            url = TAIYUAN_GJJ_TZGG_URL
        else:
            url = TAIYUAN_GJJ_TZGG_URL.replace("tzgg.html", f"tzgg_{page}.html")

        try:
            resp = session.get(url, timeout=15)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or "utf-8"
        except Exception as e:
            print(f"[Taiyuan GJJ] fetch error {url}: {e}")
            break

        items = _parse_list(resp.text)
        if not items:
            break

        page_keep = [it for it in items if it["date"] >= since.date()]
        results.extend(page_keep)

        if len(page_keep) < len(items):
            break

    seen_urls = set()
    uniq_results = []
    for it in results:
        if it["url"] in seen_urls:
            continue
        seen_urls.add(it["url"])
        uniq_results.append(it)

    return uniq_results
