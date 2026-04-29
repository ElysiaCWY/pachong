# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from urllib.parse import urljoin

from .common import make_session, mark_income_related, now_cn, norm, parse_ymd


QINGHAI_RST_BASE = "https://rst.qinghai.gov.cn"
QINGHAI_RST_API = f"{QINGHAI_RST_BASE}/zcfg/zcfg/api"
QINGHAI_RST_REFERER = f"{QINGHAI_RST_BASE}/zcfg/zczsk/index.html"


def _build_payload(page: int) -> dict:
    return {
        "page": page,
        "code": "zcfg",
        "number": "",
        "title": "",
        "date": "",
        "isParent": True,
    }


def _to_detail_url(item: dict) -> str:
    raw_url = norm(str(item.get("Url") or item.get("url") or ""))
    if raw_url:
        return urljoin(QINGHAI_RST_BASE, raw_url)

    code = norm(str(item.get("Code") or ""))
    item_id = norm(str(item.get("ID") or ""))
    if code and item_id:
        return f"{QINGHAI_RST_BASE}/zcfg/{code}/query/{item_id}.html"

    return ""


def crawl_qinghai_rst_policy(current_time: datetime | None = None, max_pages: int = 20) -> list[dict]:
    """抓取青海省人社厅政策知识库标题和链接，仅保留近24小时内条目。"""
    now = current_time or now_cn()
    if now.tzinfo is None:
        now = now.replace(tzinfo=now_cn().tzinfo)
    since_date = (now - timedelta(hours=24)).date()

    session = make_session()
    results: list[dict] = []
    seen_urls: set[str] = set()

    total_pages = None
    page = 1
    while page <= max_pages and (total_pages is None or page <= total_pages):
        try:
            resp = session.post(
                QINGHAI_RST_API,
                data=_build_payload(page),
                timeout=20,
                headers={"Referer": QINGHAI_RST_REFERER},
            )
            resp.encoding = resp.apparent_encoding or "utf-8"
            if resp.status_code != 200:
                break
            data = resp.json()
        except Exception as e:
            print(f"[QinghaiRST] fetch failed(page={page}): {e}")
            break

        rows = data.get("list") if isinstance(data, dict) else None
        paging = data.get("paging") if isinstance(data, dict) else None
        if isinstance(paging, dict) and isinstance(paging.get("total_pages_count"), int):
            total_pages = paging["total_pages_count"]

        if not isinstance(rows, list) or not rows:
            break

        page_has_recent = False
        for row in rows:
            if not isinstance(row, dict):
                continue

            title = norm(str(row.get("Title") or ""))
            date_obj = parse_ymd(norm(str(row.get("ReleaseDate") or "")))
            detail_url = _to_detail_url(row)
            if not title or not date_obj or not detail_url:
                continue

            dt = datetime(date_obj.year, date_obj.month, date_obj.day, tzinfo=now.tzinfo)
            if dt > now:
                continue
            if dt.date() < since_date:
                continue

            page_has_recent = True
            if detail_url in seen_urls:
                continue
            seen_urls.add(detail_url)

            results.append(
                {
                    "title": mark_income_related(title),
                    "url": detail_url,
                    "date": dt.date(),
                    "source": "qinghai_rst_policy",
                }
            )

        # 接口按日期倒序，当前页已无近24小时数据则可提前停止。
        if not page_has_recent:
            break

        page += 1

    results.sort(key=lambda x: (x["date"], x["title"]), reverse=True)
    return results
