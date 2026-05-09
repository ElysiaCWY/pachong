# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from urllib.parse import urljoin

from .common import make_session, mark_income_related, now_cn


CHENGDE_GJJ_INDEX = "https://www.chengdezfgjj.cn/website/announcement.html"
CHENGDE_GJJ_API = "https://www.chengdezfgjj.cn/appapi70009.json"


def _page_payload(page_no: int) -> dict:
    return {
        "buzType": 5521,
        "parentViewItemId": 9,
        "curChildViewItemId": "",
        "pagerows": 12,
        "pagenum": page_no - 1,
    }


def _parse_dt(text: str):
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None
    return dt


def _fetch_page(page_no: int):
    s = make_session()
    resp = s.get(
        CHENGDE_GJJ_API,
        params=_page_payload(page_no),
        timeout=20,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123 Safari/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Referer": CHENGDE_GJJ_INDEX,
        },
    )
    resp.raise_for_status()
    return resp.json()


def crawl_chengde_gjj_announcement(current_time: datetime | None = None, max_pages: int = 3) -> list[dict]:
    """抓取承德公积金通知公告，仅保留近24小时内发布的标题和链接。"""
    now = current_time or now_cn()
    since_dt = now - timedelta(days=1)

    results: list[dict] = []
    seen_urls: set[str] = set()

    for page_no in range(1, max_pages + 1):
        try:
            data = _fetch_page(page_no)
        except Exception as e:
            print(f"[ChengdeGJJ] fetch failed(page={page_no}): {e}")
            break

        news = ((data or {}).get("result") or {}).get("news") or {}
        news_list = news.get("newsList") or []
        total_page = news.get("totalPage") or 1

        if not news_list:
            break

        page_has_new = False
        for it in news_list:
            title = (it.get("title") or "").strip()
            seqno = it.get("seqno")
            releasetime = (it.get("datecreated") or it.get("releasetime") or "").strip()
            if not title or not seqno or not releasetime:
                continue

            dt = _parse_dt(releasetime)
            if not dt:
                continue
            if dt.tzinfo is None and now.tzinfo is not None:
                dt = dt.replace(tzinfo=now.tzinfo)

            if dt > now:
                continue
            if dt < since_dt:
                continue

            url = f"https://www.chengdezfgjj.cn/website/announcement-detail.html?seqno={seqno}"
            if url in seen_urls:
                continue
            seen_urls.add(url)
            results.append(
                {
                    "title": mark_income_related(title),
                    "url": url,
                    "date": dt,
                    "source": "chengde_gjj_announcement",
                }
            )
            page_has_new = True

        if page_no >= total_page:
            break
        if not page_has_new:
            break

    results.sort(key=lambda x: (x.get("date") or now, x.get("title", "")), reverse=True)
    return results
