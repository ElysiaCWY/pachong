# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, date
import re
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from .common import make_session, mark_income_related, now_cn, norm, parse_ymd


SHZFGJJ_INDEX = "https://www.shzfgjj.org.cn/zxdt/index.jhtml"


def _normalize_url(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme == "http" and parts.netloc.endswith(":80"):
        return urlunsplit((parts.scheme, parts.netloc[:-3], parts.path, parts.query, parts.fragment))
    if parts.scheme == "https" and parts.netloc.endswith(":443"):
        return urlunsplit((parts.scheme, parts.netloc[:-4], parts.path, parts.query, parts.fragment))
    return url


def _page_url(page_no: int) -> str:
    if page_no <= 1:
        return SHZFGJJ_INDEX
    return f"https://www.shzfgjj.org.cn/zxdt/index_{page_no}.jhtml"


def _extract_page_items(page_url: str, html: str, since_date: date) -> tuple[list[dict], bool]:
    soup = BeautifulSoup(html or "", "html.parser")
    results: list[dict] = []
    seen: set[str] = set()
    has_older_item = False

    for a_tag in soup.find_all("a", href=True):
        href = norm(a_tag.get("href") or "")
        if not re.search(r"/zxdt/\d+\.jhtml$", href):
            continue

        raw_text = norm(a_tag.get_text(" ", strip=True))
        if not raw_text:
            continue

        match = re.search(r"(20\d{2}-\d{2}-\d{2})\s*$", raw_text)
        if not match:
            match = re.search(r"(20\d{2}-\d{2}-\d{2})", raw_text)
        if not match:
            parent = a_tag.parent
            parent_text = norm(parent.get_text(" ", strip=True)) if parent else ""
            match = re.search(r"(20\d{2}-\d{2}-\d{2})", parent_text)
            if not match and parent and parent.parent:
                match = re.search(r"(20\d{2}-\d{2}-\d{2})", norm(parent.parent.get_text(" ", strip=True)))
        if not match:
            continue

        article_date = parse_ymd(match.group(1))
        if not article_date:
            continue

        if article_date < since_date:
            has_older_item = True
            continue

        title = norm(raw_text[: match.start()] + raw_text[match.end() :])
        if not title:
            title = norm(raw_text.replace(match.group(1), "", 1))
        if not title:
            continue

        full_url = _normalize_url(urljoin(page_url, href))
        if full_url in seen:
            continue
        seen.add(full_url)

        results.append(
            {
                "title": mark_income_related(title),
                "url": full_url,
                "date": article_date,
                "source": "shzfgjj_zxdt",
            }
        )

    return results, has_older_item


def crawl_shzfgjj_zxdt(current_time: datetime | None = None, max_pages: int = 7) -> list[dict]:
    """抓取绥化市住房公积金管理中心中心动态，仅保留近24小时内发布的标题和链接。"""
    now = current_time or now_cn()
    since_date = (now - timedelta(days=1)).date()
    session = make_session()
    results: list[dict] = []
    seen_urls: set[str] = set()

    for page_no in range(1, max_pages + 1):
        page_url = _page_url(page_no)
        try:
            resp = session.get(page_url, timeout=20)
            resp.encoding = resp.apparent_encoding or "utf-8"
        except Exception as e:
            print(f"[SHZFGJJ] fetch failed(page={page_no}): {e}")
            break

        if resp.status_code != 200:
            break

        page_items, has_older_item = _extract_page_items(page_url, resp.text, since_date)
        if not page_items and page_no == 1:
            break

        for item in page_items:
            if item["url"] in seen_urls:
                continue
            seen_urls.add(item["url"])
            results.append(item)

        if has_older_item:
            break

    results.sort(key=lambda x: (x.get("date") or now.date(), x.get("title", "")), reverse=True)
    return results