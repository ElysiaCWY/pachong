# -*- coding: utf-8 -*-
import re
from datetime import datetime, timedelta

import requests

from .common import mark_income_related, now_cn, norm


BASE_URL = "https://gjj.tonghua.gov.cn"
LIST_API = f"{BASE_URL}/api/fgzc/fgList"
DETAIL_URL = f"{BASE_URL}/views/CNewsDetail?id={{id}}"
LIST_CODE = "022001"


def _parse_publish_time(value: str):
    text = norm(value or "")
    if not text:
        return None

    text = text.replace("/", "-")
    text = re.sub(r"\s+", " ", text).strip()

    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _build_headers(referer: str) -> dict:
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Referer": referer,
        "X-Requested-With": "XMLHttpRequest",
    }


def _fetch_page(session: requests.Session, page_no: int, page_size: int, referer: str) -> dict:
    resp = session.get(
        LIST_API,
        params={"code": LIST_CODE, "pageNum": page_no, "pageSize": page_size},
        headers=_build_headers(referer),
        timeout=20,
    )
    resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.json()


def crawl_tonghua_gjj_notice(current_time: datetime | None = None, max_pages: int = 20, page_size: int = 10) -> list[dict]:
    """抓取通化市住房公积金管理中心通知公告，返回近24小时内的标题与链接。"""
    now = current_time or now_cn()
    since_dt = now - timedelta(hours=24)
    session = requests.Session()
    referer = f"{BASE_URL}/views/GovernmentInfo?contentCode=0220&contentMessage=%E9%80%9A%E7%9F%A5%E5%85%AC%E5%91%8A"
    results: list[dict] = []
    seen = set()

    try:
        session.get(referer, timeout=20)
    except Exception:
        pass

    for page_no in range(1, max_pages + 1):
        try:
            payload = _fetch_page(session, page_no, page_size, referer)
        except Exception as e:
            print(f"[Tonghua GJJ] Crawl error(p{page_no}): {e}")
            break

        body = payload.get("body") or {}
        items = body.get("list") or []
        if not items:
            break

        page_has_new = False
        page_oldest_dt = None
        for item in items:
            item_id = norm(item.get("id") or "")
            title = norm(item.get("title") or "")
            if not item_id or not title:
                continue

            publish_dt = _parse_publish_time(item.get("publishTime") or "")
            if publish_dt and (page_oldest_dt is None or publish_dt < page_oldest_dt):
                page_oldest_dt = publish_dt
            if publish_dt and publish_dt < since_dt:
                continue

            detail_url = DETAIL_URL.format(id=item_id)
            if detail_url in seen:
                continue
            seen.add(detail_url)

            results.append(
                {
                    "title": mark_income_related(re.sub(r"^[\ufeff\u200b]+", "", title).strip()),
                    "url": detail_url,
                    "date": publish_dt.date() if publish_dt else None,
                    "source": "tonghua_gjj_notice",
                }
            )
            page_has_new = True

        if page_no > 1 and not page_has_new:
            break
        if page_oldest_dt and page_oldest_dt < since_dt:
            break

    results.sort(key=lambda x: (x.get("date") or now_cn().date(), x.get("title", "")), reverse=True)
    return results
