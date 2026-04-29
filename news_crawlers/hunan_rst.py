# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, mark_income_related, now_cn, norm, parse_ymd


HUNAN_RST_POLICY_INDEX = "https://rst.hunan.gov.cn/rst/xxgk/zcfg/zxzc/index.html"
HUNAN_RST_POLICY_PAGE_FMT = "https://rst.hunan.gov.cn/rst/xxgk/zcfg/zxzc/index_{page}.html"
ARTICLE_URL_RE = re.compile(r"^https?://rst\.hunan\.gov\.cn/rst/xxgk/zcfg/zxzc/\d{6}/t\d+_\d+\.html$")
DATE_RE = re.compile(r"20\d{2}[-/\.]\d{1,2}[-/\.]\d{1,2}")


def _pick_article_dt(text: str) -> datetime | None:
    m = DATE_RE.search(text or "")
    if not m:
        return None
    d = parse_ymd(m.group(0).replace("/", "-").replace(".", "-"))
    if not d:
        return None
    return datetime(d.year, d.month, d.day, tzinfo=now_cn().tzinfo)


def _extract_page_items(page_url: str, html: str, now: datetime, since_date) -> tuple[list[dict], datetime | None]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[dict] = []
    newest_dt: datetime | None = None

    for a in soup.find_all("a", href=True):
        href = norm(a.get("href") or "")
        if not href:
            continue

        full_url = urljoin(page_url, href)
        if not ARTICLE_URL_RE.match(full_url):
            continue

        title = norm(a.get_text(" ", strip=True))
        if not title:
            continue

        container = a.find_parent("li") or a.find_parent("tr") or a.find_parent("td") or a.find_parent("div") or a.parent
        container_text = norm(container.get_text(" ", strip=True) if container else title)
        dt = _pick_article_dt(container_text)
        if not dt:
            continue
        if dt > now:
            continue

        if newest_dt is None or dt > newest_dt:
            newest_dt = dt

        if dt.date() < since_date:
            continue

        items.append(
            {
                "title": mark_income_related(title),
                "url": full_url,
                "date": dt.date(),
                "source": "hunan_rst_policy",
            }
        )

    return items, newest_dt


def crawl_hunan_rst_policy(current_time: datetime | None = None, max_pages: int = 20) -> list[dict]:
    """
    抓取湖南省人社厅“厅发规范性文件”近24小时条目（标题+链接）。

    该站列表日期精度仅到天，这里按日期近似近24小时过滤。
    """
    now = current_time or now_cn()
    since_date = (now - timedelta(hours=24)).date()

    s = make_session()
    results: list[dict] = []
    seen_urls: set[str] = set()

    for page in range(1, max_pages + 1):
        page_url = HUNAN_RST_POLICY_INDEX if page == 1 else HUNAN_RST_POLICY_PAGE_FMT.format(page=page)

        try:
            r = s.get(page_url, timeout=20)
            r.encoding = r.apparent_encoding or "utf-8"
            if r.status_code != 200:
                break
        except Exception as e:
            print(f"[HunanRST] fetch failed(page={page}): {e}")
            break

        page_items, newest_dt = _extract_page_items(page_url, r.text, now, since_date)
        if not page_items and newest_dt is None:
            if page == 1:
                print("[HunanRST] no policy entries found on index page")
            break

        for it in page_items:
            if it["url"] in seen_urls:
                continue
            seen_urls.add(it["url"])
            results.append(it)

        # 列表按时间倒序，若本页最新日期都早于窗口可提前停止。
        if newest_dt and newest_dt.date() < since_date:
            break

    results.sort(key=lambda x: (x["date"], x["title"]), reverse=True)
    return results
