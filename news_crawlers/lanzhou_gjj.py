# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, mark_income_related, now_cn, norm, parse_ymd


LANZHOU_GJJ_INDEX = "https://gjj.lanzhou.gov.cn/col/col269/index.html"


def _page_url(page_no: int) -> str:
    if page_no <= 1:
        return LANZHOU_GJJ_INDEX
    return f"https://gjj.lanzhou.gov.cn/col/col269/index_{page_no}.html"


def _parse_dt(text: str):
    text = norm(text)
    if not text:
        return None

    for fmt, width in (
        ("%Y-%m-%d %H:%M:%S", 19),
        ("%Y-%m-%d %H:%M", 16),
        ("%Y-%m-%d", 10),
    ):
        try:
            dt = datetime.strptime(text[:width], fmt)
            return dt
        except Exception:
            continue

    m = parse_ymd(text[:10].replace("/", "-").replace(".", "-"))
    if m:
        return datetime(m.year, m.month, m.day)
    return None


def _to_aware(dt: datetime | None, tzinfo):
    if not dt:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=tzinfo)


def _extract_page_items(page_url: str, html: str, now: datetime, since_dt: datetime):
    html = html or ""
    soup = BeautifulSoup(html, "html.parser")
    items: list[dict] = []
    newest_dt: datetime | None = None

    record_blocks = re.findall(r"<record><!\[CDATA\[(.*?)\]\]></record>", html, re.S)
    for block in record_blocks:
        soup = BeautifulSoup(block, "html.parser")
        a_tag = soup.find("a", href=True)
        if not a_tag:
            continue

        href = norm(a_tag.get("href") or "")
        title = norm(a_tag.get("title") or a_tag.get_text(" ", strip=True))
        if not href or not title or title in {"首页", "上页", "下页", "尾页"}:
            continue
        if len(title) < 6:
            continue

        full_url = urljoin(page_url, href)
        if "gjj.lanzhou.gov.cn" not in full_url:
            continue
        if not full_url.lower().endswith((".shtml", ".html")):
            continue

        td_tags = soup.find_all("td")
        date_text = td_tags[-1].get_text(" ", strip=True) if td_tags else soup.get_text(" ", strip=True)
        dt = _to_aware(_parse_dt(date_text), now.tzinfo)
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
                "url": full_url,
                "date": dt,
                "source": "lanzhou_gjj_policy",
            }
        )

    if items:
        return items, newest_dt

    for row in soup.select("tr"):
        a_tag = row.find("a", href=True)
        if not a_tag:
            continue

        href = norm(a_tag.get("href") or "")
        title = norm(a_tag.get_text(" ", strip=True))
        if not href or not title or title in {"首页", "上页", "下页", "尾页"}:
            continue
        if len(title) < 6:
            continue

        full_url = urljoin(page_url, href)
        if "gjj.lanzhou.gov.cn" not in full_url:
            continue
        if not full_url.lower().endswith((".shtml", ".html")):
            continue

        row_text = norm(row.get_text(" ", strip=True))
        dt = _to_aware(_parse_dt(row_text), now.tzinfo)
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
                "url": full_url,
                "date": dt,
                "source": "lanzhou_gjj_policy",
            }
        )

    return items, newest_dt


def crawl_lanzhou_gjj_policy(current_time: datetime | None = None, max_pages: int = 5) -> list[dict]:
    """抓取兰州住房公积金管理中心政策法规栏目，仅保留近24小时内条目。"""
    now = current_time or now_cn()
    if now.tzinfo is None:
        now = now.replace(tzinfo=now_cn().tzinfo)
    since_dt = now - timedelta(hours=24)

    session = make_session()
    results: list[dict] = []
    seen_urls: set[str] = set()

    for page_no in range(1, max_pages + 1):
        page_url = _page_url(page_no)
        try:
            resp = session.get(page_url, timeout=20)
            resp.encoding = resp.apparent_encoding or "utf-8"
        except Exception as e:
            print(f"[LanzhouGJJ] fetch failed(page={page_no}): {e}")
            break

        if resp.status_code != 200:
            break

        page_items, newest_dt = _extract_page_items(page_url, resp.text, now, since_dt)
        if not page_items and newest_dt is None:
            if page_no == 1:
                print("[LanzhouGJJ] no policy entries found on index page")
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