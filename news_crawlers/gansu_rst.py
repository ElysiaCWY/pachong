# -*- coding: utf-8 -*-
import os
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, mark_income_related, now_cn, norm, parse_ymd


GANSU_RST_BASE = "https://rst.gansu.gov.cn/rst/c113672/xxgk_xxlist.shtml"


def _build_cookie_dict(cookie_str: str) -> dict[str, str]:
    cookie_map: dict[str, str] = {}
    for seg in (cookie_str or "").split(";"):
        part = seg.strip()
        if not part or "=" not in part:
            continue
        k, v = part.split("=", 1)
        k = k.strip()
        v = v.strip()
        if k:
            cookie_map[k] = v
    return cookie_map


def _request_with_optional_cookie(session, url: str):
    resp = session.get(url, timeout=20)
    if resp.status_code not in (400, 412):
        return resp

    extra_cookie = os.getenv("GANSU_RST_COOKIE", "").strip()
    if not extra_cookie:
        return resp

    cookie_map = _build_cookie_dict(extra_cookie)
    if not cookie_map:
        return resp

    retry_session = make_session()
    retry_session.cookies.update(cookie_map)
    return retry_session.get(
        url,
        timeout=20,
        headers={"Referer": "https://rst.gansu.gov.cn/"},
    )


def _extract_page_items(page_url: str, html: str, now: datetime, since_dt: datetime) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    items = []
    seen = set()

    for a in soup.select("a[href]"):
        href = norm(a.get("href") or "")
        title = norm(a.get_text(" ", strip=True))
        if not href or not title or len(title) < 6:
            continue

        if not href.lower().endswith(".shtml"):
            continue
        if "xxgk_xxlist" in href or "index" in href:
            continue

        full_url = urljoin(page_url, href)
        row_text = norm((a.parent or a).get_text(" ", strip=True))
        m = re.search(r"(20\d{2}[-/.]\d{1,2}[-/.]\d{1,2})", row_text)
        if not m:
            continue

        date_obj = parse_ymd(m.group(1).replace("/", "-").replace(".", "-"))
        if not date_obj:
            continue

        dt = datetime(date_obj.year, date_obj.month, date_obj.day, tzinfo=now.tzinfo)
        if dt > now or dt < since_dt:
            continue

        unique_key = (title, full_url)
        if unique_key in seen:
            continue
        seen.add(unique_key)

        items.append(
            {
                "title": mark_income_related(title),
                "url": full_url,
                "date": dt.date(),
                "source": "gansu_rst_policy",
            }
        )

    return items


def _extract_next_pages(page_url: str, html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    next_pages = []
    seen = set()

    for a in soup.select("a[href]"):
        href = norm(a.get("href") or "")
        if not href:
            continue
        if "xxgk_xxlist" not in href and "index" not in href:
            continue
        if not href.lower().endswith(".shtml"):
            continue

        full_url = urljoin(page_url, href)
        if full_url in seen:
            continue
        seen.add(full_url)
        next_pages.append(full_url)

    return next_pages


def crawl_gansu_rst_policy(current_time: datetime | None = None, max_pages: int = 5) -> list[dict]:
    """抓取甘肃省人社厅政策标题与链接，仅保留近24小时内条目。"""
    now = current_time or now_cn()
    if now.tzinfo is None:
        now = now.replace(tzinfo=now_cn().tzinfo)
    since_dt = now - timedelta(hours=24)

    session = make_session()
    pending_urls = [GANSU_RST_BASE]
    visited = set()
    results: list[dict] = []
    seen_urls: set[str] = set()

    while pending_urls and len(visited) < max_pages:
        page_url = pending_urls.pop(0)
        if page_url in visited:
            continue
        visited.add(page_url)

        try:
            resp = _request_with_optional_cookie(session, page_url)
            resp.encoding = resp.apparent_encoding or "utf-8"
        except Exception as e:
            print(f"[GansuRST] fetch failed({page_url}): {e}")
            continue

        if resp.status_code != 200:
            print(
                "[GansuRST] blocked or unavailable: "
                f"status={resp.status_code}, url={page_url}. "
                "如需本地补充 cookie，可设置环境变量 GANSU_RST_COOKIE。"
            )
            continue

        page_items = _extract_page_items(page_url, resp.text, now, since_dt)
        for it in page_items:
            if it["url"] in seen_urls:
                continue
            seen_urls.add(it["url"])
            results.append(it)

        for next_url in _extract_next_pages(page_url, resp.text):
            if next_url not in visited and next_url not in pending_urls:
                pending_urls.append(next_url)

    results.sort(key=lambda x: (x["date"], x["title"]), reverse=True)
    return results
