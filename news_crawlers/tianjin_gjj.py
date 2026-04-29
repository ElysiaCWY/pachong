# -*- coding: utf-8 -*-
import re
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from news_crawlers.common import make_session, parse_ymd, now_cn, norm, mark_income_related


CATEGORY_URLS = {
    "本市规范性文件": "https://www.zfgjj.cn/tjgjjcms/mainSitePc/regalution2.jsp?cid=10844&ztc=%E6%9C%89%E6%95%88",
    "中心文件库": "https://www.zfgjj.cn/tjgjjcms/mainSitePc/regalution2.jsp?cid=10845&ztc=%E6%9C%89%E6%95%88",
}


def _fetch_html_requests(session, url: str) -> str:
    resp = session.get(url, timeout=12)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.text


def _fetch_html_playwright(url: str) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"],
        )
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
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        try:
            page.wait_for_function("document.body && /20\\d{2}-\\d{2}-\\d{2}/.test(document.body.innerText)", timeout=12000)
        except Exception:
            page.wait_for_timeout(1200)
        html = page.content()
        browser.close()
        return html


def _parse_list(html: str, source: str) -> list:
    soup = BeautifulSoup(html, "lxml")
    rows = soup.select("table tbody tr")
    items = []
    if not rows:
        return items

    for r in rows[1:]:  # skip header
        tds = r.find_all("td")
        if len(tds) < 3:
            continue
        a = tds[0].find("a")
        if not a:
            continue
        title = norm(a.get_text())
        href = a.get("href", "")
        m = re.search(r"queryContent\((\d+)\)", href)
        if m:
            content_id = m.group(1)
            url = f"https://www.zfgjj.cn/tjgjjcms/mainSitePc/regalutiondetail.jsp?id={content_id}"
        else:
            url = href

        date_s = norm(tds[2].get_text())
        d = parse_ymd(date_s)
        items.append({"title": mark_income_related(title), "url": url, "date": d, "source": source})

    return items


def crawl_tianjin_gjj_policy(current_time: datetime | None = None, max_pages: int = 5) -> list:
    """抓取天津公积金网两个政策栏目：本市规范性文件、中心文件库（近24小时）

    返回格式：[{title, url, date, source}]
    """
    now = current_time or now_cn()
    since = now - timedelta(days=1)
    results = []
    s = make_session()

    for source_name, base in CATEGORY_URLS.items():
        for p in range(1, max_pages + 1):
            if p == 1:
                url = base
            else:
                url = f"{base}&pn={p}"
            html = ""
            try:
                html = _fetch_html_requests(s, url)
            except Exception as e:
                # 某些站点存在 TLS 握手问题，先尝试浏览器渲染回退
                try:
                    html = _fetch_html_playwright(url)
                except Exception as browser_error:
                    try:
                        html = _fetch_html_requests(s, url.replace("https://", "http://"))
                    except Exception:
                        print(f"[Tianjin GJJ] fetch error {url}: {e}")
                        print(f"[Tianjin GJJ] browser fallback error {url}: {browser_error}")
                        break

            items = _parse_list(html, source_name)
            if not items:
                # 站点有时首次请求拿到的是空壳页面，尝试浏览器再抓一次
                try:
                    html = _fetch_html_playwright(url)
                    items = _parse_list(html, source_name)
                except Exception:
                    pass

            if not items:
                break

            # keep only near-24h items (site provides date only -> use date granularity)
            keep = []
            for it in items:
                if not it.get("date"):
                    continue
                if it["date"] >= since.date():
                    keep.append(it)

            results.extend(keep)

            # 如果某页全部都早于窗口，则可以停止翻页该栏目
            if len(keep) < len(items):
                break

    # remove duplicates by url
    seen = set()
    uniq = []
    for it in results:
        u = it.get("url")
        if not u or u in seen:
            continue
        seen.add(u)
        uniq.append(it)

    return uniq
