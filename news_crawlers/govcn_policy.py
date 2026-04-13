# -*- coding: utf-8 -*-
import os
from datetime import date
from urllib.parse import urljoin

from .common import make_session, norm, now_cn, parse_ymd, target_prev_workday, mark_income_related


# ===================== 中国政府网：最新政策 =====================
GOVCN_POLICY_URL = "https://www.gov.cn/zhengce/zuixin/"
GOVCN_POLICY_JSON_URL = urljoin(GOVCN_POLICY_URL, "ZUIXINZHENGCE.json")


def crawl_govcn_policy():
    """
    抓取中国政府网-最新政策。
    默认抓上一工作日，支持 GOVCN_POLICY_TARGET_DATE 覆盖。
    """
    override = parse_ymd(os.getenv("GOVCN_POLICY_TARGET_DATE"))
    target = override or target_prev_workday(now_cn().date())
    max_items = int(os.getenv("GOVCN_POLICY_MAX_ITEMS", "20"))

    s = make_session()
    try:
        r = s.get(GOVCN_POLICY_JSON_URL, timeout=20)
        r.encoding = "utf-8"
        rows = r.json()
    except Exception as e:
        print(f"GovCN Policy fetch fail: {e}")
        return []

    if not isinstance(rows, list):
        return []

    results = []
    seen = set()

    for row in rows:
        if not isinstance(row, dict):
            continue

        href = norm(str(row.get("URL") or ""))
        title = norm(str(row.get("TITLE") or ""))
        dt = parse_ymd(norm(str(row.get("DOCRELPUBTIME") or "")))

        if not href or not title:
            continue
        if len(title) < 6:
            continue
        if not dt or dt != target:
            continue

        if "gov.cn" not in href or "/zhengce/" not in href:
            continue

        url = urljoin(GOVCN_POLICY_URL, href)
        if url in seen:
            continue

        seen.add(url)
        title = mark_income_related(title)
        results.append({"title": title, "url": url, "date": dt, "source": "govcn_policy"})

        if len(results) >= max_items:
            break

    return results
