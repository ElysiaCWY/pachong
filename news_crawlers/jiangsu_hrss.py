# -*- coding: utf-8 -*-
import html
import os
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, now_cn, norm, parse_ymd, mark_income_related


JS_HRSS_POLICY_INDEX = "https://jshrss.jiangsu.gov.cn/col/col77273/index.html"
JS_HRSS_PROXY_URL = "https://jshrss.jiangsu.gov.cn/module/web/jpage/morecolumndataproxy.jsp"

JS_HRSS_PROXY_PARAMS = {
    "appid": "1",
    "webid": "67",
    "path": "/",
    "columnid": "77276,77277,77278,77279,77280,77281",
    "unitid": "313354",
    "keyWordCount": "999",
    "webname": "江苏省人力资源和社会保障厅",
    "col": "1",
    "sourceContentType": "3",
}


def _parse_li_items(fragment: str, base_url: str) -> list[dict]:
    soup = BeautifulSoup(fragment, "html.parser")
    items = []

    for li in soup.find_all("li"):
        a_tag = li.find("a", href=True)
        b_tag = li.find("b")
        if not a_tag or not b_tag:
            continue

        title = norm(a_tag.get("title") or a_tag.get_text(" ", strip=True))
        href = norm(a_tag.get("href") or "")
        dt = parse_ymd(b_tag.get_text(" ", strip=True))
        if not title or not href or not dt:
            continue

        items.append(
            {
                "title": mark_income_related(title),
                "url": urljoin(base_url, href),
                "date": dt,
                "source": "jiangsu_hrss_policy",
            }
        )

    return items


def _extract_items_from_proxy_payload(payload: str, base_url: str) -> list[dict]:
    if not payload:
        return []

    text = html.unescape(payload)
    items = _parse_li_items(text, base_url)
    if items:
        return items

    # 江苏接口外层是 XML，正文列表包装在 <record><![CDATA[...]]></record> 中。
    items = []
    for fragment in re.findall(r"<record><!\[CDATA\[(.*?)\]\]></record>", text, flags=re.S):
        items.extend(_parse_li_items(html.unescape(fragment), base_url))

    return items


def crawl_jiangsu_hrss_policy(current_time: datetime | None = None) -> list[dict]:
    """
    抓取江苏省人社厅“最新政策”标题和链接，仅保留近24小时发布内容。
    """
    now = current_time or now_cn()
    since_date = (now - timedelta(hours=24)).date()
    today = now.date()

    max_pages = max(1, int(os.getenv("JIANGSU_HRSS_POLICY_MAX_PAGES", "5")))
    request_timeout = max(20, int(os.getenv("JIANGSU_HRSS_POLICY_TIMEOUT", "60")))

    session = make_session()
    results = []
    seen_urls = set()

    for page in range(1, max_pages + 1):
        params = dict(JS_HRSS_PROXY_PARAMS)
        params["page"] = str(page)

        try:
            resp = session.get(
                JS_HRSS_PROXY_URL,
                params=params,
                timeout=request_timeout,
                headers={"Referer": JS_HRSS_POLICY_INDEX},
            )
            resp.encoding = resp.apparent_encoding or "utf-8"
            if resp.status_code != 200:
                print(f"[JiangsuHRSS] HTTP Error {resp.status_code} @ page {page}")
                break
        except Exception as e:
            print(f"[JiangsuHRSS] fetch failed(p{page}): {e}")
            break

        page_items = _extract_items_from_proxy_payload(resp.text, JS_HRSS_POLICY_INDEX)
        if not page_items:
            break

        page_has_recent = False
        for it in page_items:
            dt = it["date"]
            if dt > today:
                continue
            if dt < since_date:
                continue

            page_has_recent = True
            if it["url"] in seen_urls:
                continue
            seen_urls.add(it["url"])
            results.append(it)

        # 分页按时间倒序；当前页已无近24h时可停止。
        if not page_has_recent:
            break

    results.sort(key=lambda x: (x["date"], x["title"]), reverse=True)
    return results
