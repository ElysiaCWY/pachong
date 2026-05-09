# -*- coding: utf-8 -*-
import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, mark_income_related, now_cn, norm, parse_ymd

INDEX_URL = "http://www.lvliang.gov.cn/zfjgzd/gjjglzx/zcfg/"


def _page_url(page_no: int) -> str:
    if page_no <= 1:
        return INDEX_URL
    # 站点可能使用 index_{n}.shtml 或 index_{n}.html
    return urljoin(INDEX_URL, f"index_{page_no}.shtml")


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

            # 限制到本栏目路径或包含 /zcfg/
            if '/zcfg/' not in full and 'gjjglzx' not in full:
                if '/zfjgzd/' not in full:
                    continue

            dt = None
            # 尝试 YYYY-MM-DD
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

            # 尝试中文日期
            if dt is None:
                m3 = re.search(r"(20\d{2}年\s*\d{1,2}月\s*\d{1,2}日)", container_text)
                if m3:
                    nums = re.findall(r"\d+", m3.group(1))
                    if len(nums) >= 3:
                        try:
                            y, mth, d = map(int, nums[:3])
                            dt = datetime(y, mth, d).date()
                        except Exception:
                            dt = None

            # 也检查同级的 <span class="time"> 或 class 含 date 的元素
            if dt is None and container:
                span = container.find(lambda tag: tag.name == 'span' and ('time' in (tag.get('class') or []) or re.search(r'(date|time)', ' '.join(tag.get('class') or []), re.I)))
                if span:
                    st = norm(span.get_text(' ', strip=True))
                    dt = parse_ymd(st) or (lambda s: (lambda nums: (datetime(int(nums[0]), int(nums[1]), int(nums[2])).date() if len(nums)>=3 else None))(re.findall(r'\d+', s)))(st)

            key = (full, title)
            if key in seen:
                continue
            seen.add(key)

            results.append({
                'title': mark_income_related(title),
                'url': full,
                'date': dt,
                'source': 'lvliang_policy',
            })
        except Exception:
            continue

    return results


def crawl_lvliang_policy(current_time: datetime | None = None, max_pages: int = 3) -> list[dict]:
    """抓取吕梁市政府 - 政策法规栏目（返回 title/url/date/source 列表）。外层负责 24 小时过滤。"""
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
            print(f"[LVLIANG] Crawl error(p{page_no}): {e}")
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
