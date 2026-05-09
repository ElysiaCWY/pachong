# -*- coding: utf-8 -*-
import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, mark_income_related, now_cn, norm, parse_ymd

INDEX_URL = "https://www.sxjz.gov.cn/zwgk/bmxxgk/66gjjzx/xxgkmlgjj/zcwj66gjjzx"


def _page_url(page_no: int) -> str:
    if page_no <= 1:
        return INDEX_URL
    # 站点分页格式不确定，尝试常见命名 index_2.html
    return urljoin(INDEX_URL + '/', f"index_{page_no - 1}.html")


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

            full = urljoin(page_url, href)

            # 限制为站内详情页（通常以 .html 结尾）
            if not full.lower().endswith(('.html', '.shtml')):
                continue

            # 仅保留路径包含本栏目标识的链接
            if 'zwgk/bmxxgk/66gjjzx' not in full and '/zcwj66gjjzx' not in full:
                # 有时候站点使用不同路径，仍允许以 /zwgk/ 开头
                if '/zwgk/' not in full:
                    continue

            # 尝试解析日期 YYYY-MM-DD 或 YYYY/MM/DD
            dt = None
            m = re.search(r"(20\d{2}[-/\.]\d{1,2}[-/\.]\d{1,2})", title)
            if m:
                dt = parse_ymd(m.group(1))
                title = norm(title.replace(m.group(1), "", 1))

            if dt is None:
                container = a.parent if a.parent else None
                container_text = norm(container.get_text(" ", strip=True)) if container else ""
                m2 = re.search(r"(20\d{2}[-/\.]\d{1,2}[-/\.]\d{1,2})", container_text)
                if m2:
                    dt = parse_ymd(m2.group(1))

            # 有些页面将日期放在同级的 <span> 中
            if dt is None:
                sib = a.find_next_sibling()
                if sib:
                    stext = norm(sib.get_text(" ", strip=True))
                    m3 = re.search(r"(20\d{2}[-/\.]\d{1,2}[-/\.]\d{1,2})", stext)
                    if m3:
                        dt = parse_ymd(m3.group(1))

            key = (full, title)
            if key in seen:
                continue
            seen.add(key)

            results.append({
                "title": mark_income_related(title),
                "url": full,
                "date": dt,
                "source": "sxjz_policy",
            })
        except Exception:
            continue

    return results


def crawl_sxjz_policy(current_time: datetime | None = None, max_pages: int = 3) -> list[dict]:
    """抓取晋中市（sxjz.gov.cn）- 政策文件栏目，返回 title/url/date/source 列表。外层负责 24 小时过滤。"""
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
            print(f"[SXJZ] Crawl error(p{page_no}): {e}")
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
