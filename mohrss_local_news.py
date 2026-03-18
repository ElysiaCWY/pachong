# -*- coding: utf-8 -*-
"""
每日简报（钉钉友好最终版）
- 企业新闻：三茅日报要点（当天） + 新浪财经（周一抓上周五，其他工作日抓昨天）合并输出，统一连续编号
- 地方政策：人社部-人社动态（周一抓上周五，周二~周五抓昨天；周末不抓）

展示要求（按你最新要求）：
1) 不要底部“查看详细”
2) 每条后面都要一个 [详情](url)（蓝字可点）
3) 标题不做整段超链接（避免花眼），只让“详情”蓝字可点
4) 企业新闻里：先三茅要点，再财经；编号统一连续
5) 地方政策单独一块，单独编号从 1 开始

核心代码已拆分至 news_crawlers/ 目录。
"""

import os
import json
import time  
import re
from datetime import date, timedelta
from news_crawlers.common import now_cn, md_item_with_detail, target_prev_workday, fetch_url_content
from news_crawlers.dingtalk import dingtalk_send_markdown
from news_crawlers.sina import crawl_sina_target_day
from news_crawlers.hrloo import crawl_hrloo
from news_crawlers.tophr import crawl_tophr
from news_crawlers.chinatax import crawl_chinatax
from news_crawlers.chinatax_policy import crawl_chinatax_policy
from news_crawlers.mohrss import crawl_mohrss_target_day, crawl_mohrss_policy_target_day
from news_crawlers.ai_crawler import (
    filter_by_ai_batch,
    call_ai_summary,
    call_ai_filter,
    call_ai_daily_insight,
    call_ai_behavior_similarity_hits,
)
from news_crawlers.beijing_rsj import crawl_beijing_rsj_policy
from news_crawlers.tianjin_hrss import crawl_tianjin_hrss_policy
from news_crawlers.hebei_rst import crawl_hebei_rst_policy
from news_crawlers.shanxi_rst import crawl_shanxi_rst_policy
from news_crawlers.neimenggu_rst import crawl_neimenggu_rst_policy
from news_crawlers.yicai_hongguan import crawl_yicai_hongguan
from news_crawlers.clssn_rlzy import crawl_clssn_rlzy
from news_crawlers.hrbrand_news import crawl_hrbrand_news
from news_crawlers.hrvalue_kuai import crawl_hrvalue_kuai
from news_crawlers.hrvalue_policy import crawl_hrvalue_policy


# ===================== Markdown 组装（最终样式） =====================

INSIGHT_SKIP_TOKEN = "NO_INSIGHT"


def clean_yicai_summary(summary: str) -> str:
    """去掉一财摘要末尾的字数统计，如（149字）/（约149字）。"""
    if not summary:
        return summary
    return re.sub(r"\s*[（(](?:约\s*)?\d+\s*字[）)]\s*$", "", summary).strip()


