# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from .common import make_session, mark_income_related, now_cn


LFZFGJJ_INDEX = "https://lfzfgjj.net/website/working-dynamic.html"
LFZFGJJ_API = "https://lfzfgjj.net/appapi70009.json"


def _page_payload(page_no: int) -> dict:
    return {
        "buzType": 5501,
        "parentViewItemId": "02",
        "curChildViewItemId": "0201",
        "pagerows": 12,
        "pagenum": page_no - 1,
    }


def _fetch_page(page_no: int):
    session = make_session()
    resp = session.get(
        LFZFGJJ_API,
        params=_page_payload(page_no),
        timeout=20,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123 Safari/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Referer": LFZFGJJ_INDEX,
        },
    )
    resp.raise_for_status()
    return resp.json()


def crawl_lfzfgjj_announcement(current_time: datetime | None = None, max_pages: int = 6) -> list[dict]:
    """抓取廊坊公积金网通知公告，仅保留近24小时内发布的标题和链接。"""
    now = current_time or now_cn()
    since_date = (now - timedelta(days=1)).date()

    results: list[dict] = []
    seen_urls: set[str] = set()

    for page_no in range(1, max_pages + 1):
        try:
            data = _fetch_page(page_no)
        except Exception as e:
            print(f"[Lfzfgjj] fetch failed(page={page_no}): {e}")
            break

        result = (data or {}).get("result") or {}
        news = result.get("news") or {}
        news_list = news.get("newsList") or []
        total_page = news.get("totalPage") or 1

        if not news_list:
            break

        page_has_new = False
        for it in news_list:
            title = (it.get("title") or "").strip()
            seqno = it.get("seqno")
            releasetime = (it.get("releasetime") or "").strip()
            if not title or not seqno or not releasetime:
                continue

            try:
                dt = datetime.strptime(releasetime, "%Y-%m-%d")
            except Exception:
                continue

            if now.tzinfo is not None:
                dt = dt.replace(tzinfo=now.tzinfo)

            if dt > now:
                continue
            if dt.date() < since_date:
                continue

            url = f"https://lfzfgjj.net/website/working-dynamic-detail.html?seqno={seqno}&itemId=0201"
            if url in seen_urls:
                continue
            seen_urls.add(url)
            results.append(
                {
                    "title": mark_income_related(title),
                    "url": url,
                    "date": dt,
                    "source": "lfzfgjj_announcement",
                }
            )
            page_has_new = True

        if page_no >= total_page:
            break
        if not page_has_new:
            break

    results.sort(key=lambda x: (x.get("date") or now, x.get("title", "")), reverse=True)
    return results
