# -*- coding: utf-8 -*-
import re
from datetime import datetime
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright

from .common import make_session, mark_income_related, now_cn, norm, parse_ymd


INDEX_URL = "https://gjj.gz.gov.cn/gkmlpt/policy"


def _parse_row(page_url: str, row) -> dict | None:
    try:
        anchors = row.locator("a")
        if anchors.count() == 0:
            return None

        title_anchor = anchors.nth(0)
        href = norm(title_anchor.get_attribute("href") or "")
        title = norm(title_anchor.inner_text())
        if not href or not title:
            return None

        full_url = urljoin(page_url, href)
        if not full_url.lower().endswith(".html"):
            return None

        dt = None
        tds = row.locator("td")
        for i in range(tds.count()):
            cell_text = norm(tds.nth(i).inner_text())
            m = re.search(r"(20\d{2}-\d{2}-\d{2})", cell_text)
            if m:
                dt = parse_ymd(m.group(1))
                break

        if not dt:
            row_text = norm(row.inner_text())
            m = re.search(r"(20\d{2}-\d{2}-\d{2})", row_text)
            if m:
                dt = parse_ymd(m.group(1))

        return {
            "title": mark_income_related(title),
            "url": full_url,
            "date": dt,
            "source": "guangzhou_gjj_policy",
        }
    except Exception:
        return None


def _extract_items(page) -> list[dict]:
    results: list[dict] = []
    seen = set()

    rows = page.locator("table tbody tr")
    for i in range(rows.count()):
        item = _parse_row(page.url, rows.nth(i))
        if not item:
            continue

        key = (item["url"], item["title"])
        if key in seen:
            continue
        seen.add(key)
        results.append(item)

    return results


def _get_total_pages(page) -> int:
    body_text = norm(page.locator("body").inner_text())
    m = re.search(r"共\s*(\d+)\s*页", body_text)
    if m:
        return max(1, int(m.group(1)))
    return 1


def _goto_page(page, page_no: int) -> None:
    if page_no <= 1:
        return
    page.get_by_text(str(page_no), exact=True).click()
    page.wait_for_timeout(1200)


def crawl_guangzhou_gjj_policy(current_time: datetime | None = None, max_pages: int = 1) -> list[dict]:
    """抓取广州住房公积金管理中心 - 规范性文件（使用无头浏览器执行前端渲染）"""
    _ = current_time or now_cn()
    results: list[dict] = []
    seen_urls = set()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1400, "height": 1200})
            page.set_default_timeout(15000)
            page.goto(INDEX_URL, wait_until="networkidle", timeout=30000)

            total_pages = min(max_pages, _get_total_pages(page))
            for page_no in range(1, total_pages + 1):
                if page_no > 1:
                    _goto_page(page, page_no)

                page_items = _extract_items(page)
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

            browser.close()
    except Exception as e:
        print(f"[Guangzhou GJJ] Crawl error: {e}")
        return []

    results.sort(key=lambda x: (x.get("date") or now_cn().date(), x.get("title", "")), reverse=True)
    return results
