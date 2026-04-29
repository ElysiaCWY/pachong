# -*- coding: utf-8 -*-
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, now_cn, norm, parse_ymd


BEIJING_GJJ_POLICY_CHANNELS = {
    "管委会文件": "https://gjj.beijing.gov.cn/web/zwgk61/2024zcwj/436433461/index.html",
    "住房公积金归集政策": "https://gjj.beijing.gov.cn/web/zwgk61/2024zcwj/436433464/436433466/index.html",
    "住房公积金贷款政策": "https://gjj.beijing.gov.cn/web/zwgk61/2024zcwj/436433464/436433467/index.html",
    "其他住房资金政策": "https://gjj.beijing.gov.cn/web/zwgk61/2024zcwj/436433464/436433468/index.html",
    "住房公积金综合政策": "https://gjj.beijing.gov.cn/web/zwgk61/2024zcwj/436433464/436433465/index.html",
}


def _extract_total_pages(html: str) -> int:
    match = re.search(r"当前：\s*\d+\s*/\s*(\d+)", html or "")
    if not match:
        return 1
    try:
        return max(1, int(match.group(1)))
    except Exception:
        return 1


def _extract_page_prefix(html: str) -> str | None:
    match = re.search(r"queryArticleByCondition\(this,'([^']+-2\.html)'\)", html or "")
    if not match:
        return None
    return match.group(1)[:-len("-2.html")]


def _parse_list_page(page_url: str, html: str, source: str, since_date, today) -> tuple[list[dict], bool]:
    soup = BeautifulSoup(html or "", "html.parser")
    items: list[dict] = []
    hit_older = False

    for li in soup.select("ul.TabCon li"):
        a_tag = li.find("a", href=True)
        if not a_tag:
            continue

        title = norm(a_tag.get("title") or a_tag.get_text(" ", strip=True))
        href = norm(a_tag.get("href") or "")
        if not title or not href:
            continue

        match = re.search(r"(20\d{2}-\d{2}-\d{2})", li.get_text(" ", strip=True))
        if not match:
            continue

        article_date = parse_ymd(match.group(1))
        if not article_date:
            continue
        if article_date > today:
            continue
        if article_date < since_date:
            hit_older = True
            continue

        items.append(
            {
                "title": title,
                "url": urljoin(page_url, href),
                "date": article_date,
                "source": source,
            }
        )

    return items, hit_older


def crawl_beijing_gjj_policy(current_time: datetime | None = None) -> list[dict]:
    """抓取北京住房公积金管理中心政策文件页及其四个中心板块，保留近24小时内条目。"""
    now = current_time or now_cn()
    since_date = (now - timedelta(hours=24)).date()
    today = now.date()

    session = make_session()
    results: list[dict] = []
    seen_urls: set[str] = set()

    for source, first_url in BEIJING_GJJ_POLICY_CHANNELS.items():
        try:
            first_resp = session.get(first_url, timeout=20)
            first_resp.encoding = "utf-8"
            if first_resp.status_code != 200:
                print(f"[BeijingGJJ] HTTP Error {first_resp.status_code} @ {first_url}")
                continue

            page_prefix = _extract_page_prefix(first_resp.text)
            total_pages = _extract_total_pages(first_resp.text)

            page_no = 1
            while page_no <= total_pages:
                if page_no == 1:
                    page_url = first_url
                    html = first_resp.text
                else:
                    if not page_prefix:
                        break
                    page_url = urljoin(first_url, f"{page_prefix}-{page_no}.html")
                    resp = session.get(page_url, timeout=20)
                    resp.encoding = "utf-8"
                    if resp.status_code != 200:
                        print(f"[BeijingGJJ] HTTP Error {resp.status_code} @ {page_url}")
                        break
                    html = resp.text

                page_items, hit_older = _parse_list_page(page_url, html, source, since_date, today)
                for item in page_items:
                    if item["url"] in seen_urls:
                        continue
                    seen_urls.add(item["url"])
                    results.append(item)

                if hit_older:
                    break
                page_no += 1
        except Exception as e:
            print(f"[BeijingGJJ] Crawl error({source}): {e}")

    results.sort(key=lambda x: (x["date"], x["title"]), reverse=True)
    return results