def load_recent_history(history_file: str, days: int = 90) -> list[dict]:
    if not os.path.exists(history_file):
        return []

    cutoff = now_cn().date() - timedelta(days=days)
    results = []

    try:
        with open(history_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except Exception:
                    continue

                d = item.get("date", "")
                title = item.get("title", "")
                if not d or not title:
                    continue

                try:
                    d_obj = date.fromisoformat(d)
                except Exception:
                    continue

                if d_obj >= cutoff:
                    results.append(item)
    except Exception as e:
        print(f"[Insight] 读取历史文件失败: {e}")
        return []

    return results


def append_history_items(history_file: str, run_date: str, items: list[dict]):
    if not items:
        return

    existing_keys = set()
    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        item = json.loads(line)
                    except Exception:
                        continue
                    key = (item.get("date", ""), item.get("category", ""), item.get("title", ""))
                    existing_keys.add(key)
        except Exception as e:
            print(f"[Insight] 读取去重信息失败: {e}")

    try:
        with open(history_file, "a", encoding="utf-8") as f:
            for it in items:
                title = (it.get("title") or "").strip()
                if not title:
                    continue

                rec = {
                    "date": run_date,
                    "category": it.get("category", "unknown"),
                    "title": title,
                    "summary": (it.get("summary") or "").strip(),
                    "url": (it.get("url") or "").strip(),
                }
                key = (rec["date"], rec["category"], rec["title"])
                if key in existing_keys:
                    continue

                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                existing_keys.add(key)
    except Exception as e:
        print(f"[Insight] 写入历史文件失败: {e}")


def build_enterprise_block(run_hrloo: bool, run_sina: bool, run_tophr: bool = True) -> tuple[str, list]:
    lines = ["## 人力新闻"]
    idx = 1
    enterprise_items_all = [] # 收集所有合规的新闻，用于后续 AI 分析
    
    # 先三茅要点
    if run_hrloo:
        try:
            hr_item, hr_titles, hr_content_map = crawl_hrloo()
            if hr_item and hr_titles:
                # 增加 AI 筛选逻辑
                print(f"正在筛选三茅新闻 ({len(hr_titles)} 条)...")
                keep_flags = call_ai_filter(hr_titles)

                for i, t in enumerate(hr_titles):
                    # 如果 AI 判定无需保留，则跳过
                    if i < len(keep_flags) and not keep_flags[i]:
                        print(f"  -> [AI Filter] 筛掉三茅: {t}")
                        continue

                    # 三茅要点详情统一跳到当天三茅日报文章页（同一个 url）
                    # 尝试获取该标题对应的摘要内容
                    raw_content = hr_content_map.get(t, "")
                    
                    # 使用 AI 进行摘要，只保留重要语句
                    summary = ""
                    if raw_content:
                        # 如果内容过短，直接使用；否则调用 AI
                        if len(raw_content) < 100:
                            summary = raw_content
                        else:
                            ai_sum = call_ai_summary(raw_content)
                            summary = ai_sum if ai_sum else raw_content[:150] + "..."
                    
                    lines.append(md_item_with_detail(idx, t, hr_item["url"], summary))
                    enterprise_items_all.append({"title": t, "summary": summary, "url": hr_item["url"]})
                    idx += 1
            else:
                lines.append("（未发现当天的三茅日报）")
        except Exception as e:
            lines.append(f"（三茅抓取错误: {e}）")

    # 再新浪财经 + 第一资源 + 一财大政 + 劳动保障网人力资源 + HRbrand品牌动态 + HR价值网快讯
    enterprise_items = []
    
    if run_sina:
        try:
            _, sina_list = crawl_sina_target_day()
            # 统一格式化为 dict
            for dt, title, url in sina_list:
                enterprise_items.append({"title": title, "url": url, "source": "sina"})
        except Exception as e:
            print(f"Sina fetch error: {e}")
            
    # 第一资源 (TOPHR)
    run_tophr_env = (os.getenv("RUN_TOPHR", "1") != "0")
    if run_tophr and run_tophr_env:
        try:
            tophr_list = crawl_tophr()
            for it in tophr_list:
                it["source"] = "tophr"
                enterprise_items.append(it)
        except Exception as e:
            print(f"TopHR error: {e}")

    # 第一财经大政
    run_yicai_env = (os.getenv("RUN_YICAI_HONGGUAN", "1") != "0")
    if run_yicai_env:
        try:
            yicai_list = crawl_yicai_hongguan()
            for it in yicai_list:
                it["source"] = "yicai_hongguan"
                enterprise_items.append(it)
        except Exception as e:
            print(f"Yicai Hongguan error: {e}")

    # 中国劳动保障新闻网 - 人力资源（近24小时）
    run_clssn_env = (os.getenv("RUN_CLSSN_RLZY", "1") != "0")
    if run_clssn_env:
        try:
            clssn_list = crawl_clssn_rlzy()
            for it in clssn_list:
                it["source"] = "clssn_rlzy"
                enterprise_items.append(it)
        except Exception as e:
            print(f"CLSSN RLZY error: {e}")

    # HRbrand - 品牌动态
    run_hrbrand_env = (os.getenv("RUN_HRBRAND_NEWS", "1") != "0")
    if run_hrbrand_env:
        try:
            hrbrand_list = crawl_hrbrand_news()
            for it in hrbrand_list:
                it["source"] = "hrbrand_news"
                enterprise_items.append(it)
        except Exception as e:
            print(f"HRbrand News error: {e}")

    # HR价值网 - 快讯（近24小时）
    run_hrvalue_kuai_env = (os.getenv("RUN_HRVALUE_KUAI", "1") != "0")
    if run_hrvalue_kuai_env:
        try:
            hrvalue_kuai_list = crawl_hrvalue_kuai()
            for it in hrvalue_kuai_list:
                it["source"] = "hrvalue_kuai"
                enterprise_items.append(it)
        except Exception as e:
            print(f"HRValue Kuai error: {e}")

    # 国家税务总局 (Chinatax)
    run_chinatax_env = (os.getenv("RUN_CHINATAX", "1") != "0")
    if run_chinatax_env:
        try:
            chinatax_list = crawl_chinatax()
            for it in chinatax_list:
                it["source"] = "chinatax"
                enterprise_items.append(it)
        except Exception as e:
            print(f"Chinatax error: {e}")

    # ===== AI 批量筛选 =====
    if enterprise_items:
        enterprise_items = filter_by_ai_batch(enterprise_items)
        
    if not enterprise_items and (run_sina or (run_tophr and run_tophr_env) or run_yicai_env or run_clssn_env or run_hrbrand_env or run_hrvalue_kuai_env):
        lines.append("（AI 筛选后暂无相关高价值新闻）")
    
    # ===== AI 摘要生成 =====
    for it in enterprise_items:
        print(f"正在生成摘要: {it['title']} ...")
        content = it.get("raw_content") or fetch_url_content(it['url'])
        if not content:
            print(f"  -> 内容抓取为空，跳过摘要")
            it['summary'] = ""
            continue
            
        summary = call_ai_summary(content)
        if summary:
            print(f"  -> 摘要生成成功 (len={len(summary)}): {summary[:20]}...")
            if it.get("source") == "yicai_hongguan":
                summary = clean_yicai_summary(summary)
            it['summary'] = summary
        else:
            print(f"  -> 摘要生成失败/为空")
            it['summary'] = ""
            
        time.sleep(1) # 避免太快

    for it in enterprise_items:
        # 将这些新闻也加入到汇总列表
        enterprise_items_all.append(it)
        lines.append(md_item_with_detail(idx, it["title"], it["url"], it.get("summary")))
        idx += 1

    # 使用双换行以确保在移动端钉钉能正确分段显示
    return "\n\n".join(lines).strip(), enterprise_items_all

def build_policy_block(run_mohrss: bool) -> tuple[str, list]:
    lines = ["## 人社动态 & 政策"]
    policy_items_all = [] # 收集所有政策标题，用于后续 AI 分析

    # 周末不抓
    now = now_cn()
    wd = now.weekday()
    if wd >= 5:
        lines.append("（周末不抓取）")
        return "\n\n".join(lines).strip(), []

    hit_dynamics = []
    hit_policies = []
    chinatax_policies = []
    beijing_policies = []
    tianjin_policies = []
    hebei_policies = []
    shanxi_policies = []
    neimenggu_policies = []
    hrvalue_policies = []
    
    # 1. 人社部
    if run_mohrss:
        try:
            _, _, hit_dynamics = crawl_mohrss_target_day()
            _, _, hit_policies = crawl_mohrss_policy_target_day()
        except Exception as e:
            print(f"MOHRSS fetch error: {e}")
            lines.append(f"（人社部抓取错误: {e}）")

    # 2. 国家税务总局 - 政策法规
    run_chinatax_env = (os.getenv("RUN_CHINATAX", "1") != "0")
    if run_chinatax_env:
        try:
            chinatax_policies = crawl_chinatax_policy()
        except Exception as e:
            print(f"Chinatax policy fetch error: {e}")

    # 3. 京津冀政策 + 山西 + 内蒙古
    try:
        target_date = target_prev_workday(now.date())
        # print(f"Fetching local policies for {target_date} ...")
        beijing_policies = crawl_beijing_rsj_policy(target_date)
        tianjin_policies = crawl_tianjin_hrss_policy(target_date)
        hebei_policies = crawl_hebei_rst_policy(target_date)
        shanxi_policies = crawl_shanxi_rst_policy(target_date)
        neimenggu_policies = crawl_neimenggu_rst_policy(target_date)
    except Exception as e:
        print(f"JJJ/SX/NM Policy error: {e}")

    # 4. HR价值网 - 政策
    run_hrvalue_policy_env = (os.getenv("RUN_HRVALUE_POLICY", "1") != "0")
    if run_hrvalue_policy_env:
        try:
            hrvalue_policies = crawl_hrvalue_policy()
        except Exception as e:
            print(f"HRValue policy fetch error: {e}")

    # 汇总判断
    all_empty = (
        not hit_dynamics and 
        not hit_policies and 
        not chinatax_policies and 
        not beijing_policies and 
        not tianjin_policies and 
        not hebei_policies and
        not shanxi_policies and
        not neimenggu_policies and
        not hrvalue_policies
    )

    if all_empty:
        if not run_mohrss and not run_chinatax_env:
             lines.append("（本次未启用）")
        else:
             lines.append("（无更新或本次未命中）")
        return "\n\n".join(lines).strip(), []

    # 仅筛选人社动态，政策文件不筛选
    if hit_dynamics:
        before_count = len(hit_dynamics)
        hit_dynamics = filter_by_ai_batch(hit_dynamics)
        print(f"[AI Filter][人社部动态] 共 {before_count} 条，保留 {len(hit_dynamics)} 条")

    idx = 1
    # 先展示政策文件（人社部 + 税务总局 + 京津冀 + 山西 + 内蒙古）
    has_policy = bool(
        hit_policies
        or chinatax_policies
        or beijing_policies
        or tianjin_policies
        or hebei_policies
        or shanxi_policies
        or neimenggu_policies
        or hrvalue_policies
    )

    if not has_policy and not hit_dynamics:
        lines.append("（AI 筛选后暂无相关人社动态）")
        return "\n\n".join(lines).strip(), []
    
    if has_policy:
        lines.append("**政策文件**")
        for it in hit_policies:
            policy_items_all.append(it)
            lines.append(md_item_with_detail(idx, it["title"], it["url"]))
            idx += 1
        for it in chinatax_policies:
            title = f"【税务总局】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in beijing_policies:
            title = f"【北京】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in tianjin_policies:
            title = f"【天津】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in hebei_policies:
            title = f"【河北】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in shanxi_policies:
            title = f"【山西】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in neimenggu_policies:
            title = f"【内蒙古】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in hrvalue_policies:
            title = f"【HR价值网】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1

    # 再展示人社部的地方动态
    if hit_dynamics:
        if has_policy:
            lines.append("")
        lines.append("**地方动态**")
        for it in hit_dynamics:
            policy_items_all.append(it)
            lines.append(md_item_with_detail(idx, it["title"], it["url"]))
            idx += 1

    return "\n\n".join(lines).strip(), policy_items_all

def build_markdown(enterprise_block: str, policy_block: str, insight_block: str = "") -> str:
    mmdd = now_cn().strftime("%m-%d")
    md = [f"## {mmdd} 每日简报", ""]
    md.append(enterprise_block or "## 财经新闻\n（本次未生成）")
    md.append("\n---\n")
    md.append(policy_block or "## 人社动态\n（本次未生成）")

    if insight_block and insight_block.strip() and insight_block.strip() != INSIGHT_SKIP_TOKEN:
        md.append("\n---\n")
        md.append("## 每日洞察分析")
        md.append(insight_block.strip())

    return "\n".join(md).strip() + "\n"


def main():
    # 周末不运行（你规则里周六/周日不抓）
    wd = now_cn().weekday()
    if wd >= 5:
        print("[INFO] 周末不运行")
        return

    run_hrloo = (os.getenv("RUN_HRLOO", "1").strip() != "0")
    run_sina = (os.getenv("RUN_SINA", "1").strip() != "0")
    run_mohrss = (os.getenv("RUN_MOHRSS", "1").strip() != "0")
    history_file = os.getenv("INSIGHT_HISTORY_FILE", "insight_history.jsonl")

    enterprise_block, enterprise_items = build_enterprise_block(run_hrloo, run_sina)
    policy_block, policy_items = build_policy_block(run_mohrss)

    insight_input_items = []
    for it in enterprise_items:
        insight_input_items.append(
            {
                "category": "enterprise",
                "title": it.get("title", ""),
                "summary": it.get("summary", ""),
                "url": it.get("url", ""),
            }
        )
    for it in policy_items:
        insight_input_items.append(
            {
                "category": "policy",
                "title": it.get("title", ""),
                "summary": it.get("summary", ""),
                "url": it.get("url", ""),
            }
        )

    insight_block = ""
    if insight_input_items:
        recent_history = load_recent_history(history_file, days=90)
        enterprise_today_items = [it for it in insight_input_items if it.get("category") == "enterprise"]
        enterprise_today_count = len(enterprise_today_items)
        similar_hits = call_ai_behavior_similarity_hits(enterprise_today_items, recent_history)

        print(f"[Insight] 触发检查: 当日高价值新闻={enterprise_today_count}, 历史相似命中={similar_hits}")

        # 最小触发阈值：当日至少一条高价值新闻 + 历史命中至少 2 条相似事件
        if enterprise_today_count >= 1 and similar_hits >= 2:
            try:
                insight_block = call_ai_daily_insight(insight_input_items, recent_history)
            except Exception as e:
                print(f"[Insight] AI 洞察生成失败: {e}")
                insight_block = ""
        else:
            insight_block = INSIGHT_SKIP_TOKEN

    md = build_markdown(enterprise_block, policy_block, insight_block)

    run_date = now_cn().strftime("%Y-%m-%d")
    append_history_items(history_file, run_date, insight_input_items)

    out_file = os.getenv("OUT_FILE", "daily_all.md")
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(md)

    title = f"{now_cn().strftime('%m-%d')} 每日简报"
    
    # 尝试发送，如果失败打印日志但不抛出异常中断
    try:
        results = dingtalk_send_markdown(title, md)
        for it in results:
            print(f"✅ DingTalk OK ({it['group']}):", it["resp"])
    except RuntimeError as e:
        # 可能是没有配置钉钉，或者网络问题
        print(f"⚠️ DingTalk Warning: {e}")
    except Exception as e:
        print(f"❌ DingTalk Error: {e}")
        
    print("✅ wrote:", out_file)


if __name__ == "__main__":
    main()
