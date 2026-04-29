# -*- coding: utf-8 -*-
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, mark_income_related, now_cn, norm, parse_ymd


CHONGQING_HRSS_INDEX = "https://rlsbj.cq.gov.cn/zwgk_182/zfxxgkml/zcwj_145360/jfxzgfxwj/index.html"
CHONGQING_HRSS_PAGE_FMT = "https://rlsbj.cq.gov.cn/zwgk_182/zfxxgkml/zcwj_145360/jfxzgfxwj/index_{page}.html"


def _page_url(page_no: int) -> str:
    if page_no <= 1:
        return CHONGQING_HRSS_INDEX
    return CHONGQING_HRSS_PAGE_FMT.format(page=page_no - 1)


def _parse_article_dt(text: str):
    match = re.search(r"20\d{2}[年/-]\d{1,2}[月/-]\d{1,2}日?", norm(text or ""))
    if not match:
        return None

    date_text = match.group(0).replace("年", "-").replace("月", "-").replace("日", "")
    parsed = parse_ymd(date_text)
    if not parsed:
        return None
    return datetime(parsed.year, parsed.month, parsed.day, tzinfo=now_cn().tzinfo)


def _extract_page_items(page_url: str, html: str, now: datetime, since_date):
    soup = BeautifulSoup(html, "html.parser")
    items = []
    newest_dt = None

    for row in soup.select("tr.zcwjk-list-c"):
        title_tag = row.select_one("td.title a[href] p.tit")
        link_tag = row.select_one("td.title a[href]")
        time_tag = row.select_one("span.time")
        if not title_tag or not link_tag or not time_tag:
            continue

        title = norm(title_tag.get_text(" ", strip=True))
        href = norm(link_tag.get("href") or "")
        dt = _parse_article_dt(time_tag.get_text(" ", strip=True))
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
                "source": "chongqing_hrss_policy",
            }
        )

    return items, newest_dt


def crawl_chongqing_hrss_policy(current_time: datetime | None = None, max_pages: int = 20) -> list[dict]:
    """抓取重庆市人社局行政规范性文件栏目标题和链接，仅保留近24小时条目。"""
    now = current_time or now_cn()
    if now.tzinfo is None:
        now = now.replace(tzinfo=now_cn().tzinfo)
    since_date = (now - timedelta(hours=24)).date()

    session = make_session()
    results = []
    seen_urls = set()

    for page_no in range(1, max_pages + 1):
        page_url = _page_url(page_no)
        try:
            resp = session.get(page_url, timeout=20)
            resp.encoding = resp.apparent_encoding or "utf-8"
            if resp.status_code != 200:
                break
        except Exception as e:
            print(f"[ChongqingHRSS] fetch failed(page={page_no}): {e}")
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