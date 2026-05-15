# -*- coding: utf-8 -*-
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, mark_income_related, now_cn, norm


BASE_URL = "https://www.ybzfgjj.cn"
INDEX_URL = f"{BASE_URL}/zhengcefagui/"
ARTICLE_RE = re.compile(r"^https?://www\.ybzfgjj\.cn/zhengcefagui/.+\.html$")
DATE_RE = re.compile(r"日期[:：]\s*(20\d{2}-\d{2}-\d{2}(?:\s+\d{2}:\d{2}:\d{2})?)")


def _parse_datetime(text: str):
    value = norm(text or "")
    if not value:
        return None

    value = value.replace("/", "-")
    for fmt, width in (("%Y-%m-%d %H:%M:%S", 19), ("%Y-%m-%d %H:%M", 16), ("%Y-%m-%d", 10)):
        try:
            return datetime.strptime(value[:width], fmt)
        except Exception:
            continue
    return None


def _attach_tz(dt: datetime | None, tzinfo):
    if not dt:
        return None
    if dt.tzinfo is None and tzinfo is not None:
        return dt.replace(tzinfo=tzinfo)
    return dt


def _extract_items(html: str, page_url: str, now: datetime, since_dt: datetime) -> tuple[list[dict], str | None]:
    soup = BeautifulSoup(html or "", "html.parser")
    results: list[dict] = []
    seen = set()
    next_page_url = None

    for a in soup.find_all("a", href=True):
        href = norm(a.get("href") or "")
        if not href:
            continue

        full_url = urljoin(page_url, href)
        if not ARTICLE_RE.match(full_url):
            continue

        title = norm(a.get_text(" ", strip=True) or a.get("title") or "")
        parent = a.find_parent(["li", "div", "dd", "tr"])
        text = norm(parent.get_text(" ", strip=True) if parent else a.parent.get_text(" ", strip=True) if a.parent else "")
        if not title and text:
            title_text = re.sub(r"^\s*\[[^\]]*\]\s*", "", text)
            title_text = re.split(r"(?:日期[:：]|20\d{2}-\d{2}-\d{2})", title_text, 1)[0]
            title = norm(title_text)
        if not title:
            continue
        m = DATE_RE.search(text)
        dt = _attach_tz(_parse_datetime(m.group(1)), now.tzinfo) if m else None
        if not dt:
            # 兜底抓取列表里裸日期
            m2 = re.search(r"(20\d{2}-\d{2}-\d{2}(?:\s+\d{2}:\d{2}:\d{2})?)", text)
            dt = _attach_tz(_parse_datetime(m2.group(1)), now.tzinfo) if m2 else None

        if not dt:
            continue
        if dt > now:
            continue
        if dt < since_dt:
            continue

        if full_url in seen:
            continue
        seen.add(full_url)

        results.append(
            {
                "title": mark_income_related(title),
                "url": full_url,
                "date": dt,
                "source": "ybzfgjj_policy",
            }
        )

    # 下一页
    next_link = soup.find("a", string=re.compile(r"下一页|>", re.I))
    if next_link and next_link.get("href"):
        next_page_url = urljoin(page_url, next_link.get("href"))

    return results, next_page_url


def crawl_ybzfgjj_policy(current_time: datetime | None = None, max_pages: int = 3) -> list[dict]:
    """抓取延边州住房公积金管理中心政策法规栏目，返回近24小时内发布的标题与链接。"""
    now = current_time or now_cn()
    since_dt = now - timedelta(hours=24)
    session = make_session()

    results: list[dict] = []
    seen = set()
    page_url = INDEX_URL

    for _ in range(1, max_pages + 1):
        try:
            resp = session.get(page_url, timeout=20)
            resp.encoding = resp.apparent_encoding or "utf-8"
            if resp.status_code != 200:
                break
        except Exception as e:
            print(f"[YBZFGJJ] fetch failed: {e}")
            break

        page_items, next_page_url = _extract_items(resp.text, page_url, now, since_dt)
        if not page_items:
            if not next_page_url:
                break
        for item in page_items:
            if item["url"] in seen:
                continue
            seen.add(item["url"])
            results.append(item)

        if not next_page_url:
            break
        page_url = next_page_url

    results.sort(key=lambda x: (x.get("date") or now, x.get("title", "")), reverse=True)
    return results
