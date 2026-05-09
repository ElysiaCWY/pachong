# -*- coding: utf-8 -*-
import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, mark_income_related, now_cn, norm, parse_ymd

INDEX_URL = "https://www.yuncheng.gov.cn/bmzt/zfgjjzl/zcfg/index.shtml"


def _page_url(page_no: int) -> str:
    if page_no <= 1:
        return INDEX_URL
    # 常见分页形式 index_{n}.shtml
    return urljoin(INDEX_URL.rsplit('/', 1)[0] + '/', f"index_{page_no}.shtml")


def _parse_chinese_date(text: str):
    if not text:
        return None
    m = re.search(r"(20\d{2}年\s*\d{1,2}月\s*\d{1,2}日)", text)
    if not m:
        return None
    s = m.group(1)
    nums = re.findall(r"\d+", s)
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

            # 目标为本栏目下的详情页
            if not full.lower().endswith(('.shtml', '.html')):
                continue

            if 'bmzt/zfgjjzl/zcfg' not in full and '/zcfg/' not in full:
                if '/bmzt/' not in full:
                    continue

            dt = None
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
                # 尝试中文日期格式
                dt = _parse_chinese_date(title) or _parse_chinese_date(container_text)

            # 也可能有独立的 <span class="time"> 或 class 包含 date 的元素
            if dt is None and container:
                span = container.find('span', class_=re.compile(r'(time|date)', re.I))
                if span:
                    st = norm(span.get_text(' ', strip=True))
                    dt = parse_ymd(st) or _parse_chinese_date(st)

            key = (full, title)
            if key in seen:
                continue
            seen.add(key)

            results.append({
                'title': mark_income_related(title),
                'url': full,
                'date': dt,
                'source': 'yuncheng_policy',
            })
        except Exception:
            continue

    return results


def crawl_yuncheng_policy(current_time: datetime | None = None, max_pages: int = 3) -> list[dict]:
    """抓取运城市政务网 - 政策法规栏目（返回 title/url/date/source 列表）。外层负责 24 小时过滤。"""
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
            print(f"[YUNCHENG] Crawl error(p{page_no}): {e}")
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
