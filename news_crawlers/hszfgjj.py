# -*- coding: utf-8 -*-
import json
from datetime import datetime, timedelta

import requests

from .common import mark_income_related, now_cn


HSZFGJJ_INDEX = "https://www.hszfgjj.org.cn/list?activeIndex=8"
HSZFGJJ_API = "https://www.hszfgjj.org.cn/token/admin/huaxin/index"


def _page_payload(page_no: int) -> dict:
    return {
        "data": json.dumps(
            {
                "buzType": 5501,
                "keyword": "",
                "parentViewItemId": "03",
                "curChildViewItemId": "",
                "pagenum": page_no - 1,
                "pagerows": "10",
            },
            ensure_ascii=False,
        ),
        "url": "appapi70009.json",
    }


def _parse_dt(text: str):
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        try:
            return datetime.strptime(text, "%Y-%m-%d")
        except Exception:
            return None


def crawl_hszfgjj_policy_regulations(current_time: datetime | None = None, max_pages: int = 6) -> list[dict]:
    """抓取衡水公积金网 - 政策法规，仅保留近24小时内发布的标题和链接。"""
    now = current_time or now_cn()
    since_dt = now - timedelta(days=1)
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123 Safari/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Referer": HSZFGJJ_INDEX,
        }
    )

    results: list[dict] = []
    seen_urls: set[str] = set()

    for page_no in range(1, max_pages + 1):
        try:
            resp = session.post(HSZFGJJ_API, data=_page_payload(page_no), timeout=20, verify=False)
            resp.raise_for_status()
            data = json.loads(resp.content.decode("utf-8-sig"))
        except Exception as e:
            print(f"[HSZGJJ] fetch failed(page={page_no}): {e}")
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
            dt_text = (it.get("datecreated") or it.get("releasetime") or "").strip()
            if not title or not seqno or not dt_text:
                continue

            dt = _parse_dt(dt_text)
            if not dt:
                continue
            if dt.tzinfo is None and now.tzinfo is not None:
                dt = dt.replace(tzinfo=now.tzinfo)

            if dt > now:
                continue
            if dt < since_dt:
                continue

            url = f"https://www.hszfgjj.org.cn/new_details?channelIds=80&id={seqno}"
            if url in seen_urls:
                continue
            seen_urls.add(url)
            results.append(
                {
                    "title": mark_income_related(title),
                    "url": url,
                    "date": dt,
                    "source": "hszfgjj_policy_regulations",
                }
            )
            page_has_new = True

        if page_no >= total_page:
            break
        if not page_has_new:
            break

    results.sort(key=lambda x: (x.get("date") or now, x.get("title", "")), reverse=True)
    return results
