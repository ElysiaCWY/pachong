# -*- coding: utf-8 -*-
import os
import re
from datetime import date
from urllib.parse import urljoin
from bs4 import BeautifulSoup, Tag
from .common import make_session, norm, parse_ymd, now_cn

# ===================== 人力资讯：HRLoo（三茅） =====================

CN_TITLE_DATE = re.compile(r"[（(]\s*(20\d{2})\s*[年\-/.]\s*(\d{1,2})\s*[月\-/.]\s*(\d{1,2})\s*[)）]")
SECTION_BLACKLIST = {"AI最前沿", "热点速递", "行业观察", "最新动态"}
CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩"

def date_from_bracket_title(text: str):
    m = CN_TITLE_DATE.search(text or "")
    if not m:
        return None
    try:
        y, mo, d = int(m[1]), int(m[2]), int(m[3])
        return date(y, mo, d)
    except Exception:
        return None

def looks_like_numbered(text: str) -> bool:
    return bool(re.match(r"^\s*[（(]?\s*\d{1,2}\s*[)）]?\s*[、.．]\s*\S+", text or ""))

def strip_leading_num(t: str) -> str:
    t = re.sub(r"^\s*[（(]?\s*\d{1,2}\s*[)）]?\s*[、.．]\s*", "", t)
    t = re.sub(r"^\s*[" + CIRCLED + r"]\s*", "", t)
    t = re.sub(r"^\s*[０-９]+\s*[、.．]\s*", "", t)
    return t.strip()

