# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, now_cn, norm, parse_ymd, mark_income_related


CQ_GJJ_GSGG_URL = "https://www.cqgjj.cn/info/iList.jsp?cat_id=11366"


def _parse_list(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    items: list[dict] = []

    for li in soup.select("li"):
        span = li.find("span")
        a = li.find("a", href=True)
        if not span or not a:
            continue

        date_text = norm(span.get_text())
        article_date = parse_ymd(date_text)
        if not article_date:
            continue

        href = a.get("to-href") or a.get("href") or ""
        if not href or href.startswith("javascript:"):
            continue

        title = norm(a.get("title") or a.get_text())
        if not title:
            continue

        items.append(
            {
                "title": mark_income_related(title),
                "url": urljoin(CQ_GJJ_GSGG_URL, href),
                "date": article_date,
                "source": "公示公告",
            }
        )

    # 去掉导航等重复节点，仅保留真正文章链接
    seen = set()
    uniq = []
    for it in items:
        key = (it["title"], it["url"], it["date"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(it)
    return uniq


def crawl_cqgjj_gsgg(current_time: datetime | None = None, max_pages: int = 4) -> list[dict]:
    """抓取重庆公积金中心公示公告（近24小时）。"""
    now = current_time or now_cn()
    since = now - timedelta(days=1)
    session = make_session()
    results: list[dict] = []

    for page in range(1, max_pages + 1):
        url = CQ_GJJ_GSGG_URL if page == 1 else f"{CQ_GJJ_GSGG_URL}&cur_page={page}"
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
        resp.encoding = "utf-8"

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
