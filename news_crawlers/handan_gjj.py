# -*- coding: utf-8 -*-
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from .common import make_session, mark_income_related, now_cn, norm, parse_ymd


INDEX_URL = "https://housefund.hd.gov.cn/website/regulation-list.html"


def _parse_title_date(text: str) -> tuple[str, datetime | None]:
    text = norm(text)
    if not text:
        return "", None

    m = re.match(r"^(.*?)(20\d{2}-\d{2}-\d{2})$", text)
    if m:
        title = norm(m.group(1))
        dt = parse_ymd(m.group(2))
        return title, dt

    m = re.search(r"(20\d{2}-\d{2}-\d{2})", text)
    if m:
        dt = parse_ymd(m.group(1))
        title = norm(text.replace(m.group(1), "", 1))
        return title, dt

    return text, None


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
            if "regulation-detail.html" not in full_url:
                continue
            if "housefund.hd.gov.cn" not in full_url:
                continue

            raw_text = a.get_text(" ", strip=True)
            title, dt = _parse_title_date(raw_text)
            if not title or len(title) < 4:
                continue

            # 兜底：若 a 文本里没有日期，从父容器文本找
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
                    "source": "handan_gjj_policy",
                }
            )
        except Exception:
            continue

    return results


def _fetch_html_playwright(url: str) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"],
        )
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )
        page.set_extra_http_headers({"Accept-Language": "zh-CN,zh;q=0.9"})
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        try:
            page.wait_for_timeout(1200)
        except Exception:
            pass
        html = page.content()
        browser.close()
        return html


def crawl_handan_gjj_policy(current_time: datetime | None = None, max_pages: int = 1) -> list[dict]:
    """抓取邯郸公积金政策法规列表，仅保留近24小时内条目。"""
    now = current_time or now_cn()
    since = now - timedelta(days=1)
    session = make_session()
    results: list[dict] = []

    try:
        resp = session.get(INDEX_URL, timeout=15)
        resp.encoding = resp.apparent_encoding or "utf-8"
        if resp.status_code != 200:
            return []
    except Exception as e:
        print(f"[HandanGJJ] fetch failed: {e}")
        return []

    page_items = _extract_items(INDEX_URL, resp.text)
    if not page_items:
        try:
            page_items = _extract_items(INDEX_URL, _fetch_html_playwright(INDEX_URL))
        except Exception as e:
            print(f"[HandanGJJ] playwright fallback failed: {e}")

    if not page_items:
        return []

    for it in page_items:
        d = it.get("date")
        if not d:
            continue
        if d >= since.date():
            results.append(it)

    results.sort(key=lambda x: (x.get("date") or now.date(), x.get("title", "")), reverse=True)
    return results