class HRLooCrawler:
    def __init__(self):
        self.session = make_session()
        self.results = []

        override = parse_ymd(os.getenv("HR_TARGET_DATE"))
        self.target_date = override or now_cn().date()

        self.daily_title_pat = re.compile(r"三茅日[报報]")
        self.sources = [u.strip() for u in os.getenv(
            "SRC_HRLOO_URLS",
            "https://www.hrloo.com/,https://www.hrloo.com/news/hr"
        ).split(",") if u.strip()]

    def crawl(self):
        for base in self.sources:
            if self._crawl_source(base):
                break

    def _crawl_source(self, base):
        try:
            r = self.session.get(base, timeout=20)
        except Exception:
            return False
        if r.status_code != 200:
            return False

        soup = BeautifulSoup(r.text, "html.parser")

        items = soup.select("div.dwxfd-list-items div.dwxfd-list-content-left")
        if items:
            for div in items:
                a = div.find("a", href=True)
                if not a:
                    continue
                title_text = norm(a.get_text())
                if not self.daily_title_pat.search(title_text):
                    continue
                t2 = date_from_bracket_title(title_text)
                if t2 and t2 != self.target_date:
                    continue
                abs_url = urljoin(base, a["href"])
                if self._try_detail(abs_url):
                    return True

        links = []
        for a in soup.select("a[href*='/news/']"):
            href = a.get("href", "")
            if not re.search(r"/news/\d+\.html$", href):
                continue
            text = norm(a.get_text())
            if not self.daily_title_pat.search(text):
                continue
            t2 = date_from_bracket_title(text)
            if t2 and t2 != self.target_date:
                continue
            links.append(urljoin(base, href))

        seen = set()
        for u in links:
            if u in seen:
                continue
            seen.add(u)
            if self._try_detail(u):
                return True
        return False

    def _try_detail(self, abs_url):
        _, titles, page_title, content_map = self._fetch_detail_clean(abs_url)
        if not page_title or not self.daily_title_pat.search(page_title):
            return False

        t3 = date_from_bracket_title(page_title)
        if t3 and t3 != self.target_date:
            return False
        if not titles:
            return False

        self.results.append({
            "title": page_title,
            "url": abs_url,
            "titles": titles,
            "content_map": content_map  # 新增
        })
        return True

    def _extract_h2_titles(self, root: Tag):
        out = []
        for h2 in root.select("h2.style-h2, h2[class*='style-h2']"):
            text = norm(h2.get_text())
            if not text:
                continue
            text = strip_leading_num(text)
            text = re.split(r"[（(]", text)[0].strip()
            if not text:
                continue
            if text in SECTION_BLACKLIST:
                continue
            if len(text) >= 4:
                out.append(text)

        seen, final = set(), []
        for t in out:
            if t not in seen:
                seen.add(t)
                final.append(t)
        return final

    def _extract_numbered_titles(self, root: Tag):
        out = []
        for p in root.find_all(["p", "h2", "h3", "div", "span", "li"]):
            text = norm(p.get_text())
            if looks_like_numbered(text):
                text = strip_leading_num(text)
                text = re.split(r"[（(]", text)[0].strip()
                if text and len(text) >= 4 and text not in SECTION_BLACKLIST:
                    out.append(text)
        seen, final = set(), []
        for t in out:
            if t not in seen:
                seen.add(t)
                final.append(t)
        return final

    def _pick_container(self, soup: BeautifulSoup):
        selectors = [
            ".content-con.fn-wenda-detail-infomation",
            ".fn-wenda-detail-infomation",
            ".content-con.hr-rich-text.fn-wenda-detail-infomation",
            ".hr-rich-text.fn-wenda-detail-infomation",
            ".fn-hr-rich-text.custom-style-warp",
            ".custom-style-warp",
            ".content-wrap-con",
        ]
        for sel in selectors:
            node = soup.select_one(sel)
            if node:
                return node
        return soup

    def _fetch_detail_clean(self, url):
        try:
            r = self.session.get(url, timeout=(6, 20))
            if r.status_code != 200:
                return None, [], ""
            r.encoding = r.apparent_encoding or "utf-8"
            soup = BeautifulSoup(r.text, "html.parser")

            h1 = soup.find("h1")
            page_title = norm(h1.get_text()) if h1 else ""
            if not page_title:
                title_tag = soup.find(["h1", "h2"])
                page_title = norm(title_tag.get_text()) if title_tag else ""

            container = self._pick_container(soup)
            # 提取内容：为每个标题提取后续正文
            content_map = {}
            
            # 尝试提取标题列表
            titles = self._extract_h2_titles(container)
            if not titles:
                titles = self._extract_numbered_titles(container)

            # 新增：尝试根据 titles 提取每个 title 对应的下方文本
            if titles:
                # full_text = container.get_text(separator="\n")
                # lines = [l.strip() for l in full_text.split("\n") if l.strip()]
                
                for i, t in enumerate(titles):
                    # 简单逻辑：找到该标题在 lines 中的位置，取到下一个标题之前的内容
                    # 注意：这只是个模糊匹配，因为标题在 正文 里可能带序号
                    # 优化：在 DOM 中找最近邻
                    next_t = titles[i+1] if i + 1 < len(titles) else None
                    content_map[t] = self._find_content_for_title(container, t, next_t)

            return None, titles, page_title, content_map
        except Exception:
            return None, [], "", {}

    def _find_content_for_title(self, container: Tag, title_text: str, next_title_text: str = None) -> str:
        """
        简单尝试：在 container 中找到包含 title_text 的标签，然后往下找 p 标签的内容，直到遇到下一个疑似标题
        """
        # 1. 找到所有由 extract_xxx 识别出的标题节点
        # 这里为了简化，我们仅在 text 中定位。
        # 更好的做法是遍历 container 的子节点。
        
        # 简化版：直接搜包含该文本的元素
        target = None
        for elem in container.find_all(["p", "h2", "h3", "div", "span", "strong", "b"]):
            if title_text in elem.get_text():
                target = elem
                break
        
        if not target:
            return ""

        # 收集后续兄弟节点的文本
        content = []
        curr = target.next_sibling
        while curr:
            if isinstance(curr, Tag):
                txt = norm(curr.get_text())
                
                # 如果明确传入了下一个标题，且文本大概匹配，则停止
                if next_title_text and len(next_title_text) > 2 and next_title_text in txt:
                    break
                
                # 如果遇到下一个类似标题的特征（比如 h2, 或者带序号的 strong），则停止
                if looks_like_numbered(txt) and len(txt) < 30: # 疑似下一个标题
                     break

                if txt:
                    content.append(txt)
            curr = curr.next_sibling
            if len(content) > 10: # 只要抓几段即可，不需要全文，但也稍微多一点给 AI
                break
        
        # 过滤掉不需要的固定结尾文案
        result = "".join(content)
        result = result.replace("注：文中内容整合于网络。如有侵权，请留言小编删除。", "")
        return result

def crawl_hrloo():
    c = HRLooCrawler()
    c.crawl()
    if not c.results:
        return None, [], {}
    it = c.results[0]
    return it, it.get("titles", []), it.get("content_map", {})
