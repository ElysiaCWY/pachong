# -*- coding: utf-8 -*-
import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, now_cn, norm, parse_ymd, mark_income_related

INDEX_URL = "http://ncgjj.nc.gov.cn/nczfgjj/gjjdfzcfg/list.shtml"


def _page_url(page_no: int) -> str:
    if page_no <= 1:
        return INDEX_URL
    return f"http://ncgjj.nc.gov.cn/nczfgjj/gjjdfzcfg/list_{page_no}.shtml"


def _extract_items(page_url: str, html: str) -> list[dict]:
    soup = BeautifulSoup(html or "", "html.parser")
    results: list[dict] = []
    seen = set()

    for a in soup.select("a[href]"):
        try:
            href = norm(a.get("href") or "")
            title = norm(a.get_text(" ", strip=True))
            if not href or not title:
                continue

            if not href.lower().endswith(".shtml"):
                continue
            if "/nczfgjj/gjjdfzcfg/" not in href and "list_" in href:
                continue

            full_url = urljoin(page_url, href)
            if "/nczfgjj/gjjdfzcfg/" not in full_url:
                continue
            if full_url in seen:
                continue

            # 页面通常是“[标题] 2025-12-26”这种形式，优先从父节点文本提日期
            container = a.parent.parent if a.parent and a.parent.parent else (a.parent if a.parent else None)
            container_text = norm(container.get_text(" ", strip=True)) if container else ""
            m = re.search(r"(20\d{2}-\d{2}-\d{2})", container_text)
            if not m:
                for ns in a.next_siblings:
                    try:
                        txt = ns if isinstance(ns, str) else (ns.get_text(" ", strip=True) if hasattr(ns, "get_text") else "")
                        txt = norm(txt)
                        m = re.search(r"(20\d{2}-\d{2}-\d{2})", txt)
                        if m:
                            break
                    except Exception:
                        continue

            if not m:
                nxt = a.find_next(string=re.compile(r"20\d{2}-\d{2}-\d{2}"))
                if nxt:
                    m = re.search(r"(20\d{2}-\d{2}-\d{2})", str(nxt))

            dt = parse_ymd(m.group(1)) if m else None
            seen.add(full_url)
            results.append(
                {
                    "title": mark_income_related(title),
                    "url": full_url,
                    "date": dt,
                    "source": "nanchang_gjj_zcfg",
                }
            )
        except Exception:
            continue

    return results


def crawl_nanchang_gjj_zcfg(current_time: datetime | None = None, max_pages: int = 3) -> list[dict]:
    """抓取南昌公积金政策法规板块标题与链接，保留可用于 24 小时过滤的日期字段。"""
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
            print(f"[Nanchang GJJ] Crawl error(p{page_no}): {e}")
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
