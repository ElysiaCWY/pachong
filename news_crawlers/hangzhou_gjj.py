# -*- coding: utf-8 -*-
import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, now_cn, norm, parse_ymd, mark_income_related

INDEX_URL = "https://gjj.hangzhou.gov.cn/col/col1229287759/index.html"
PAGE_FMT = "https://gjj.hangzhou.gov.cn/col/col1229287759/index_{page}.html"


def _candidate_page_url(first_url: str, page_no: int) -> str:
    if page_no <= 1:
        return first_url
    return PAGE_FMT.format(page=page_no)


def _parse_list_page(html: str, page_url: str) -> list[dict]:
    soup = BeautifulSoup(html or "", "html.parser")
    results: list[dict] = []

    # 常见结构：列表中含 <a href="...">标题</a>，附近或父节点包含发布日期
    for a in soup.find_all("a", href=True):
        try:
            href = (a.get("href") or "").strip()
            if not href:
                continue

            # 仅保留具体文章页（站点使用 /art/ 路径发布文章）
            if '/art/' not in href or not href.endswith('.html'):
                continue

            full = urljoin(page_url, href)

            title = norm(a.get_text(" ", strip=True))
            if not title:
                continue

            # 在父容器或相邻文本中寻找日期 YYYY-MM-DD
            date_text = ""
            container = a.parent.parent if a.parent and a.parent.parent else (a.parent if a.parent else None)
            container_text = norm(container.get_text(" ", strip=True)) if container else ""
            m = re.search(r"(20\d{2}-\d{2}-\d{2})", container_text)
            if not m:
                # 检查紧邻的兄弟节点和后续文本
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
                # 在后续元素中查找日期文本
                nxt = a.find_next(string=re.compile(r"20\d{2}-\d{2}-\d{2}"))
                if nxt:
                    m = re.search(r"(20\d{2}-\d{2}-\d{2})", str(nxt))

            dt = parse_ymd(m.group(1)) if m else None

            results.append({
                "title": mark_income_related(title),
                "url": full,
                "date": dt,
                "source": "hangzhou_gjj_xzfg",
            })
        except Exception:
            continue

    return results


def crawl_hangzhou_gjj_xzfg(current_time: datetime | None = None, max_pages: int = 4) -> list[dict]:
    """抓取杭州住房公积金网 - 行政规范性文件（列表页标题+链接+日期），返回条目列表。"""
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
            print(f"[Hangzhou GJJ] Crawl error(p{p}): {e}")
            break

        page_items = _parse_list_page(resp.text, page_url)
        if not page_items:
            # 如果当前页没有匹配结果，继续下一页以兼容不同分页
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

    # 最近的在前
    results.sort(key=lambda x: (x.get("date") or now_cn().date(), x.get("title", "")), reverse=True)
    return results
