# -*- coding: utf-8 -*-
import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, mark_income_related, now_cn, norm, parse_ymd


INDEX_URL = "https://zfgjj.guilin.gov.cn/zcfg/zxwj/"


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
            if "zcfg/zxwj" not in full_url or not full_url.lower().endswith((".shtml", ".html")):
                continue

            # 页面标题前直接带发布日期，优先从 a 文本或祖先节点提取
            dt = None
            raw_text = norm(a.get_text(" ", strip=True))
            m = re.search(r"(20\d{2}-\d{2}-\d{2})", raw_text)
            if m:
                dt = parse_ymd(m.group(1))
                title = norm(raw_text.replace(m.group(1), "", 1))

            if not dt:
                container = a.parent if a.parent else None
                container_text = norm(container.get_text(" ", strip=True)) if container else ""
                m2 = re.search(r"(20\d{2}-\d{2}-\d{2})", container_text)
                if m2:
                    dt = parse_ymd(m2.group(1))

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
                    "source": "guilin_gjj_zxwj",
                }
            )
        except Exception:
            continue

    return results


def crawl_guilin_gjj_zxwj(current_time: datetime | None = None, max_pages: int = 2) -> list[dict]:
    """抓取桂林住房公积金管理中心 - 中心文件（近24小时筛选依赖 date 字段）"""
    _ = current_time or now_cn()
    session = make_session()
    results: list[dict] = []
    seen_urls = set()

    try:
        resp = session.get(INDEX_URL, timeout=15)
        resp.encoding = resp.apparent_encoding or "utf-8"
        if resp.status_code != 200:
            return []
    except Exception as e:
        print(f"[Guilin GJJ] Crawl error: {e}")
        return []

    page_items = _extract_items(INDEX_URL, resp.text)
    for it in page_items:
        if it["url"] in seen_urls:
            continue
        seen_urls.add(it["url"])
        results.append(it)

    results.sort(key=lambda x: (x.get("date") or now_cn().date(), x.get("title", "")), reverse=True)
    return results
