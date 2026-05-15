# -*- coding: utf-8 -*-
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .common import mark_income_related, now_cn, norm


BASE_URL = "http://bsgjj.cbs.gov.cn"
LIST_PAGE = f"{BASE_URL}/zcfg/zxzc/"


def _parse_publish_time(value: str):
    if not value:
        return None
    text = norm(value)
    if not text:
        return None

    text = text.replace('/', '-').strip()
    text = re.sub(r"[\[\]()\s]+", " ", text)

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[: len(fmt)], fmt)
        except Exception:
            continue
    # 尝试从字符串中抽取 YYYY-MM-DD
    m = re.search(r"(\d{4}-\d{1,2}-\d{1,2})", text)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y-%m-%d")
        except Exception:
            pass
    return None


def crawl_baishan_gjj_center(current_time: datetime | None = None, max_pages: int = 3) -> list[dict]:
    """抓取白山住房公积金中心“中心政策/通知”列表，返回近24小时发布的条目。"""
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
        print(f"[Baishan GJJ] Fetch list page error: {e}")
        return []

    # 常见列表结构：ul/li/a + 日期在 sibling 或者在同一 li 的 span
    candidates = []
    for a in soup.select("a"):
        href = a.get("href") or ""
        if not href:
            continue
        # 只关心 zcfg 或 zxzc 下的链接
        if "/zcfg" not in href and "/zxzc" not in href:
            continue
        title = norm(a.get_text() or "").strip()
        if not title:
            continue

        # 尝试寻找发布时间：优先查找父 li 或相邻的时间标签
        pub_text = ""
        parent = a.find_parent("li") or a.find_parent("div")
        if parent:
            # 常见 <span class="date">2026-05-12</span>
            span = parent.find(lambda tag: tag.name in ["span", "i", "em"] and re.search(r"\d{4}", (tag.get_text() or "")))
            if span:
                pub_text = span.get_text()
        if not pub_text:
            # 查找后续兄弟节点
            sib = a.find_next_sibling()
            if sib and sib.get_text():
                pub_text = sib.get_text()

        candidates.append((title, href, pub_text))

    for title, href, pub_text in candidates:
        try:
            url = urljoin(BASE_URL, href)
        except Exception:
            url = href

        if url in seen:
            continue

        publish_dt = _parse_publish_time(pub_text or "")
        if publish_dt and publish_dt > now:
            # 未来时间跳过
            continue

        # 若无时间信息，尝试请求详情页查找发布日期（尽量避免大量请求）
        if not publish_dt:
            # 仅在需要时请求一次详情页，且限速
            try:
                dresp = session.get(url, timeout=15)
                dresp.encoding = dresp.apparent_encoding or "utf-8"
                dsoup = BeautifulSoup(dresp.text, "html.parser")
                # 常见时间样式
                cand = dsoup.find(lambda tag: tag.name in ["span", "p", "div"] and re.search(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}", (tag.get_text() or "")))
                if cand:
                    publish_dt = _parse_publish_time(cand.get_text())
            except Exception:
                publish_dt = None

        # 若能解析到时间，则进行24小时过滤
        if publish_dt:
            if publish_dt < since_dt:
                continue

        # 若完全无法解析时间，则跳过（避免误报）
        if not publish_dt:
            print(f"[Baishan GJJ] Skip item without publish time: {title}")
            continue

        seen.add(url)
        results.append(
            {
                "title": mark_income_related(title),
                "url": url,
                "date": publish_dt.date() if publish_dt else None,
                "source": "baishan_gjj_policy",
            }
        )

    # 排序：按时间降序
    results.sort(key=lambda x: (x.get("date") or now_cn().date(), x.get("title", "")), reverse=True)
    return results
