# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, date
import re
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup
import requests
import urllib3
from urllib3.exceptions import InsecureRequestWarning

from .common import make_session, mark_income_related, now_cn, norm, parse_ymd


JXGJJ_INDEX = "https://www.jxgjj.org.cn/zxwj/index.jhtml"
ARTICLE_RE = re.compile(r"^https?://(?:www\.)?jxgjj\.org\.cn(?::80)?/zxwj/\d+\.jhtml$")

urllib3.disable_warnings(InsecureRequestWarning)


def _normalize_url(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme == "http" and parts.netloc.endswith(":80"):
        return urlunsplit((parts.scheme, parts.netloc[:-3], parts.path, parts.query, parts.fragment))
    if parts.scheme == "https" and parts.netloc.endswith(":443"):
        return urlunsplit((parts.scheme, parts.netloc[:-4], parts.path, parts.query, parts.fragment))
    return url


def _page_url(page_no: int) -> str:
    if page_no <= 1:
        return JXGJJ_INDEX
    return f"https://www.jxgjj.org.cn/zxwj/index_{page_no}.jhtml"


def _extract_page_items(page_url: str, html: str, since_date: date) -> tuple[list[dict], bool]:
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

        if full_url in seen:
            continue
        seen.add(full_url)

        results.append(
            {
                "title": mark_income_related(title),
                "url": full_url,
                "date": article_date,
                "source": "jxgjj_zxwj",
            }
        )

    return results, has_older_item


def _safe_get(session, url: str, timeout: int = 20):
    try:
        return session.get(url, timeout=timeout)
    except Exception:
        # 部分环境下该站点证书链不完整；改用独立请求关闭校验兜底，避免与自定义 TLS 适配器冲突。
        return requests.get(url, headers=dict(session.headers), timeout=timeout, verify=False)


def crawl_jxgjj_zxwj(current_time: datetime | None = None, max_pages: int = 4) -> list[dict]:
    """抓取鸡西住房公积金管理中心中心文件，仅保留近24小时内发布的标题和链接。"""
    now = current_time or now_cn()
    since_date = (now - timedelta(days=1)).date()
    session = make_session()
    results: list[dict] = []
    seen_urls: set[str] = set()

    for page_no in range(1, max_pages + 1):
        page_url = _page_url(page_no)
        try:
            resp = _safe_get(session, page_url, timeout=20)
            resp.encoding = resp.apparent_encoding or "utf-8"
        except Exception as e:
            print(f"[JXGJJ] fetch failed(page={page_no}): {e}")
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