# -*- coding: utf-8 -*-
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, now_cn, norm, mark_income_related


FJ_RST_BBMWJ_URL = "https://rst.fujian.gov.cn/zw/zxwj/bbmwj/"


def _extract_publish_date_from_url(url: str):
    # 例: /202604/t20260402_7118505.htm
    m = re.search(r"t(20\d{6})_\d+\.htm", url)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y%m%d").date()
    except Exception:
        return None


def crawl_fujian_rst_bbmwj(current_time: datetime | None = None) -> list[dict]:
    """
    抓取福建省人社厅“本部门文件”标题和链接。
    仅保留近24小时发布（按日期粒度）的条目。
    """
    now = current_time or now_cn()
    since_date = (now - timedelta(hours=24)).date()
    today = now.date()

    session = make_session()
    try:
        resp = session.get(FJ_RST_BBMWJ_URL, timeout=20)
        resp.encoding = resp.apparent_encoding or "utf-8"
        if resp.status_code != 200:
            print(f"[FujianRST] HTTP Error {resp.status_code}")
            return []
    except Exception as e:
        print(f"[FujianRST] fetch failed: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    results = []
    seen = set()

    for a_tag in soup.select("a[href]"):
        href = norm(a_tag.get("href") or "")
        if not href:
            continue

        # 本部门文件正文链接（信息公开目录下）
        if "zfxxgk/zfxxgkml/" not in href:
            continue
        if not re.search(r"t20\d{6}_\d+\.htm", href):
            continue

        title = norm(a_tag.get("title") or a_tag.get_text(" ", strip=True))
        if not title or len(title) < 6:
            continue

        full_url = urljoin(FJ_RST_BBMWJ_URL, href)
        dt = _extract_publish_date_from_url(full_url)
        if not dt:
            continue
        if dt > today:
            continue
        if dt < since_date:
            continue

        if full_url in seen:
            continue
        seen.add(full_url)

        results.append(
            {
                "title": mark_income_related(title),
                "url": full_url,
                "date": dt,
                "source": "fujian_rst_bbmwj",
            }
        )

    results.sort(key=lambda x: (x["date"], x["title"]), reverse=True)
    return results
