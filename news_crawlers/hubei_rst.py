# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from urllib.parse import urljoin

from .common import make_session, mark_income_related, now_cn, norm


HUBEI_RST_BASE = "https://rst.hubei.gov.cn"
HUBEI_RST_POLICY_FEEDS = {
    "hubei_gfxwj": "/zfxxgk/zc/gfxwj/list.json",
    "hubei_qtzdgkwj": "/zfxxgk/zc/qtzdgkwj/flfg.json",
}


def _parse_doc_datetime(text: str) -> datetime | None:
    raw = norm(text)
    if not raw:
        return None

    for fmt, n in (("%Y-%m-%d %H:%M:%S", 19), ("%Y-%m-%d", 10)):
        try:
            dt = datetime.strptime(raw[:n], fmt)
            return dt.replace(tzinfo=now_cn().tzinfo)
        except Exception:
            continue
    return None


def crawl_hubei_rst_policy(current_time: datetime | None = None) -> list[dict]:
    """
    抓取湖北省人社厅政策栏目：
    1) 规范性文件 (/zfxxgk/zc/gfxwj/)
    2) 其他主动公开文件 (/zfxxgk/zc/qtzdgkwj/)

    仅保留近24小时内发布的文章标题与链接。
    """
    now = current_time or now_cn()
    since = now - timedelta(hours=24)

    session = make_session()
    results = []
    seen_urls = set()

    for source, feed_path in HUBEI_RST_POLICY_FEEDS.items():
        feed_url = urljoin(HUBEI_RST_BASE, feed_path)
        try:
            resp = session.get(feed_url, timeout=20)
            resp.encoding = resp.apparent_encoding or "utf-8"
            if resp.status_code != 200:
                print(f"[HubeiRST] HTTP Error {resp.status_code} @ {feed_url}")
                continue
            data = resp.json()
        except Exception as e:
            print(f"[HubeiRST] fetch failed({source}): {e}")
            continue

        rows = (data or {}).get("data") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            continue

        for row in rows:
            if not isinstance(row, dict):
                continue

            title = norm(str(row.get("FILENAME") or ""))
            href = norm(str(row.get("URL") or ""))
            dt = _parse_doc_datetime(str(row.get("DOCRELTIME") or row.get("PUBDATE") or ""))
            if not title or not href or not dt:
                continue
            if dt > now:
                continue
            if dt < since:
                continue

            full_url = urljoin(HUBEI_RST_BASE, href)
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            results.append(
                {
                    "title": mark_income_related(title),
                    "url": full_url,
                    "date": dt.date(),
                    "source": source,
                }
            )

    results.sort(key=lambda x: (x["date"], x["title"]), reverse=True)
    return results
