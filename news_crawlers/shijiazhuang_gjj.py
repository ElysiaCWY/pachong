# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from urllib.parse import urljoin
import re

from bs4 import BeautifulSoup

from .common import make_session, now_cn, norm, parse_ymd, mark_income_related


SJZ_GJJ_ZCFG_URL = "https://www.sjzgjj.cn/zcfg/index.jhtml"


def _parse_list(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    items: list[dict] = []

    # 尝试匹配常见的文章链接（以 .jhtml 结尾）
    for a in soup.find_all("a", href=True):
        href = a.get("href") or ""
        if not href or not href.endswith(".jhtml"):
            continue

        title = norm(a.get("title") or a.get_text())
        if not title:
            continue

        # 在链接附近查找日期，优先使用同级或父节点文本中的 YYYY-MM-DD
        candidate_text = " ".join([t.strip() for t in a.parent.get_text(separator=" ").split()])
        m = re.search(r"(\d{4}-\d{2}-\d{2})", candidate_text)
        if not m:
            # 尝试查找紧邻的下一个文本节点
            nxt = a.next_sibling
            txt = ""
            if nxt and isinstance(nxt, str):
                txt = nxt.strip()
            else:
                txt = a.parent.get_text()
            m = re.search(r"(\d{4}-\d{2}-\d{2})", txt)

        if not m:
            continue

        article_date = parse_ymd(m.group(1))
        if not article_date:
            continue

        items.append(
            {
                "title": mark_income_related(title),
                "url": urljoin(SJZ_GJJ_ZCFG_URL, href),
                "date": article_date,
                "source": "政策法规",
            }
        )

    # 去重并保持顺序
    seen = set()
    uniq = []
    for it in items:
        key = (it["title"], it["url"], it["date"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(it)
    return uniq


def crawl_shijiazhuang_gjj_policy(current_time: datetime | None = None, max_pages: int = 5) -> list[dict]:
    """抓取石家庄住房公积金网 - 政策法规栏目（近24小时）。"""
    now = current_time or now_cn()
    since = now - timedelta(days=1)
    session = make_session()
    results: list[dict] = []

    for page in range(1, max_pages + 1):
        if page == 1:
            url = SJZ_GJJ_ZCFG_URL
        else:
            url = SJZ_GJJ_ZCFG_URL.replace("index.jhtml", f"index_{page}.jhtml")

        try:
            resp = session.get(url, timeout=15)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or "utf-8"
            html = resp.text
        except Exception as e:
            print(f"[Shijiazhuang GJJ] fetch error {url}: {e}")
            break

        items = _parse_list(html)
        if not items:
            break

        page_keep = [it for it in items if it["date"] >= since]
        results.extend(page_keep)

        # 若本页没有新近项，停止翻页
        if len(page_keep) < len(items):
            break

    # URL 去重
    seen_urls = set()
    uniq_results = []
    for it in results:
        if it["url"] in seen_urls:
            continue
        seen_urls.add(it["url"])
        uniq_results.append(it)

    return uniq_results
