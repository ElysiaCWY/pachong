# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from bs4 import BeautifulSoup

from .common import make_session, now_cn, norm, parse_ymd, mark_income_related


AH_HRSS_LABEL_API = "https://hrss.ah.gov.cn/site/label/8888"

# 行政规范性文件 / 其他政策文件
AH_POLICY_CATS = {
    "anhui_xingzheng_gfxwj": "6717425",
    "anhui_qita_zcwj": "6714211",
}


def _fetch_cat_page(session, cat_id: str, page_index: int) -> str:
    data = {
        "labelName": "publicInfoList",
        "siteId": "6784211",
        "pageSize": "15",
        "pageIndex": str(page_index),
        "isDate": "true",
        "dateFormat": "yyyy-MM-dd",
        "length": "45",
        "active": "0",
        "organId": "6595721",
        "type": "6",
        "fileNum": "",
        "filterFileNum": "",
        "catIds": cat_id,
        "fromCode": "title",
        "sortType": "1",  # 按发布日期
        "action": "list",
        "fuzzySearch": "false",
        "keyWords": "",
        "publicDivId": "tab_0_0",
        "isInvalid": "0,5",
        "result": "暂无相关信息",
        "file": "/jh2/publicInfoList_xzgfk",
    }
    r = session.post(AH_HRSS_LABEL_API, data=data, timeout=20, headers={"Referer": "https://hrss.ah.gov.cn/public/column/6595721?type=6&action=xinzheng"})
    r.encoding = r.apparent_encoding or "utf-8"
    return r.text if r.status_code == 200 else ""


def _parse_page(html: str, source: str) -> list[dict]:
    soup = BeautifulSoup(html or "", "html.parser")
    rows = []

    for tr in soup.select("table.r_xh_b tbody tr"):
        if "title" in (tr.get("class") or []):
            continue

        a_tag = tr.select_one("td div.title a[href]")
        if not a_tag:
            continue

        title = norm(a_tag.get("title") or a_tag.get_text(" ", strip=True))
        url = norm(a_tag.get("href") or "")
        if not title or not url:
            continue

        date_text = ""
        for span in tr.select("p.subTitle span"):
            txt = norm(span.get_text(" ", strip=True))
            if "成文日期" in txt:
                date_text = txt.split("：", 1)[-1].strip()
                break

        dt = parse_ymd(date_text)
        if not dt:
            continue

        rows.append(
            {
                "title": mark_income_related(title),
                "url": url,
                "date": dt,
                "source": source,
            }
        )

    return rows


def crawl_anhui_hrss_policy(current_time: datetime | None = None) -> list[dict]:
    """
    抓取安徽省人社厅：行政规范性文件 + 其他政策文件。
    仅保留近24小时发布（按日期粒度）的文章标题与链接。
    """
    now = current_time or now_cn()
    since_date = (now - timedelta(hours=24)).date()
    today = now.date()

    session = make_session()
    max_pages = 3
    results = []
    seen = set()

    for source, cat_id in AH_POLICY_CATS.items():
        for page in range(1, max_pages + 1):
            try:
                html = _fetch_cat_page(session, cat_id, page)
            except Exception as e:
                print(f"[AnhuiHRSS] fetch failed({source}, p{page}): {e}")
                break

            items = _parse_page(html, source)
            if not items:
                break

            page_has_recent = False
            for it in items:
                dt = it["date"]
                if dt > today:
                    continue
                if dt < since_date:
                    continue

                page_has_recent = True
                if it["url"] in seen:
                    continue
                seen.add(it["url"])
                results.append(it)

            if not page_has_recent:
                break

    results.sort(key=lambda x: (x["date"], x["title"]), reverse=True)
    return results
