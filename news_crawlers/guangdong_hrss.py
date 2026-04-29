# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, now_cn, norm, parse_ymd, mark_income_related


GD_HRSS_POLICY_CHANNELS = {
    "guangdong_gfxwj": "https://hrss.gd.gov.cn/zwgk/xxgkml/bmwj/gfxwj/index.html",
    "guangdong_qtwj_shbz": "https://hrss.gd.gov.cn/zwgk/xxgkml/bmwj/qtwj/shbz/index.html",
}


def _page_url(index_url: str, page: int) -> str:
    if page <= 1:
        return index_url
    return index_url.replace("index.html", f"index_{page}.html")


def _extract_page_items(index_url: str, html: str, source: str, now: datetime, since_date) -> tuple[list[dict], datetime | None]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[dict] = []
    newest_dt: datetime | None = None

    for li in soup.select("ul.list li"):
        a_tag = li.select_one("a[href]")
        d_tag = li.select_one("span.pubDate")
        if not a_tag or not d_tag:
            continue

        title = norm(a_tag.get("title") or a_tag.get_text(" ", strip=True))
        href = norm(a_tag.get("href") or "")
        dt = parse_ymd(norm(d_tag.get_text(" ", strip=True)))
        if not title or not href or not dt:
            continue
        if dt > now.date():
            continue

        dtz = datetime(dt.year, dt.month, dt.day, tzinfo=now.tzinfo)
        if newest_dt is None or dtz > newest_dt:
            newest_dt = dtz

        if dt < since_date:
            continue

        items.append(
            {
                "title": mark_income_related(title),
                "url": urljoin(index_url, href),
                "date": dt,
                "source": source,
            }
        )

    return items, newest_dt


def _crawl_channel(session, source: str, index_url: str, now: datetime, since_date, max_pages: int = 30) -> list[dict]:
    results: list[dict] = []
    seen_urls: set[str] = set()

    for page in range(1, max_pages + 1):
        page_url = _page_url(index_url, page)
        try:
            resp = session.get(page_url, timeout=20)
            resp.encoding = resp.apparent_encoding or "utf-8"
            if resp.status_code != 200:
                break
        except Exception as e:
            print(f"[GuangdongHRSS] fetch failed({source}, p{page}): {e}")
            break

        page_items, newest_dt = _extract_page_items(index_url, resp.text, source, now, since_date)
        if not page_items and newest_dt is None:
            break

        for it in page_items:
            if it["url"] in seen_urls:
                continue
            seen_urls.add(it["url"])
            results.append(it)

        # 列表按发布时间倒序，若当前页最新日期已早于窗口，可提前停止翻页
        if newest_dt and newest_dt.date() < since_date:
            break

    return results


def crawl_guangdong_hrss_policy(current_time: datetime | None = None) -> list[dict]:
    """
    抓取广东省人社厅政策栏目：
    1) 规范性文件
    2) 其它文件-社会保障

    仅保留近24小时发布（按日期粒度）的标题与链接。
    """
    now = current_time or now_cn()
    since_date = (now - timedelta(hours=24)).date()

    session = make_session()
    results: list[dict] = []
    seen_urls: set[str] = set()

    for source, index_url in GD_HRSS_POLICY_CHANNELS.items():
        try:
            channel_items = _crawl_channel(session, source, index_url, now, since_date)
        except Exception as e:
            print(f"[GuangdongHRSS] crawl failed({source}): {e}")
            continue

        for it in channel_items:
            if it["url"] in seen_urls:
                continue
            seen_urls.add(it["url"])
            results.append(it)

    results.sort(key=lambda x: (x["date"], x["title"]), reverse=True)
    return results
