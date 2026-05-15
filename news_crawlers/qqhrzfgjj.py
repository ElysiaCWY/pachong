# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
import re
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from .common import make_session, mark_income_related, now_cn, norm, parse_ymd


QQHRZFGJJ_INDEX = "https://www.qqhrzfgjj.org.cn/tzgg/index.jhtml"
QQHRZFGJJ_PAGE_FMT = "https://www.qqhrzfgjj.org.cn/tzgg/index_{page}.jhtml"
ARTICLE_RE = re.compile(r"^https?://www\.qqhrzfgjj\.org\.cn(?::80)?/tzgg/\d+\.jhtml$")


def _normalize_url(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme == "http" and parts.netloc.endswith(":80"):
        return urlunsplit((parts.scheme, parts.netloc[:-3], parts.path, parts.query, parts.fragment))
    if parts.scheme == "https" and parts.netloc.endswith(":443"):
        return urlunsplit((parts.scheme, parts.netloc[:-4], parts.path, parts.query, parts.fragment))
    return url


def _page_url(page_no: int) -> str:
    if page_no <= 1:
        return QQHRZFGJJ_INDEX
    return QQHRZFGJJ_PAGE_FMT.format(page=page_no)


def _extract_page_items(page_url: str, html: str, since_date) -> tuple[list[dict], bool]:
    soup = BeautifulSoup(html or "", "html.parser")
    results: list[dict] = []
    seen: set[str] = set()
    has_older_item = False

    for a_tag in soup.find_all("a", href=True):
        href = norm(a_tag.get("href") or "")
        if not href:
            continue

        full_url = _normalize_url(urljoin(page_url, href))
        if not ARTICLE_RE.match(full_url):
            continue

        title = norm(a_tag.get("title") or a_tag.get_text(" ", strip=True))
        if not title:
            continue

        container = a_tag.parent
        container_text = norm(container.get_text(" ", strip=True)) if container else ""
        match = re.search(r"(20\d{2}-\d{2}-\d{2})", container_text)
        if not match and container and container.parent:
            match = re.search(r"(20\d{2}-\d{2}-\d{2})", norm(container.parent.get_text(" ", strip=True)))
        if not match:
            continue

        article_date = parse_ymd(match.group(1))
        if not article_date:
            continue

        if article_date < since_date:
            has_older_item = True
            continue

        if full_url in seen:
            continue
        seen.add(full_url)

        results.append(
            {
                "title": mark_income_related(title),
                "url": full_url,
                "date": article_date,
                "source": "qqhrzfgjj_tzgg",
            }
        )

    return results, has_older_item


def crawl_qqhrzfgjj_tzgg(current_time: datetime | None = None, max_pages: int = 3) -> list[dict]:
    """抓取齐齐哈尔住房公积金管理中心通知公告，仅保留近24小时内发布的标题和链接。"""
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
            print(f"[QQHRZFGJJ] fetch failed(page={page_no}): {e}")
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