# -*- coding: utf-8 -*-
import os
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, now_cn, norm, mark_income_related


SH_HRSS_POLICY_INDEX = "https://rsj.sh.gov.cn/tgwgfx_17726/index.html"


def _build_page_candidates(page_no: int) -> list[str]:
    if page_no <= 1:
        return [SH_HRSS_POLICY_INDEX]

    base_dir = SH_HRSS_POLICY_INDEX.rsplit("/", 1)[0] + "/"
    # 站点分页脚本存在两种命名方式：index_2.html 或 index_1.html（第二页）
    return [
        urljoin(base_dir, f"index_{page_no}.html"),
        urljoin(base_dir, f"index_{page_no - 1}.html"),
    ]


def _pick_valid_page(session, page_no: int) -> tuple[str | None, str]:
    for candidate in _build_page_candidates(page_no):
        try:
            resp = session.get(candidate, timeout=20)
            if resp.status_code != 200:
                continue
            resp.encoding = resp.apparent_encoding or "utf-8"
            if "control-table" not in resp.text:
                continue
            return candidate, resp.text
        except Exception:
            continue
    return None, ""


def _parse_ymd_to_date(text: str):
    m = re.search(r"(20\d{2})-(\d{1,2})-(\d{1,2})", norm(text))
    if not m:
        return None
    try:
        y, mo, d = map(int, m.groups())
        return datetime(y, mo, d, tzinfo=now_cn().tzinfo).date()
    except Exception:
        return None


def crawl_shanghai_hrss_policy(current_time: datetime | None = None) -> list[dict]:
    """
    抓取上海市人社局“规范性文件”标题链接。
    仅保留近24小时内（按日期粒度近似）的条目。
    """
    now = current_time or now_cn()
    since_date = (now - timedelta(hours=24)).date()
    today = now.date()

    max_pages = max(1, int(os.getenv("SHANGHAI_HRSS_POLICY_MAX_PAGES", "8")))

    session = make_session()
    results = []
    seen_urls = set()
    visited_pages = set()

    for page_no in range(1, max_pages + 1):
        page_url, html = _pick_valid_page(session, page_no)
        if not page_url or not html or page_url in visited_pages:
            continue
        visited_pages.add(page_url)

        soup = BeautifulSoup(html, "html.parser")
        table = soup.select_one("table.control-table")
        if not table:
            continue

        hit_older = False
        for tr in table.select("tbody tr"):
            a_tag = tr.select_one("td a[href]")
            if not a_tag:
                continue

            href = norm(a_tag.get("href") or "")
            title = norm(a_tag.get("title") or a_tag.get_text(" ", strip=True))
            if not href or not title:
                continue

            tds = tr.find_all("td")
            publish_date = None
            if len(tds) >= 3:
                publish_date = _parse_ymd_to_date(tds[2].get_text(" ", strip=True))
            if not publish_date:
                publish_date = _parse_ymd_to_date(tr.get_text(" ", strip=True))
            if not publish_date:
                continue

            if publish_date > today:
                continue
            if publish_date < since_date:
                hit_older = True
                continue

            full_url = urljoin(page_url, href)
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            results.append(
                {
                    "title": mark_income_related(title),
                    "url": full_url,
                    "date": publish_date,
                    "source": "shanghai_hrss_policy",
                }
            )

        # 列表按发布日期倒序，命中旧数据后停止翻页
        if hit_older:
            break

    results.sort(key=lambda x: (x["date"], x["title"]), reverse=True)
    return results
