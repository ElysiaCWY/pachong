# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from .common import make_session, now_cn, norm


BTGJJ_LIST_API = "https://www.btgjj.cn/lzrj-admin/appraisal/content/getTitleList"
BTGJJ_ARTICLE_URL = "https://www.btgjj.cn/#/website/article/{article_id}"
BTGJJ_LIST_ID = 94


def _parse_release_time(raw_value: str, tzinfo) -> datetime | None:
    text = norm(str(raw_value or ""))
    if not text:
        return None

    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        pass

    normalized = text.replace("T", " ")
    for fmt, width in (("%Y-%m-%d %H:%M:%S", 19), ("%Y-%m-%d %H:%M", 16)):
        try:
            return datetime.strptime(normalized[:width], fmt).replace(tzinfo=tzinfo)
        except Exception:
            continue

    return None


def crawl_btgjj_policy(current_time: datetime | None = None, max_pages: int = 8) -> list[dict]:
    """抓取包头市住房公积金 - 公积金法规，保留近24小时内条目。"""
    now = current_time or now_cn()
    since = now - timedelta(hours=24)
    session = make_session()
    results: list[dict] = []
    seen_urls: set[str] = set()

    for page_num in range(1, max_pages + 1):
        params = {"pageNum": page_num, "pageSize": 10, "id": BTGJJ_LIST_ID}

        try:
            resp = session.get(BTGJJ_LIST_API, params=params, timeout=20)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or "utf-8"
            payload = resp.json()
        except Exception as e:
            print(f"[BTGJJ] fetch error page={page_num}: {e}")
            break

        data = payload.get("data") or {}
        items = data.get("list") or []
        if not items:
            break

        page_has_fresh = False
        page_hit_older = False

        for item in items:
            try:
                article_id = item.get("id")
                title = norm(item.get("title") or "")
                release_time = _parse_release_time(item.get("releaseTime"), now.tzinfo)

                if not article_id or not title or not release_time:
                    continue
                if release_time > now:
                    continue
                if release_time < since:
                    page_hit_older = True
                    continue

                page_has_fresh = True
                url = BTGJJ_ARTICLE_URL.format(article_id=article_id)
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                results.append(
                    {
                        "title": title,
                        "url": url,
                        "date": release_time,
                        "source": "btgjj_policy",
                    }
                )
            except Exception:
                continue

        if page_hit_older or not page_has_fresh:
            break

    results.sort(key=lambda x: (x["date"], x["title"]), reverse=True)
    return results