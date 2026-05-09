# -*- coding: utf-8 -*-
import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, mark_income_related, now_cn, norm, parse_ymd

INDEX_URL = "https://xzgjj.sxxz.gov.cn/zcfg/zxwj/"


def _page_url(page_no: int) -> str:
    if page_no <= 1:
        return INDEX_URL
    return urljoin(INDEX_URL, f"index_{page_no}.html")


def _parse_chinese_date(text: str):
    if not text:
        return None
    m = re.search(r"(20\d{2}年\s*\d{1,2}月\s*\d{1,2}日)", text)
    if not m:
        return None
    nums = re.findall(r"\d+", m.group(1))
    if len(nums) >= 3:
        y, mth, d = map(int, nums[:3])
        try:
            return datetime(y, mth, d).date()
        except Exception:
            return None
    return None


def _extract_items(page_url: str, html: str) -> list[dict]:
    soup = BeautifulSoup(html or "", "html.parser")
    results: list[dict] = []
    seen = set()

    for a in soup.find_all('a', href=True):
        try:
            href = norm(a.get('href') or '')
            title = norm(a.get_text(' ', strip=True))
            if not href or not title:
                continue

            full = urljoin(page_url, href)

            # 目标通常为站内详情页
            if not full.lower().endswith(('.html', '.shtml')):
                continue

            # 限制到本栏目路径或至少包含 /zcfg/ 或 /zxwj/
            if '/zcfg/zxwj/' not in full and '/zxwj/' not in full and '/zcfg/' not in full:
                if '/zcfg' not in full and '/zwgk' not in full:
                    continue

            dt = None
            # 优先尝试 YYYY-MM-DD
            m = re.search(r"(20\d{2}[-/\.]\d{1,2}[-/\.]\d{1,2})", title)
            if m:
                dt = parse_ymd(m.group(1))
                title = norm(title.replace(m.group(1), '', 1))

            if dt is None:
                container = a.parent
                container_text = norm(container.get_text(' ', strip=True)) if container else ''
                m2 = re.search(r"(20\d{2}[-/\.]\d{1,2}[-/\.]\d{1,2})", container_text)
                if m2:
                    dt = parse_ymd(m2.group(1))

            if dt is None:
                # 尝试中文日期
                dt = _parse_chinese_date(title) or _parse_chinese_date(container_text)

            # 可能在同级 <span> 中
            if dt is None and container:
                sib = container.find('span')
                if sib:
                    st = norm(sib.get_text(' ', strip=True))
                    dt = parse_ymd(st) or _parse_chinese_date(st)

            key = (full, title)
            if key in seen:
                continue
            seen.add(key)

            results.append({
                'title': mark_income_related(title),
                'url': full,
                'date': dt,
                'source': 'sxxz_xzgjj',
            })
        except Exception:
            continue

    return results


def crawl_sxxz_xzgjj_zxwj(current_time: datetime | None = None, max_pages: int = 3) -> list[dict]:
    """抓取陕西咸阳市（xzgjj.sxxz.gov.cn）- 中心文件栏目（返回 title/url/date/source 列表）。外层负责 24 小时过滤。"""
    _ = current_time or now_cn()
    session = make_session()
    results: list[dict] = []
    seen_urls = set()

    for page_no in range(1, max_pages + 1):
        page_url = _page_url(page_no)
        try:
            resp = session.get(page_url, timeout=15)
            resp.encoding = resp.apparent_encoding or 'utf-8'
            if resp.status_code != 200:
                break
        except Exception as e:
            print(f"[SXXZ XZGJJ] Crawl error(p{page_no}): {e}")
            break

        page_items = _extract_items(page_url, resp.text)
        if not page_items:
            continue

        page_has_new = False
        for it in page_items:
            if it['url'] in seen_urls:
                continue
            seen_urls.add(it['url'])
            results.append(it)
            page_has_new = True

        if page_no > 1 and not page_has_new:
            break

    results.sort(key=lambda x: (x.get('date') or now_cn().date(), x.get('title', '')), reverse=True)
    return results
