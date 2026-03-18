# -*- coding: utf-8 -*-
import os
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from .common import make_session, norm

# ===================== 第一财经：大政 =====================
YICAI_HONGGUAN_URL = "https://www.yicai.com/news/hongguan/"


def _clean_title(raw: str) -> str:
    t = norm(raw)
    # 去掉尾部常见的阅读数/评论数/时间信息
    t = re.sub(r"\s+\d+\s+\d+\s*(分钟前|小时前|昨天\s*\d{1,2}:\d{2}|\d{2}-\d{2}\s*\d{1,2}:\d{2})\s*$", "", t)
    t = re.sub(r"\s+\d+\s*(分钟前|小时前)\s*$", "", t)
    return t.strip()


def crawl_yicai_hongguan():
    """
    抓取第一财经-大政列表页的新闻标题与链接。
    仅返回新闻正文链接（/news/数字.html），并按出现顺序去重。
    """
    max_items = int(os.getenv("YICAI_MAX_ITEMS", "5"))

    s = make_session()
    try:
        r = s.get(YICAI_HONGGUAN_URL, timeout=15)
        r.encoding = r.apparent_encoding or "utf-8"
    except Exception as e:
        print(f"Yicai Hongguan fetch fail: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")

    results = []
    seen = set()

    def add_item(title: str, href: str):
        title = _clean_title(title)
        if not title or len(title) < 6:
            return
        if title in {"周榜", "月榜"}:
            return
        if not re.search(r"/news/\d+\.html$", href or ""):
            return

        url = urljoin(YICAI_HONGGUAN_URL, href)
        if url in seen:
            return
        seen.add(url)
        results.append({"title": title, "url": url, "source": "yicai_hongguan"})

    # 主路径：DOM 提取
    for a in soup.find_all("a", href=True):
        add_item(a.get_text(" ", strip=True), (a.get("href") or "").strip())
        if len(results) >= max_items:
            break

    # 兜底：页面结构变化时，使用正则抓取 <a ... href="/news/数字.html">标题</a>
    if len(results) < max_items:
        html = r.text or ""
        pairs = re.findall(r'<a[^>]+href=["\']([^"\']*/news/\d+\.html)["\'][^>]*>(.*?)</a>', html, flags=re.I | re.S)
        for href, raw_title in pairs:
            # 去除标题中的内联标签
            title = re.sub(r"<[^>]+>", "", raw_title or "")
            add_item(title, href)
            if len(results) >= max_items:
                break

    return results
