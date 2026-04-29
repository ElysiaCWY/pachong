# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, mark_income_related, now_cn, norm, parse_ymd


HENAN_HRSS_INDEX_URL = "https://hrss.henan.gov.cn/gfxwjzlk/"
HENAN_HRSS_YEAR_URL = "https://hrss.henan.gov.cn/gfxwjzlk/2009nzh/2023/"

HENAN_HRSS_CATEGORY_URLS = {
    "henan_gfxwj_yzh": "https://hrss.henan.gov.cn/gfxwjzlk/2009nzh/2023/yzh/",
    "henan_gfxwj_efz": "https://hrss.henan.gov.cn/gfxwjzlk/2009nzh/2023/efz/",
    "henan_gfxwj_sjycj": "https://hrss.henan.gov.cn/gfxwjzlk/2009nzh/2023/sjycj/",
    "henan_gfxwj_srlzyldgl": "https://hrss.henan.gov.cn/gfxwjzlk/2009nzh/2023/srlzyldgl/",
    "henan_gfxwj_wzynljs": "https://hrss.henan.gov.cn/gfxwjzlk/2009nzh/2023/wzynljs/",
    "henan_gfxwj_lzcgl": "https://hrss.henan.gov.cn/gfxwjzlk/2009nzh/2023/lzcgl/",
    "henan_gfxwj_qzyjsrybshgl": "https://hrss.henan.gov.cn/gfxwjzlk/2009nzh/2023/qzyjsrybshgl/",
    "henan_gfxwj_bsydwrsgl": "https://hrss.henan.gov.cn/gfxwjzlk/2009nzh/2023/bsydwrsgl/",
    "henan_gfxwj_jnmggz": "https://hrss.henan.gov.cn/gfxwjzlk/2009nzh/2023/jnmggz/",
    "henan_gfxwj_sldgx": "https://hrss.henan.gov.cn/gfxwjzlk/2009nzh/2023/sldgx/",
    "henan_gfxwj_syczzgylbx": "https://hrss.henan.gov.cn/gfxwjzlk/2009nzh/2023/syczzgylbx/",
    "henan_gfxwj_secxjmylbx": "https://hrss.henan.gov.cn/gfxwjzlk/2009nzh/2023/secxjmylbx/",
    "henan_gfxwj_sssybx": "https://hrss.henan.gov.cn/gfxwjzlk/2009nzh/2023/sssybx/",
    "henan_gfxwj_ssgsbx": "https://hrss.henan.gov.cn/gfxwjzlk/2009nzh/2023/ssgsbx/",
    "henan_gfxwj_swshbzjjjd": "https://hrss.henan.gov.cn/gfxwjzlk/2009nzh/2023/swshbzjjjd/",
    "henan_gfxwj_sldjzc": "https://hrss.henan.gov.cn/gfxwjzlk/2009nzh/2023/sldjzc/",
}

ARTICLE_URL_RE = re.compile(r"^https?://hrss\.henan\.gov\.cn/20\d{2}/\d{2}-\d{2}/\d+\.html$")
DATE_RE = re.compile(r"20\d{2}[-/\. ]\d{1,2}[-/\. ]\d{1,2}")


def _pick_article_date(text: str, href: str) -> datetime | None:
    match = DATE_RE.search(text or "")
    if not match:
        match = DATE_RE.search(href or "")
    if not match:
        return None

    date_obj = parse_ymd(match.group(0))
    if not date_obj:
        return None

    return datetime(date_obj.year, date_obj.month, date_obj.day, tzinfo=now_cn().tzinfo)


def _extract_items_from_page(page_url: str, html: str, source: str, now: datetime, since_date) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    results: list[dict] = []
    seen_urls: set[str] = set()

    for a_tag in soup.find_all("a", href=True):
        href = norm(a_tag.get("href") or "")
        if not href:
            continue

        full_url = urljoin(page_url, href)
        if not ARTICLE_URL_RE.match(full_url):
            continue
        if full_url in seen_urls:
            continue

        title = norm(a_tag.get_text(" ", strip=True))
        if not title:
            continue

        container = a_tag.find_parent("tr") or a_tag.find_parent("li") or a_tag.find_parent("div") or a_tag.find_parent("td") or a_tag.parent
        container_text = norm(container.get_text(" ", strip=True) if container else a_tag.get_text(" ", strip=True))
        dt = _pick_article_date(container_text, full_url)
        if not dt:
            continue
        if dt > now:
            continue
        if dt.date() < since_date:
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

    return results


def crawl_henan_hrss_policy(current_time: datetime | None = None) -> list[dict]:
    """
    抓取河南省人社厅“规范性文件资料库”中近24小时发布的文章标题和链接。

    该站点按栏目页展示文库条目，日期精度只有到天，因此这里以日期近似近24小时过滤。
    """
    now = current_time or now_cn()
    since_date = (now - timedelta(hours=24)).date()

    session = make_session()
    try:
        session.get(HENAN_HRSS_INDEX_URL, timeout=20)
        session.get(HENAN_HRSS_YEAR_URL, timeout=20)
    except Exception as e:
        print(f"[HenanHRSS] warmup failed: {e}")

    results: list[dict] = []
    seen_urls: set[str] = set()

    for source, page_url in HENAN_HRSS_CATEGORY_URLS.items():
        try:
            resp = session.get(page_url, timeout=20)
            resp.encoding = resp.apparent_encoding or "utf-8"
            if resp.status_code != 200:
                print(f"[HenanHRSS] HTTP Error {resp.status_code} @ {page_url}")
                continue
        except Exception as e:
            print(f"[HenanHRSS] fetch failed({source}): {e}")
            continue

        page_items = _extract_items_from_page(page_url, resp.text, source, now, since_date)
        for item in page_items:
            if item["url"] in seen_urls:
                continue
            seen_urls.add(item["url"])
            results.append(item)

    results.sort(key=lambda x: (x["date"], x["title"]), reverse=True)
    return results
