# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from urllib.parse import urljoin

from .common import make_session, now_cn, norm, mark_income_related


HLJ_HRSS_POLICY_PAGE = "https://hrss.hlj.gov.cn/hrss/c111748/zfxxgk.shtml?tab=gkzc"
HLJ_HRSS_API_BASE = "https://hrss.hlj.gov.cn"
HLJ_HRSS_WEBSITE_CODE = "hrss"

# 政策 > 行政规范性文件 / 其它文件
HLJ_POLICY_CHANNELS = {
    "heilongjiang_gfxwj": "99011f14464e422f836056b9b64832a9",
    "heilongjiang_qtwj": "38e74d9e3e374405bd898921ce22f70c",
}


def _to_dt_from_ms(ms) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=now_cn().tzinfo)
    except Exception:
        return None


def crawl_heilongjiang_hrss_policy() -> list[dict]:
    """
    抓取黑龙江省人社厅“政策”板块中的“行政规范性文件”“其它文件”。
    仅保留近24小时发布的条目。
    """
    now = now_cn()
    since = now - timedelta(hours=24)

    s = make_session()

    # 先访问入口页，获取会话与反爬上下文
    try:
        s.get(HLJ_HRSS_POLICY_PAGE, timeout=20)
    except Exception as e:
        print(f"[HeilongjiangHRSS] warmup failed: {e}")

    results = []
    seen = set()

    for source, channel_id in HLJ_POLICY_CHANNELS.items():
        page = 1
        while True:
            api = (
                f"{HLJ_HRSS_API_BASE}/common/search/{channel_id}"
                f"?_isAgg=true&_isJson=true&_pageSize=15&_template=index"
                f"&_rangeTimeGte=&_channelName=&page={page}&websiteCodeName={HLJ_HRSS_WEBSITE_CODE}"
            )

            try:
                r = s.get(api, timeout=20, headers={"Referer": HLJ_HRSS_POLICY_PAGE})
                data = r.json()
            except Exception as e:
                print(f"[HeilongjiangHRSS] fetch failed({source}, p{page}): {e}")
                break

            rows = ((data or {}).get("data") or {}).get("results") or []
            if not rows:
                break

            hit_older = False
            for row in rows:
                if not isinstance(row, dict):
                    continue

                title = norm(str(row.get("title") or ""))
                href = norm(str(row.get("url") or ""))
                dt = _to_dt_from_ms(row.get("publishedTime"))

                if not title or not href or not dt:
                    continue
                if dt > now:
                    continue
                if dt < since:
                    hit_older = True
                    continue

                url = urljoin(HLJ_HRSS_API_BASE, href)
                if url in seen:
                    continue
                seen.add(url)

                title = mark_income_related(title)
                results.append(
                    {
                        "title": title,
                        "url": url,
                        "date": dt.date(),
                        "source": source,
                    }
                )

            # 列表按发布时间倒序，命中旧数据后可提前停止翻页
            if hit_older:
                break
            page += 1

    return results
