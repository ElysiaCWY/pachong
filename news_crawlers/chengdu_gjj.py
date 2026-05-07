# -*- coding: utf-8 -*-
import math
import os
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, mark_income_related, now_cn, norm, parse_ymd


CHENGDU_GJJ_CHANNELS = {
    "地方性法规": "https://cdzfgjj.chengdu.gov.cn/cdgjj/c1156359/news_dfwj.shtml",
    "部门规章": "https://cdzfgjj.chengdu.gov.cn/cdgjj/c1156360/news_dfwj.shtml",
    "规范性文件": "https://cdzfgjj.chengdu.gov.cn/cdgjj/c1156361/news_dfwj.shtml",
    "其他文件": "https://cdzfgjj.chengdu.gov.cn/cdgjj/c1156362/news_dfwj.shtml",
}


def _build_cookie_dict(cookie_str: str) -> dict[str, str]:
    cookie_map: dict[str, str] = {}
    for seg in (cookie_str or "").split(";"):
        part = seg.strip()
        if not part or "=" not in part:
            continue
        k, v = part.split("=", 1)
        k = k.strip()
        v = v.strip()
        if k:
            cookie_map[k] = v
    return cookie_map


def _request_with_optional_cookie(session, url: str):
    resp = session.get(
        url,
        timeout=20,
        headers={"Referer": "https://cdzfgjj.chengdu.gov.cn/"},
    )
    if resp.status_code not in (400, 412):
        return resp

    extra_cookie = os.getenv("CHENGDU_GJJ_COOKIE", "").strip()
    if not extra_cookie:
        return resp

    cookie_map = _build_cookie_dict(extra_cookie)
    if not cookie_map:
        return resp

    retry_session = make_session()
    retry_session.cookies.update(cookie_map)
    return retry_session.get(
        url,
        timeout=20,
        headers={"Referer": "https://cdzfgjj.chengdu.gov.cn/"},
    )


def _page_url(index_url: str, page_no: int) -> str:
    if page_no <= 1:
        return index_url
    return index_url.replace(".shtml", f"_{page_no}.shtml", 1)


def _parse_article_dt(text: str):
    text = norm(text)
    if not text:
        return None
    m = re.search(r"20\d{2}[-/]\d{1,2}[-/]\d{1,2}", text)
    if m:
        try:
            return parse_ymd(m.group(0))
        except Exception:
            pass
    return None


def _extract_page_items(page_url: str, html: str, source: str, since_dt: datetime, now: datetime):
    soup = BeautifulSoup(html, "html.parser")
    items = []
    newest_dt = None

    # Usually list items are within some ul/li or div
    for li in soup.select("ul li, .news-list li, div.txt-list ul li, .list li"):
        a_tag = li.find("a", href=True)
        if not a_tag:
            continue
        
        href = norm(a_tag.get("href") or "")
        title = norm(a_tag.get("title") or a_tag.get_text(" ", strip=True))
        if not title or not href:
            continue
        
        # skip common unrelated links
        if title in ["首页", "下一页", "尾页", "上一页"]:
            continue

        date_text = li.get_text(" ", strip=True)
        article_date = _parse_article_dt(date_text)
        if not article_date:
            continue
            
        dt = datetime.combine(article_date, datetime.min.time(), tzinfo=now.tzinfo)

        if dt > now:
            continue

        if newest_dt is None or dt > newest_dt:
            newest_dt = dt

        if dt < since_dt:
            continue

        items.append(
            {
                "title": mark_income_related(title),
                "url": urljoin(page_url, href),
                "date": article_date,
                "source": f"chengdu_gjj_{source}",
            }
        )

    return items, newest_dt


def crawl_chengdu_gjj_policy(current_time: datetime | None = None, max_pages: int = 5) -> list[dict]:
    now = current_time or now_cn()
    if now.tzinfo is None:
        now = now.replace(tzinfo=now_cn().tzinfo)
    since_dt = now - timedelta(hours=24)

    session = make_session()
    results: list[dict] = []
    seen_urls: set[str] = set()

    for source, index_url in CHENGDU_GJJ_CHANNELS.items():
        try:
            for page_no in range(1, max_pages + 1):
                page_url = _page_url(index_url, page_no)
                resp = _request_with_optional_cookie(session, page_url)
                resp.encoding = resp.apparent_encoding or "utf-8"
                if resp.status_code != 200:
                    break

                page_items, newest_dt = _extract_page_items(page_url, resp.text, source, since_dt, now)
                
                # If cannot find any items or newest_dt is too old, stop for this channel
                if not page_items and newest_dt is None:
                    break

                for item in page_items:
                    if item["url"] in seen_urls:
                        continue
                    seen_urls.add(item["url"])
                    results.append(item)

                if newest_dt and newest_dt < since_dt:
                    break
        except Exception as e:
            print(f"[ChengduGJJ] Error crawling {source}: {e}")

    results.sort(key=lambda x: (x["date"], x["title"]), reverse=True)
    return results
