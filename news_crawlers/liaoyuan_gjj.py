# -*- coding: utf-8 -*-
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, mark_income_related, now_cn, norm, parse_ymd


INDEX_URL = "https://www.lygjj.cn/zecjd/index.jhtml"
HOME_URL = "https://www.lygjj.cn/"
PAGE_FMT = "https://www.lygjj.cn/zecjd/index_{page}.jhtml"


def _page_url(page_no: int) -> str:
    if page_no <= 1:
        return INDEX_URL
    return PAGE_FMT.format(page=page_no - 1)


def _extract_date_from_text(text: str):
    text = norm(text or "")
    if not text:
        return None

    match = re.search(r"(20\d{2}-\d{2}-\d{2})", text)
    if match:
        return parse_ymd(match.group(1))

    match = re.search(r"(20\d{2})[年/-](\d{1,2})[月/-](\d{1,2})日?", text)
    if match:
        return parse_ymd(f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}")

    return None


def _clean_title(text: str) -> str:
    title = norm(text or "")
    if not title:
        return ""
    title = re.sub(r"^(?:\[[^\]]+\])+,?", "", title).strip()
    title = re.sub(r"^20\d{2}-\d{2}-\d{2}", "", title).strip()
    return title


def _extract_items(page_url: str, html: str) -> list[dict]:
    soup = BeautifulSoup(html or "", "html.parser")
    results: list[dict] = []
    seen = set()

    # Links are like /zecjd/1872.jhtml and date appears adjacent
    for a in soup.select("a[href]"):
        try:
            href = norm(a.get("href") or "")
            if not href or not href.lower().endswith(".jhtml"):
                continue

            full_url = urljoin(page_url, href)
            # only accept urls under /zecjd/
            if "/zecjd/" not in full_url:
                continue

            title = _clean_title(a.get_text(" ", strip=True) or a.get("title") or "")
            if not title:
                continue

            # skip index page links
            if full_url.rstrip('/').endswith('index.jhtml'):
                continue

            # try to extract date from a nearby span (site uses <span class="spantime">YYYY-MM-DD</span>)
            dt = None
            container = a.find_parent('li') or (a.parent if a.parent else None)
            if container:
                span = container.select_one('.spantime')
                if span:
                    dt = _extract_date_from_text(span.get_text(' ', strip=True))
            if not dt and container:
                container_text = norm(container.get_text(' ', strip=True))
                dt = _extract_date_from_text(container_text)
            if not dt:
                dt = _extract_date_from_text(title)

            if full_url in seen:
                continue
            seen.add(full_url)

            results.append(
                {
                    "title": mark_income_related(title),
                    "url": full_url,
                    "date": dt,
                    "source": "liaoyuan_gjj_policy",
                }
            )
        except Exception:
            continue

    return results


def crawl_liaoyuan_gjj_zecjd(current_time: datetime | None = None, max_pages: int = 5) -> list[dict]:
    """抓取辽源市住房公积金管理中心 - 中心规定文件（近24小时）。"""
    now = current_time or now_cn()
    session = make_session()
    results: list[dict] = []
    seen_urls = set()
    since_date = (now - timedelta(hours=24)).date()

    try:
        session.get(HOME_URL, timeout=15)
    except Exception:
        pass

    for page_no in range(1, max_pages + 1):
        page_url = _page_url(page_no)
        try:
            resp = session.get(page_url, timeout=15)
            resp.encoding = resp.apparent_encoding or "utf-8"
            if resp.status_code != 200:
                break
        except Exception as e:
            print(f"[Liaoyuan GJJ] Crawl error(p{page_no}): {e}")
            break

        page_items = _extract_items(page_url, resp.text)
        if not page_items:
            break

        page_has_new = False
        page_oldest_dt = None
        for it in page_items:
            dt = it.get("date")
            if dt and (page_oldest_dt is None or dt < page_oldest_dt):
                page_oldest_dt = dt
            if dt and dt < since_date:
                continue
            if it["url"] in seen_urls:
                continue
            seen_urls.add(it["url"])
            results.append(it)
            page_has_new = True

        if page_no > 1 and not page_has_new:
            break
        if page_oldest_dt and page_oldest_dt < since_date:
            break

    results.sort(key=lambda x: (x.get("date") or now_cn().date(), x.get("title", "")), reverse=True)
    return results
