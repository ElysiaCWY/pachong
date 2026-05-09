# -*- coding: utf-8 -*-
import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, mark_income_related, now_cn, norm, parse_ymd

SITE_BASE = "https://yqgjj.yq.gov.cn"
INDEX_URL = SITE_BASE + "/zcfg/"


def _parse_chinese_date(text: str) -> datetime | None:
    if not text:
        return None
    m = re.search(r"(20\d{2}-\d{2}-\d{2})", text)
    if m:
        return parse_ymd(m.group(1))
    m2 = re.search(r"(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日", text)
    if m2:
        y, mo, d = m2.group(1), m2.group(2).zfill(2), m2.group(3).zfill(2)
        try:
            return parse_ymd(f"{y}-{mo}-{d}")
        except Exception:
            return None
    return None


def _parse_list_page(html: str, page_url: str) -> list[dict]:
    soup = BeautifulSoup(html or "", "html.parser")
    results: list[dict] = []

    for a in soup.find_all("a", href=True):
        try:
            href = (a.get("href") or "").strip()
            if not href:
                continue

            # 仅站内链接或相对链接，且通常以 .html 或 .shtml 结尾
            if not (href.endswith('.html') or href.endswith('.shtml')):
                continue

            full = urljoin(page_url, href)
            if not full.startswith(SITE_BASE):
                continue

            title = norm(a.get_text(" ", strip=True))
            if not title or len(title) < 4:
                continue

            # 尝试在父容器或相邻文本中找到日期
            date_text = ""
            container = a.parent.parent if a.parent and a.parent.parent else (a.parent if a.parent else None)
            container_text = norm(container.get_text(" ", strip=True)) if container else ""
            dt = _parse_chinese_date(container_text)

            if dt is None:
                # 查找相邻 sibling 或后续文本
                for ns in a.next_siblings:
                    try:
                        txt = ns if isinstance(ns, str) else (ns.get_text(" ", strip=True) if hasattr(ns, "get_text") else "")
                        txt = norm(txt)
                        dt = _parse_chinese_date(txt)
                        if dt:
                            break
                    except Exception:
                        continue

            if dt is None:
                nxt = a.find_next(string=re.compile(r"20\d{2}-\d{2}-\d{2}|20\d{2}年"))
                if nxt:
                    dt = _parse_chinese_date(str(nxt))

            results.append({
                "title": mark_income_related(title),
                "url": full,
                "date": dt,
                "source": "yqgjj_policy",
            })
        except Exception:
            continue

    return results


def crawl_yqgjj_policy(current_time: datetime | None = None, max_pages: int = 3) -> list[dict]:
    """抓取永清/阳泉（yqgjj）站点的政策法规列表，返回 title/url/date/source 列表。仅收集页面上的标题/链接和可解析的日期（供外层统一做 24 小时过滤）。"""
    _ = current_time or now_cn()
    session = make_session()
    results: list[dict] = []
    seen = set()

    for p in range(1, max_pages + 1):
        page_url = INDEX_URL if p <= 1 else INDEX_URL
        try:
            resp = session.get(page_url, timeout=15)
            resp.encoding = resp.apparent_encoding or "utf-8"
            if resp.status_code != 200:
                break
        except Exception as e:
            print(f"[YQGJJ] Crawl error(p{p}): {e}")
            break

        page_items = _parse_list_page(resp.text, page_url)
        if not page_items:
            continue

        page_has_new = False
        for it in page_items:
            if it["url"] in seen:
                continue
            seen.add(it["url"])
            results.append(it)
            page_has_new = True

        if p > 1 and not page_has_new:
            break

    results.sort(key=lambda x: (x.get("date") or now_cn().date(), x.get("title", "")), reverse=True)
    return results
