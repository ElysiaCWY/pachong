# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from urllib.parse import urljoin
import re

from bs4 import BeautifulSoup

from .common import make_session, mark_income_related, now_cn, norm


ZJK_GJJ_INDEX = "https://www.zjkgjj.cn/qiyexinxi/46.html"
ARTICLE_RE = re.compile(r"^https?://www\.zjkgjj\.cn/InformationDisclosure_details/\d+\.html$")
DATETIME_RE = re.compile(r"(20\d{2}-\d{2}-\d{2}\s+\d{2}:\d{2})")


def _parse_items(page_url: str, html: str, now: datetime, since_dt: datetime) -> list[dict]:
    soup = BeautifulSoup(html or "", "html.parser")
    results: list[dict] = []
    seen = set()

    # 页面核心结构：div.p_list > div.p_loopitem > p.e_text-14.s_title + 时间文本
    for item in soup.select("div.p_list div.p_loopitem"):
        a = item.find("a", href=True)
        if not a:
            continue

        href = norm(a.get("href") or "")
        if not href:
            continue

        full_url = urljoin(page_url, href)
        if not ARTICLE_RE.match(full_url):
            continue

        title = norm(a.get_text(" ", strip=True) or a.get("title") or "")
        if not title:
            continue

        item_text = norm(item.get_text(" ", strip=True))
        m = DATETIME_RE.search(item_text)
        if not m:
            continue

        dt = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M")
        if now.tzinfo is not None and dt.tzinfo is None:
            dt = dt.replace(tzinfo=now.tzinfo)
        if dt > now:
            continue

        if dt < since_dt:
            continue

        key = full_url
        if key in seen:
            continue
        seen.add(key)

        results.append(
            {
                "title": mark_income_related(title),
                "url": full_url,
                "date": dt,
                "source": "zjkgjj_normative_files",
            }
        )

    return results


def crawl_zjkgjj_normative_files(current_time: datetime | None = None, max_pages: int = 1) -> list[dict]:
    """抓取张家口公积金网 - 规范性文件，仅保留近24小时内发布的标题和链接。"""
    now = current_time or now_cn()
    since_dt = now - timedelta(days=1)
    session = make_session()

    results: list[dict] = []

    for page_no in range(1, max_pages + 1):
        # 当前栏目页面未发现分页，保留接口形态便于后续扩展。
        page_url = ZJK_GJJ_INDEX
        try:
            resp = session.get(page_url, timeout=20)
            resp.encoding = resp.apparent_encoding or "utf-8"
            if resp.status_code != 200:
                break
        except Exception as e:
            print(f"[ZJKGJJ] fetch failed(page={page_no}): {e}")
            break

        page_items = _parse_items(page_url, resp.text, now, since_dt)
        if not page_items:
            break

        results.extend(page_items)
        # 页面看起来是单页列表；如果后续有分页，可在这里扩展。
        break

    results.sort(key=lambda x: (x.get("date") or now, x.get("title", "")), reverse=True)
    return results
