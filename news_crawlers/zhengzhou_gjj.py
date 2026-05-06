# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, mark_income_related, now_cn, norm, parse_ymd


ZHENGZHOU_GJJ_LAW_INDEX = "https://public.zhengzhou.gov.cn/?a=info&k=law&t=path&i=01&d=49"
ZHENGZHOU_GJJ_LAW_PAGE_FMT = "https://public.zhengzhou.gov.cn/?a=info&k=law&t=path&i=01&d=49&page={page}"

ARTICLE_URL_RE = re.compile(r"^https?://public\.zhengzhou\.gov\.cn/[A-Za-z0-9]+/\d+\.jhtml$")
DATE_RE = re.compile(r"20\d{2}[-/\.]\d{1,2}[-/\.]\d{1,2}")


def _extract_page_items(page_url: str, html: str, now: datetime, since_date) -> tuple[list[dict], datetime | None]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[dict] = []
    newest_dt: datetime | None = None

    blocks = soup.select("ul.common-list > a[href]")
    if not blocks:
        blocks = soup.find_all("a", href=True)

    for a in blocks:
        href = norm(a.get("href") or "")
        if not href:
            continue

        full_url = urljoin(page_url, href)
        if not ARTICLE_URL_RE.match(full_url):
            continue

        title = norm(a.find("span").get_text(" ", strip=True) if a.find("span") else a.get_text(" ", strip=True))
        if not title:
            continue

        date_text = norm(a.find("em").get_text(" ", strip=True) if a.find("em") else a.get_text(" ", strip=True))
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
                "source": "zhengzhou_gjj_law",
            }
        )

    return items, newest_dt


def crawl_zhengzhou_gjj_law(current_time: datetime | None = None, max_pages: int = 8) -> list[dict]:
    """抓取郑州住房公积金中心“行政规范性文件”近24小时条目（标题+链接）。"""
    now = current_time or now_cn()
    since_date = (now - timedelta(hours=24)).date()

    s = make_session()
    results: list[dict] = []
    seen_urls: set[str] = set()

    for page in range(1, max_pages + 1):
        page_url = ZHENGZHOU_GJJ_LAW_INDEX if page == 1 else ZHENGZHOU_GJJ_LAW_PAGE_FMT.format(page=page)

        try:
            r = s.get(page_url, timeout=20)
            r.encoding = r.apparent_encoding or "utf-8"
            if r.status_code != 200:
                break
        except Exception as e:
            print(f"[ZhengzhouGJJ] fetch failed(page={page}): {e}")
            break

        page_items, newest_dt = _extract_page_items(page_url, r.text, now, since_date)
        if not page_items and newest_dt is None:
            if page == 1:
                print("[ZhengzhouGJJ] no law entries found on index page")
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
