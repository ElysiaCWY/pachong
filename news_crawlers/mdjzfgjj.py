# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
import re
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from .common import make_session, mark_income_related, now_cn, norm


INDEX_URL = "https://www.mdjzfgjj.cn/zxwj/index.jhtml"
PAGE_FMT = "https://www.mdjzfgjj.cn/zxwj/index_{page}.jhtml"
ARTICLE_RE = re.compile(r"^https?://www\.mdjzfgjj\.cn(?::80)?/dfzc/\d+\.jhtml$")


def _normalize_url(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme == "http" and parts.netloc.endswith(":80"):
        return urlunsplit((parts.scheme, parts.netloc[:-3], parts.path, parts.query, parts.fragment))
    if parts.scheme == "https" and parts.netloc.endswith(":443"):
        return urlunsplit((parts.scheme, parts.netloc[:-4], parts.path, parts.query, parts.fragment))
    return url


def _page_url(page_no: int) -> str:
    if page_no <= 1:
        return INDEX_URL
    return PAGE_FMT.format(page=page_no)


def _extract_pub_datetime(html: str, now: datetime) -> datetime | None:
    text = norm(BeautifulSoup(html or "", "html.parser").get_text(" ", strip=True))
    match = re.search(r"(20\d{2}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", text)
    if not match:
        return None

    try:
        dt = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None

    if now.tzinfo is not None and dt.tzinfo is None:
        dt = dt.replace(tzinfo=now.tzinfo)
    return dt


def _extract_page_items(page_url: str, html: str, now: datetime, since_dt: datetime) -> tuple[list[dict], bool]:
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

        title = norm(a_tag.get_text(" ", strip=True))
        if not title or len(title) < 4:
            continue

        try:
            detail_resp = make_session().get(full_url, timeout=20)
            detail_resp.encoding = detail_resp.apparent_encoding or "utf-8"
            if detail_resp.status_code != 200:
                continue
        except Exception:
            continue

        dt = _extract_pub_datetime(detail_resp.text, now)
        if not dt:
            continue

        if dt > now:
            continue
        if dt < since_dt:
            has_older_item = True
            continue

        if full_url in seen:
            continue
        seen.add(full_url)

        results.append(
            {
                "title": mark_income_related(title),
                "url": full_url,
                "date": dt,
                "source": "mdjzfgjj_zxwj",
            }
        )

    return results, has_older_item


def _extract_total_pages(html: str) -> int:
    match = re.search(r"共\d+条记录\s*\d+/(\d+)页", html or "")
    if not match:
        return 1
    try:
        return max(1, int(match.group(1)))
    except Exception:
        return 1


def crawl_mdjzfgjj_zxwj(current_time: datetime | None = None, max_pages: int = 4) -> list[dict]:
    """抓取牡丹江住房公积金管理中心政策法规，仅保留近24小时内发布的标题和链接。"""
    now = current_time or now_cn()
    since_dt = now - timedelta(hours=24)
    session = make_session()
    results: list[dict] = []
    seen_urls: set[str] = set()

    try:
        first_resp = session.get(INDEX_URL, timeout=20)
        first_resp.encoding = first_resp.apparent_encoding or "utf-8"
        if first_resp.status_code != 200:
            return []
    except Exception as e:
        print(f"[MDJZFGJJ] fetch failed(page=1): {e}")
        return []

    total_pages = min(_extract_total_pages(first_resp.text), max_pages)

    for page_no in range(1, total_pages + 1):
        if page_no == 1:
            html = first_resp.text
            page_url = INDEX_URL
        else:
            page_url = _page_url(page_no)
            try:
                resp = session.get(page_url, timeout=20)
                resp.encoding = resp.apparent_encoding or "utf-8"
                if resp.status_code != 200:
                    break
                html = resp.text
            except Exception as e:
                print(f"[MDJZFGJJ] fetch failed(page={page_no}): {e}")
                break

        page_items, has_older_item = _extract_page_items(page_url, html, now, since_dt)
        if not page_items and page_no == 1:
            break

        for item in page_items:
            if item["url"] in seen_urls:
                continue
            seen_urls.add(item["url"])
            results.append(item)

        if has_older_item:
            break

    results.sort(key=lambda x: (x.get("date") or now, x.get("title", "")), reverse=True)
    return results