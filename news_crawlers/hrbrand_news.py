# -*- coding: utf-8 -*-
import os
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from .common import make_session, norm, now_cn

# ===================== HRbrand：品牌动态 =====================
HRBRAND_NEWS_URL = "http://www.hrbrand.net/news.php"


def _clean_title(raw: str) -> str:
    """清理列表页标题噪音，保留核心标题。"""
    t = norm(raw)
    # 去掉尾部日期
    t = re.sub(r"\s+20\d{2}/\d{1,2}/\d{1,2}\s*$", "", t)
    # 列表页通常用 ... 拼接摘要，仅保留标题部分
    t = re.split(r"\.\.\.|……", t)[0].strip()
    return t


def _parse_publish_time(li_node):
    """
    解析列表项发布时间。
    优先用封面图中的 14 位时间戳，其次使用 nlr-03 的日期文本。
    """
    tz = now_cn().tzinfo

    # 1) 尝试从图片路径提取 YYYYMMDDHHMMSS
    img = li_node.find("img", src=True)
    if img:
        src = img.get("src") or ""
        m = re.search(r"(20\d{12})", src)
        if m:
            try:
                dt = datetime.strptime(m.group(1), "%Y%m%d%H%M%S")
                return dt.replace(tzinfo=tz)
            except Exception:
                pass

    # 2) 回退到列表日期 YYYY/MM/DD
    date_div = li_node.select_one(".nlr-03")
    date_text = norm(date_div.get_text(" ", strip=True)) if date_div else ""
    if date_text:
        for fmt in ("%Y/%m/%d", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(date_text, fmt)
                return dt.replace(tzinfo=tz)
            except Exception:
                continue

    return None


def crawl_hrbrand_news():
    """
    抓取 HRbrand 品牌动态列表页的新闻标题与链接。
    仅返回品牌动态正文链接（news-detail.php?i=数字），按出现顺序去重。
    且仅保留近 24 小时发布的文章。
    """
    max_items = int(os.getenv("HRBRAND_MAX_ITEMS", "8"))
    now = now_cn()
    cutoff = now - timedelta(hours=24)

    s = make_session()
    try:
        r = s.get(HRBRAND_NEWS_URL, timeout=15)
        r.encoding = r.apparent_encoding or "utf-8"
    except Exception as e:
        print(f"HRbrand fetch fail: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")

    results = []
    seen = set()

    # 优先按明确列表结构解析（li -> a + nlr-01 + nlr-03）
    for li in soup.select("div.ind-news-list ul li"):
        a = li.find("a", href=True)
        if not a:
            continue

        href = (a.get("href") or "").strip()
        if not re.search(r"news-detail\.php\?i=\d+$", href):
            continue

        title_node = li.select_one(".nlr-01")
        raw_title = title_node.get_text(" ", strip=True) if title_node else a.get_text(" ", strip=True)
        title = _clean_title(raw_title)
        if not title or len(title) < 6:
            continue

        pub_dt = _parse_publish_time(li)
        if not pub_dt or pub_dt < cutoff:
            continue

        url = urljoin(HRBRAND_NEWS_URL, href)
        if url in seen:
            continue

        seen.add(url)
        results.append(
            {
                "title": title,
                "url": url,
                "source": "hrbrand_news",
                "published_at": pub_dt.strftime("%Y-%m-%d %H:%M"),
            }
        )

        if len(results) >= max_items:
            break

    return results
