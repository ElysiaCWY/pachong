# -*- coding: utf-8 -*-
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from .common import make_session, norm, now_cn

# ===================== 快消品网：多板块 =====================
FMCG_CHINA_BASE = "http://www.fmcgchina.com"

# 板块列表
SECTIONS = [
    ("dj", "快消品-独家"),
    ("yp", "快消品-饮品"),
    ("sp", "快消品-食品"),
    ("rh", "快消品-日化"),
    ("ls", "快消品-零售"),
    ("ds", "快消品-电商"),
    ("zh", "快消品-综合"),
]

def parse_fmcg_date(text: str):
    """
    解析日期 YYYY-MM-DD
    """
    if not text:
        return None
    m = re.search(r"(\d{4}-\d{2}-\d{2})", text)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y-%m-%d")
        except:
            return None
    return None

def crawl_fmcg_china():
    """
    抓取快消品网多个板块的文章。
    仅抓取24小时内（或当天/昨天）的文章。
    """
    s = make_session()
    all_results = []
    seen_urls = set()
    
    # 时间过滤：最近 24 小时
    now = now_cn().replace(tzinfo=None)
    cutoff = now - timedelta(hours=24)
    # 宽松模式：如果是今天的日期或昨天的日期，都保留
    today_date = now.date()
    yesterday_date = today_date - timedelta(days=1)

    for code, source_name in SECTIONS:
        url = f"{FMCG_CHINA_BASE}/{code}"
        try:
            # print(f"Fetching {source_name}: {url}")
            r = s.get(url, timeout=15)
            r.encoding = "utf-8" # 或者是 gbk/gb2312, 视实际情况，fetch_webpage 没显示乱码，可能是 utf-8
            if r.encoding == "ISO-8859-1":
                r.encoding = r.apparent_encoding
                
            soup = BeautifulSoup(r.text, "html.parser")
            
            # 查找列表项
            # 结构推测：标题 a 标签，附近有 date
            # 遍历所有 a 标签
            links = soup.find_all("a", href=True)
            
            for a in links:
                href = a["href"]
                # 链接必须包含 /newsinfo/
                if "/newsinfo/" not in href:
                    continue
                
                title = norm(a.get_text())
                if len(title) < 5:
                    continue
                    
                full_url = urljoin(url, href)
                if full_url in seen_urls:
                    continue
                
                # 找日期
                # 向上找容器
                found_date = None
                container = a.parent
                # 向上3层找日期
                for _ in range(3):
                    if not container:
                        break
                    # 在容器内找日期文本
                    # "2026-03-24"
                    txts = container.stripped_strings
                    for t in txts:
                        if t == title: continue
                        dt = parse_fmcg_date(t)
                        if dt:
                            found_date = dt
                            break
                    if found_date:
                        break
                    container = container.parent
                
                if not found_date:
                    continue
                
                # 时间过滤
                # 如果 found_date (00:00:00) >= cutoff (now-24h)，通常有效
                # 但如果 found_date 是昨天，cutoff 是昨天下午，则 found_date < cutoff (False)
                # 所以我们用日期判定：只要是今天或昨天发布的，都算
                
                pub_date = found_date.date()
                if pub_date < yesterday_date:
                    continue
                    
                seen_urls.add(full_url)
                all_results.append({
                    "title": title,
                    "url": full_url,
                    "published_at": found_date.strftime("%Y-%m-%d"),
                    "source": "fmcg_china", # 使用统一 source key, 或者 source_name
                    "section": source_name 
                })

        except Exception as e:
            print(f"FMCG China ({code}) error: {e}")
            continue

    # 按时间倒序
    all_results.sort(key=lambda x: x["published_at"], reverse=True)
    return all_results
