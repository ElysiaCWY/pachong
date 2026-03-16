# -*- coding: utf-8 -*-
import os
import re
from datetime import date
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from .common import make_session, norm, target_prev_workday, now_cn, parse_ymd

# ===================== 国家税务总局：政策法规 =====================
# “最新文件”列表页
CHINATAX_POLICY_URL = "https://fgk.chinatax.gov.cn/zcfgk/c100006/listflfg.html"

def crawl_chinatax_policy():
    """
    抓取国家税务总局-政策法规库-最新文件
    仅抓昨天（或指定日期）发布的。
    """
    override = parse_ymd(os.getenv("CHINATAX_TARGET_DATE"))
    today = now_cn().date()
    # 默认抓 yesterday
    target = override or target_prev_workday(today)

    s = make_session()
    try:
        r = s.get(CHINATAX_POLICY_URL, timeout=15)
        r.encoding = "utf-8"
        html = r.text
    except Exception as e:
        print(f"Chinatax Policy fetch fail: {e}")
        return []

    soup = BeautifulSoup(html, "html.parser")
    results = []
    seen = set()

    # 观察页面文本: 标题...文号...日期
    # 可能结构: <div class="list">...</div>
    # 策略：查找所有日期节点，向前找对应的标题链接
    
    # 匹配 YYYY-MM-DD
    # 文本中日期显然是单独的节点或在一行末尾
    
    # 方案1：遍历所有文本节点找日期
    # 方案2：遍历所有链接，看其后是否跟随日期
    
    # 我们先尝试遍历所有包含 href 的 a 标签，
    # 检查其父级或兄弟节点的文本中是否包含 target 日期
    
    # 也有可能是在 table > tr > td 中
    
    candidates = soup.find_all(string=re.compile(r"\d{4}-\d{2}-\d{2}"))
    
    target_str = target.strftime("%Y-%m-%d")
    
    for text_node in candidates:
        if target_str not in text_node:
            continue
            
        # 找到了今天的日期节点
        # 往上找 container (例如 li, tr, div)
        container = text_node.parent
        found_link = None
        
        # 向上查找 3 层，在每一层里找 a 标签
        for _ in range(3):
            if not container:
                break
            # 找该容器下的主要链接 (排除翻页等无关链接)
            # 通常标题链接字数较多
            links = container.find_all("a", href=True)
            for a in links:
                txt = norm(a.get_text())
                if len(txt) > 4: # 假设标题至少4个字
                    found_link = a
                    break
            if found_link:
                break
            container = container.parent
            
        if found_link:
            href = found_link["href"]
            url = urljoin(CHINATAX_POLICY_URL, href)
            title = norm(found_link.get_text())
            
            if url not in seen:
                seen.add(url)
                results.append({"title": title, "url": url, "date": target})
                
    return results
