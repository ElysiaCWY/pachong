# -*- coding: utf-8 -*-
import re
from datetime import datetime, timedelta, date
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, now_cn, norm, parse_ymd, mark_income_related


INDEX_URL = "https://www.tsgjj.com/website/gjj-gjjwj.html?itemId=0402"


def _fetch_html_requests(session, url: str) -> str:
    resp = session.get(url, timeout=15)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.text


def _extract_date_from_text(s: str) -> date | None:
    if not s:
        return None
    s = norm(s)
    # YYYY-MM-DD or YYYY.MM.DD or YYYY/MM/DD
    m = re.search(r"(20\d{2})[\-\./](\d{1,2})[\-\./](\d{1,2})", s)
    if m:
        y, mo, d = m.group(1), m.group(2), m.group(3)
        try:
            return date(int(y), int(mo), int(d))
        except Exception:
            return None

    # Chinese date: 2026年5月8日
    m = re.search(r"(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日", s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except Exception:
            return None

    # fallback to parse_ymd for simpler formats
    return parse_ymd(s)


def _parse_list(html: str, base_url: str) -> list[dict]:
    soup = BeautifulSoup(html or "", "html.parser")
    items: list[dict] = []

    # Try table rows first
    rows = soup.select("table tbody tr")
    if rows:
        for r in rows:
            a = r.find("a")
            if not a or not a.get("href"):
                continue
            title = norm(a.get_text(" ", strip=True))
            href = a.get("href")
            url = urljoin(base_url, href)
            txt = norm(r.get_text(" ", strip=True))
            d = _extract_date_from_text(txt)
            items.append({"title": mark_income_related(title), "url": url, "date": d, "source": "tsgjj_center"})
        return items

    # Try common list structures (ul/li)
    lis = soup.select("ul li, div.list li, div.news-list li")
    if lis:
        for li in lis:
            a = li.find("a")
            if not a or not a.get("href"):
                continue
            title = norm(a.get_text(" ", strip=True))
            href = a.get("href")
            url = urljoin(base_url, href)
            txt = norm(li.get_text(" ", strip=True))
            d = _extract_date_from_text(txt)
            items.append({"title": mark_income_related(title), "url": url, "date": d, "source": "tsgjj_center"})
        return items

    # Fallback: scan all links on page and try to find nearby date text
    for a in soup.find_all("a", href=True):
        href = a.get("href") or ""
        if not href.endswith('.html') and 'content' not in href and 'article' not in href:
            continue
        title = norm(a.get_text(" ", strip=True))
        if not title:
            continue
        url = urljoin(base_url, href)

        # search parent/next siblings for date
        date_text = ""
        container = a.parent
        if container:
            date_text = norm(container.get_text(" ", strip=True))

        d = _extract_date_from_text(date_text)
        if not d:
            # try siblings
            for ns in a.next_siblings:
                try:
                    txt = ns if isinstance(ns, str) else (ns.get_text(" ", strip=True) if hasattr(ns, "get_text") else "")
                    txt = norm(txt)
                    d = _extract_date_from_text(txt)
                    if d:
                        break
                except Exception:
                    continue

        items.append({"title": mark_income_related(title), "url": url, "date": d, "source": "tsgjj_center"})

    return items


def crawl_tsgjj_center(current_time: datetime | None = None, max_pages: int = 3) -> list[dict]:
    """抓取日照公积金网站（示例）：中心文件（仅近24小时）

    返回列表元素为 {title, url, date, source}
    """
    now = current_time or now_cn()
    since_dt = now - timedelta(days=1)
    s = make_session()
    results: list[dict] = []

    for p in range(1, max_pages + 1):
        if p == 1:
            url = INDEX_URL
        else:
            # 站点可能通过 page 参数分页，尝试常见格式
            url = f"{INDEX_URL}&page={p}"

        try:
            html = _fetch_html_requests(s, url)
        except Exception:
            # 不做浏览器回退，直接跳过失败页
            break

        items = _parse_list(html, url)
        if not items:
            break

        # keep only items within last 24 hours (date granularity -> compare date)
        keep = []
        for it in items:
            d = it.get("date")
            if not d:
                continue
            # convert to datetime at midnight for comparison
            dt = datetime(d.year, d.month, d.day)
            if dt >= since_dt.replace(hour=0, minute=0, second=0, microsecond=0):
                keep.append(it)

        results.extend(keep)

        # if some items on this page are older, stop paginating
        if len(keep) < len(items):
            break

    # dedupe by url preserving order
    seen = set()
    uniq = []
    for it in results:
        u = it.get("url")
        if not u or u in seen:
            continue
        seen.add(u)
        uniq.append(it)

    return uniq
