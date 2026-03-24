# -*- coding: utf-8 -*-
import os
import re
import time
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from .common import norm, now_cn, target_prev_workday, mark_income_related

# ===================== 地方政策：人社部-人社动态（Playwright） =====================
MOHRSS_DEFAULT_LIST_URL = "https://www.mohrss.gov.cn/SYrlzyhshbzb/dongtaixinwen/dfdt/index.html"
MOHRSS_POLICY_URL = "https://www.mohrss.gov.cn/was5/web/search?channelid=203464&orderby=date&default=isall"
RE_DATE_DASH = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")
RE_DATE_CN = re.compile(r"\b(20\d{2})年(\d{1,2})月(\d{1,2})日\b")

def normalize_date_text(text: str):
    if not text:
        return None
    s = norm(text)

    m1 = RE_DATE_DASH.search(s)
    if m1:
        return m1.group(1)

    m2 = RE_DATE_CN.search(s)
    if m2:
        y = m2.group(1)
        mo = int(m2.group(2))
        d = int(m2.group(3))
        return f"{y}-{mo:02d}-{d:02d}"
    return None

def fetch_rendered_html(url: str, retries: int = 2) -> str:
    last_html = ""
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"],
        )

        for _ in range(retries + 1):
            page = browser.new_page(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/123.0.0.0 Safari/537.36"
                ),
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
            )
            page.set_extra_http_headers({"Accept-Language": "zh-CN,zh;q=0.9"})

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                try:
                    page.wait_for_function(
                        "document.body && /20\\d{2}-\\d{2}-\\d{2}/.test(document.body.innerText)",
                        timeout=12000
                    )
                except Exception:
                    page.wait_for_timeout(1500)

                html = page.content()
                last_html = html

                if len(html or "") < 5000:
                    page.close()
                    time.sleep(1.2)
                    continue

                page.close()
                browser.close()
                return html

            except Exception:
                try:
                    page.close()
                except Exception:
                    pass
                time.sleep(1.2)

        browser.close()
        return last_html

def parse_list_robust(html: str, page_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    items = []

    for node in soup.find_all(string=True):
        dt = normalize_date_text(str(node))
        if not dt:
            continue

        container = node.parent
        for _ in range(12):
            if not container:
                break
            a = container.find("a", href=True)
            if a and norm(a.get_text()):
                href = a["href"].strip()
                if ".html" in href:
                    title = norm(a.get_text())
                    title = mark_income_related(title)
                    items.append({
                        "date": dt,
                        "title": title,
                        "url": urljoin(page_url, href)
                    })
                    break
            container = container.parent

    seen, uniq = set(), []
    for it in items:
        key = (it["date"], it["title"], it["url"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(it)

    uniq.sort(key=lambda x: (x["date"], x["title"]), reverse=True)
    return uniq

def crawl_mohrss_target_day():
    today = now_cn().date()
    target = target_prev_workday(today)
    list_url = (os.getenv("MOHRSS_LIST_URL") or MOHRSS_DEFAULT_LIST_URL).strip()

    html = fetch_rendered_html(list_url, retries=2)
    items = parse_list_robust(html, list_url)
    hit = [x for x in items if x["date"] == target.strftime("%Y-%m-%d")]
    return target, list_url, hit

def crawl_mohrss_policy_target_day():
    today = now_cn().date()
    target = target_prev_workday(today)
    list_url = MOHRSS_POLICY_URL

    html = fetch_rendered_html(list_url, retries=2)
    items = parse_list_robust(html, list_url)
    hit = [x for x in items if x["date"] == target.strftime("%Y-%m-%d")]
    return target, list_url, hit
