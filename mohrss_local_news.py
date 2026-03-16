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
import time  # 补上缺失的 time 模块导入
from news_crawlers.common import now_cn, md_item_with_detail, target_prev_workday, fetch_url_content
from news_crawlers.dingtalk import dingtalk_send_markdown
from news_crawlers.sina import crawl_sina_target_day
from news_crawlers.hrloo import crawl_hrloo
from news_crawlers.tophr import crawl_tophr
from news_crawlers.chinatax import crawl_chinatax
from news_crawlers.chinatax_policy import crawl_chinatax_policy
from news_crawlers.mohrss import crawl_mohrss_target_day, crawl_mohrss_policy_target_day
from news_crawlers.ai_crawler import filter_by_ai_batch, call_ai_summary
from news_crawlers.beijing_rsj import crawl_beijing_rsj_policy
from news_crawlers.tianjin_hrss import crawl_tianjin_hrss_policy
from news_crawlers.hebei_rst import crawl_hebei_rst_policy
from news_crawlers.shanxi_rst import crawl_shanxi_rst_policy
from news_crawlers.neimenggu_rst import crawl_neimenggu_rst_policy


# ===================== Markdown 组装（最终样式） =====================

def build_enterprise_block(run_hrloo: bool, run_sina: bool, run_tophr: bool = True) -> str:
    lines = ["## 财经新闻"]
    idx = 1
    
    # 先三茅要点
    if run_hrloo:
        try:
            hr_item, hr_titles, hr_content_map = crawl_hrloo()
            if hr_item and hr_titles:
                for t in hr_titles:
                    # 三茅要点详情统一跳到当天三茅日报文章页（同一个 url）
                    # 尝试获取该标题对应的摘要内容
                    summary = hr_content_map.get(t, "")
                    # 如果内容太长，也可以考虑再让 AI 润色一下，或者直接截取
                    if len(summary) > 150:
                        summary = summary[:145] + "..."
                        
                    lines.append(md_item_with_detail(idx, t, hr_item["url"], summary))
                    idx += 1
            else:
                lines.append("（未发现当天的三茅日报）")
        except Exception as e:
            lines.append(f"（三茅抓取错误: {e}）")

    # 再新浪财经 + 第一资源
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
        
    if not enterprise_items and (run_sina or (run_tophr and run_tophr_env)):
        lines.append("（AI 筛选后暂无相关高价值新闻）")
    
    # ===== AI 摘要生成 =====
    for it in enterprise_items:
        print(f"正在生成摘要: {it['title']} ...")
        content = fetch_url_content(it['url'])
        if not content:
            print(f"  -> 内容抓取为空，跳过摘要")
            it['summary'] = ""
            continue
            
        summary = call_ai_summary(content)
        if summary:
            print(f"  -> 摘要生成成功 (len={len(summary)}): {summary[:20]}...")
            it['summary'] = summary
        else:
            print(f"  -> 摘要生成失败/为空")
            it['summary'] = ""
            
        time.sleep(1) # 避免太快

    for it in enterprise_items:
        lines.append(md_item_with_detail(idx, it["title"], it["url"], it.get("summary")))
        idx += 1

    # 使用双换行以确保在移动端钉钉能正确分段显示
    return "\n\n".join(lines).strip()

def build_policy_block(run_mohrss: bool) -> str:
    lines = ["## 人社动态 & 政策"]

    # 周末不抓
    now = now_cn()
    wd = now.weekday()
    if wd >= 5:
        lines.append("（周末不抓取）")
        return "\n\n".join(lines).strip()

    hit_dynamics = []
    hit_policies = []
    chinatax_policies = []
    beijing_policies = []
    tianjin_policies = []
    hebei_policies = []
    shanxi_policies = []
    neimenggu_policies = []
    
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

    # 汇总判断
    all_empty = (
        not hit_dynamics and 
        not hit_policies and 
        not chinatax_policies and 
        not beijing_policies and 
        not tianjin_policies and 
        not hebei_policies and
        not shanxi_policies and
        not neimenggu_policies
    )

    if all_empty:
        if not run_mohrss and not run_chinatax_env:
             lines.append("（本次未启用）")
        else:
             lines.append("（无更新或本次未命中）")
        return "\n\n".join(lines).strip()

    idx = 1
    # 先展示政策文件（人社部 + 税务总局 + 京津冀 + 山西 + 内蒙古）
    has_policy = bool(hit_policies or chinatax_policies or beijing_policies or tianjin_policies or hebei_policies or shanxi_policies or neimenggu_policies)
    
    if has_policy:
        lines.append("**政策文件**")
        for it in hit_policies:
            lines.append(md_item_with_detail(idx, it["title"], it["url"]))
            idx += 1
        for it in chinatax_policies:
            title = f"【税务总局】{it['title']}"
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in beijing_policies:
            title = f"【北京】{it['title']}"
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in tianjin_policies:
            title = f"【天津】{it['title']}"
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in hebei_policies:
            title = f"【河北】{it['title']}"
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in shanxi_policies:
            title = f"【山西】{it['title']}"
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in neimenggu_policies:
            title = f"【内蒙古】{it['title']}"
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1

    # 再展示人社部的地方动态

    # 再展示人社部的地方动态
    if hit_dynamics:
        if has_policy:
            lines.append("")
        lines.append("**地方动态**")
        for it in hit_dynamics:
            lines.append(md_item_with_detail(idx, it["title"], it["url"]))
            idx += 1

    return "\n\n".join(lines).strip()

def build_markdown(enterprise_block: str, policy_block: str) -> str:
    mmdd = now_cn().strftime("%m-%d")
    md = [f"## {mmdd} 每日简报", ""]
    md.append(enterprise_block or "## 财经新闻\n（本次未生成）")
    md.append("\n---\n")
    md.append(policy_block or "## 人社动态\n（本次未生成）")
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

    enterprise_block = build_enterprise_block(run_hrloo, run_sina)
    policy_block = build_policy_block(run_mohrss)

    md = build_markdown(enterprise_block, policy_block)

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
