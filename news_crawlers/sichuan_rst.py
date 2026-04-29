# -*- coding: utf-8 -*-
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, mark_income_related, now_cn, norm


SICHUAN_RST_CHANNELS = {
    "sichuan_zcfgqt": "https://rst.sc.gov.cn/rst/zcfgqt/zfxxgkpage2023.shtml",
    "sichuan_xzgfxwj": "https://rst.sc.gov.cn/rst/xzgfxwj/zfxxgkpagegfwj2023.shtml",
}


def _page_url(index_url: str, page_no: int) -> str:
    if page_no <= 1:
        return index_url
    return index_url.replace(".shtml", f"_{page_no}.shtml", 1)


def _parse_article_dt(text: str):
    text = norm(text)
    if not text:
        return None

    m = re.search(r"(20\d{2})[年/-](\d{1,2})[月/-](\d{1,2})日?", text)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=now_cn().tzinfo)
        except Exception:
            return None

    m = re.search(r"(\d{10,13})", text)
    if m:
        try:
            stamp = int(m.group(1))
            if len(m.group(1)) == 10:
                stamp *= 1000
            return datetime.fromtimestamp(stamp / 1000.0, tz=now_cn().tzinfo)
        except Exception:
            return None

    return None


def _extract_page_items(page_url: str, html: str, now: datetime, since_dt: datetime):
    soup = BeautifulSoup(html, "html.parser")
    items = []
    newest_dt = None

    for row in soup.select("div.biaobody ul li"):
        link = row.select_one("div.lie2 a[href]") or row.find("a", href=True)
        if not link:
            continue

        href = norm(link.get("href") or "")
        title = norm(link.get("title") or link.get_text(" ", strip=True))
        if not href or not title:
            continue

        dt_tag = row.select_one("div.lie4")
        dt_text = dt_tag.get_text(" ", strip=True) if dt_tag else row.get_text(" ", strip=True)
        dt = _parse_article_dt(dt_text)
        if not dt:
            continue
        if dt > now:
            continue

        if newest_dt is None or dt > newest_dt:
            newest_dt = dt

        if dt < since_dt:
            continue

        items.append(
            {
                "title": mark_income_related(title),
                "url": urljoin(page_url, href),
                "date": dt.date(),
                "source": "sichuan_rst_policy",
            }
        )

    return items, newest_dt


def crawl_sichuan_rst_policy(current_time: datetime | None = None, max_pages: int = 20) -> list[dict]:
    """抓取四川省人社厅两个政策栏目标题和链接，仅保留近24小时内条目。"""
    now = current_time or now_cn()
    if now.tzinfo is None:
        now = now.replace(tzinfo=now_cn().tzinfo)
    since_dt = now - timedelta(hours=24)

    session = make_session()
    results: list[dict] = []
    seen_urls: set[str] = set()

    for _, index_url in SICHUAN_RST_CHANNELS.items():
        for page_no in range(1, max_pages + 1):
            page_url = _page_url(index_url, page_no)
            try:
                resp = session.get(page_url, timeout=20)
                resp.encoding = resp.apparent_encoding or "utf-8"
                if resp.status_code != 200:
                    break
            except Exception as e:
                print(f"[SichuanRST] fetch failed(page={page_no}): {e}")
                break

            page_items, newest_dt = _extract_page_items(page_url, resp.text, now, since_dt)
            if not page_items and newest_dt is None:
                break

            for item in page_items:
                if item["url"] in seen_urls:
                    continue
                seen_urls.add(item["url"])
                results.append(item)

            if newest_dt and newest_dt < since_dt:
                break

    results.sort(key=lambda x: (x["date"], x["title"]), reverse=True)
    return results