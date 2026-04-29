# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, now_cn, norm, parse_ymd, mark_income_related


ZJ_HRSS_POLICY_URL = "https://rlsbt.zj.gov.cn/col/col1229101516/index.html"


def crawl_zhejiang_hrss_policy(current_time: datetime | None = None) -> list[dict]:
    """
    抓取浙江省人社厅“行政规范性文件”列表。
    仅保留近24小时内发布的标题和链接。
    """
    now = current_time or now_cn()
    since_date = (now - timedelta(hours=24)).date()
    today = now.date()

    session = make_session()
    try:
        resp = session.get(ZJ_HRSS_POLICY_URL, timeout=20)
        resp.encoding = resp.apparent_encoding or "utf-8"
        if resp.status_code != 200:
            print(f"[ZhejiangHRSS] HTTP Error {resp.status_code}")
            return []
    except Exception as e:
        print(f"[ZhejiangHRSS] fetch failed: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    results = []
    seen_urls = set()

    # 列表在 page-content 区域，条目为 li，时间在 span.bt_time
    for li in soup.select("div.page-content li"):
        a_tag = li.select_one("a[href]")
        t_tag = li.select_one("span.bt_time")
        if not a_tag or not t_tag:
            continue

        title = norm(a_tag.get("title") or a_tag.get_text(" ", strip=True))
        href = norm(a_tag.get("href") or "")
        dt = parse_ymd(t_tag.get_text(" ", strip=True))
        if not title or not href or not dt:
            continue
        if dt > today:
            continue
        if dt < since_date:
            continue

        full_url = urljoin(ZJ_HRSS_POLICY_URL, href)
        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)

        results.append(
            {
                "title": mark_income_related(title),
                "url": full_url,
                "date": dt,
                "source": "zhejiang_hrss_policy",
            }
        )

    results.sort(key=lambda x: (x["date"], x["title"]), reverse=True)
    return results
