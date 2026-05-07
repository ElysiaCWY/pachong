# -*- coding: utf-8 -*-
import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, mark_income_related, now_cn, norm, parse_ymd


KUNMING_GJJ_CHANNELS = [
    "https://zfgjj.km.gov.cn/zfxxgk/zcwj/xzgfxwj/",
    "https://zfgjj.km.gov.cn/zfxxgk/zcwj/qtwj/",
]


def _channel_page_url(channel_url: str, page_no: int) -> str:
    if page_no <= 1:
        return channel_url
    return urljoin(channel_url, f"index_{page_no - 1}.shtml")


def _extract_item_date(text: str):
    text = norm(text)
    if not text:
        return None

    m = re.search(r"(20\d{2}-\d{1,2}-\d{1,2})", text)
    if not m:
        return None

    return parse_ymd(m.group(1))


def _looks_like_datetime_text(text: str) -> bool:
    text = norm(text)
    if not text:
        return True
    if re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?", text):
        return True
    if re.fullmatch(r"\d{1,2}:\d{2}(?::\d{2})?", text):
        return True
    if not re.search(r"[\u4e00-\u9fffA-Za-z]", text):
        return True
    return False


def _extract_page_items(page_url: str, html: str):
    soup = BeautifulSoup(html or "", "html.parser")
    items: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def _append_item(href: str, raw_title: str, raw_date_text: str = ""):
        href = norm(href)
        if not href:
            return

        full_url = urljoin(page_url, href)
        if "zfgjj.km.gov.cn/c/" not in full_url:
            return
        if not full_url.lower().endswith((".shtml", ".html")):
            return

        raw_title = norm(raw_title)
        if not raw_title or len(raw_title) < 6:
            return

        date_obj = _extract_item_date(raw_date_text) or _extract_item_date(raw_title)
        if not date_obj:
            return

        title = norm(
            re.sub(
                r"\s*(20\d{2}-\d{1,2}-\d{1,2})(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?\s*$",
                "",
                raw_title,
            )
        )
        if not title or _looks_like_datetime_text(title):
            return

        key = (full_url, title)
        if key in seen:
            return
        seen.add(key)

        items.append(
            {
                "title": mark_income_related(title),
                "url": full_url,
                "date": date_obj,
                "source": "kunming_gjj_policy",
            }
        )

    # 优先匹配该站点数据表格结构（标题列 + 发布日期列）
    for row in soup.select("div.data-table-item"):
        title_a = row.select_one("p.w659 a[href]")
        if not title_a:
            continue
        date_a = row.select_one("p.w80 a")
        date_text = ""
        if date_a:
            date_text = norm(date_a.get("title") or date_a.get_text(" ", strip=True))
        _append_item(
            title_a.get("href") or "",
            title_a.get_text(" ", strip=True),
            date_text,
        )

    if items:
        return items

    for a_tag in soup.find_all("a", href=True):
        href = norm(a_tag.get("href") or "")
        parent_text = norm(a_tag.parent.get_text(" ", strip=True)) if a_tag.parent else ""
        raw_title = norm(a_tag.get("title") or a_tag.get_text(" ", strip=True))
        if not raw_title and not parent_text:
            continue

        candidate_title = raw_title
        if _looks_like_datetime_text(candidate_title):
            candidate_title = parent_text
        if not candidate_title or len(candidate_title) < 6:
            continue

        date_obj = _extract_item_date(raw_title) or _extract_item_date(parent_text)
        if not date_obj:
            continue

        title = norm(re.sub(r"\s*(20\d{2}-\d{1,2}-\d{1,2})(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?\s*$", "", candidate_title))
        if _looks_like_datetime_text(title):
            title = norm(re.sub(r"\s*(20\d{2}-\d{1,2}-\d{1,2})(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?\s*$", "", parent_text))
        if not title or _looks_like_datetime_text(title):
            continue

        _append_item(href, title, parent_text)

    return items


def crawl_kunming_gjj_policy(current_time: datetime | None = None, max_pages: int = 2) -> list[dict]:
    """抓取昆明住房公积金政策文件（行政规范性文件/其他文件）。

    仅返回标题、链接和日期；近24小时由主流程统一过滤。
    """
    _ = current_time or now_cn()
    session = make_session()
    results: list[dict] = []
    seen_urls: set[str] = set()

    for channel_url in KUNMING_GJJ_CHANNELS:
        for page_no in range(1, max_pages + 1):
            page_url = _channel_page_url(channel_url, page_no)
            try:
                resp = session.get(page_url, timeout=20)
                resp.encoding = resp.apparent_encoding or "utf-8"
            except Exception as e:
                print(f"[KunmingGJJ] fetch failed(page={page_no}): {e}")
                break

            if resp.status_code != 200:
                break

            page_items = _extract_page_items(page_url, resp.text)
            if not page_items:
                if page_no == 1:
                    continue
                break

            for item in page_items:
                if item["url"] in seen_urls:
                    continue
                seen_urls.add(item["url"])
                results.append(item)

    results.sort(key=lambda x: (x.get("date") or now_cn().date(), x.get("title", "")), reverse=True)
    return results