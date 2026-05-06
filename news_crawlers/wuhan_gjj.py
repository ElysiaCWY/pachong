# -*- coding: utf-8 -*-
import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, mark_income_related, now_cn, norm, parse_ymd


INDEX_URL = "https://gjj.wuhan.gov.cn/zwgk/zc/gfxwj/index.html"


def _page_url(page_no: int) -> str:
    if page_no <= 1:
        return INDEX_URL
    return f"https://gjj.wuhan.gov.cn/zwgk/zc/gfxwj/index_{page_no - 1}.html"


def _extract_items(page_url: str, html: str) -> list[dict]:
    soup = BeautifulSoup(html or "", "html.parser")
    results: list[dict] = []
    seen = set()

    for a in soup.find_all("a", href=True):
        try:
            href = norm(a.get("href") or "")
            title = norm(a.get_text(" ", strip=True))
            if not href or not title:
                continue

            full_url = urljoin(page_url, href)
            if "/zwgk/zc/gfxwj/" not in full_url:
                continue
            if not full_url.lower().endswith(".html"):
                continue

            # 列表文本通常是“标题YYYY-MM-DD”直接拼接
            raw_text = norm(a.get_text(" ", strip=True))
            dt = None
            m = re.search(r"(20\d{2}-\d{2}-\d{2})", raw_text)
            if m:
                dt = parse_ymd(m.group(1))
                title = norm(raw_text.replace(m.group(1), "", 1))

            if not dt:
                container = a.parent.parent if a.parent and a.parent.parent else (a.parent if a.parent else None)
                container_text = norm(container.get_text(" ", strip=True)) if container else ""
                m = re.search(r"(20\d{2}-\d{2}-\d{2})", container_text)
                if m:
                    dt = parse_ymd(m.group(1))

            if not title:
                continue

            key = (full_url, title)
            if key in seen:
                continue
            seen.add(key)

            results.append(
                {
                    "title": mark_income_related(title),
                    "url": full_url,
                    "date": dt,
                    "source": "wuhan_gjj_gfxwj",
                }
            )
        except Exception:
            continue

    return results


def crawl_wuhan_gjj_gfxwj(current_time: datetime | None = None, max_pages: int = 3) -> list[dict]:
    """抓取武汉住房公积金管理中心规范性文件列表，保留近24小时过滤所需的日期字段。"""
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
            print(f"[Wuhan GJJ] Crawl error(p{page_no}): {e}")
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
