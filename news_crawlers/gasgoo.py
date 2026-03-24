# -*- coding: utf-8 -*-
import re
from urllib.parse import urljoin
from datetime import datetime, date
from bs4 import BeautifulSoup
from .common import make_session, norm, now_cn, target_prev_workday

# ===================== 盖世汽车 =====================
GASGOO_URLS = [
    ("产业", "https://auto.gasgoo.com/industry/C-108"),
    ("车企", "https://auto.gasgoo.com/automaker/C-109"),
]

def parse_gasgoo_time(text: str) -> datetime:
    """
    从文本中提取时间，格式形如: 2026-03-24 12:09:27
    """
    if not text:
        return None
    # 匹配: 2026-03-24 12:09:27
    m = re.search(r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})", text)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
        except:
            pass
    return None

def crawl_gasgoo(target_date: date = None) -> list[dict]:
    """
    抓取盖世汽车指定板块的新闻（产业 + 车企）。
    返回: List[Dict] [{'title':..., 'url':..., 'date':..., 'section':...}]
    """
    if target_date is None:
        target_date = target_prev_workday(now_cn().date())

    results = []
    seen_urls = set()

    sess = make_session()
    sess.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://auto.gasgoo.com/"
    })

    print(f"[Gasgoo] 开始抓取，目标日期: {target_date}")

    for section_name, url in GASGOO_URLS:
        print(f"  -> 正在抓取板块: {section_name} ({url})")
        try:
            resp = sess.get(url, timeout=15)
            # 自动识别编码（通常是 utf-8）
            resp.encoding = resp.apparent_encoding
            
            soup = BeautifulSoup(resp.text, "html.parser")
            
            dls = soup.find_all("dl")
            count_section = 0
            
            for dl in dls:
                h2 = dl.find("h2", class_="bigtitle")
                if not h2:
                    continue
                
                a_tag = h2.find("a")
                if not a_tag:
                    continue
                
                title = norm(a_tag.get_text())
                href = a_tag.get("href")
                full_url = urljoin(url, href)
                
                if full_url in seen_urls:
                    continue
                
                # 提取时间
                dl_text = dl.get_text(separator=" ", strip=True)
                pub_time = parse_gasgoo_time(dl_text)
                
                if not pub_time:
                    continue
                
                pub_date = pub_time.date()
                
                if pub_date == target_date:
                    seen_urls.add(full_url)
                    results.append({
                        "title": f"【{section_name}】{title}",
                        "url": full_url,
                        "date": pub_time,
                        "section": section_name,
                        "source": "gasgoo"
                    })
                    count_section += 1
                elif pub_date < target_date:
                    pass
            
            print(f"     已抓取 {count_section} 条符合条件的文章")

        except Exception as e:
            print(f"  [Error] {section_name} 抓取失败: {e}")

    # 按时间倒序排序
    results.sort(key=lambda x: x["date"], reverse=True)
    return results
