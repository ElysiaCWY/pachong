# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from urllib.parse import urljoin

from .common import make_session, now_cn, norm, parse_ymd, mark_income_related


SD_BASE = "https://hrss.shandong.gov.cn"
SD_SEARCH_URL = "https://hrss.shandong.gov.cn/gentleCMS/search/index.do"

SD_OTHER_FILES_URL = "https://hrss.shandong.gov.cn/channels/ch00342/"
SD_OTHER_FILES_PCHANNELID = "3289c910-2cb1-472d-90b2-9758437aeff4"

SD_NORMATIVE_URL = "https://hrss.shandong.gov.cn/channels/ch00472/"
SD_NORMATIVE_CHANNELID = "393dabcf-79cb-415f-b722-df55b25088f0"
SD_NORMATIVE_WJFL = "法律法规规章及规范性文件"

SD_SITEID = "7f6d5d22-89b8-44d7-b0b4-f4a0185a4f8e"


def _search_items(session, payload: dict, referer: str) -> list[dict]:
    resp = session.post(
        SD_SEARCH_URL,
        data=payload,
        headers={"Referer": referer},
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    result = data.get("result")
    return result if isinstance(result, list) else []


def _parse_result_item(obj: dict, source: str) -> dict | None:
    title = norm(str(obj.get("NAME") or ""))
    href = norm(str(obj.get("URL") or ""))
    pub_text = norm(str(obj.get("PUBDATE") or obj.get("PROP19") or ""))
    publish_date = parse_ymd(pub_text[:10]) if pub_text else None

    if not title or not href or not publish_date:
        return None

    return {
        "title": mark_income_related(title),
        "url": urljoin(SD_BASE, href),
        "date": publish_date,
        "source": source,
    }


def _crawl_normative_items(session, since_date, today) -> list[dict]:
    results = []
    seen_urls = set()
    max_pages = 4

    for page_no in range(1, max_pages + 1):
        start = (page_no - 1) * 15
        rows = _search_items(
            session,
            {
                "NAME": "",
                "WJFL": SD_NORMATIVE_WJFL,
                "PROP1": "",
                "ZCWH": "",
                "CHANNELID": SD_NORMATIVE_CHANNELID,
                "SITEID": SD_SITEID,
                "start": start,
                "pageSize": 15,
            },
            referer=SD_NORMATIVE_URL,
        )
        if not rows:
            break

        hit_older = False
        for row in rows:
            item = _parse_result_item(row, "shandong_hrss_normative")
            if not item:
                continue
            if item["date"] > today:
                continue
            if item["date"] < since_date:
                hit_older = True
                continue
            if item["url"] in seen_urls:
                continue
            seen_urls.add(item["url"])
            results.append(item)

        if hit_older:
            break

    return results


def _crawl_lrssf_items(session, since_date, today) -> list[dict]:
    results = []
    seen_urls = set()
    max_pages = 4

    for page_no in range(1, max_pages + 1):
        start = (page_no - 1) * 15
        rows = _search_items(
            session,
            {
                "NAME": "",
                "WJFL": "",
                "GKWH": "",
                "ZTFL": "",
                "TCFL": "鲁人社发",
                "PCHANNELID": SD_OTHER_FILES_PCHANNELID,
                "CHANNELID": "",
                "SITEID": SD_SITEID,
                "start": start,
                "pageSize": 15,
            },
            referer=SD_OTHER_FILES_URL,
        )
        if not rows:
            break

        hit_older = False
        for row in rows:
            item = _parse_result_item(row, "shandong_hrss_lrssf")
            if not item:
                continue
            if item["date"] > today:
                continue
            if item["date"] < since_date:
                hit_older = True
                continue
            if item["url"] in seen_urls:
                continue
            seen_urls.add(item["url"])
            results.append(item)

        if hit_older:
            break

    return results


def crawl_shandong_hrss_policy(current_time: datetime | None = None) -> list[dict]:
    """
    抓取山东省人社厅：规范性文件 + 鲁人社发。
    仅保留近24小时发布（按日期粒度）的标题与链接。
    """
    now = current_time or now_cn()
    since_date = (now - timedelta(hours=24)).date()
    today = now.date()

    session = make_session()
    results = []
    seen_urls = set()

    try:
        normative_items = _crawl_normative_items(session, since_date, today)
    except Exception as e:
        print(f"[ShandongHRSS] normative fetch failed: {e}")
        normative_items = []

    try:
        lrssf_items = _crawl_lrssf_items(session, since_date, today)
    except Exception as e:
        print(f"[ShandongHRSS] lrssf fetch failed: {e}")
        lrssf_items = []

    for item in normative_items + lrssf_items:
        if item["url"] in seen_urls:
            continue
        seen_urls.add(item["url"])
        results.append(item)

    results.sort(key=lambda x: (x["date"], x["title"]), reverse=True)
    return results