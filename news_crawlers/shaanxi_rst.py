# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, mark_income_related, now_cn, norm, parse_ymd


SHAANXI_RST_INDEX = "https://rst.shaanxi.gov.cn/zcfg/zcfgsjk/gfxwj/jy/index.html"
SHAANXI_RST_PAGE_FMT = "https://rst.shaanxi.gov.cn/zcfg/zcfgsjk/gfxwj/jy/index_{page}.html"


def _page_url(page_no: int) -> str:
    if page_no <= 1:
        return SHAANXI_RST_INDEX
    return SHAANXI_RST_PAGE_FMT.format(page=page_no - 1)


def _extract_page_items(page_url: str, html: str, now: datetime, since_date):
    soup = BeautifulSoup(html, "html.parser")
    items = []
    newest_dt = None

    for li in soup.select("ul.list li.list-item"):
        a_tag = li.select_one("a.clearfix[href]")
        title_tag = li.select_one("a.clearfix .text")
        date_tag = li.select_one("a.clearfix .time")
        if not a_tag or not title_tag or not date_tag:
            continue

        href = norm(a_tag.get("href") or "")
        title = norm(title_tag.get_text(" ", strip=True))
        date_obj = parse_ymd(norm(date_tag.get_text(" ", strip=True)))
        if not href or not title or not date_obj:
            continue

        dt = datetime(date_obj.year, date_obj.month, date_obj.day, tzinfo=now.tzinfo)
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
                "source": "shaanxi_rst_policy",
            }
        )

    return items, newest_dt


def crawl_shaanxi_rst_policy(current_time: datetime | None = None, max_pages: int = 20) -> list[dict]:
    """抓取陕西省人社厅规范性文件-就业栏目标题和链接，仅保留近24小时内条目。"""
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
            print(f"[ShaanxiRST] fetch failed(page={page_no}): {e}")
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