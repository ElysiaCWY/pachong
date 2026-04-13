# -*- coding: utf-8 -*-
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, now_cn, norm, mark_income_related


LN_POLICY_CHANNELS = {
    "liaoning_lrsg": "https://rst.ln.gov.cn/rst/zfxx/fdzdgknr/lzyj/rstgfxwj/lrsg/index.shtml",
    "liaoning_lrsf": "https://rst.ln.gov.cn/rst/zfxx/fdzdgknr/lzyj/rstgfxwj/lrsf/index.shtml",
    "liaoning_lrs": "https://rst.ln.gov.cn/rst/zfxx/fdzdgknr/lzyj/rstgfxwj/lrs/index.shtml",
}


def _extract_page_template(html: str) -> tuple[str | None, int]:
    total_pages = 1
    total_match = re.search(r"totalpage=\"(\d+)\"", html)
    if total_match:
        try:
            total_pages = max(1, int(total_match.group(1)))
        except Exception:
            total_pages = 1

    tpl_match = re.search(r"'([^']*%1\.shtml)'", html)
    if not tpl_match:
        return None, total_pages
    return tpl_match.group(1), total_pages


def _extract_publish_dt(url: str) -> datetime | None:
    m = re.search(r"/(20\d{12})\d*/index\.shtml", url)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y%m%d%H%M%S").replace(tzinfo=now_cn().tzinfo)
    except Exception:
        return None


def _parse_list_page(page_url: str, html: str, source: str, since: datetime, now: datetime) -> tuple[list[dict], bool]:
    soup = BeautifulSoup(html, "html.parser")
    results = []
    hit_older = False

    for li in soup.find_all("li"):
        a_tag = li.find("a", href=True)
        if not a_tag:
            continue

        href = (a_tag.get("href") or "").strip()
        if "/rst/zfxx/fdzdgknr/lzyj/rstgfxwj/" not in href:
            continue

        title = norm(a_tag.get_text(" ", strip=True))
        if not title:
            continue

        url = urljoin(page_url, href)
        published_dt = _extract_publish_dt(url)
        if not published_dt:
            continue
        if published_dt > now:
            continue
        if published_dt < since:
            hit_older = True
            continue

        results.append(
            {
                "title": mark_income_related(title),
                "url": url,
                "date": published_dt.date(),
                "source": source,
            }
        )

    return results, hit_older


def crawl_liaoning_hrss_policy(current_time: datetime | None = None) -> list[dict]:
    """
    抓取辽宁省人社厅三类政策文件，仅保留近24小时发布的标题和链接。
    """
    now = current_time or now_cn()
    since = now - timedelta(hours=24)
    session = make_session()
    results = []
    seen_urls = set()

    for source, first_url in LN_POLICY_CHANNELS.items():
        try:
            first_resp = session.get(first_url, timeout=20)
            first_resp.encoding = first_resp.apparent_encoding or "utf-8"
            if first_resp.status_code != 200:
                print(f"[LiaoningHRSS] HTTP Error {first_resp.status_code} @ {first_url}")
                continue

            page_template, total_pages = _extract_page_template(first_resp.text)
            page_no = 1
            while page_no <= total_pages:
                if page_no == 1:
                    page_url = first_url
                    html = first_resp.text
                else:
                    if not page_template:
                        break
                    page_url = urljoin(first_url, page_template.replace("%1", str(page_no)))
                    resp = session.get(page_url, timeout=20)
                    resp.encoding = resp.apparent_encoding or "utf-8"
                    if resp.status_code != 200:
                        print(f"[LiaoningHRSS] HTTP Error {resp.status_code} @ {page_url}")
                        break
                    html = resp.text

                page_items, hit_older = _parse_list_page(page_url, html, source, since, now)
                for item in page_items:
                    if item["url"] in seen_urls:
                        continue
                    seen_urls.add(item["url"])
                    results.append(item)

                if hit_older:
                    break
                page_no += 1
        except Exception as e:
            print(f"[LiaoningHRSS] Crawl error({source}): {e}")

    results.sort(key=lambda x: (x["date"], x["title"]), reverse=True)
    return results