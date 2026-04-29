# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from html import unescape
from urllib.parse import urljoin

from .common import make_session, mark_income_related, now_cn, norm


GUANGXI_RST_BASE = "http://rst.gxzf.gov.cn"
GUANGXI_RST_LIST_URL = f"{GUANGXI_RST_BASE}/irs/front/list"
GUANGXI_RST_QUERY_CODE = "189682f495f"
GUANGXI_RST_TABLE_NAME = "t_18797a40156"
GUANGXI_RST_STATUS_FIELD = "f_2023420956721"
GUANGXI_RST_STATUS_VALUE = "有效"
GUANGXI_RST_SORT_FIELD = "f_2023419659396"
GUANGXI_RST_POLICY_CHANNELS = {
    "guangxi_gzgjzc": {
        "label": "广西规章政策",
        "channel_id": "59993",
    },
    "guangxi_btgfxwj": {
        "label": "本厅规范性文件",
        "channel_id": "59994",
    },
}


def _parse_dt(raw: str) -> datetime | None:
    text = norm(unescape(str(raw or "")))
    if not text:
        return None

    for fmt, length in (("%Y-%m-%d %H:%M:%S", 19), ("%Y-%m-%d", 10)):
        try:
            dt = datetime.strptime(text[:length], fmt)
            return dt.replace(tzinfo=now_cn().tzinfo)
        except Exception:
            continue
    return None


def _build_payload(channel_id: str, page_no: int, page_size: int = 20) -> dict:
    return {
        "code": GUANGXI_RST_QUERY_CODE,
        "tableName": GUANGXI_RST_TABLE_NAME,
        "pageNo": page_no,
        "pageSize": page_size,
        "searchFields": [
            {
                "fieldName": GUANGXI_RST_STATUS_FIELD,
                "searchWord": GUANGXI_RST_STATUS_VALUE,
                "withHighLight": False,
            }
        ],
        "sorts": [
            {
                "sortField": GUANGXI_RST_SORT_FIELD,
                "sortOrder": "DESC",
            }
        ],
        "customFilter": {
            "operator": "and",
            "properties": [],
            "filters": [
                {
                    "operator": "or",
                    "properties": [
                        {
                            "property": "channel_id",
                            "operator": "eq",
                            "value": channel_id,
                        },
                        {
                            "property": "f_20211013721943",
                            "operator": "eq",
                            "value": 0,
                        },
                    ],
                }
            ],
        },
    }


def _extract_page_items(session, channel_id: str, now: datetime, since: datetime, page_no: int) -> tuple[list[dict], datetime | None]:
    payload = _build_payload(channel_id, page_no)
    resp = session.post(GUANGXI_RST_LIST_URL, json=payload, timeout=20)
    resp.raise_for_status()
    data = resp.json()

    rows = (((data or {}).get("data") or {}).get("list") or [])
    items: list[dict] = []
    newest_dt: datetime | None = None

    for row in rows:
        if not isinstance(row, dict):
            continue

        title = norm(unescape(str(row.get("f_2023419305471") or row.get("DOCTITLE") or "")))
        href = norm(str(row.get("doc_pub_url") or row.get("DOCPUBURL") or row.get("f_2023419200054") or ""))
        dt = _parse_dt(str(row.get("save_time") or row.get("f_2023419659396") or row.get("f_2023921132911") or ""))

        if not title or not href or not dt:
            continue
        if dt > now:
            continue

        if newest_dt is None or dt > newest_dt:
            newest_dt = dt

        if dt < since:
            continue

        full_url = href if href.startswith("http") else urljoin(GUANGXI_RST_BASE, href)
        items.append(
            {
                "title": mark_income_related(title),
                "url": full_url,
                "date": dt.date(),
                "source": "guangxi_rst_policy",
            }
        )

    return items, newest_dt


def crawl_guangxi_rst_policy(current_time: datetime | None = None, max_pages: int = 20) -> list[dict]:
    """
    抓取广西壮族自治区人力资源和社会保障厅政策栏目：
    1) 广西规章政策
    2) 本厅规范性文件

    仅保留近24小时发布的标题与链接。
    """
    now = current_time or now_cn()
    since = now - timedelta(hours=24)

    session = make_session()
    results: list[dict] = []
    seen_urls: set[str] = set()

    for source, meta in GUANGXI_RST_POLICY_CHANNELS.items():
        channel_id = meta["channel_id"]
        try:
            for page_no in range(1, max_pages + 1):
                page_items, newest_dt = _extract_page_items(session, channel_id, now, since, page_no)
                if not page_items and newest_dt is None:
                    break

                for item in page_items:
                    if item["url"] in seen_urls:
                        continue
                    seen_urls.add(item["url"])
                    item["source"] = source
                    results.append(item)

                if newest_dt and newest_dt < since:
                    break
        except Exception as e:
            print(f"[GuangxiRST] fetch failed({source}): {e}")
            continue

    results.sort(key=lambda x: (x["date"], x["title"]), reverse=True)
    return results