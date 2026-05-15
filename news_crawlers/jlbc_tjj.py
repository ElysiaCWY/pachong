# -*- coding: utf-8 -*-
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .common import mark_income_related, now_cn, norm


BASE_URL = "http://xxgk.jlbc.gov.cn"
LIST_PAGE = f"{BASE_URL}/zsjg/tjj/xxgkml/"


def _parse_publish_time(value: str):
    if not value:
        return None
    text = norm(value)
    if not text:
        return None

    text = text.replace('/', '-').strip()
    m = re.search(r"(\d{4}-\d{1,2}-\d{1,2})", text)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y-%m-%d")
        except Exception:
            pass

    # 支持带时分的格式
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text[: len(fmt)], fmt)
        except Exception:
            continue
    return None


def crawl_jlbc_tjj(current_time: datetime | None = None, max_pages: int = 2) -> list[dict]:
    """抓取 `xxgk.jlbc` 统计局/信息公开栏目下的条目，返回近24小时发布的标题与链接。"""
    now = current_time or now_cn()
    since_dt = now - timedelta(hours=24)

    session = requests.Session()
    results: list[dict] = []
    seen = set()

    try:
        resp = session.get(LIST_PAGE, timeout=20)
        resp.encoding = resp.apparent_encoding or "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        print(f"[JLBC TJJ] Fetch list page error: {e}")
        return []

    # 解析常见列表项
    for a in soup.select("a"):
        href = a.get("href") or ""
        if not href:
            continue
        # 只处理本站相对或本站绝对链接
        if not (href.startswith("/zsjg") or href.startswith("/zsjg/") or "/zsjg/" in href):
            continue

        title = norm(a.get_text() or "").strip()
        if not title:
            continue

        # 尝试从祖先元素或相邻元素提取日期
        pub_text = ""
        parent = a.find_parent("li") or a.find_parent("div")
        if parent:
            cand = parent.find(lambda tag: tag.name in ["span", "i", "em", "p"] and re.search(r"\d{4}", (tag.get_text() or "")))
            if cand:
                pub_text = cand.get_text()
        if not pub_text:
            sib = a.find_next_sibling()
            if sib and sib.get_text():
                pub_text = sib.get_text()

        try:
            url = urljoin(BASE_URL, href)
        except Exception:
            url = href

        if url in seen:
            continue

        publish_dt = _parse_publish_time(pub_text or "")

        # 若无时间则请求详情页快速查找
        if not publish_dt:
            try:
                dresp = session.get(url, timeout=15)
                dresp.encoding = dresp.apparent_encoding or "utf-8"
                dsoup = BeautifulSoup(dresp.text, "html.parser")
                cand = dsoup.find(lambda tag: tag.name in ["span", "p", "div"] and re.search(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}", (tag.get_text() or "")))
                if cand:
                    publish_dt = _parse_publish_time(cand.get_text())
            except Exception:
                publish_dt = None

        if publish_dt:
            if publish_dt > now:
                continue
            if publish_dt < since_dt:
                continue
        else:
            # 无法解析时间，跳过以避免误报
            print(f"[JLBC TJJ] Skip item without publish time: {title}")
            continue

        seen.add(url)
        results.append(
            {
                "title": mark_income_related(title),
                "url": url,
                "date": publish_dt.date() if publish_dt else None,
                "source": "jlbc_tjj_policy",
            }
        )

    results.sort(key=lambda x: (x.get("date") or now_cn().date(), x.get("title", "")), reverse=True)
    return results
