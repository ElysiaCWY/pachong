# -*- coding: utf-8 -*-
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, mark_income_related, now_cn, norm


GUIZHOU_RST_POLICY_INDEX = "https://rst.guizhou.gov.cn/zwgk/jdhy/zcwj/"
GUIZHOU_RST_POLICY_PAGE_FMT = "https://rst.guizhou.gov.cn/zwgk/jdhy/zcwj/index_{page}.html"

GUIZHOU_RST_DB_INDEX = "https://rst.guizhou.gov.cn/zwgk/gzhgfxwjsjk/gfxwjsjk/index.html"
GUIZHOU_RST_DB_API = "https://rst.guizhou.gov.cn/irs/front/list?orderBy=startTime_desc"
GUIZHOU_RST_DB_TABLE = "t_179d1430e47"
GUIZHOU_RST_DB_CHANNEL = "5818754"
GUIZHOU_RST_DB_TENANT = "303"


def _policy_page_url(page_no: int) -> str:
    if page_no <= 1:
        return GUIZHOU_RST_POLICY_INDEX
    return GUIZHOU_RST_POLICY_PAGE_FMT.format(page=page_no - 1)


def _parse_policy_dt(text: str):
    text = norm(text)
    m = re.search(r"(20\d{2}-\d{2}-\d{2})\s+(\d{2}:\d{2})", text)
    if not m:
        return None
    try:
        dt = datetime.strptime(f"{m.group(1)} {m.group(2)}", "%Y-%m-%d %H:%M")
    except Exception:
        return None
    return dt.replace(tzinfo=now_cn().tzinfo)


def _extract_policy_page_items(page_url: str, html: str, now: datetime, since_dt: datetime):
    soup = BeautifulSoup(html, "html.parser")
    items = []
    newest_dt = None

    for a_tag in soup.find_all("a", href=True):
        href = norm(a_tag.get("href") or "")
        if not re.search(r"/zwgk/jdhy/zcwj/\d{6}/t\d+_\d+\.html$", href):
            continue

        title = norm(a_tag.get("title") or a_tag.get_text(" ", strip=True))
        if not title:
            continue

        li_tag = a_tag.find_parent("li") or a_tag.parent
        container_text = norm(li_tag.get_text(" ", strip=True) if li_tag else a_tag.get_text(" ", strip=True))
        dt = _parse_policy_dt(container_text)
        if not dt:
            continue
        if dt > now:
            continue

        if newest_dt is None or dt > newest_dt:
            newest_dt = dt

        if dt < since_dt:
            continue

        items.append(
            {
                "title": mark_income_related(title),
                "url": urljoin(page_url, href),
                "date": dt.date(),
                "source": "guizhou_rst_policy",
            }
        )

    return items, newest_dt


def _db_payload(page_no: int, page_size: int = 10) -> dict:
    return {
        "tenantId": GUIZHOU_RST_DB_TENANT,
        "tableName": GUIZHOU_RST_DB_TABLE,
        "pageNo": page_no,
        "pageSize": page_size,
        "searchFields": [{"fieldName": "f_202163381596", "searchWord": GUIZHOU_RST_DB_CHANNEL}],
        "sorts": [{"sortField": "save_time", "sortOrder": "DESC"}],
        "isPage": True,
    }


def _extract_db_page_items(data: dict, now: datetime, since_dt: datetime):
    items = []
    newest_dt = None
    for row in data.get("data", {}).get("list", []) or []:
        title = norm(row.get("f_202163974476") or "")
        href = norm(row.get("doc_pub_url") or "")
        save_time = norm(row.get("save_time") or "")
        if not title or not href or not save_time:
            continue

        try:
            dt = datetime.strptime(save_time[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=now.tzinfo)
        except Exception:
            continue

        if dt > now:
            continue
        if newest_dt is None or dt > newest_dt:
            newest_dt = dt
        if dt < since_dt:
            continue

        items.append(
            {
                "title": mark_income_related(title),
                "url": href if href.startswith("http") else urljoin(GUIZHOU_RST_DB_INDEX, href),
                "date": dt.date(),
                "source": "guizhou_rst_db",
            }
        )

    return items, newest_dt


def crawl_guizhou_rst_policy(current_time: datetime | None = None, max_pages: int = 30) -> list[dict]:
    """抓取贵州省人社厅政策文件与规范性文件数据库的标题和链接，仅保留近24小时内条目。"""
    now = current_time or now_cn()
    if now.tzinfo is None:
        now = now.replace(tzinfo=now_cn().tzinfo)
    since_dt = now - timedelta(hours=24)

    session = make_session()
    results: list[dict] = []
    seen_urls: set[str] = set()

    # 1) 政策文件栏目（静态分页）
    for page_no in range(1, max_pages + 1):
        page_url = _policy_page_url(page_no)
        try:
            resp = session.get(page_url, timeout=20)
            resp.encoding = resp.apparent_encoding or "utf-8"
            if resp.status_code != 200:
                break
        except Exception as e:
            print(f"[GuizhouRST] fetch failed(policy,page={page_no}): {e}")
            break

        page_items, newest_dt = _extract_policy_page_items(page_url, resp.text, now, since_dt)
        if not page_items and newest_dt is None:
            break

        for item in page_items:
            if item["url"] in seen_urls:
                continue
            seen_urls.add(item["url"])
            results.append(item)

        if newest_dt and newest_dt < since_dt:
            break

    # 2) 规范性文件数据库（API 分页）
    for page_no in range(1, max_pages + 1):
        try:
            resp = session.post(GUIZHOU_RST_DB_API, json=_db_payload(page_no), timeout=20)
            if resp.status_code != 200:
                break
            data = resp.json()
        except Exception as e:
            print(f"[GuizhouRST] fetch failed(db,page={page_no}): {e}")
            break

        page_items, newest_dt = _extract_db_page_items(data, now, since_dt)
        if not page_items and newest_dt is None:
            break

        for item in page_items:
            if item["url"] in seen_urls:
                continue
            seen_urls.add(item["url"])
            results.append(item)

        pager = (data.get("data") or {}).get("pager") or {}
        total = pager.get("total")
        page_size = pager.get("pageSize") or 10
        if total and page_no * page_size >= total:
            break
        if newest_dt and newest_dt < since_dt:
            break

    results.sort(key=lambda x: (x["date"], x["title"]), reverse=True)
    return results