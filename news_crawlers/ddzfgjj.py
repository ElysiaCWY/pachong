# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
import re
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from .common import make_session, mark_income_related, now_cn, norm, parse_ymd


DDZGJJ_SJWJ_INDEX = "https://www.ddzfgjj.com/sgjjwj/index.jhtml"


def _normalize_url(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme == "http" and parts.netloc.endswith(":80"):
        return urlunsplit((parts.scheme, parts.netloc[:-3], parts.path, parts.query, parts.fragment))
    if parts.scheme == "https" and parts.netloc.endswith(":443"):
        return urlunsplit((parts.scheme, parts.netloc[:-4], parts.path, parts.query, parts.fragment))
    return url


def _page_url(page_no: int) -> str:
    if page_no <= 1:
        return DDZGJJ_SJWJ_INDEX
    return f"https://www.ddzfgjj.com/sgjjwj/index_{page_no}.jhtml"


def _extract_total_pages(html: str) -> int:
    match = re.search(r"共\d+条记录\s*\d+/(\d+)页", html or "")
    if not match:
        return 1
    try:
        return max(1, int(match.group(1)))
    except Exception:
        return 1


def _extract_page_items(page_url: str, html: str, now: datetime, since_date) -> tuple[list[dict], bool]:
    soup = BeautifulSoup(html or "", "html.parser")
    results: list[dict] = []
    seen: set[str] = set()
    has_older_item = False

    for li in soup.find_all("li"):
        a_tag = li.select_one("span.span580 a[href]") or li.select_one("a[href]")
        if not a_tag:
            continue

        text = norm(li.get_text(" ", strip=True))
        match = re.search(r"(20\d{2}-\d{2}-\d{2})", text)
        if not match:
            continue

        article_date = parse_ymd(match.group(1))
        if not article_date:
            continue
        if article_date > now.date():
            continue
        if article_date < since_date:
            has_older_item = True
            continue

        title = norm(a_tag.get("title") or a_tag.get_text(" ", strip=True))
        href = norm(a_tag.get("href") or "")
        if not title or not href:
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
                "source": "ddzfgjj_sgjjwj",
            }
        )

    return results, has_older_item


def crawl_ddzfgjj_sgjjwj(current_time: datetime | None = None, max_pages: int = 4) -> list[dict]:
    """抓取丹东住房公积金管理中心市公积金文件，仅保留近24小时内条目。"""
    now = current_time or now_cn()
    since_date = (now - timedelta(hours=24)).date()

    session = make_session()
    results: list[dict] = []
    seen_urls: set[str] = set()

    try:
        first_resp = session.get(DDZGJJ_SJWJ_INDEX, timeout=20)
        first_resp.encoding = first_resp.apparent_encoding or "utf-8"
        if first_resp.status_code != 200:
            print(f"[DDZGJJ] HTTP Error {first_resp.status_code}")
            return []
    except Exception as e:
        print(f"[DDZGJJ] fetch failed(page=1): {e}")
        return []

    total_pages = min(_extract_total_pages(first_resp.text), max_pages)

    for page_no in range(1, total_pages + 1):
        if page_no == 1:
            page_url = DDZGJJ_SJWJ_INDEX
            html = first_resp.text
        else:
            page_url = _page_url(page_no)
            try:
                resp = session.get(page_url, timeout=20)
                resp.encoding = resp.apparent_encoding or "utf-8"
                if resp.status_code != 200:
                    print(f"[DDZGJJ] HTTP Error {resp.status_code} @ page={page_no}")
                    break
                html = resp.text
            except Exception as e:
                print(f"[DDZGJJ] fetch failed(page={page_no}): {e}")
                break

        page_items, has_older_item = _extract_page_items(page_url, html, now, since_date)
        if not page_items and page_no == 1:
            break

        for item in page_items:
            if item["url"] in seen_urls:
                continue
            seen_urls.add(item["url"])
            results.append(item)

        if has_older_item:
            break

    results.sort(key=lambda x: (x["date"], x["title"]), reverse=True)
    return results