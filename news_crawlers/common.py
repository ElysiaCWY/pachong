# -*- coding: utf-8 -*-
import os
import re
import time
import ssl
import json
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, date
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    from zoneinfo import ZoneInfo
except Exception:
    from backports.zoneinfo import ZoneInfo

# ===================== 通用 =====================
TZ = ZoneInfo(os.getenv("HR_TZ", "Asia/Shanghai"))

def now_cn() -> datetime:
    return datetime.now(TZ)

def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())

def truncate_text(s: str, max_len: int = 55) -> str:
    s = norm(s)
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"

def safe_md_text(s: str) -> str:
    # 防止标题里出现 [] 影响 markdown
    # 额外清理可能导致排版错乱的特殊符号/不可见字符
    s = (s or "").replace("[", "【").replace("]", "】")
    # 移除零宽字符等（可选）
    return s

def parse_ymd(s: str):
    s = (s or "").strip()
    if not s:
        return None
    try:
        y, m, d = map(int, re.split(r"[-/\.]", s))
        return date(y, m, d)
    except Exception:
        return None

def target_prev_workday(today: date) -> date:
    """
    周一：抓上周五（today - 3）
    周二~周五：抓昨天（today - 1）
    周末：不运行（由 main 控制）
    """
    if today.weekday() == 0:
        return today - timedelta(days=3)
    return today - timedelta(days=1)

def fetch_url_content(url: str) -> str:
    """
    简单抓取网页主要文本内容（去除 HTML 标签、script、style）。
    """
    if not url:
        return ""
    try:
        s = make_session()
        resp = s.get(url, timeout=15)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding  # 自动识别编码

        soup = BeautifulSoup(resp.text, "lxml")
        
        # 移除无关标签
        for s_tag in soup(["script", "style", "header", "footer", "nav", "aside", "noscript"]):
            s_tag.extract()
            
        # 提取可见文本
        text = soup.get_text(separator="\n")
        
        # 清理空白行
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        content = "\n".join(lines)
        
        # 如果太长，截取前 3000 字给 AI 即可（节省 token 且足够摘要）
        return content[:3000]
    except Exception as e:
        print(f"[Fetch Content Error] {url}: {e}")
        return ""

def md_item_with_detail(i: int, title: str, url: str, summary: str = None) -> str:
    """
    每条输出： 1. 标题  👉 [详情](url)
    如果有摘要，则换行显示引用的摘要。
    """
    # 强制截断为 50 字以内，避免过多换行
    title = safe_md_text(truncate_text(title, 50))
    line = f"{i}. {title} [详情]({url})"
    if summary:
        # 使用 Markdown 引用语法显示摘要，注意双换行以防吞行，以及全角冒号
        line += f"\n> AI摘要：{summary}"
    return line

class LegacyTLSAdapter(HTTPAdapter):
    def init_poolmanager(self, *a, **kw):
        ctx = ssl.create_default_context()
        if hasattr(ssl, "OP_LEGACY_SERVER_CONNECT"):
            ctx.options |= ssl.OP_LEGACY_SERVER_CONNECT
        kw["ssl_context"] = ctx
        return super().init_poolmanager(*a, **kw)

def make_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9"
    })
    r = Retry(total=3, backoff_factor=0.6, status_forcelist=[500, 502, 503, 504])
    s.mount("https://", LegacyTLSAdapter(max_retries=r))
    return s
