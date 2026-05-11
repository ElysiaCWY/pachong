# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, date
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, mark_income_related, now_cn, norm, parse_ymd


ALSZFGJJ_INDEX = "http://www.alszfgjj.org.cn/col/col4016/index.html"


def _page_url(page_no: int) -> str:
    if page_no <= 1:
        return ALSZFGJJ_INDEX
    return ALSZFGJJ_INDEX.replace("index.html", f"index_{page_no - 1}.html")


def _extract_page_items(page_url: str, html: str, since_date: date) -> tuple[list[dict], bool]:
    soup = BeautifulSoup(html or "", "html.parser")
    results: list[dict] = []
    seen: set[str] = set()
    has_older_item = False

    for a in soup.find_all("a", href=True):
        href = norm(a.get("href") or "")
        if not href or "/col/col4016/" not in href:
            continue

        title = norm(a.get("title") or a.get_text(" ", strip=True))
        if not title or len(title) < 2:
            continue

        parent = a.parent
        parent_text = norm(parent.get_text(" ", strip=True)) if parent else ""

        # 支持 YYYY-MM-DD 和 中文日期格式 YYYY年MM月DD日
        dt = None
        m = re.search(r"(20\d{2}-\d{2}-\d{2})", parent_text)
        if m:
            dt = parse_ymd(m.group(1))
        else:
            m2 = re.search(r"(20\d{2})年(\d{1,2})月(\d{1,2})日", parent_text)
            if m2:
                try:
                    y = int(m2.group(1)); mo = int(m2.group(2)); d = int(m2.group(3))
                    from datetime import date as _d
                    dt = _d(y, mo, d)
                except Exception:
                    dt = None

        if not dt:
            continue

        if dt < since_date:
            has_older_item = True
            continue

        full_url = urljoin(page_url, href)
        if full_url in seen:
            continue
        seen.add(full_url)

        results.append(
            {
                "title": mark_income_related(title),
                "url": full_url,
                "date": dt,
                "source": "alszfgjj_policy",
            }
        )

    return results, has_older_item


def crawl_alszfgjj_policy(current_time: datetime | None = None, max_pages: int = 3) -> list[dict]:
    """抓取阿拉善盟住房公积金中心政策法规栏目，仅返回近24小时内条目。"""
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
            print(f"[ALSZFGJJ] fetch failed(page={page_no}): {e}")
            break

        if resp.status_code != 200:
            break

        page_items, has_older_item = _extract_page_items(page_url, resp.text, since_date)
        if not page_items and page_no == 1:
            break

        for it in page_items:
            if it["url"] in seen_urls:
                continue
            seen_urls.add(it["url"])
            results.append(it)

        if has_older_item:
            break

    results.sort(key=lambda x: (x.get("date") or now.date(), x.get("title", "")), reverse=True)
    return results
