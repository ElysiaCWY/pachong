# -*- coding: utf-8 -*-
import re
import time
from datetime import datetime, timedelta, date
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from .common import norm, now_cn, target_prev_workday

# ===================== InfoQ 产业新闻 =====================
# 用户给出的 URL 是 https://www.infoq.cn/topic/%20industrynews
# 实际可能是 https://www.infoq.cn/topic/industry-news 或 /news 下的板块
# 我们优先尝试 https://www.infoq.cn/topic/industry-news，如果失败则尝试 /news
INFOQ_TOPIC_URL = "https://www.infoq.cn/topic/industry-news"
INFOQ_NEWS_URL = "https://www.infoq.cn/news"

def parse_infoq_time(text: str) -> datetime:
    """
    解析 InfoQ 时间格式：
    1. "5 小时前", "19 小时前"
    2. "03-20" (今年)
    3. "2025-12-31"
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
        
        # 绝对日期 MM-DD
        m_md = re.match(r"(\d{1,2})-(\d{1,2})", text)
        if m_md and len(text) <= 5: # 简单过滤，避免匹配到 2026-03-20
            year = now.year
            month = int(m_md.group(1))
            day = int(m_md.group(2))
            # 如果是未来的日期（比如跨年），可能需要减一年？通常 InfoQ 显示当年
            return datetime(year, month, day)
            
        # 绝对日期 YYYY-MM-DD
        m_ymd = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
        if m_ymd:
             return datetime(int(m_ymd.group(1)), int(m_ymd.group(2)), int(m_ymd.group(3)))
             
    except Exception:
        pass
    return None

def crawl_infoq(target_date=None):
    """
    抓取 InfoQ 产业新闻。
    如果 target_date 为空，默认抓取近 24 小时或昨天的数据。
    """
    if target_date is None:
        target_date = target_prev_workday(now_cn().date())
        
    results = []
    seen = set()
    
    print(f"[InfoQ] Start crawling... Target Date: {target_date}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            # 设置较大的 viewport 以加载更多
            viewport={"width": 1280, "height": 1024}
        )
        page = context.new_page()
        
        try:
            # 优先尝试 topic 页面 (https://www.infoq.cn/topic/industry-news)
            target_url = "https://www.infoq.cn/topic/industry-news"
            print(f"  -> Visiting {target_url}")
            
            # 使用 try/except 捕获可能的加载错误
            try:
                page.goto(target_url, wait_until="networkidle", timeout=30000)
            except Exception as e:
                print(f"  -> Page load timed out or failed: {e}")
            
            time.sleep(3) # 等待 React 渲染
            
            # 检查是否有 404
            content = page.content()
            if "404" in page.title() or "Not Found" in content or "无法提取" in content:
                print("  -> Topic page seemingly empty/404, check selectors or fallback")
                # 尝试点击 "更多产业动态" 如果在 /news 页面
                # 这里简单处理：如果在 topic 没找到内容，就去 /news 找
                # 但首先检查当前页面有没有 article-item
                pass

            # 滚动加载
            for _ in range(3):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(1.5)
            
            # 使用 Playwright 定位器提取
            # InfoQ 列表项通用结构: .article-item (或者 h6 > a)
            # 我们先拿所有的链接，再找旁边的日期
            
            # 查找所有文章标题链接
            # 常见选择器：.com-article-title, h6 a, h4 a
            links = page.locator("a.com-article-title").all()
            if not links:
                links = page.locator("h6 a").all()
            if not links:
                links = page.locator(".article-item .title a").all()
                
            print(f"  -> Found {len(links)} article links via locator")
            
            for link in links:
                title = norm(link.inner_text())
                href = link.get_attribute("href")
                if not href or not title:
                    continue
                
                full_url = urljoin(INFOQ_NEWS_URL, href)
                if full_url in seen:
                    continue
                
                # 寻找日期
                # 日期通常在父容器内的 .date, .time, .author-date 等
                # 我们向上找 container
                # 使用 XPath 找附近的日期文本
                # 比如：../../..//span[contains(@class, 'date')]
                
                # 在 Playwright 中，我们可以从 ele 获取父级 handle
                # 但 python api 比较麻烦，我们可以直接 evaluate JS 或者用 text search
                
                # 简单起见，从 inner_text 所在的 block 获取整个 text
                # 然后解析日期
                
                # 向上找 3 层 div/li
                try:
                    container = link.locator("xpath=./../../..")
                    if container.count() > 0:
                        txt = container.first.inner_text()
                        # 解析 txt 中的日期
                        # 逐行或逐词解析
                        found_date = None
                        
                        # 优先匹配 regex
                        # YYYY-MM-DD
                        m = re.search(r"(\d{4}-\d{2}-\d{2})", txt)
                        if m:
                            found_date = datetime.strptime(m.group(1), "%Y-%m-%d").date()
                        else:
                            # MM-DD
                            m2 = re.search(r"(\d{1,2})-(\d{1,2})", txt)
                            if m2:
                                found_date = date(now_cn().year, int(m2.group(1)), int(m2.group(2)))
                            else:
                                # 相对时间
                                if "分钟前" in txt:
                                    found_date = now_cn().date()
                                elif "小时前" in txt:
                                    # 如果是 23 小时前，可能是昨天
                                    # 为了简便，如果是小时前，大部分是今天，少部分是昨天
                                    # 解析小时数
                                    mh = re.search(r"(\d+)\s*小时前", txt)
                                    if mh:
                                        hours = int(mh.group(1))
                                        dt = now_cn() - timedelta(hours=hours)
                                        found_date = dt.date()
                                elif "天前" in txt:
                                    md = re.search(r"(\d+)\s*天前", txt)
                                    if md:
                                        days = int(md.group(1))
                                        dt = now_cn() - timedelta(days=days)
                                        found_date = dt.date()
                                        
                        if found_date:
                            if found_date == target_date:
                                seen.add(full_url)
                                results.append({
                                    "title": title, # 可以加上 【产业】 前缀如果确认是产业新闻
                                    "url": full_url,
                                    "date": found_date, # 这里只存 date 对象用于排序
                                    "source": "infoq"
                                })
                except Exception as e:
                    pass

        except Exception as e:
            print(f"[InfoQ] Error: {e}")
        finally:
            browser.close()
            
    # 按时间倒序
    # results 中的 date 是 date 对象，为了统一格式 specific datetime sorting irrelevant if only date
    # 但 common.py 可能需要 datetime?
    # 转换为 datetime for sorting consistency
    final_results = []
    for r in results:
        # Convert date back to datetime (midnight)
        dt = datetime(r['date'].year, r['date'].month, r['date'].day)
        r['date'] = dt
        final_results.append(r)
        
    final_results.sort(key=lambda x: x["date"], reverse=True)
    return final_results
