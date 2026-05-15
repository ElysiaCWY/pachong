# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, date
import re
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from .common import make_session, mark_income_related, now_cn, norm, parse_ymd


JZSGJJ_POLICY_INDEX = "https://jzsgjj.cn/newslistnew.jsp?listid=25&navid=4"


def _normalize_url(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme == "http" and parts.netloc.endswith(":80"):
        return urlunsplit((parts.scheme, parts.netloc[:-3], parts.path, parts.query, parts.fragment))
    if parts.scheme == "https" and parts.netloc.endswith(":443"):
        return urlunsplit((parts.scheme, parts.netloc[:-4], parts.path, parts.query, parts.fragment))
    return url


def _page_url(page_no: int) -> str:
    if page_no <= 1:
        return JZSGJJ_POLICY_INDEX
    return f"{JZSGJJ_POLICY_INDEX}&page={page_no}"


def _extract_total_pages(html: str) -> int:
    # 尝试从分页文本中提取总页数，例如 “共 5 页” 或链接到最后一页的 href
    if not html:
        return 1
    m = re.search(r"共\s*(\d+)\s*页", html)
    if m:
        try:
            return max(1, int(m.group(1)))
        except Exception:
            pass
    # fallback: try to find last page link like &page=N
    m2 = re.findall(r"[?&]page=(\d+)", html)
    if m2:
        try:
            return max(1, max(map(int, m2)))
        except Exception:
            return 1
    return 1


def _extract_page_items(page_url: str, html: str, now: datetime, since_date: date) -> tuple[list[dict], bool]:
    soup = BeautifulSoup(html or "", "html.parser")
    results: list[dict] = []
    seen: set[str] = set()
    has_older_item = False

    # 常见的列表容器
    candidates = []
    candidates.extend(soup.find_all("li"))
    # 也尝试查找带链接的 a 标签作为回退
    if not candidates:
        candidates = soup.find_all("a")

    for node in candidates:
        a_tag = None
        if node.name == "li":
            a_tag = node.select_one("a[href]")
            text = norm(node.get_text(" ", strip=True))
        else:
            a_tag = node if node.name == "a" and node.get("href") else None
            text = norm(node.get_text(" ", strip=True))

        if not a_tag:
            continue

        # 尝试通过多种格式提取日期
        article_date = None
        m = re.search(r"(20\d{2}[-/\.]\d{1,2}[-/\.]\d{1,2})", text)
        if m:
            article_date = parse_ymd(m.group(1))
        if not article_date:
            m_cn = re.search(r"(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日", text)
            if m_cn:
                try:
                    y = int(m_cn.group(1)); mm = int(m_cn.group(2)); d = int(m_cn.group(3))
                    article_date = date(y, mm, d)
                except Exception:
                    article_date = None

        if not article_date:
            # 还有可能是 yyyy/mm/dd 或 yyyy.mm.dd
            m2 = re.search(r"(20\d{2})[\-/\.](\d{1,2})[\-/\.](\d{1,2})", text)
            if m2:
                try:
                    y = int(m2.group(1)); mm = int(m2.group(2)); d = int(m2.group(3))
                    article_date = date(y, mm, d)
                except Exception:
                    article_date = None

        if not article_date:
            continue

        if article_date > now.date():
            continue
        if article_date < since_date:
            has_older_item = True
            continue

        title = norm(a_tag.get("title") or a_tag.get_text(" ", strip=True))
        href = norm(a_tag.get("href") or "")
        if not title or not href:
            continue

        full_url = _normalize_url(urljoin(page_url, href))
        if full_url in seen:
            continue
        seen.add(full_url)

        results.append(
            {
                "title": mark_income_related(title),
                "url": full_url,
                "date": article_date,
                "source": "jzsgjj_policy",
            }
        )

    return results, has_older_item


def crawl_jzsgjj_policy(current_time: datetime | None = None, max_pages: int = 3) -> list[dict]:
    """抓取晋中（jzsgjj.cn）政策/法规列表，仅保留近24小时内条目。"""
    now = current_time or now_cn()
    since_date = (now - timedelta(hours=24)).date()

    session = make_session()
    results: list[dict] = []
    seen_urls: set[str] = set()

    try:
        first_resp = session.get(JZSGJJ_POLICY_INDEX, timeout=20)
        first_resp.encoding = first_resp.apparent_encoding or "utf-8"
        if first_resp.status_code != 200:
            print(f"[JZSGJJ] HTTP Error {first_resp.status_code}")
            return []
    except Exception as e:
        print(f"[JZSGJJ] fetch failed(page=1): {e}")
        return []

    total_pages = min(_extract_total_pages(first_resp.text), max_pages)

    for page_no in range(1, total_pages + 1):
        if page_no == 1:
            page_url = JZSGJJ_POLICY_INDEX
            html = first_resp.text
        else:
            page_url = _page_url(page_no)
            try:
                resp = session.get(page_url, timeout=20)
                resp.encoding = resp.apparent_encoding or "utf-8"
                if resp.status_code != 200:
                    print(f"[JZSGJJ] HTTP Error {resp.status_code} @ page={page_no}")
                    break
                html = resp.text
            except Exception as e:
                print(f"[JZSGJJ] fetch failed(page={page_no}): {e}")
                break

        page_items, has_older_item = _extract_page_items(page_url, html, now, since_date)
        if not page_items and page_no == 1:
            break

        for item in page_items:
            if item["url"] in seen_urls:
                continue
            seen_urls.add(item["url"])
            results.append(item)

        if has_older_item:
            break

    results.sort(key=lambda x: (x["date"], x["title"]), reverse=True)
    return results
