# -*- coding: utf-8 -*-
import re
import time
from datetime import datetime, timedelta, date
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from .common import norm, now_cn, target_prev_workday

# ===================== 创业邦 (Cyzone) =====================
CYZONE_News_URL = "https://www.cyzone.cn/channel/news"

def parse_cyzone_time(text: str) -> datetime:
    """
    解析创业邦时间格式：
    1. "5分钟前", "3小时前"
    2. "昨天 10:20"
    3. "2025-01-01"
    """
    text = (text or "").strip()
    if not text:
        return None
    
    now = now_cn().replace(tzinfo=None)
    
    try:
        # 相对时间
        if "分钟前" in text:
            m = re.search(r"(\d+)\s*分钟前", text)
            if m:
                return now - timedelta(minutes=int(m.group(1)))
        if "小时前" in text:
            m = re.search(r"(\d+)\s*小时前", text)
            if m:
                return now - timedelta(hours=int(m.group(1)))
        if "天前" in text:
            m = re.search(r"(\d+)\s*天前", text)
            if m:
                return now - timedelta(days=int(m.group(1)))
        
        # 处理 "昨天"
        if "昨天" in text:
            return now - timedelta(days=1)
            
        # 绝对日期 YYYY-MM-DD
        m_ymd = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
        if m_ymd:
             return datetime(int(m_ymd.group(1)), int(m_ymd.group(2)), int(m_ymd.group(3)))
             
    except Exception:
        pass
    return None

def crawl_cyzone(target_date=None):
    """
    抓取创业邦 (Cyzone) 资讯频道。
    默认抓取 target_date (通常是昨天/今天) 的新闻。
    """
    if target_date is None:
        target_date = target_prev_workday(now_cn().date())
        
    results = []
    seen = set()
    
    print(f"[Cyzone] Start crawling... Target Date: {target_date}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 1024}
        )
        page = context.new_page()
        
        try:
            print(f"  -> Visiting {CYZONE_News_URL}")
            page.goto(CYZONE_News_URL, wait_until="networkidle", timeout=45000)
            
            # 等待内容加载，如果没有 article-item，可能是别的类名，我们多试几个
            # 常见： .article-item, .list-item, .item
            try:
                page.wait_for_selector(".article-item, .list-doc, .item-title", timeout=5000)
            except:
                pass

            # 滚动加载
            for _ in range(3):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(1.5)
            
            # 尝试获取列表 items
            # 分析结构: 通常是 ul > li 或者 div.list > div.item
            # 我们可以直接查找所有带有 title 的链接
            
            # 方案 A: 查找所有文章链接容器
            # 假设结构是 container -> (title, time)
            # 通过 evaluate 拿到更多信息
            
            items = page.locator(".article-item").all()
            if not items:
                items = page.locator(".list-doc").all() # 尝试另一个可能的类名
            
            # 如果还是找不到，尝试通过 link class 找
            if not items:
                print("  -> No standard items found, trying generic link search")
                links = page.locator("a.item-title").all()
                # 这种情况下很难找到对应的时间，除非通过 parent
                for link in links:
                    title = norm(link.inner_text())
                    href = link.get_attribute("href")
                    # 尝试找时间：通常在 parent 的 sibling 或 child
                    # 这里简化处理：如果是 generic 模式，可能无法精确过滤时间，
                    # 除非进去看，或者假设它是最近的。
                    # 为了准确性，我们 try to find time nearby using XPath
                    try:
                        # 假设结构: 
                        # <div class="item">
                        #   <div class="info"> <a class="title">...</a> </div>
                        #   <div class="time">...</div>
                        # </div>
                        # xpath: ./following::span[contains(@class, 'time')]
                        # 或者 ./../..//span[contains(@class, 'time')]
                        pass
                    except:
                        pass
            
            print(f"  -> Found {len(items)} potential items")
            
            for item in items:
                try:
                    # 获取标题
                    title_el = item.locator(".item-title")
                    if title_el.count() == 0:
                        title_el = item.locator("a.title")
                    
                    if title_el.count() == 0:
                        continue
                        
                    title = norm(title_el.first.inner_text())
                    href = title_el.first.get_attribute("href") or ""
                    full_url = urljoin(CYZONE_News_URL, href)
                    
                    if full_url in seen:
                        continue
                        
                    # 获取时间
                    time_txt = ""
                    # 尝试常见的时间 class
                    time_el = item.locator(".time")
                    if time_el.count() == 0:
                        time_el = item.locator(".date")
                    
                    if time_el.count() > 0:
                        time_txt = time_el.first.inner_text()
                    else:
                        # 尝试在这个 item 的文本里找类似时间的 pattern
                        full_txt = item.inner_text()
                        # 简单的正则提取
                        m = re.search(r"(\d+分钟前|\d+小时前|昨天|\d{4}-\d{2}-\d{2})", full_txt)
                        if m:
                            time_txt = m.group(1)
                            
                    dt = parse_cyzone_time(time_txt)
                    
                    if dt and dt.date() == target_date:
                        seen.add(full_url)
                        results.append({
                            "title": title,
                            "url": full_url,
                            "date": dt,
                            "source": "cyzone"
                        })
                        
                except Exception as e:
                    continue

        except Exception as e:
            print(f"[Cyzone] Error: {e}")
        finally:
            browser.close()
            
    # 按时间倒序
    results.sort(key=lambda x: x["date"], reverse=True)
    return results
