# coding: utf-8
"""
平江住房公积金网 - 政策解读抓取
目标：抓取政策/解读类文章标题和链接，返回近24小时内发布的条目
接口：crawl_pjzfgjj_policy() -> list[dict]: {title,url,ts}
"""
from __future__ import annotations
import re
from datetime import datetime, timedelta
from typing import List, Dict

from .common import make_session, now_cn


def _parse_datetime_from_text(s: str):
    """尝试从文本解析出 datetime（本地时区），优先支持 YYYY-MM-DD HH:MM 等常见格式。"""
    if not s:
        return None
    s = s.strip()
    # 常见完整时间
    m = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?:[\sT]+(\d{1,2}):(\d{1,2}))?", s)
    if m:
        y, mo, d, hh, mm = m.groups()
        hh = hh or "0"
        mm = mm or "0"
        try:
            from datetime import datetime
            return datetime(int(y), int(mo), int(d), int(hh), int(mm), tzinfo=now_cn().tzinfo)
        except Exception:
            return None
    # 退回到仅年月日数字
    m2 = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
    if m2:
        y, mo, d = m2.groups()
        try:
            from datetime import datetime
            return datetime(int(y), int(mo), int(d), tzinfo=now_cn().tzinfo)
        except Exception:
            return None
    return None

BASE = "https://www.pjzfgjj.cn"
LIST_URL = "https://www.pjzfgjj.cn/12789/"  # 该页面为政策解读列表


def crawl_pjzfgjj_policy() -> List[Dict]:
    """爬取平江站政策解读，返回近24小时内的列表。
    每项至少包含 `title` 和 `url`，可选 `ts`（UTC或本地ISO）用于时间判断。
    """
    sess = make_session()
    resp = sess.get(LIST_URL, timeout=15)
    resp.encoding = resp.apparent_encoding
    html = resp.text

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    items = []

    # 页面通常以列表形式呈现，尝试寻找 class 或 ul/li
    # 兼容多种结构：li > a, div.article-list a 等
    anchors = []
    for sel in (".article-list a", "ul li a", "div.list a", "div.newsList a"):
        anchors = soup.select(sel)
        if anchors:
            break

    if not anchors:
        # 退回到所有文章链接中按 href 匹配路径包含 /12789/ 的链接
        anchors = [a for a in soup.find_all("a", href=True) if "/12789/" in a["href"]]

    # 解析每个链接的标题和可能的发布日期（若列表中无日期再请求详情页）
    cutoff = now_cn() - timedelta(hours=24)

    for a in anchors:
        title = (a.get_text() or "").strip()
        href = a.get("href") or ""
        if not href:
            continue
        if href.startswith("/"):
            url = BASE + href
        elif href.startswith("http"):
            url = href
        else:
            url = BASE.rstrip("/") + "/" + href.lstrip("/")

        # 尝试从同一 li/parent 中提取时间文字
        pub_ts = None
        parent = a.parent
        date_text = ""
        if parent:
            # 常见日期格式：2026-05-12 或 2026/05/12 或 05-12
            date_text = " ".join([t.strip() for t in parent.strings if re.search(r"\d{4}|\d{2}", t)])
        # 解析日期
        if date_text:
            dt = _parse_datetime_from_text(date_text)
            if dt:
                pub_ts = dt
        # 如果没有日期或不能解析，尝试抓取详情页头部的发布时间
        if not pub_ts:
            try:
                dresp = sess.get(url, timeout=15)
                dresp.encoding = dresp.apparent_encoding
                dsoup = BeautifulSoup(dresp.text, "lxml")
                # 常见位置：time, .pubtime, .article-meta, .update-time
                cand = dsoup.select_one("time, .pubtime, .article-meta, .date, .info")
                if cand:
                    pub_txt = cand.get_text().strip()
                    dt = _parse_datetime_from_text(pub_txt)
                    if dt:
                        pub_ts = dt
            except Exception:
                pub_ts = None

        # 如果仍然没有时间，跳过时间过滤（保守策略：不加入）
        if not pub_ts:
            continue

        # 过滤近24小时
        if pub_ts < cutoff:
            continue

        items.append({"title": title, "url": url, "ts": pub_ts.isoformat()})

    return items
