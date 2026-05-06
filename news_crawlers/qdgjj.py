# -*- coding: utf-8 -*-
import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, mark_income_related, now_cn, norm, parse_ymd


INDEX_URL = "https://www.qdgjj.com/zcfg_108/zcjd_108/"


def _page_url(page_no: int) -> str:
    if page_no <= 1:
        return INDEX_URL
    return f"https://www.qdgjj.com/zcfg_108/zcjd_108/index.shtml?i={page_no - 1}"


def _extract_date_and_title(raw_text: str) -> tuple[datetime | None, str]:
    text = norm(raw_text)
    if not text:
        return None, ""

    m = re.match(r"^(20\d{2}-\d{2}-\d{2})(.+)$", text)
    if m:
        dt = parse_ymd(m.group(1))
        title = norm(m.group(2))
        return dt, title

    m = re.search(r"(20\d{2}-\d{2}-\d{2})", text)
    if not m:
        return None, text

    dt = parse_ymd(m.group(1))
    title = norm(text.replace(m.group(1), "", 1))
    return dt, title


def _extract_items(page_url: str, html: str) -> list[dict]:
    soup = BeautifulSoup(html or "", "html.parser")
    results: list[dict] = []
    seen = set()

    for a in soup.find_all("a", href=True):
        try:
            href = norm(a.get("href") or "")
            if not href:
                continue

            full_url = urljoin(page_url, href)
            if "/zcfg_108/zcjd_108/" not in full_url:
                continue
            if not full_url.lower().endswith(".shtml"):
                continue

            raw_text = a.get_text(" ", strip=True)
            dt, title = _extract_date_and_title(raw_text)

            if not title:
                continue
            if len(title) < 4:
                continue

            # 兜底：如果标题文本没有包含日期，从父容器文本里找
            if dt is None:
                container = a.parent.parent if a.parent and a.parent.parent else (a.parent if a.parent else None)
                container_text = norm(container.get_text(" ", strip=True)) if container else ""
                m = re.search(r"(20\d{2}-\d{2}-\d{2})", container_text)
                if m:
                    dt = parse_ymd(m.group(1))

            key = (full_url, title)
            if key in seen:
                continue
            seen.add(key)

            results.append(
                {
                    "title": mark_income_related(title),
                    "url": full_url,
                    "date": dt,
                    "source": "qdgjj_zcjd",
                }
            )
        except Exception:
            continue

    return results


def crawl_qdgjj_zcjd(current_time: datetime | None = None, max_pages: int = 5) -> list[dict]:
    """抓取青岛公积金政策解读板块，保留标题、链接和日期字段。"""
    _ = current_time or now_cn()
    session = make_session()
    results: list[dict] = []
    seen_urls = set()

    for page_no in range(1, max_pages + 1):
        page_url = _page_url(page_no)
        try:
            resp = session.get(page_url, timeout=15)
            resp.encoding = resp.apparent_encoding or "utf-8"
            if resp.status_code != 200:
                break
        except Exception as e:
            print(f"[QDGJJ] Crawl error(p{page_no}): {e}")
            break

        page_items = _extract_items(page_url, resp.text)
        if not page_items:
            continue

        page_has_new = False
        for it in page_items:
            if it["url"] in seen_urls:
                continue
            seen_urls.add(it["url"])
            results.append(it)
            page_has_new = True

        if page_no > 1 and not page_has_new:
            break

    results.sort(key=lambda x: (x.get("date") or now_cn().date(), x.get("title", "")), reverse=True)
    return results
