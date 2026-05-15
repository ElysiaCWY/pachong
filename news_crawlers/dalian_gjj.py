# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, now_cn, norm, parse_ymd


DL_GJJ_POLICY_INDEX = "https://gjj.dl.gov.cn/col/col5552/index.html"
DL_GJJ_POLICY_PROXY = (
    "https://gjj.dl.gov.cn/module/web/jpage/dataproxy.jsp?"
    "page={page}&webid=41&path=https://gjj.dl.gov.cn/&columnid=5552&unitid=37566&"
    "webname=%25E5%25A4%25A7%25E8%25BF%259E%25E5%25B8%2582%25E4%25BD%258F%25E6%2588%25BF%25E5%2585%25AC%25E7%25A7%25AF%25E9%2587%2591%25E7%25AE%25A1%25E7%2590%2586%25E4%25B8%25AD%25E5%25BF%2583&"
    "permissiontype=0"
)


def _extract_total_pages(xml_text: str) -> int:
    match = re.search(r"<totalpage>(\d+)</totalpage>", xml_text or "")
    if not match:
        return 1
    try:
        return max(1, int(match.group(1)))
    except Exception:
        return 1


def _parse_record_html(record_html: str, page_url: str) -> dict | None:
    soup = BeautifulSoup(record_html or "", "html.parser")
    a_tag = soup.select_one("a[href]")
    span_tag = soup.select_one("span")
    if not a_tag or not span_tag:
        return None

    title = norm(a_tag.get("title") or a_tag.get_text(" ", strip=True))
    href = norm(a_tag.get("href") or "")
    date_match = re.search(r"\[(\d{4}-\d{2}-\d{2})\]", span_tag.get_text(" ", strip=True))
    article_date = parse_ymd(date_match.group(1)) if date_match else None
    if not title or not href or not article_date:
        return None

    return {
        "title": title,
        "url": urljoin(page_url, href),
        "date": article_date,
        "source": "dalian_gjj_policy",
    }


def crawl_dalian_gjj_policy(current_time: datetime | None = None, max_pages: int | None = None) -> list[dict]:
    """抓取大连市住房公积金管理中心政策法规栏目，仅保留近24小时内条目。"""
    now = current_time or now_cn()
    since_date = (now - timedelta(hours=24)).date()

    session = make_session()
    results: list[dict] = []
    seen_urls: set[str] = set()

    try:
        first_resp = session.get(DL_GJJ_POLICY_PROXY.format(page=1), timeout=20)
        first_resp.encoding = first_resp.apparent_encoding or "utf-8"
        if first_resp.status_code != 200:
            print(f"[DalianGJJ] HTTP Error {first_resp.status_code}")
            return []
    except Exception as e:
        print(f"[DalianGJJ] fetch failed(page=1): {e}")
        return []

    total_pages = _extract_total_pages(first_resp.text)
    if max_pages is not None:
        total_pages = min(total_pages, max_pages)

    for page_no in range(1, total_pages + 1):
        if page_no == 1:
            xml_text = first_resp.text
        else:
            try:
                resp = session.get(DL_GJJ_POLICY_PROXY.format(page=page_no), timeout=20)
                resp.encoding = resp.apparent_encoding or "utf-8"
                if resp.status_code != 200:
                    print(f"[DalianGJJ] HTTP Error {resp.status_code} @ page={page_no}")
                    break
                xml_text = resp.text
            except Exception as e:
                print(f"[DalianGJJ] fetch failed(page={page_no}): {e}")
                break

        records = re.findall(r"<record><!\[CDATA\[(.*?)\]\]></record>", xml_text or "", re.S)
        if not records:
            break

        hit_older = False
        for record_html in records:
            item = _parse_record_html(record_html, DL_GJJ_POLICY_INDEX)
            if not item:
                continue
            item_date = item["date"]
            if item_date > now.date():
                continue
            if item_date < since_date:
                hit_older = True
                continue
            if item["url"] in seen_urls:
                continue
            seen_urls.add(item["url"])
            results.append(item)

        if hit_older:
            break

    results.sort(key=lambda x: (x["date"], x["title"]), reverse=True)
    return results