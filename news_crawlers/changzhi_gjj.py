# -*- coding: utf-8 -*-
import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, mark_income_related, now_cn, norm, parse_ymd

INDEX_URL = "https://zfgjj.changzhi.gov.cn/zcfg/zxwj/"


def _page_url(page_no: int) -> str:
    if page_no <= 1:
        return INDEX_URL
    return urljoin(INDEX_URL, f"index_{page_no - 1}.html")


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
            # 仅保留站内详情页链接
            if not full_url.lower().endswith(('.html', '.shtml')):
                continue

            # 从文本或父容器中提取日期（格式 YYYY-MM-DD 或 中文日期）
            dt = None
            m = re.search(r"(20\d{2}-\d{2}-\d{2})", title)
            if m:
                dt = parse_ymd(m.group(1))
                title = norm(title.replace(m.group(1), "", 1))

            if dt is None:
                container = a.parent if a.parent else None
                container_text = norm(container.get_text(" ", strip=True)) if container else ""
                m2 = re.search(r"(20\d{2}-\d{2}-\d{2})", container_text)
                if m2:
                    dt = parse_ymd(m2.group(1))

            key = (full_url, title)
            if key in seen:
                continue
            seen.add(key)

            results.append({
                "title": mark_income_related(title),
                "url": full_url,
                "date": dt,
                "source": "changzhi_gjj_zxwj",
            })
        except Exception:
            continue

    return results


def crawl_changzhi_gjj_zxwj(current_time: datetime | None = None, max_pages: int = 2) -> list[dict]:
    """抓取长治公积金网 - 中心文件（返回 title/url/date/source 列表），外层负责 24 小时过滤。"""
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
            print(f"[Changzhi GJJ] Crawl error(p{page_no}): {e}")
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
