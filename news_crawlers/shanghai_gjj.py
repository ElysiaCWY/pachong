# -*- coding: utf-8 -*-
import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, now_cn, norm, parse_ymd, mark_income_related


SH_GJJ_POLICY_CATEGORIES = {
    "公积金法规": "https://www.shzfgjj.cn/html/newxxgk/zcwj/gjjfg/index.html",
    "规范性文件": "https://www.shzfgjj.cn/html/newxxgk/zcwj/gfxwj/index.html",
    "管理文件": "https://www.shzfgjj.cn/html/newxxgk/zcwj/gjjgwh/index.html",
}


def _parse_list_page(page_url: str, html: str, source: str) -> list[dict]:
    soup = BeautifulSoup(html or "", "html.parser")
    results: list[dict] = []

    main = soup.select_one("div.list-main.col-lg-9.col-12.float-left")
    if not main:
        main = soup.select_one("div.list-main") or soup

    for list_part in main.select("div.list-part"):
        for li in list_part.select("ul li"):
            a_tag = li.find("a", href=True)
            if not a_tag:
                continue

            href = norm(a_tag.get("href") or "")
            title = norm(a_tag.get("title") or a_tag.get_text(" ", strip=True))
            if not href or not title:
                continue
            if "/html/newxxgk/zcwj/" not in href:
                continue

            date_text = ""
            li_text = li.get_text(" ", strip=True)
            match = re.search(r"(20\d{2}-\d{2}-\d{2})", li_text)
            if match:
                date_text = match.group(1)

            item = {
                "title": mark_income_related(title),
                "url": urljoin(page_url, href),
                "date": parse_ymd(date_text) if date_text else None,
                "source": source,
            }
            results.append(item)

    return results


def _candidate_page_url(first_url: str, page_no: int) -> str:
    if page_no <= 1:
        return first_url
    base_dir = first_url.rsplit("/", 1)[0] + "/"
    return urljoin(base_dir, f"index{page_no}.html")


def crawl_shanghai_gjj_policy(current_time: datetime | None = None, max_pages: int = 20) -> list[dict]:
    """抓取上海住房公积金网政策文件下的公积金法规、规范性文件和管理文件三栏。"""
    _ = current_time or now_cn()
    session = make_session()
    results: list[dict] = []
    seen_urls: set[str] = set()

    for source, first_url in SH_GJJ_POLICY_CATEGORIES.items():
        page_no = 1
        while page_no <= max_pages:
            page_url = _candidate_page_url(first_url, page_no)
            try:
                resp = session.get(page_url, timeout=20)
                resp.encoding = resp.apparent_encoding or "utf-8"
                if resp.status_code != 200:
                    break
            except Exception as e:
                print(f"[ShanghaiGJJ] Crawl error({source}, p{page_no}): {e}")
                break

            page_items = _parse_list_page(page_url, resp.text, source)
            if not page_items:
                break

            page_has_new = False
            for item in page_items:
                if item["url"] in seen_urls:
                    continue
                seen_urls.add(item["url"])
                results.append(item)
                page_has_new = True

            if page_no > 1 and not page_has_new:
                break

            page_no += 1

    results.sort(key=lambda x: (x["date"] or now_cn().date(), x["title"]), reverse=True)
    return results