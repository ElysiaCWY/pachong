# -*- coding: utf-8 -*-
import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, mark_income_related, now_cn, norm, parse_ymd


INDEX_URL = "http://gjjzx.changsha.gov.cn/jdhy/wzjd/"


def _page_url(page_no: int) -> str:
    if page_no <= 1:
        return INDEX_URL
    return urljoin(INDEX_URL, f"index_{page_no - 1}.html")


def _extract_items(page_url: str, html: str) -> list[dict]:
    soup = BeautifulSoup(html or "", "html.parser")
    results: list[dict] = []
    seen = set()

    # 页面中列表项通常以“YYYY-MM-DD[标题](url)”形式排列，或为若干 <a> 链接
    # 遍历所有 a 标签并过滤出指向具体 html 页的链接
    for a in soup.find_all("a", href=True):
        try:
            href = norm(a.get("href") or "")
            title = norm(a.get_text(" ", strip=True))
            if not href or not title:
                continue

            full_url = urljoin(page_url, href)
            # 仅保留指向详情页的 html 链接
            if not full_url.lower().endswith('.html'):
                continue

            # 有些站点把日期写在 a 文本前或父容器里，尝试从 a 本身或父容器提取 YYYY-MM-DD
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
                    "source": "changsha_gjj_wzjd",
                }
            )
        except Exception:
            continue

    return results


def crawl_changsha_gjj_wzjd(current_time: datetime | None = None, max_pages: int = 2) -> list[dict]:
    """抓取长沙住房公积金管理中心 - 文字解读（近24小时筛选需依赖 date 字段）"""
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
            print(f"[Changsha GJJ] Crawl error(p{page_no}): {e}")
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
