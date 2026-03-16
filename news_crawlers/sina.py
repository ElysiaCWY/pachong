# -*- coding: utf-8 -*-
import os
import re
import time
import requests
from datetime import datetime
from bs4 import BeautifulSoup, Tag
from urllib.parse import urljoin
from .common import TZ, now_cn, norm, parse_ymd, target_prev_workday

# ===================== 企业新闻：新浪财经 =====================
SINA_START_URL = "https://finance.sina.com.cn/roll/c/221431.shtml"
SINA_MAX_PAGES = int(os.getenv("SINA_MAX_PAGES", "5"))
SINA_SLEEP_SEC = float(os.getenv("SINA_SLEEP_SEC", "0.8"))
SINA_MAX_ITEMS = int(os.getenv("SINA_MAX_ITEMS", "15"))
SINA_DATE_RE = re.compile(r"\((\d{2})月(\d{2})日\s*(\d{2}):(\d{2})\)")

def sina_get_html(url: str) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    r = requests.get(url, headers=headers, timeout=15)
    r.raise_for_status()
    if not r.encoding or r.encoding.lower() == "iso-8859-1":
        r.encoding = r.apparent_encoding
    return r.text

def sina_parse_datetime(text: str):
    m = SINA_DATE_RE.search(text or "")
    if not m:
        return None
    month, day, hh, mm = map(int, m.groups())
    now = now_cn()
    year = now.year
    if now.month == 1 and month == 12:
        year -= 1
    try:
        return datetime(year, month, day, hh, mm, tzinfo=TZ)
    except Exception:
        return None

def sina_find_next_page(soup: BeautifulSoup):
    a = soup.find("a", string=lambda s: s and "下一页" in s)
    if a and a.get("href"):
        return urljoin(SINA_START_URL, a["href"])
    return None

def sina_pick_best_link(li: Tag):
    links = []
    for a in li.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href:
            continue
        abs_url = urljoin(SINA_START_URL, href)
        text = a.get_text(strip=True)
        links.append((abs_url, text))
    if not links:
        return None, None

    def score(u: str):
        s = 0
        if ".shtml" in u: s += 10
        if "/doc-" in u: s += 8
        if "/article/" in u: s += 6
        if "finance.sina.com.cn" in u: s += 2
        return s

    links.sort(key=lambda x: score(x[0]), reverse=True)
    return links[0][0], links[0][1]

def crawl_sina_target_day():
    override = parse_ymd(os.getenv("SINA_TARGET_DATE"))
    today = now_cn().date()
    target = override or target_prev_workday(today)

    seen_link = set()
    seen_tt = set()
    results = []

    url = SINA_START_URL
    hit = False

    for _ in range(1, SINA_MAX_PAGES + 1):
        html = sina_get_html(url)
        soup = BeautifulSoup(html, "html.parser")

        container = soup.select_one("div.listBlk")
        if not container:
            break
        lis = container.find_all("li")
        if not lis:
            break

        for li in lis:
            text_all = li.get_text(" ", strip=True)
            dt = sina_parse_datetime(text_all)
            if not dt or dt.date() != target:
                continue

            link, anchor_text = sina_pick_best_link(li)
            if not link:
                continue

            a0 = li.find("a")
            title = (a0.get_text(strip=True) if a0 else "") or (anchor_text or "")
            title = norm(title)
            if not title:
                continue

            k1 = link
            k2 = (title, dt.strftime("%Y-%m-%d %H:%M"))
            if k1 in seen_link or k2 in seen_tt:
                continue

            seen_link.add(k1)
            seen_tt.add(k2)
            results.append((dt, title, link))
            hit = True

        if hit:
            dts = [sina_parse_datetime(li.get_text(" ", strip=True)) for li in lis]
            dts = [d for d in dts if d]
            if dts and all(d.date() < target for d in dts):
                break

        next_url = sina_find_next_page(soup)
        if not next_url:
            break
        url = next_url
        time.sleep(SINA_SLEEP_SEC)

    results.sort(key=lambda x: x[0], reverse=True)
    return target, results[:SINA_MAX_ITEMS]
