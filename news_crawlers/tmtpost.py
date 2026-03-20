# -*- coding: utf-8 -*-
import re
import time
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from .common import norm, now_cn

# ===================== 钛媒体：最新 =====================
TMTPOST_NEW_URL = "https://www.tmtpost.com/new"
MAX_SCROLLS = 30  # 滚动次数上限，防止无限循环

def parse_tmtpost_time(text: str) -> datetime:
    """
    解析钛媒体时间格式：
    1. "10分钟前", "1小时前"
    2. "2026-03-19 12:34"
    3. "昨天 12:34"
    """
    text = (text or "").strip().replace("·", "").strip()
    if not text:
        return None
    
    now = now_cn().replace(tzinfo=None)
    
    try:
        # 1. 相对时间
        if "分钟前" in text:
            mins = int(re.search(r"(\d+)", text).group(1))
            return now - timedelta(minutes=mins)
        if "小时前" in text:
            hours = int(re.search(r"(\d+)", text).group(1))
            return now - timedelta(hours=hours)
        if "昨天" in text:
            # 昨天 HH:MM
            m = re.search(r"(\d{1,2}):(\d{2})", text)
            if m:
                yesterday = now.date() - timedelta(days=1)
                return datetime(yesterday.year, yesterday.month, yesterday.day, int(m.group(1)), int(m.group(2)))
            # 仅显示昨天
            return datetime(now.year, now.month, now.day) - timedelta(days=1)
        if "天前" in text:
             days = int(re.search(r"(\d+)", text).group(1))
             return now - timedelta(days=days)

        # 2. 绝对时间
        # 2026-03-19 15:30
        if re.match(r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}", text):
            return datetime.strptime(text, "%Y-%m-%d %H:%M")
            
    except Exception:
        pass
    return None

def crawl_tmtpost():
    """
    抓取钛媒体-最新文章。
    使用 Playwright 模拟滚动加载，直到覆盖24小时。
    """
    results = []
    seen = set()
    now = now_cn().replace(tzinfo=None)
    cutoff_time = now - timedelta(hours=24)
    
    print(f"[TMTPost] Start crawling with Playwright...")
    
    with sync_playwright() as p:
        # 启动浏览器
        browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        page = browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        
        try:
            page.goto(TMTPOST_NEW_URL, wait_until="domcontentloaded", timeout=60000)
            time.sleep(2) # 等待初始加载
            
            last_item_count = 0
            
            for scroll in range(MAX_SCROLLS):
                # 获取当前所有文章
                # 钛媒体的列表项一般在 ._right (或者 .post-item 等，需视具体渲染情况而定)
                # 根据之前的分析，class 是 _right
                
                # 滚动到底部
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                # 等待加载
                try:
                    # 等待新的列表项出现，或者只是sleep
                    time.sleep(1.5)
                except Exception:
                    pass
                
                # 解析当前页面内容
                content = page.content()
                soup = BeautifulSoup(content, "html.parser")
                items = soup.find_all("div", class_="_right")
                current_count = len(items)
                
                print(f"[TMTPost] Scroll {scroll+1}/{MAX_SCROLLS}, items found: {current_count}")
                
                if current_count == last_item_count:
                    # 没有新内容加载
                    print("[TMTPost] No new items loaded. Stopping.")
                    break
                last_item_count = current_count
                
                # 检查最后一篇文章的时间
                # 优化：不需要每次都解析所有，只解析最后几个以判断是否达到cutoff
                # 但为了准确收集，我们最后统一解析或者分批解析
                # 这里为了简单，检查最后5个的时间，如果都早于cutoff，则停止
                
                stop_signal = False
                check_items = items[-10:] if len(items) > 10 else items
                old_count = 0
                
                for item in check_items:
                    time_tag = item.find(class_="newTime") # 或 _time
                    if time_tag:
                        pub_time = parse_tmtpost_time(time_tag.get_text())
                        if pub_time and pub_time < cutoff_time:
                            old_count += 1
                
                if old_count >= 3: # 只要有几篇已经是旧闻了，就认为到了
                    print("[TMTPost] Reached 24h limit. Stopping.")
                    stop_signal = True
                    break
            
            # 最终解析所有收集到的HTML
            # 注意：items 变量在循环外可能是旧的，需重新获取最新soup
            final_content = page.content()
            soup = BeautifulSoup(final_content, "html.parser")
            all_items = soup.find_all("div", class_="_right")
            
            print(f"[TMTPost] Parsing {len(all_items)} total items...")
            
            for item in all_items:
                try:
                    # 标题
                    t_tag = item.find("a", class_="_tit")
                    if not t_tag:
                        continue
                    
                    title = norm(t_tag.get_text())
                    href = t_tag.get("href", "").strip()
                    
                    if not href.startswith("http"):
                        href = "https://www.tmtpost.com" + href
                        
                    # 过滤视频 /video/
                    if "/video/" in href or "/watch/" in href:
                        continue
                        
                    if href in seen:
                        continue
                        
                    # 时间
                    time_tag = item.find(class_=lambda x: x and ("newTime" in x or "_time" in x))
                    pub_time = None
                    if time_tag:
                        pub_time = parse_tmtpost_time(time_tag.get_text())
                    
                    if pub_time:
                        if pub_time >= cutoff_time:
                            seen.add(href)
                            results.append({
                                "title": title,
                                "url": href,
                                "source": "tmtpost",
                                "time": pub_time.strftime("%Y-%m-%d %H:%M")
                            })
                except Exception as e:
                    continue

        except Exception as e:
            print(f"[TMTPost] Error: {e}")
        finally:
            browser.close()

    print(f"[TMTPost] Collected {len(results)} items within 24h.")
    return results
