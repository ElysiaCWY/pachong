# -*- coding: utf-8 -*-
import os
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, mark_income_related, now_cn, norm, parse_ymd


GUIYANG_GJJ_BASE = "https://gjj.guiyang.gov.cn/zfxxgk/fdzdgknr/fdzdgknrfggw/fggwbmwj/"


def _build_cookie_dict(cookie_str: str) -> dict[str, str]:
    cookie_map: dict[str, str] = {}
    for seg in (cookie_str or "").split(";"):
        part = seg.strip()
        if not part or "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key:
            cookie_map[key] = value
    return cookie_map


def _request_with_optional_cookie(session, url: str):
    resp = session.get(
        url,
        timeout=20,
        headers={"Referer": "https://gjj.guiyang.gov.cn/"},
    )
    if resp.status_code not in (400, 412):
        return resp

    extra_cookie = os.getenv("GUIYANG_GJJ_COOKIE", "").strip()
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
        headers={"Referer": "https://gjj.guiyang.gov.cn/"},
    )


def _page_url(page_no: int) -> str:
    if page_no <= 1:
        return GUIYANG_GJJ_BASE
    return urljoin(GUIYANG_GJJ_BASE, f"index_{page_no - 1}.html")


def _parse_article_dt(text: str):
    text = norm(text)
    if not text:
        return None

    match = re.search(r"20\d{2}[-/]\d{1,2}[-/]\d{1,2}", text)
    if not match:
        return None

    try:
        return parse_ymd(match.group(0).replace("/", "-"))
    except Exception:
        return None


def _extract_page_items(page_url: str, html: str, today, since_date):
    soup = BeautifulSoup(html or "", "html.parser")
    items: list[dict] = []
    newest_date = None

    for li in soup.select("div.zfxxgk_zdgkc li"):
        a_tag = li.find("a", href=True)
        if not a_tag:
            continue

        href = norm(a_tag.get("href") or "")
        if not href:
            continue

        if not href.lower().endswith(".html"):
            continue

        title = norm(a_tag.get("title") or a_tag.get_text(" ", strip=True))
        if not title or len(title) < 6:
            continue
        if title in {"首页", "上一页", "下一页", "尾页"}:
            continue

        date_tag = li.find("b")
        date_text = norm(date_tag.get_text(" ", strip=True)) if date_tag else norm(li.get_text(" ", strip=True))
        article_date = _parse_article_dt(date_text)
        if not article_date:
            continue

        if article_date > today:
            continue

        if newest_date is None or article_date > newest_date:
            newest_date = article_date

        if article_date < since_date:
            continue

        items.append(
            {
                "title": mark_income_related(title),
                "url": urljoin(page_url, href),
                "date": article_date,
                "source": "guiyang_gjj_policy",
            }
        )

    return items, newest_date


def crawl_guiyang_gjj_policy(current_time: datetime | None = None, max_pages: int = 20) -> list[dict]:
    """抓取贵阳市住房公积金管理中心法规公文-政策文件，仅保留近24小时内条目。"""
    now = current_time or now_cn()
    if now.tzinfo is None:
        now = now.replace(tzinfo=now_cn().tzinfo)
    since_date = (now - timedelta(hours=24)).date()
    today = now.date()

    session = make_session()
    results: list[dict] = []
    seen_urls: set[str] = set()

    for page_no in range(1, max_pages + 1):
        page_url = _page_url(page_no)
        try:
            resp = _request_with_optional_cookie(session, page_url)
            resp.encoding = resp.apparent_encoding or "utf-8"
        except Exception as e:
            print(f"[GuiyangGJJ] fetch failed(page={page_no}): {e}")
            break

        if resp.status_code != 200:
            print(f"[GuiyangGJJ] HTTP Error {resp.status_code} @ {page_url}")
            break

        page_items, newest_date = _extract_page_items(page_url, resp.text, today, since_date)
        if not page_items and newest_date is None:
            break

        for item in page_items:
            if item["url"] in seen_urls:
                continue
            seen_urls.add(item["url"])
            results.append(item)

        if newest_date and newest_date < since_date:
            break

    results.sort(key=lambda x: (x["date"], x["title"]), reverse=True)
    return results