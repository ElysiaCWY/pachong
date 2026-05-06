# -*- coding: utf-8 -*-
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from news_crawlers.common import make_session, norm, parse_ymd, mark_income_related

BASE = "https://www.hrbgjj.org.cn"
INDEX = "https://www.hrbgjj.org.cn/zxwj/index.jhtml"
PAGE_FMT = "https://www.hrbgjj.org.cn/zxwj/index_{page}.jhtml"
ARTICLE_RE = re.compile(r"/zxwj/\d+\.jhtml$")


def _extract_items_from_soup(soup):
    items = []
    # 匹配 /zxwj/xxxx.jhtml 的链接
    for a in soup.find_all("a", href=ARTICLE_RE):
        try:
            title = norm(a.get_text())
            if not title:
                continue

            href = a.get("href")
            full = urljoin(BASE, href)

            # 尝试从父节点文本中抽取日期（常见展示为：<a>title</a> 2025-12-24）
            parent_text = norm(a.parent.get_text(" ")) if a.parent else ""
            m = re.search(r"(\d{4}-\d{2}-\d{2})", parent_text)

            # 尝试更多邻近查找：next_siblings / find_next
            if not m:
                # 检查紧随其后的文本节点或元素
                for ns in a.next_siblings:
                    try:
                        txt = ns if isinstance(ns, str) else (ns.get_text(" ") if hasattr(ns, "get_text") else "")
                        txt = norm(txt)
                        m = re.search(r"(\d{4}-\d{2}-\d{2})", txt)
                        if m:
                            break
                    except Exception:
                        continue

            if not m:
                # 在后续元素中查找日期文本（限定搜索深度）
                nxt = a.find_next(string=re.compile(r"\d{4}-\d{2}-\d{2}"))
                if nxt:
                    m = re.search(r"(\d{4}-\d{2}-\d{2})", str(nxt))

            dt = parse_ymd(m.group(1)) if m else None

            items.append({"title": mark_income_related(title), "url": full, "date": dt, "source": "hrb_gjj_zxwj"})
        except Exception:
            continue
    return items


def crawl_hrbgjj_zxwj(current_time=None, max_pages: int = 6):
    """抓取哈尔滨公积金中心文件列表，返回条目列表，条目字典包含 title/url/date/source"""
    session = make_session()
    out = []

    for p in range(1, max_pages + 1):
        try:
            url = INDEX if p == 1 else PAGE_FMT.format(page=p)
            resp = session.get(url, timeout=15)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding
            soup = BeautifulSoup(resp.text, "lxml")

            items = _extract_items_from_soup(soup)
            if not items:
                # 如果当前页没有符合的条目，继续下一页以防分页结构不同
                continue

            # 合并去重（简单按 url）
            seen = set(it["url"] for it in out)
            for it in items:
                if it["url"] in seen:
                    continue
                out.append(it)
                seen.add(it["url"])

        except Exception as e:
            print(f"[Harbin GJJ Crawl Error] {e}")
            break

    return out
