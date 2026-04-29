# -*- coding: utf-8 -*-
# -*- coding: utf-8 -*-
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, mark_income_related, now_cn, norm, parse_ymd


XINJIANG_HRSS_CHANNELS = {
    "xinjiang_zcwj": "https://rst.xinjiang.gov.cn/xjrst/zcwj/zfxxgk_gknrz.shtml",
    "xinjiang_gfxwjm": "https://rst.xinjiang.gov.cn/xjrst/gfxwjm/zfxxgk_gknrz.shtml",
}


def _page_url(index_url: str, page_no: int) -> str:
    if page_no <= 1:
        return index_url
    return index_url.replace(".shtml", f"_{page_no}.shtml", 1)


def _extract_total_pages(html: str) -> int:
    soup = BeautifulSoup(html or "", "html.parser")
    script_text = "\n".join(script.get_text(" ", strip=True) for script in soup.find_all("script"))
    target = html or ""
    combined = f"{target}\n{script_text}"

    for pattern in (
        r"createPageHTML\('page-div',\s*(\d+),\s*(\d+),\s*'zfxxgk_gknrz',\s*'shtml',\s*(\d+)\)",
        r"createPageHTML\('page-div',\s*(\d+),\s*(\d+),\s*\"zfxxgk_gknrz\",\s*\"shtml\",\s*(\d+)\)",
    ):
        match = re.search(pattern, combined, flags=re.I)
        if match:
            try:
                return max(1, int(match.group(1)))
            except Exception:
                return 1
    return 1


def _extract_page_items(page_url: str, html: str, now: datetime, since_date):
    soup = BeautifulSoup(html, "html.parser")
    items = []
    newest_dt = None

    for dd in soup.select("div.gknr_list dl dd"):
        a_tag = dd.find("a", href=True)
        span_tag = dd.find("span")
        if not a_tag or not span_tag:
            continue

        title = norm(a_tag.get("title") or a_tag.get_text(" ", strip=True))
        href = norm(a_tag.get("href") or "")
        date_obj = parse_ymd(norm(span_tag.get_text(" ", strip=True)))
        if not title or not href or not date_obj:
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
                "source": "xinjiang_rst_policy",
            }
        )

    return items, newest_dt


def crawl_xinjiang_rst_policy(current_time: datetime | None = None, max_pages: int = 20) -> list[dict]:
    """抓取新疆人社厅两个政策栏目标题和链接，仅保留近24小时内条目。"""
    now = current_time or now_cn()
    if now.tzinfo is None:
        now = now.replace(tzinfo=now_cn().tzinfo)
    since_date = (now - timedelta(hours=24)).date()

    session = make_session()
    results: list[dict] = []
    seen_urls: set[str] = set()

    for source, index_url in XINJIANG_HRSS_CHANNELS.items():
        total_pages = None
        for page_no in range(1, max_pages + 1):
            if total_pages is not None and page_no > total_pages:
                break

            page_url = _page_url(index_url, page_no)
            try:
                resp = session.get(page_url, timeout=20)
                resp.encoding = resp.apparent_encoding or "utf-8"
                if resp.status_code != 200:
                    break
            except Exception as e:
                print(f"[XinjiangRST] fetch failed({source}, page={page_no}): {e}")
                break

            if page_no == 1:
                total_pages = min(max_pages, _extract_total_pages(resp.text))

            page_items, newest_dt = _extract_page_items(page_url, resp.text, now, since_date)
            if not page_items and newest_dt is None:
                break

            for item in page_items:
                if item["url"] in seen_urls:
                    continue
                seen_urls.add(item["url"])
                item["source"] = source
                results.append(item)

            if newest_dt and newest_dt.date() < since_date:
                break

    results.sort(key=lambda x: (x["date"], x["title"]), reverse=True)
    return results
