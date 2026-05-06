# -*- coding: utf-8 -*-
import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, now_cn, norm, parse_ymd, mark_income_related


INDEX_URL = "https://gjj.nanjing.gov.cn/zwgk/tzgg/"
PAGE_FMT = "https://gjj.nanjing.gov.cn/zwgk/tzgg/index_{page}.html"


def _candidate_page_url(first_url: str, page_no: int) -> str:
    if page_no <= 1:
        return first_url
    return PAGE_FMT.format(page=page_no - 1)


def _parse_list_page(html: str, page_url: str) -> list[dict]:
    soup = BeautifulSoup(html or "", "html.parser")
    results: list[dict] = []

    for a in soup.find_all("a", href=True):
        try:
            href = (a.get("href") or "").strip()
            if not href.endswith('.html'):
                continue
            full = urljoin(page_url, href)
            # 仅保留指向本板块的链接
            if "/zwgk/tzgg/" not in full:
                continue

            title = norm(a.get_text(" ", strip=True))
            if not title:
                continue

            # 优先从同一父元素中寻找日期，再在邻近文本中查找
            date_text = ""
            # 优先在更宽的容器中找日期（如 <li> 包含 <span> 和日期文本）
            container = a.parent.parent if a.parent and a.parent.parent else (a.parent if a.parent else None)
            container_text = norm(container.get_text(" ", strip=True)) if container else ""
            m = re.search(r"(20\d{2}-\d{2}-\d{2})", container_text)
            if m:
                date_text = m.group(1)
            else:
                # 检查紧邻的兄弟节点和后续文本
                for ns in a.next_siblings:
                    try:
                        txt = ns if isinstance(ns, str) else (ns.get_text(" ", strip=True) if hasattr(ns, "get_text") else "")
                        txt = norm(txt)
                        m = re.search(r"(20\d{2}-\d{2}-\d{2})", txt)
                        if m:
                            date_text = m.group(1)
                            break
                    except Exception:
                        continue

            results.append({
                "title": mark_income_related(title),
                "url": full,
                "date": parse_ymd(date_text) if date_text else None,
                "source": "nanjing_gjj_tzgg",
            })
        except Exception:
            continue

    return results


def crawl_nanjing_gjj_tzgg(current_time: datetime | None = None, max_pages: int = 6) -> list[dict]:
    """抓取南京住房公积金网 - 通知公告（近24小时候选项通过主流程过滤）。"""
    _ = current_time or now_cn()
    session = make_session()
    results: list[dict] = []
    seen = set()

    for p in range(1, max_pages + 1):
        page_url = _candidate_page_url(INDEX_URL, p)
        try:
            resp = session.get(page_url, timeout=15)
            resp.encoding = resp.apparent_encoding or "utf-8"
            if resp.status_code != 200:
                break
        except Exception as e:
            print(f"[NanjingGJJ] Crawl error(p{p}): {e}")
            break

        page_items = _parse_list_page(resp.text, page_url)
        if not page_items:
            break

        page_has_new = False
        for it in page_items:
            if it["url"] in seen:
                continue
            seen.add(it["url"])
            results.append(it)
            page_has_new = True

        if p > 1 and not page_has_new:
            break

    # 最近的在前
    results.sort(key=lambda x: (x.get("date") or now_cn().date(), x.get("title", "")), reverse=True)
    return results
