# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, date
import json
from urllib.parse import urljoin, urlsplit, urlunsplit

from .common import make_session, mark_income_related, now_cn, norm, parse_ymd


QTHGJJ_INDEX = "https://www.qthgjj.org.cn/qthsgjj/c101097/zdhlist.shtml"
QTHGJJ_CHANNEL_ID = "4e1876185304470e8e47d908914bb47d"
QTHGJJ_API = "https://www.qthgjj.org.cn/common/search/{channel_id}?_isAgg=false&_isJson=true&_pageSize={page_size}&_template=index&_rangeTimeGte=&_channelName=&page={page_no}"


def _normalize_url(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme == "http" and parts.netloc.endswith(":80"):
        return urlunsplit((parts.scheme, parts.netloc[:-3], parts.path, parts.query, parts.fragment))
    if parts.scheme == "https" and parts.netloc.endswith(":443"):
        return urlunsplit((parts.scheme, parts.netloc[:-4], parts.path, parts.query, parts.fragment))
    return url


def _page_url(page_no: int, page_size: int = 20) -> str:
    return QTHGJJ_API.format(channel_id=QTHGJJ_CHANNEL_ID, page_size=page_size, page_no=page_no)


def _extract_page_items(api_payload: dict, since_dt: datetime) -> tuple[list[dict], bool]:
    results: list[dict] = []
    has_older_item = False

    for item in api_payload.get("data", {}).get("results", []) or []:
        title = norm(item.get("title") or "")
        url = norm(item.get("url") or "")
        published_str = norm(item.get("publishedTimeStr") or item.get("publishedTime") or "")
        if not title or not url or not published_str:
            continue

        try:
            published_at = datetime.strptime(published_str[:19], "%Y-%m-%d %H:%M:%S")
        except Exception:
            published_at = None

        if not published_at:
            continue

        if published_at < since_dt:
            has_older_item = True
            continue

        results.append(
            {
                "title": mark_income_related(title),
                "url": _normalize_url(urljoin(QTHGJJ_INDEX, url)),
                "date": published_at.date(),
                "source": "qthgjj_zdhlist",
            }
        )

    return results, has_older_item


def crawl_qthgjj_zdhlist(current_time: datetime | None = None, max_pages: int = 3) -> list[dict]:
    """抓取七台河市住房公积金管理中心中心文件，仅保留近24小时内发布的标题和链接。"""
    now = current_time or now_cn()
    session = make_session()
    results: list[dict] = []
    seen_urls: set[str] = set()
    since_dt = now - timedelta(days=1)

    for page_no in range(1, max_pages + 1):
        page_url = _page_url(page_no)
        try:
            resp = session.get(page_url, timeout=20)
            resp.encoding = resp.apparent_encoding or "utf-8"
        except Exception as e:
            print(f"[QTHGJJ] fetch failed(page={page_no}): {e}")
            break

        if resp.status_code != 200:
            break

        try:
            payload = resp.json()
        except Exception:
            try:
                payload = json.loads(resp.text)
            except Exception:
                break

        page_items, has_older_item = _extract_page_items(payload, since_dt)
        if not page_items and page_no == 1:
            break

        for item in page_items:
            if item["url"] in seen_urls:
                continue
            seen_urls.add(item["url"])
            results.append(item)

        if has_older_item:
            break

    results.sort(key=lambda x: (x.get("date") or now.date(), x.get("title", "")), reverse=True)
    return results