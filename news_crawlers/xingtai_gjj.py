# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from .common import make_session, mark_income_related, now_cn, parse_ymd


XINGTAI_GJJ_INDEX = "https://gjj.xingtai.gov.cn/website/governmentNew.html?itemId=025"
XINGTAI_GJJ_API = "https://gjj.xingtai.gov.cn/appapi70009.json"


def _page_payload(page_no: int) -> dict:
    return {
        "buzType": 5526,
        "parentViewItemId": "02",
        "curChildViewItemId": "025",
        "pagenum": page_no - 1,
        "pagerows": 8,
        "keyword": "",
    }


def _parse_date(text: str):
    d = parse_ymd((text or "").strip())
    return d


def _extract_items(payload: dict, now: datetime, since_date) -> tuple[list[dict], bool]:
    s = make_session()
    resp = s.post(
        XINGTAI_GJJ_API,
        data=payload,
        timeout=20,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123 Safari/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Referer": XINGTAI_GJJ_INDEX,
        },
    )
    resp.raise_for_status()
    data = resp.json()
    news = (((data or {}).get("result") or {}).get("news") or {})
    news_list = news.get("newsList") or []

    items: list[dict] = []
    has_older_item = False
    for it in news_list:
        title = (it.get("title") or "").strip()
        releasetime = (it.get("releasetime") or "").strip()
        seqno = it.get("seqno")
        if not title or not seqno:
            continue

        d = _parse_date(releasetime)
        if not d:
            continue
        if d > now.date():
            continue
        if d < since_date:
            has_older_item = True
            continue

        items.append(
            {
                "title": mark_income_related(title),
                "url": f"https://gjj.xingtai.gov.cn/website/gover_con_page.html?seqno={seqno}&itemId=025",
                "date": d,
                "source": "xingtai_gjj_policy",
            }
        )

    return items, has_older_item


def crawl_xingtai_gjj_policy(current_time: datetime | None = None, max_pages: int = 3) -> list[dict]:
    """抓取邢台公积金政策栏目，仅保留近24小时内发布的条目。"""
    now = current_time or now_cn()
    since_date = (now - timedelta(days=1)).date()

    results: list[dict] = []
    seen_urls: set[str] = set()

    for page_no in range(1, max_pages + 1):
        try:
            page_items, has_older_item = _extract_items(_page_payload(page_no), now, since_date)
        except Exception as e:
            print(f"[XingtaiGJJ] fetch failed(page={page_no}): {e}")
            break

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
