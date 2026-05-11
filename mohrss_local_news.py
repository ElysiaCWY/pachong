import os
import json
import time  
import re
import sys
from datetime import date, timedelta, datetime
from dotenv import load_dotenv
from news_crawlers.common import now_cn, md_item_with_detail, target_prev_workday, fetch_url_content, clean_yicai_summary, norm
from news_crawlers.log_utils import setup_logging
from news_crawlers.history_manager import (
    load_recent_history,
    append_history_items,
    filter_against_history,
    verify_history_items_written,
)
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
    call_ai_check_relevance,
    call_ai_shorten_title,
    call_ai_daily_insight,
    call_ai_behavior_similarity_hits,
    call_ai_industry_trend_impact_hit,
    call_ai_deduplicate,
    call_ai_industry_tag_with_web,
    call_ai_keep_max_impact_per_company,
)
from news_crawlers.beijing_rsj import crawl_beijing_rsj_policy
from news_crawlers.beijing_gjj import crawl_beijing_gjj_policy
from news_crawlers.chengdu_gjj import crawl_chengdu_gjj_policy
from news_crawlers.tianjin_hrss import crawl_tianjin_hrss_policy
from news_crawlers.guiyang_gjj import crawl_guiyang_gjj_policy
from news_crawlers.kunming_gjj import crawl_kunming_gjj_policy
from news_crawlers.tianjin_gjj import crawl_tianjin_gjj_policy
from news_crawlers.hebei_rst import crawl_hebei_rst_policy
from news_crawlers.shanxi_rst import crawl_shanxi_rst_policy
from news_crawlers.neimenggu_rst import crawl_neimenggu_rst_policy
from news_crawlers.jilin_hrss import crawl_jilin_hrss_policy
from news_crawlers.yicai_hongguan import crawl_yicai_hongguan
from news_crawlers.clssn_rlzy import crawl_clssn_rlzy
from news_crawlers.hrbrand_news import crawl_hrbrand_news
from news_crawlers.hrvalue_kuai import crawl_hrvalue_kuai
from news_crawlers.hrvalue_policy import crawl_hrvalue_policy
from news_crawlers.govcn_policy import crawl_govcn_policy
from news_crawlers.heilongjiang_hrss import crawl_heilongjiang_hrss_policy
from news_crawlers.liaoning_hrss import crawl_liaoning_hrss_policy
from news_crawlers.shanghai_hrss import crawl_shanghai_hrss_policy
from news_crawlers.shanghai_gjj import crawl_shanghai_gjj_policy
from news_crawlers.taiyuan_gjj import crawl_taiyuan_gjj_policy
from news_crawlers.shijiazhuang_gjj import crawl_shijiazhuang_gjj_policy
from news_crawlers.zhengzhou_gjj import crawl_zhengzhou_gjj_law
from news_crawlers.hefei_gjj import crawl_hefei_gjj_policy
from news_crawlers.shenyang_gjj import crawl_shenyang_gjj_policy
from news_crawlers.yqgjj import crawl_yqgjj_policy
from news_crawlers.hrbgjj import crawl_hrbgjj_zxwj
from news_crawlers.jlgjj import crawl_jlgjj_policy
from news_crawlers.nanjing_gjj import crawl_nanjing_gjj_tzgg
from news_crawlers.hangzhou_gjj import crawl_hangzhou_gjj_xzfg
from news_crawlers.fuzhou_gjj import crawl_fuzhou_gjj_zcfg
from news_crawlers.nanchang_gjj import crawl_nanchang_gjj_zcfg
from news_crawlers.qdgjj import crawl_qdgjj_zcjd
from news_crawlers.qhdgjj import crawl_qhdgjj_tzgg
from news_crawlers.handan_gjj import crawl_handan_gjj_policy
from news_crawlers.xingtai_gjj import crawl_xingtai_gjj_policy
from news_crawlers.baoding_gjj import crawl_baoding_gjj_zxwj
from news_crawlers.zjkgjj import crawl_zjkgjj_normative_files
from news_crawlers.chengde_gjj import crawl_chengde_gjj_announcement
from news_crawlers.cangzhou_gjj import crawl_cangzhou_gjj_announcement
from news_crawlers.lfzfgjj import crawl_lfzfgjj_announcement
from news_crawlers.tlzfgjj import crawl_tlzfgjj_tzgg
from news_crawlers.cfszfgjj import crawl_cfszfgjj_policy
from news_crawlers.ordos_gjj import crawl_ordos_gjj_zxgdw
from news_crawlers.hszfgjj import crawl_hszfgjj_policy_regulations
from news_crawlers.wuhan_gjj import crawl_wuhan_gjj_gfxwj
from news_crawlers.whsgjj import crawl_whsgjj_zxwj
from news_crawlers.xamzfgjj import crawl_xamzfgjj_zxwj
from news_crawlers.xlglgjj import crawl_xlglgjj_dfwj
from news_crawlers.alszfgjj import crawl_alszfgjj_policy
from news_crawlers.tsgjj import crawl_tsgjj_center
from news_crawlers.changsha_gjj import crawl_changsha_gjj_wzjd
from news_crawlers.guangzhou_gjj import crawl_guangzhou_gjj_policy
from news_crawlers.guilin_gjj import crawl_guilin_gjj_zxwj
from news_crawlers.lanzhou_gjj import crawl_lanzhou_gjj_policy
from news_crawlers.yinchuan_gjj import crawl_yinchuan_gjj_policy
from news_crawlers.jiangsu_hrss import crawl_jiangsu_hrss_policy
from news_crawlers.zhejiang_hrss import crawl_zhejiang_hrss_policy
from news_crawlers.anhui_hrss import crawl_anhui_hrss_policy
from news_crawlers.fujian_rst import crawl_fujian_rst_bbmwj
from news_crawlers.jiangxi_rst import crawl_jiangxi_rst_policy
from news_crawlers.shandong_hrss import crawl_shandong_hrss_policy
from news_crawlers.henan_hrss import crawl_henan_hrss_policy
from news_crawlers.hubei_rst import crawl_hubei_rst_policy
from news_crawlers.hunan_rst import crawl_hunan_rst_policy
from news_crawlers.guangdong_hrss import crawl_guangdong_hrss_policy
from news_crawlers.guangxi_rst import crawl_guangxi_rst_policy
from news_crawlers.hainan_hrss import crawl_hainan_hrss_policy
from news_crawlers.chongqing_hrss import crawl_chongqing_hrss_policy
from news_crawlers.cqgjj import crawl_cqgjj_gsgg
from news_crawlers.sichuan_rst import crawl_sichuan_rst_policy
from news_crawlers.guizhou_rst import crawl_guizhou_rst_policy
from news_crawlers.yunnan_hrss import crawl_yunnan_hrss_policy
from news_crawlers.xizang_hrss import crawl_xizang_hrss_policy
from news_crawlers.shaanxi_rst import crawl_shaanxi_rst_policy
from news_crawlers.gansu_rst import crawl_gansu_rst_policy
from news_crawlers.qinghai_rst import crawl_qinghai_rst_policy
from news_crawlers.xinjiang_rst import crawl_xinjiang_rst_policy
from news_crawlers.ningxia_hrss import crawl_ningxia_hrss_policy
from news_crawlers.hlbe_gjj import crawl_hlbe_gjj_policy
from news_crawlers.btgjj import crawl_btgjj_policy
from news_crawlers.caixin_companies import crawl_caixin_companies
from news_crawlers.jiemian_business import crawl_jiemian_business
from news_crawlers.thsi_unlisted import crawl_thsi_unlisted
from news_crawlers.cnfin_dj import crawl_cnfin_dj
from news_crawlers.tmtpost import crawl_tmtpost
from news_crawlers.fortune_cn import crawl_fortune_cn
from news_crawlers.vbdata import crawl_vbdata
from news_crawlers.fmcg_china import crawl_fmcg_china
from news_crawlers.gasgoo import crawl_gasgoo
from news_crawlers.infoq import crawl_infoq
from news_crawlers.cyzone import crawl_cyzone
from news_crawlers.huxiu import crawl_huxiu
from news_crawlers.jcgov import crawl_jcgov_policy
from news_crawlers.zf365 import crawl_zf365_tzgg
from news_crawlers.sxjz import crawl_sxjz_policy
from news_crawlers.yuncheng import crawl_yuncheng_policy
from news_crawlers.sxxz_xzgjj import crawl_sxxz_xzgjj_zxwj
from news_crawlers.lvliang import crawl_lvliang_policy
from news_crawlers.changzhi_gjj import crawl_changzhi_gjj_zxwj
from news_crawlers.cyzone import crawl_cyzone

load_dotenv()


# ===================== Markdown 组装（最终样式） =====================

INSIGHT_SKIP_TOKEN = "NO_INSIGHT"

INDUSTRY_TAG_RULES = [
    ("车企", ["汽车", "车企", "新能源车", "智能驾驶", "比亚迪", "长安", "吉利", "奇瑞", "长城", "上汽", "广汽", "一汽", "蔚来", "小鹏", "理想", "赛力斯", "特斯拉"]),
    ("AI", ["人工智能", "大模型", "AI", "AIGC", "智能体", "算力"]),
    ("半导体", ["半导体", "芯片", "晶圆", "EDA", "封测"]),
    ("互联网", ["互联网", "平台", "电商", "社交", "本地生活", "云服务", "SaaS"]),
    ("金融", ["银行", "保险", "券商", "基金", "信托", "金融科技", "支付"]),
    ("医药", ["医药", "医疗", "生物", "器械", "创新药", "医院", "药企"]),
    ("能源", ["能源", "光伏", "风电", "储能", "电池", "氢能", "石油", "天然气"]),
    ("消费", ["快消", "零售", "食品", "饮料", "日化", "美妆", "连锁"]),
    ("制造", ["制造", "工厂", "工业", "装备", "机器人", "供应链"]),
    ("物流", ["物流", "快递", "仓储", "运输", "航运", "港口"]),
    ("地产", ["地产", "房地产", "物业", "城投"]),
    ("教育", ["教育", "职教", "培训", "高校", "学校"]),
]

SOURCE_DEFAULT_TAG = {
    "gasgoo": "车企",
    "fmcg_china": "消费",
    "infoq": "科技",
    "cyzone": "创投",
    "hrloo": "人力资源",
    "tophr": "人力资源",
    "hrbrand_news": "人力资源",
    "hrvalue_kuai": "人力资源",
    "clssn_rlzy": "人力资源",
}

# 强规则优先：这类关键词通常属于政策/监管，不应被打成金融行业新闻
REGULATORY_POLICY_KEYWORDS = [
    "税务总局",
    "税务",
    "补缴",
    "查补",
    "稽查",
    "监管",
    "财政部",
    "发改委",
    "政策",
]

POLICY_KEEP_KEYWORDS = [
    "工资",
    "薪酬",
    "薪资",
    "个人所得税",
    "个税",
    "津贴",
    "补贴",
    "社保",
    "公积金",
    "最低工资",
    "收入",
    "待遇",
    "养老金",
    "失业金",
    "医保",
    "保险",
    "劳务派遣",
    "外包",
]


def _strip_leading_tag(title: str) -> str:
    if not title:
        return ""
    return re.sub(r"^【[^】]{1,12}】", "", title).strip()


def _infer_industry_tag(title: str, summary: str = "", source: str = "", url: str = "") -> str:
    clean_title = _strip_leading_tag(title)
    text = f"{clean_title} {summary}".lower()

    # 高优先级纠偏：监管/税务类信息直接归为政策
    for kw in REGULATORY_POLICY_KEYWORDS:
        if kw.lower() in text:
            return "政策"

    # 优先用 AI + 联网搜索识别行业
    ai_tag = call_ai_industry_tag_with_web(clean_title, summary, url)
    if ai_tag and ai_tag != "企业":
        return ai_tag

    # 联网识别不确定时，回退本地关键词规则
    for tag, kws in INDUSTRY_TAG_RULES:
        for kw in kws:
            if kw.lower() in text:
                return tag

    return SOURCE_DEFAULT_TAG.get(source, "企业")


def _ensure_industry_tag(title: str, summary: str = "", source: str = "", url: str = "") -> str:
    clean_title = _strip_leading_tag(title)
    tag = _infer_industry_tag(clean_title, summary, source, url)
    return f"【{tag}】{clean_title}" if clean_title else title


def _build_fallback_summary(title: str, content: str = "") -> str:
    """
    当 AI 摘要失败时，给出尽量可读的兜底摘要，避免发布空摘要。
    """
    clean_title = _strip_leading_tag(title)
    if content:
        text = re.sub(r"\s+", " ", content).strip()
        # 优先取第一句，避免粗暴按字数硬截断。
        parts = [p.strip() for p in re.split(r"[。！？!?]", text) if p.strip()]
        if parts:
            first = parts[0]
            if len(first) >= 12:
                return first.strip("，,;；:：") + "。"

    if clean_title:
        return f"{clean_title}。"
    return "暂无摘要。"


def _build_fallback_insight(reason: str, enterprise_items: list[dict]) -> str:
    """
    当 AI 洞察返回 NO_INSIGHT 时，使用趋势命中信息生成可发布的兜底洞察。
    """
    clean_reason = re.sub(r"\s+", " ", (reason or "").strip())
    if clean_reason and not clean_reason.endswith(("。", "！", "？")):
        clean_reason += "。"
    if len(clean_reason) > 140:
        clean_reason = clean_reason[:140].rstrip("，,;；:：") + "。"

    tags = []
    for it in enterprise_items[:20]:
        title = (it.get("title") or "").strip()
        m = re.match(r"^【([^】]{1,12})】", title)
        if not m:
            continue
        tag = m.group(1).strip()
        if tag and tag not in tags:
            tags.append(tag)
        if len(tags) >= 3:
            break

    tag_text = "、".join(tags) if tags else "重点行业"
    prefix = clean_reason if clean_reason else "今日高价值新闻呈现出明确的结构性变化。"
    return (
        f"{prefix}对 HRO 企业而言，短期应优先布局{tag_text}相关岗位的人才供给与灵活用工交付能力，"
        "同步加强招聘合规和用工成本管理，以承接需求波动带来的新增机会并控制交付风险。"
    )


def _policy_item_hit_keywords(item: dict) -> bool:
    title = _strip_leading_tag((item.get("title") or "").strip())
    summary = (item.get("summary") or "").strip()
    text = f"{title} {summary}"
    return any(kw in text for kw in POLICY_KEEP_KEYWORDS)


def _filter_policy_items_by_keywords(items: list[dict], source_name: str) -> list[dict]:
    kept = []
    before = len(items)
    for it in items:
        if _policy_item_hit_keywords(it):
            kept.append(it)
        else:
            print(f"[Policy Keyword Filter] 剔除({source_name}): {(it.get('title') or '').strip()}")
    print(f"[Policy Keyword Filter] {source_name}: {before} -> {len(kept)}")
    return kept


def _coerce_policy_item_datetime(raw_date) -> datetime | None:
    """
    将政策条目的 date 字段统一转为 datetime，便于做近24小时过滤。
    """
    if not raw_date:
        return None

    tz = now_cn().tzinfo

    if isinstance(raw_date, datetime):
        return raw_date if raw_date.tzinfo else raw_date.replace(tzinfo=tz)

    if isinstance(raw_date, date):
        return datetime(raw_date.year, raw_date.month, raw_date.day, tzinfo=tz)

    text = norm(str(raw_date))
    if not text:
        return None

    for fmt, width in (
        ("%Y-%m-%d %H:%M:%S", 19),
        ("%Y-%m-%d %H:%M", 16),
        ("%Y/%m/%d %H:%M:%S", 19),
        ("%Y/%m/%d %H:%M", 16),
        ("%Y-%m-%d", 10),
        ("%Y/%m/%d", 10),
    ):
        try:
            dt = datetime.strptime(text[:width], fmt)
            return dt.replace(tzinfo=tz)
        except Exception:
            continue

    return None


def _filter_policy_items_last_24h(items: list[dict], source_name: str, now: datetime) -> list[dict]:
    """
    统一近24小时过滤兜底：
    - 若条目带完整时间，用严格 24h 窗口；
    - 若站点仅提供 YYYY-MM-DD，则按日期粒度近似 24h（since_date~today）。
    """
    since = now - timedelta(hours=24)
    kept = []
    before = len(items)

    for it in items:
        raw_date = it.get("date")
        dt = _coerce_policy_item_datetime(raw_date)
        if not dt:
            print(f"[Policy 24h Filter] 剔除({source_name}): 无法解析发布时间 - {(it.get('title') or '').strip()}")
            continue

        if dt > now:
            print(f"[Policy 24h Filter] 剔除({source_name}): 发布时间晚于当前时间 - {(it.get('title') or '').strip()}")
            continue

        # 日期粒度站点无法做到严格到小时，这里用日期窗口近似。
        if isinstance(raw_date, date) and not isinstance(raw_date, datetime):
            in_window = (since.date() <= dt.date() <= now.date())
        else:
            in_window = (since <= dt <= now)

        if in_window:
            kept.append(it)
        else:
            print(f"[Policy 24h Filter] 剔除({source_name}): 超出24小时窗口 - {(it.get('title') or '').strip()}")

    print(f"[Policy 24h Filter] {source_name}: {before} -> {len(kept)}")
    return kept


def _pre_publish_fill_missing_summaries(items: list[dict]) -> tuple[list[dict], int]:
    """
    发布前检查：为缺失摘要的条目补齐摘要，避免发送空摘要。
    """
    fixed = 0
    for it in items:
        summary = (it.get("summary") or "").strip()
        if summary:
            continue

        title = it.get("title", "")
        url = it.get("url", "")
        content = (it.get("raw_content") or "").strip()
        if not content and url:
            content = fetch_url_content(url)

        ai_sum = call_ai_summary(content) if content else ""
        if ai_sum:
            it["summary"] = ai_sum
        else:
            it["summary"] = _build_fallback_summary(title, content)
        fixed += 1

    return items, fixed





def build_enterprise_block(run_hrloo: bool, run_sina: bool, run_tophr: bool = True, history_file: str = "insight_history.jsonl") -> tuple[str, list]:
    lines = ["## 人力新闻"]
    candidates = [] # 收集所有（HRloo + 其他）待展示新闻
    
    # ================= 1. 三茅 (HRloo) =================
    if run_hrloo:
        try:
            hr_item, hr_titles, hr_content_map = crawl_hrloo()
            if hr_item and hr_titles:
                # 三茅先过一把历史记录去重，以节省 AI 和后续的流程
                hr_candidates = [{"title": t, "url": hr_item.get("url", "")} for t in hr_titles]
                hr_candidates = filter_against_history(hr_candidates, history_file, category="enterprise")
                hr_titles = [it["title"] for it in hr_candidates]

                if not hr_titles:
                    lines.append("（当天的三茅日报已发布过，或无新内容）")
                else:
                    # 增加 AI 筛选逻辑
                    print(f"正在筛选三茅新闻 ({len(hr_titles)} 条)...")
                keep_flags = call_ai_filter(hr_titles)

                for i, t in enumerate(hr_titles):
                    # 如果 AI 判定无需保留，则跳过
                    if i < len(keep_flags) and not keep_flags[i]:
                        print(f"  -> [AI Filter] 筛掉三茅: {t}")
                        continue

                    # 三茅要点详情统一跳到当天三茅日报文章页（同一个 url）
                    raw_content = hr_content_map.get(t, "")
                    
                    # 使用 AI 进行摘要
                    summary = ""
                    if raw_content:
                        if len(raw_content) < 100:
                            summary = _build_fallback_summary(t, raw_content)
                        else:
                            ai_sum = call_ai_summary(raw_content)
                            summary = ai_sum if ai_sum else _build_fallback_summary(t, raw_content)
                    
                    # 加入候选池 (不直接生成 lines)
                    candidates.append({"title": t, "summary": summary, "url": hr_item["url"], "source": "hrloo"})
            else:
                lines.append("（未发现当天的三茅日报）")
        except Exception as e:
            lines.append(f"（三茅抓取错误: {e}）")

    # ================= 2. 其他平台聚合 =================
    enterprise_items = []
    
    if run_sina:
        try:
            _, sina_list = crawl_sina_target_day()
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

    # 财新网 - 公司（近24小时）
    run_caixin_env = (os.getenv("RUN_CAIXIN_COMPANIES", "1") != "0")
    if run_caixin_env:
        try:
            caixin_list = crawl_caixin_companies()
            for it in caixin_list:
                it["source"] = "caixin_companies"
                enterprise_items.append(it)
        except Exception as e:
            print(f"Caixin Companies error: {e}")

    # 界面新闻 - 商业（近24小时）
    run_jiemian_env = (os.getenv("RUN_JIEMIAN_BUSINESS", "1") != "0")
    if run_jiemian_env:
        try:
            jiemian_list = crawl_jiemian_business()
            for it in jiemian_list:
                it["source"] = "jiemian_business"
                enterprise_items.append(it)
        except Exception as e:
            print(f"Jiemian Business error: {e}")

    # 中国金融信息网 - 独家（近24小时）
    run_cnfin_dj_env = (os.getenv("RUN_CNFIN_DJ", "1") != "0")
    if run_cnfin_dj_env:
        try:
            cnfin_list = crawl_cnfin_dj()
            for it in cnfin_list:
                it["source"] = "cnfin_dj"
                enterprise_items.append(it)
        except Exception as e:
            print(f"CNFIN Exclusive error: {e}")

    # 钛媒体 - 最新（近24小时）
    run_tmtpost_env = (os.getenv("RUN_TMTPOST", "1") != "0")
    if run_tmtpost_env:
        try:
            tmtpost_list = crawl_tmtpost()
            for it in tmtpost_list:
                it["source"] = "tmtpost"
                enterprise_items.append(it)
        except Exception as e:
            print(f"TMTPost error: {e}")

    # 同花顺 - 非上市公司（前一工作日）
    run_thsi_env = (os.getenv("RUN_THSI_UNLISTED", "1") != "0")
    if run_thsi_env:
        try:
            thsi_list = crawl_thsi_unlisted()
            for it in thsi_list:
                it["source"] = "thsi_unlisted"
                enterprise_items.append(it)
        except Exception as e:
            print(f"THSI Unlisted error: {e}")

    # 财富中文网 - 商业（昨天）
    run_fortune_env = (os.getenv("RUN_FORTUNE_CN", "1") != "0")
    if run_fortune_env:
        try:
            fortune_list = crawl_fortune_cn()
            for it in fortune_list:
                it["source"] = "fortune_cn"
                enterprise_items.append(it)
        except Exception as e:
           print(f"FortuneCN error: {e}")

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

    # 动脉网 - 指定栏目（近24小时）
    run_vbdata_env = (os.getenv("RUN_VBDATA", "1") != "0")
    if run_vbdata_env:
        try:
            vbdata_list = crawl_vbdata()
            for it in vbdata_list:
                it["source"] = "vbdata"
                enterprise_items.append(it)
        except Exception as e:
            print(f"VBData error: {e}")

    # 快消品网 - 多板块（独家、饮品、食品、日化、零售、电商、综合）
    # 通常该网站更新不频繁，但板块多，合并抓取
    run_fmcg_env = (os.getenv("RUN_FMCG_CHINA", "1") != "0")
    if run_fmcg_env:
        try:
            fmcg_list = crawl_fmcg_china()
            for it in fmcg_list:
                it["source"] = "fmcg_china"
                enterprise_items.append(it)
        except Exception as e:
            print(f"FMCG China error: {e}")

    # 盖世汽车 - 产业+车企
    run_gasgoo_env = (os.getenv("RUN_GASGOO", "1") != "0")
    if run_gasgoo_env:
        try:
            # 默认抓取目标工作日新闻（内部自动判断）
            gasgoo_list = crawl_gasgoo()
            for it in gasgoo_list:
                it["source"] = "gasgoo"
                enterprise_items.append(it)
        except Exception as e:
            print(f"Gasgoo error: {e}")

    # InfoQ - 产业动态
    run_infoq_env = (os.getenv("RUN_INFOQ", "1") != "0")
    if run_infoq_env:
        try:
            # 默认抓取目标工作日新闻
            infoq_list = crawl_infoq()
            for it in infoq_list:
                it["source"] = "infoq"
                enterprise_items.append(it)
        except Exception as e:
            print(f"InfoQ error: {e}")

    # 创业邦 - 资讯频道
    run_cyzone_env = (os.getenv("RUN_CYZONE", "1") != "0")
    if run_cyzone_env:
        try:
            # 默认抓取目标工作日新闻
            cyzone_list = crawl_cyzone()
            for it in cyzone_list:
                it["source"] = "cyzone"
                enterprise_items.append(it)
        except Exception as e:
            print(f"Cyzone error: {e}")

    # 虎嗅 - 资讯
    run_huxiu_env = (os.getenv("RUN_HUXIU", "1") != "0")
    if run_huxiu_env:
        try:
            # 默认抓取目标工作日新闻
            huxiu_list = crawl_huxiu()
            for it in huxiu_list:
                it["source"] = "huxiu"
                enterprise_items.append(it)
        except Exception as e:
            print(f"Huxiu error: {e}")

    # ===== 历史记录排重 (其他平台) =====
    if enterprise_items:
        before_len = len(enterprise_items)
        enterprise_items = filter_against_history(enterprise_items, history_file, category="enterprise")
        print(f"[History Filter] 财经/人力新闻排重: {before_len} -> {len(enterprise_items)}")

    # ===== AI 批量筛选 (其他平台) =====
    if enterprise_items:
        enterprise_items = filter_by_ai_batch(enterprise_items)
        
    if not enterprise_items and (run_sina or (run_tophr and run_tophr_env) or run_yicai_env or run_clssn_env or run_hrbrand_env or run_hrvalue_kuai_env):
        lines.append("（AI 筛选后暂无相关高价值新闻）")
    
    # ===== AI 摘要生成 & 二次筛选 (其他平台) =====
    for it in enterprise_items:
        print(f"正在生成摘要: {it['title']} ...")
        content = it.get("raw_content") or fetch_url_content(it['url'])
        if not content:
            print(f"  -> 内容抓取为空，使用兜底摘要")
            it['summary'] = _build_fallback_summary(it['title'])
            candidates.append(it) # 虽然无摘要，但也加入
            continue
            
        summary = call_ai_summary(content)
        if summary:
            # 二次筛选
            if not call_ai_check_relevance(it['title'], summary):
                print(f"  -> [AI SecFilter] 剔除无关内容: {it['title']}")
                continue

            print(f"  -> 摘要生成成功: {summary[:20]}...")
            if it.get("source") == "yicai_hongguan":
                summary = clean_yicai_summary(summary)
            it['summary'] = summary
        else:
            it['summary'] = _build_fallback_summary(it['title'], content)
            
        candidates.append(it)

    # ================= 发布前摘要检查（补齐空摘要） =================
    if candidates:
        candidates, fixed_count = _pre_publish_fill_missing_summaries(candidates)
        if fixed_count > 0:
            print(f"[Publish Check] 已补齐摘要 {fixed_count} 条")

    # ================= 二次历史排重（含摘要语义近似） =================
    if candidates:
        before_len = len(candidates)
        candidates = filter_against_history(candidates, history_file, category="enterprise")
        print(f"[History Filter][2nd pass] 企业新闻排重: {before_len} -> {len(candidates)}")

    # ================= 3. 同公司多新闻影响力择优 =================
    if candidates:
        candidates = call_ai_keep_max_impact_per_company(candidates)

    # ================= 4. 全局去重 (HRloo + Others) =================
    if candidates:
        candidates = call_ai_deduplicate(candidates)

    # ================= 5. 最终渲染 =================
    idx = 1
    enterprise_items_all = []
    
    for it in candidates:
        # 检查标题长度，若超过50字，进行缩写
        t = it["title"]
        t = _strip_leading_tag(t)
        title_len = len(t)
        if title_len > 50:
            print(f"  -> 标题过长 ({title_len}字)，AI正在缩写: {t}")
            short_t = call_ai_shorten_title(t)
            if short_t:
                print(f"     => {short_t} (len={len(short_t)})")
                t = short_t

        # 所有已筛选企业新闻统一补充行业前缀标签
        t = _ensure_industry_tag(t, it.get("summary", ""), it.get("source", ""), it.get("url", ""))
        it["title"] = t

        # 收集最终结果
        enterprise_items_all.append(it)
        lines.append(md_item_with_detail(idx, t, it["url"], it.get("summary")))
        idx += 1

    # 使用双换行以确保在移动端钉钉能正确分段显示
    return "\n\n".join(lines).strip(), enterprise_items_all

def build_policy_block(run_mohrss: bool, history_file: str = "insight_history.jsonl") -> tuple[str, list]:
    lines = ["## 人社动态 & 政策"]
    policy_items_all = [] # 收集所有政策标题，用于后续 AI 分析

    # 不再根据周末跳过抓取，始终尝试生成政策区块
    # 当前时间，用于“近24小时”过滤等操作
    now = now_cn()

    hit_dynamics = []
    hit_policies = []
    chinatax_policies = []
    beijing_policies = []
    beijing_gjj_policies = []
    chengdu_gjj_policies = []
    guiyang_gjj_policies = []
    kunming_gjj_policies = []
    tianjin_policies = []
    hebei_policies = []
    shanxi_policies = []
    neimenggu_policies = []
    jilin_policies = []
    henan_policies = []
    hubei_policies = []
    hunan_policies = []
    guangdong_policies = []
    guangxi_policies = []
    hainan_policies = []
    chongqing_policies = []
    sichuan_policies = []
    guizhou_policies = []
    yunnan_policies = []
    xizang_policies = []
    shaanxi_policies = []
    gansu_policies = []
    qinghai_policies = []
    ningxia_policies = []
    xinjiang_policies = []
    hlbe_gjj_policies = []
    btgjj_policies = []
    hrvalue_policies = []
    govcn_policies = []
    heilongjiang_policies = []
    liaoning_policies = []
    shanghai_policies = []
    shanghai_gjj_policies = []
    taiyuan_gjj_policies = []
    shijiazhuang_policies = []
    zhengzhou_gjj_policies = []
    shenyang_gjj_policies = []
    hrbgjj_policies = []
    jlgjj_policies = []
    hangzhou_gjj_policies = []
    hefei_gjj_policies = []
    fuzhou_gjj_policies = []
    nanchang_gjj_policies = []
    changsha_gjj_policies = []
    guangzhou_gjj_policies = []
    guilin_gjj_policies = []
    tsgjj_policies = []
    lanzhou_gjj_policies = []
    yinchuan_gjj_policies = []
    yqgjj_policies = []
    changzhi_policies = []
    jcgov_policies = []
    zf365_policies = []
    sxjz_policies = []
    yuncheng_policies = []
    sxxz_xzgjj_policies = []
    lvliang_policies = []
    qdgjj_zcjd_policies = []
    qhdgjj_policies = []
    handan_gjj_policies = []
    xingtai_gjj_policies = []
    baoding_gjj_policies = []
    zjkgjj_policies = []
    chengde_gjj_policies = []
    cangzhou_gjj_policies = []
    lfzfgjj_policies = []
    tlzfgjj_policies = []
    cfszfgjj_policies = []
    ordos_gjj_policies = []
    whsgjj_zxwj_policies = []
    xamzfgjj_zxwj_policies = []
    xlglgjj_dfwj_policies = []
    alszfgjj_policies = []
    hszfgjj_policies = []
    wuhan_gjj_policies = []
    tianjin_gjj_policies = []
    nanjing_gjj_policies = []
    cqgjj_gsgg_policies = []
    jiangsu_policies = []
    zhejiang_policies = []
    anhui_policies = []
    fujian_policies = []
    jiangxi_policies = []
    shandong_policies = []
    
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
        jilin_policies = crawl_jilin_hrss_policy(target_date)
    except Exception as e:
        print(f"JJJ/SX/NM Policy error: {e}")

    # 北京住房公积金管理中心 - 管委会文件 + 四个中心板块（近24小时）
    run_beijing_gjj_policy_env = (os.getenv("RUN_BEIJING_GJJ_POLICY", "1") != "0")
    if run_beijing_gjj_policy_env:
        try:
            beijing_gjj_policies = crawl_beijing_gjj_policy()
        except Exception as e:
            print(f"Beijing GJJ policy fetch error: {e}")

    # 成都住房公积金管理中心-地方文件（近24小时）
    run_chengdu_gjj_policy_env = (os.getenv("RUN_CHENGDU_GJJ_POLICY", "1") != "0")
    if run_chengdu_gjj_policy_env:
        try:
            chengdu_gjj_policies = crawl_chengdu_gjj_policy()
        except Exception as e:
            print(f"Chengdu GJJ policy fetch error: {e}")
    
    run_guiyang_gjj_policy_env = (os.getenv("RUN_GUIYANG_GJJ_POLICY", "1") != "0")
    if run_guiyang_gjj_policy_env:
        try:
            guiyang_gjj_policies = crawl_guiyang_gjj_policy()
        except Exception as e:
            print(f"Guiyang GJJ policy fetch error: {e}")

    # 昆明住房公积金管理中心 - 政策文件（近24小时）
    run_kunming_gjj_policy_env = (os.getenv("RUN_KUNMING_GJJ_POLICY", "1") != "0")
    if run_kunming_gjj_policy_env:
        try:
            kunming_gjj_policies = crawl_kunming_gjj_policy()
        except Exception as e:
            print(f"Kunming GJJ policy fetch error: {e}")

    # 3.1 河南省人社厅 - 规范性文件资料库（近24小时）
    run_henan_policy_env = (os.getenv("RUN_HENAN_HRSS_POLICY", "1") != "0")
    if run_henan_policy_env:
        try:
            henan_policies = crawl_henan_hrss_policy()
        except Exception as e:
            print(f"Henan HRSS policy fetch error: {e}")

    # 3.2 湖北省人社厅 - 规范性文件 + 其他主动公开文件（近24小时）
    run_hubei_policy_env = (os.getenv("RUN_HUBEI_RST_POLICY", "1") != "0")
    if run_hubei_policy_env:
        try:
            hubei_policies = crawl_hubei_rst_policy()
        except Exception as e:
            print(f"Hubei RST policy fetch error: {e}")

    # 3.3 湖南省人社厅 - 厅发规范性文件（近24小时）
    run_hunan_policy_env = (os.getenv("RUN_HUNAN_RST_POLICY", "1") != "0")
    if run_hunan_policy_env:
        try:
            hunan_policies = crawl_hunan_rst_policy()
        except Exception as e:
            print(f"Hunan RST policy fetch error: {e}")

    # 3.4 广东省人社厅 - 规范性文件 + 其他文件(社会保障)（近24小时）
    run_guangdong_policy_env = (os.getenv("RUN_GUANGDONG_HRSS_POLICY", "1") != "0")
    if run_guangdong_policy_env:
        try:
            guangdong_policies = crawl_guangdong_hrss_policy()
        except Exception as e:
            print(f"Guangdong HRSS policy fetch error: {e}")

    # 3.5 广西壮族自治区人社厅 - 规章政策 + 本厅规范性文件（近24小时）
    run_guangxi_policy_env = (os.getenv("RUN_GUANGXI_RST_POLICY", "1") != "0")
    if run_guangxi_policy_env:
        try:
            guangxi_policies = crawl_guangxi_rst_policy()
        except Exception as e:
            print(f"Guangxi RST policy fetch error: {e}")

    # 3.6 海南省人社厅 - 部门文件（近24小时）
    run_hainan_policy_env = (os.getenv("RUN_HAINAN_HRSS_POLICY", "1") != "0")
    if run_hainan_policy_env:
        try:
            hainan_policies = crawl_hainan_hrss_policy()
        except Exception as e:
            print(f"Hainan HRSS policy fetch error: {e}")

    # 3.7 重庆市人社局 - 行政规范性文件（近24小时）
    run_chongqing_policy_env = (os.getenv("RUN_CHONGQING_HRSS_POLICY", "1") != "0")
    if run_chongqing_policy_env:
        try:
            chongqing_policies = crawl_chongqing_hrss_policy()
        except Exception as e:
            print(f"Chongqing HRSS policy fetch error: {e}")

    # 3.8 四川省人社厅 - 政策 / 行政规范性文件（近24小时）
    run_sichuan_policy_env = (os.getenv("RUN_SICHUAN_RST_POLICY", "1") != "0")
    if run_sichuan_policy_env:
        try:
            sichuan_policies = crawl_sichuan_rst_policy()
        except Exception as e:
            print(f"Sichuan RST policy fetch error: {e}")

    # 3.9 贵州省人社厅 - 政策文件 + 规范性文件数据库（近24小时）
    run_guizhou_policy_env = (os.getenv("RUN_GUIZHOU_RST_POLICY", "1") != "0")
    if run_guizhou_policy_env:
        try:
            guizhou_policies = crawl_guizhou_rst_policy()
        except Exception as e:
            print(f"Guizhou RST policy fetch error: {e}")

    # 3.10 云南省人社厅 - 通知公告 + 政策文件（近24小时）
    run_yunnan_policy_env = (os.getenv("RUN_YUNNAN_HRSS_POLICY", "1") != "0")
    if run_yunnan_policy_env:
        try:
            yunnan_policies = crawl_yunnan_hrss_policy()
        except Exception as e:
            print(f"Yunnan HRSS policy fetch error: {e}")

    # 3.11 西藏自治区人社厅 - 行政规范性文件（近24小时）
    run_xizang_policy_env = (os.getenv("RUN_XIZANG_HRSS_POLICY", "1") != "0")
    if run_xizang_policy_env:
        try:
            xizang_policies = crawl_xizang_hrss_policy()
        except Exception as e:
            print(f"Xizang HRSS policy fetch error: {e}")

    # 3.12 陕西省人社厅 - 规范性文件（就业，近24小时）
    run_shaanxi_policy_env = (os.getenv("RUN_SHAANXI_RST_POLICY", "1") != "0")
    if run_shaanxi_policy_env:
        try:
            shaanxi_policies = crawl_shaanxi_rst_policy()
        except Exception as e:
            print(f"Shaanxi RST policy fetch error: {e}")

    # 3.13 甘肃省人社厅 - 信息公开目录（近24小时）
    run_gansu_policy_env = (os.getenv("RUN_GANSU_RST_POLICY", "1") != "0")
    if run_gansu_policy_env:
        try:
            gansu_policies = crawl_gansu_rst_policy()
        except Exception as e:
            print(f"Gansu RST policy fetch error: {e}")

    # 3.14 青海省人社厅 - 政策知识库（近24小时）
    run_qinghai_policy_env = (os.getenv("RUN_QINGHAI_RST_POLICY", "1") != "0")
    if run_qinghai_policy_env:
        try:
            qinghai_policies = crawl_qinghai_rst_policy()
        except Exception as e:
            print(f"Qinghai RST policy fetch error: {e}")

    # 3.15 宁夏回族自治区人社厅 - 社会保障/厅发文件/劳动关系/规范性文件（近24小时）
    run_ningxia_policy_env = (os.getenv("RUN_NINGXIA_HRSS_POLICY", "1") != "0")
    if run_ningxia_policy_env:
        try:
            ningxia_policies = crawl_ningxia_hrss_policy()
        except Exception as e:
            print(f"Ningxia HRSS policy fetch error: {e}")

    # 3.16 新疆维吾尔自治区人社厅 - 政策文件 / 规范性文件（近24小时）
    run_xinjiang_policy_env = (os.getenv("RUN_XINJIANG_RST_POLICY", "1") != "0")
    if run_xinjiang_policy_env:
        try:
            xinjiang_policies = crawl_xinjiang_rst_policy()
        except Exception as e:
            print(f"Xinjiang RST policy fetch error: {e}")

    # 呼伦贝尔住房公积金 - 政策法规（近24小时）
    run_hlbe_gjj_policy_env = (os.getenv("RUN_HLBE_GJJ_POLICY", "1") != "0")
    if run_hlbe_gjj_policy_env:
        try:
            hlbe_gjj_policies = crawl_hlbe_gjj_policy()
        except Exception as e:
            print(f"HLBE GJJ policy fetch error: {e}")

    # 包头住房公积金 - 公积金法规（近24小时）
    run_btgjj_policy_env = (os.getenv("RUN_BTGJJ_POLICY", "1") != "0")
    if run_btgjj_policy_env:
        try:
            btgjj_policies = crawl_btgjj_policy()
        except Exception as e:
            print(f"BTGJJ policy fetch error: {e}")

    # 4. HR价值网 - 政策
    run_hrvalue_policy_env = (os.getenv("RUN_HRVALUE_POLICY", "1") != "0")
    if run_hrvalue_policy_env:
        try:
            hrvalue_policies = crawl_hrvalue_policy()
        except Exception as e:
            print(f"HRValue policy fetch error: {e}")

    # 5. 中国政府网 - 最新政策
    run_govcn_policy_env = (os.getenv("RUN_GOVCN_POLICY", "1") != "0")
    if run_govcn_policy_env:
        try:
            govcn_policies = crawl_govcn_policy()
        except Exception as e:
            print(f"GovCN policy fetch error: {e}")

    # 6. 黑龙江省人社厅 - 政策（行政规范性文件/其它文件，近24小时）
    run_heilongjiang_policy_env = (os.getenv("RUN_HEILONGJIANG_HRSS_POLICY", "1") != "0")
    if run_heilongjiang_policy_env:
        try:
            heilongjiang_policies = crawl_heilongjiang_hrss_policy()
        except Exception as e:
            print(f"Heilongjiang HRSS policy fetch error: {e}")

    # 7. 辽宁省人社厅 - 政策（三个规范性文件栏目，近24小时）
    run_liaoning_policy_env = (os.getenv("RUN_LIAONING_HRSS_POLICY", "1") != "0")
    if run_liaoning_policy_env:
        try:
            liaoning_policies = crawl_liaoning_hrss_policy()
        except Exception as e:
            print(f"Liaoning HRSS policy fetch error: {e}")

    # 8. 上海市人社局 - 规范性文件（近24小时）
    run_shanghai_policy_env = (os.getenv("RUN_SHANGHAI_HRSS_POLICY", "1") != "0")
    if run_shanghai_policy_env:
        try:
            shanghai_policies = crawl_shanghai_hrss_policy()
        except Exception as e:
            print(f"Shanghai HRSS policy fetch error: {e}")

    # 上海住房公积金网 - 公积金法规 + 规范性文件 + 管理文件（全部分页）
    run_shanghai_gjj_policy_env = (os.getenv("RUN_SHANGHAI_GJJ_POLICY", "1") != "0")
    if run_shanghai_gjj_policy_env:
        try:
            shanghai_gjj_policies = crawl_shanghai_gjj_policy()
        except Exception as e:
            print(f"Shanghai GJJ policy fetch error: {e}")

    # 太原住房公积金中心 - 通知公告（近24小时）
    run_taiyuan_gjj_policy_env = (os.getenv("RUN_TAIYUAN_GJJ_POLICY", "1") != "0")
    if run_taiyuan_gjj_policy_env:
        try:
            taiyuan_gjj_policies = crawl_taiyuan_gjj_policy()
        except Exception as e:
            print(f"Taiyuan GJJ policy fetch error: {e}")

    # 石家庄住房公积金网 - 政策法规（近24小时）
    run_shijiazhuang_gjj_policy_env = (os.getenv("RUN_SHIJIAZHUANG_GJJ_POLICY", "1") != "0")
    if run_shijiazhuang_gjj_policy_env:
        try:
            shijiazhuang_policies = crawl_shijiazhuang_gjj_policy()
        except Exception as e:
            print(f"Shijiazhuang GJJ policy fetch error: {e}")

    # 郑州住房公积金管理中心 - 行政规范性文件（近24小时）
    run_zhengzhou_gjj_policy_env = (os.getenv("RUN_ZHENGZHOU_GJJ_POLICY", "1") != "0")
    if run_zhengzhou_gjj_policy_env:
        try:
            zhengzhou_gjj_policies = crawl_zhengzhou_gjj_law()
        except Exception as e:
            print(f"Zhengzhou GJJ policy fetch error: {e}")

    # 沈阳住房公积金管理中心 - 政策法规（近24小时）
    run_shenyang_gjj_policy_env = (os.getenv("RUN_SHENYANG_GJJ_POLICY", "1") != "0")
    if run_shenyang_gjj_policy_env:
        try:
            shenyang_gjj_policies = crawl_shenyang_gjj_policy()
        except Exception as e:
            print(f"Shenyang GJJ policy fetch error: {e}")

    # 哈尔滨住房公积金中心 - 中心文件（近24小时）
    run_harbin_gjj_policy_env = (os.getenv("RUN_HARBIN_GJJ_POLICY", "1") != "0")
    if run_harbin_gjj_policy_env:
        try:
            hrbgjj_policies = crawl_hrbgjj_zxwj()
        except Exception as e:
            print(f"Harbin GJJ policy fetch error: {e}")

    # 吉林市住房公积金管理中心 - 政策文件（近24小时）
    run_jlgjj_policy_env = (os.getenv("RUN_JLGJJ_POLICY", "1") != "0")
    if run_jlgjj_policy_env:
        try:
            jlgjj_policies = crawl_jlgjj_policy()
        except Exception as e:
            print(f"Jilin GJJ policy fetch error: {e}")

    # 南京住房公积金网 - 通知公告（近24小时）
    run_nanjing_gjj_env = (os.getenv("RUN_NANJING_GJJ_TZGG", "1") != "0")
    if run_nanjing_gjj_env:
        try:
            nanjing_gjj_policies = crawl_nanjing_gjj_tzgg()
        except Exception as e:
            print(f"Nanjing GJJ tzgg fetch error: {e}")

    # 合肥住房公积金网 - 公积金政策（近24小时）
    run_hefei_gjj_env = (os.getenv("RUN_HEFEI_GJJ_POLICY", "1") != "0")
    if run_hefei_gjj_env:
        try:
            hefei_gjj_policies = crawl_hefei_gjj_policy()
        except Exception as e:
            print(f"Hefei GJJ policy fetch error: {e}")

    # 永清/阳泉公积金网 - 政策法规（近24小时）
    run_yqgjj_env = (os.getenv("RUN_YQGJJ_POLICY", "1") != "0")
    if run_yqgjj_env:
        try:
            yqgjj_policies = crawl_yqgjj_policy()
        except Exception as e:
            print(f"YQGJJ policy fetch error: {e}")

    # 长治住房公积金网 - 中心文件（近24小时）
    run_changzhi_env = (os.getenv("RUN_CHANGZHI_GJJ_ZXWJ", "1") != "0")
    if run_changzhi_env:
        try:
            changzhi_policies = crawl_changzhi_gjj_zxwj()
        except Exception as e:
            print(f"Changzhi GJJ fetch error: {e}")

    # 晋城市政务网 - 政策文件（近24小时）
    run_jcgov_env = (os.getenv("RUN_JCGOV_POLICY", "1") != "0")
    if run_jcgov_env:
        try:
            jcgov_policies = crawl_jcgov_policy()
        except Exception as e:
            print(f"JC GOV policy fetch error: {e}")

    # 晋中市政务网 - 政策文件（近24小时）
    run_sxjz_env = (os.getenv("RUN_SXJZ_POLICY", "1") != "0")
    if run_sxjz_env:
        try:
            sxjz_policies = crawl_sxjz_policy()
        except Exception as e:
            print(f"SXJZ policy fetch error: {e}")

    # 运城市政务网 - 政策法规（近24小时）
    run_yuncheng_env = (os.getenv("RUN_YUNCHENG_POLICY", "1") != "0")
    if run_yuncheng_env:
        try:
            yuncheng_policies = crawl_yuncheng_policy()
        except Exception as e:
            print(f"Yuncheng policy fetch error: {e}")

    # 咸阳/县级住房公积金网 - 中心文件（近24小时）
    run_sxxz_env = (os.getenv("RUN_SXXZ_XZGJJ", "1") != "0")
    if run_sxxz_env:
        try:
            sxxz_xzgjj_policies = crawl_sxxz_xzgjj_zxwj()
        except Exception as e:
            print(f"SXXZ XZGJJ fetch error: {e}")

    # 吕梁市政府 - 政策法规（近24小时）
    run_lvliang_env = (os.getenv("RUN_LVLIANG_POLICY", "1") != "0")
    if run_lvliang_env:
        try:
            lvliang_policies = crawl_lvliang_policy()
        except Exception as e:
            print(f"Lvliang policy fetch error: {e}")

    # zf365 - 通知公告（近24小时）
    run_zf365_env = (os.getenv("RUN_ZF365_TZGG", "1") != "0")
    if run_zf365_env:
        try:
            zf365_policies = crawl_zf365_tzgg()
        except Exception as e:
            print(f"ZF365 tzgg fetch error: {e}")

    # 福州住房公积金网 - 政策法规（近24小时）
    run_fuzhou_gjj_env = (os.getenv("RUN_FUZHOU_GJJ_ZCFG", "1") != "0")
    if run_fuzhou_gjj_env:
        try:
            fuzhou_gjj_policies = crawl_fuzhou_gjj_zcfg()
        except Exception as e:
            print(f"Fuzhou GJJ zcfg fetch error: {e}")

    # 南昌住房公积金网 - 政策法规（近24小时）
    run_nanchang_gjj_env = (os.getenv("RUN_NANCHANG_GJJ_ZCFG", "1") != "0")
    if run_nanchang_gjj_env:
        try:
            nanchang_gjj_policies = crawl_nanchang_gjj_zcfg()
        except Exception as e:
            print(f"Nanchang GJJ zcfg fetch error: {e}")

    # 青岛住房公积金网 - 政策解读（近24小时）
    run_qdgjj_zcjd_env = (os.getenv("RUN_QDGJJ_ZCJD", "1") != "0")
    if run_qdgjj_zcjd_env:
        try:
            qdgjj_zcjd_policies = crawl_qdgjj_zcjd()
        except Exception as e:
            print(f"QDGJJ zcjd fetch error: {e}")

    # 秦皇岛公积金网 - 通知公告（近24小时）
    run_qhdgjj_env = (os.getenv("RUN_QHDGJJ_TZGG", "1") != "0")
    if run_qhdgjj_env:
        try:
            qhdgjj_policies = crawl_qhdgjj_tzgg()
        except Exception as e:
            print(f"QHDGJJ tzgg fetch error: {e}")

    # 邯郸公积金网 - 政策法规（近24小时）
    run_handan_gjj_env = (os.getenv("RUN_HANDAN_GJJ_POLICY", "1") != "0")
    if run_handan_gjj_env:
        try:
            handan_gjj_policies = crawl_handan_gjj_policy()
        except Exception as e:
            print(f"Handan GJJ policy fetch error: {e}")

    # 邢台公积金网 - 政策（近24小时）
    run_xingtai_gjj_env = (os.getenv("RUN_XINGTAI_GJJ_POLICY", "1") != "0")
    if run_xingtai_gjj_env:
        try:
            xingtai_gjj_policies = crawl_xingtai_gjj_policy()
        except Exception as e:
            print(f"Xingtai GJJ policy fetch error: {e}")

    # 保定公积金网 - 中心文件（近24小时）
    run_baoding_gjj_env = (os.getenv("RUN_BAODING_GJJ_ZXWJ", "1") != "0")
    if run_baoding_gjj_env:
        try:
            baoding_gjj_policies = crawl_baoding_gjj_zxwj()
        except Exception as e:
            print(f"Baoding GJJ zxwj fetch error: {e}")

    # 张家口公积金网 - 规范性文件（近24小时）
    run_zjkgjj_env = (os.getenv("RUN_ZJKGJJ_NORMATIVE_FILES", "1") != "0")
    if run_zjkgjj_env:
        try:
            zjkgjj_policies = crawl_zjkgjj_normative_files()
        except Exception as e:
            print(f"ZJK GJJ normative files fetch error: {e}")

    # 承德公积金网 - 通知公告（近24小时）
    run_chengde_gjj_env = (os.getenv("RUN_CHENGDE_GJJ_ANNOUNCEMENT", "1") != "0")
    if run_chengde_gjj_env:
        try:
            chengde_gjj_policies = crawl_chengde_gjj_announcement()
        except Exception as e:
            print(f"Chengde GJJ announcement fetch error: {e}")

    # 沧州公积金网 - 通知公告（近24小时）
    run_cangzhou_gjj_env = (os.getenv("RUN_CANGZHOU_GJJ_ANNOUNCEMENT", "1") != "0")
    if run_cangzhou_gjj_env:
        try:
            cangzhou_gjj_policies = crawl_cangzhou_gjj_announcement()
        except Exception as e:
            print(f"Cangzhou GJJ announcement fetch error: {e}")

    # 廊坊公积金网 - 通知公告（近24小时）
    run_lfzfgjj_env = (os.getenv("RUN_LFZFGJJ_ANNOUNCEMENT", "1") != "0")
    if run_lfzfgjj_env:
        try:
            lfzfgjj_policies = crawl_lfzfgjj_announcement()
        except Exception as e:
            print(f"Langfang GJJ announcement fetch error: {e}")

    # 通辽公积金中心 - 通知公告（近24小时，且标题必须包含“公积金”）
    run_tlzfgjj_env = (os.getenv("RUN_TLZFGJJ_TZGG", "1") != "0")
    if run_tlzfgjj_env:
        try:
            tlzfgjj_policies = crawl_tlzfgjj_tzgg()
        except Exception as e:
            print(f"TLZFGJJ tzgg fetch error: {e}")

    # 赤峰市住房公积金中心 - 政策法规（近24小时）
    run_cfszfgjj_env = (os.getenv("RUN_CFSZFGJJ_POLICY", "1") != "0")
    if run_cfszfgjj_env:
        try:
            cfszfgjj_policies = crawl_cfszfgjj_policy()
        except Exception as e:
            print(f"CFSZFGJJ policy fetch error: {e}")

    # 鄂尔多斯住房公积金 - 中心规定文件（近24小时）
    run_ordos_gjj_env = (os.getenv("RUN_ORDOS_GJJ_ZXGDW", "1") != "0")
    if run_ordos_gjj_env:
        try:
            ordos_gjj_policies = crawl_ordos_gjj_zxgdw()
        except Exception as e:
            print(f"Ordos GJJ zxgdw fetch error: {e}")

    # 乌海市住房公积金中心 - 中心文件（近24小时）
    run_whsgjj_zxwj_env = (os.getenv("RUN_WHSGJJ_ZXWJ", "1") != "0")
    if run_whsgjj_zxwj_env:
        try:
            whsgjj_zxwj_policies = crawl_whsgjj_zxwj()
        except Exception as e:
            print(f"WHSGJJ zxwj fetch error: {e}")

    # 兴安盟住房公积金中心 - 中心文件（近24小时）
    run_xamzfgjj_zxwj_env = (os.getenv("RUN_XAMZFGJJ_ZXWJ", "1") != "0")
    if run_xamzfgjj_zxwj_env:
        try:
            xamzfgjj_zxwj_policies = crawl_xamzfgjj_zxwj()
        except Exception as e:
            print(f"XAMZFGJJ zxwj fetch error: {e}")

    # 锡林郭勒盟住房公积金中心 - 地方文件（近24小时）
    run_xlglgjj_dfwj_env = (os.getenv("RUN_XLGLGJJ_DFWJ", "1") != "0")
    if run_xlglgjj_dfwj_env:
        try:
            xlglgjj_dfwj_policies = crawl_xlglgjj_dfwj()
        except Exception as e:
            print(f"XLGLGJJ dfwj fetch error: {e}")

    # 阿拉善盟住房公积金中心 - 政策法规（近24小时）
    run_alszfgjj_env = (os.getenv("RUN_ALSZFGJJ_POLICY", "1") != "0")
    if run_alszfgjj_env:
        try:
            alszfgjj_policies = crawl_alszfgjj_policy()
        except Exception as e:
            print(f"ALSZFGJJ policy fetch error: {e}")

    # 衡水公积金网 - 政策法规（近24小时）
    run_hszfgjj_env = (os.getenv("RUN_HSZFGJJ_POLICY_REGULATIONS", "1") != "0")
    if run_hszfgjj_env:
        try:
            hszfgjj_policies = crawl_hszfgjj_policy_regulations()
        except Exception as e:
            print(f"Hengshui GJJ policy regulations fetch error: {e}")

    # 武汉住房公积金管理中心 - 规范性文件（近24小时）
    run_wuhan_gjj_env = (os.getenv("RUN_WUHAN_GJJ_GFXWJ", "1") != "0")
    if run_wuhan_gjj_env:
        try:
            wuhan_gjj_policies = crawl_wuhan_gjj_gfxwj()
        except Exception as e:
            print(f"Wuhan GJJ gfxwj fetch error: {e}")

    # 长沙住房公积金网 - 文字解读（近24小时）
    run_changsha_gjj_env = (os.getenv("RUN_CHANGSHA_GJJ_WZJD", "1") != "0")
    if run_changsha_gjj_env:
        try:
            changsha_gjj_policies = crawl_changsha_gjj_wzjd()
        except Exception as e:
            print(f"Changsha GJJ wzjd fetch error: {e}")

    # 广州住房公积金网 - 规范性文件（近24小时）
    run_guangzhou_gjj_env = (os.getenv("RUN_GUANGZHOU_GJJ_POLICY", "1") != "0")
    if run_guangzhou_gjj_env:
        try:
            guangzhou_gjj_policies = crawl_guangzhou_gjj_policy()
        except Exception as e:
            print(f"Guangzhou GJJ policy fetch error: {e}")

    # 桂林住房公积金管理中心 - 中心文件（近24小时）
    run_guilin_gjj_env = (os.getenv("RUN_GUILIN_GJJ_ZXWJ", "1") != "0")
    if run_guilin_gjj_env:
        try:
            guilin_gjj_policies = crawl_guilin_gjj_zxwj()
        except Exception as e:
            print(f"Guilin GJJ zxwj fetch error: {e}")

    # TSGJJ 网站 - 中心文件（近24小时）
    run_tsgjj_center_env = (os.getenv("RUN_TSGJJ_CENTER", "1") != "0")
    if run_tsgjj_center_env:
        try:
            tsgjj_policies = crawl_tsgjj_center()
        except Exception as e:
            print(f"TSGJJ center fetch error: {e}")

    # 兰州住房公积金管理中心 - 政策法规（近24小时）
    run_lanzhou_gjj_env = (os.getenv("RUN_LANZHOU_GJJ_POLICY", "1") != "0")
    if run_lanzhou_gjj_env:
        try:
            lanzhou_gjj_policies = crawl_lanzhou_gjj_policy()
        except Exception as e:
            print(f"Lanzhou GJJ policy fetch error: {e}")

    # 银川住房公积金管理中心 - 政策法规（近24小时）
    run_yinchuan_gjj_env = (os.getenv("RUN_YINCHUAN_GJJ_POLICY", "1") != "0")
    if run_yinchuan_gjj_env:
        try:
            yinchuan_gjj_policies = crawl_yinchuan_gjj_policy()
        except Exception as e:
            print(f"Yinchuan GJJ policy fetch error: {e}")

    # 杭州住房公积金网 - 行政规范性文件（近24小时）
    run_hangzhou_gjj_env = (os.getenv("RUN_HANGZHOU_GJJ_XZFG", "1") != "0")
    if run_hangzhou_gjj_env:
        try:
            hangzhou_gjj_policies = crawl_hangzhou_gjj_xzfg()
        except Exception as e:
            print(f"Hangzhou GJJ xzfg fetch error: {e}")

    # 天津住房公积金网 - 本市规范性文件 + 中心文件库（近24小时）
    run_tianjin_gjj_policy_env = (os.getenv("RUN_TIANJIN_GJJ_POLICY", "1") != "0")
    if run_tianjin_gjj_policy_env:
        try:
            tianjin_gjj_policies = crawl_tianjin_gjj_policy()
        except Exception as e:
            print(f"Tianjin GJJ policy fetch error: {e}")

    # 重庆住房公积金中心 - 公示公告（近24小时）
    run_cqgjj_gsgg_env = (os.getenv("RUN_CQGJJ_GSGG", "1") != "0")
    if run_cqgjj_gsgg_env:
        try:
            cqgjj_gsgg_policies = crawl_cqgjj_gsgg()
        except Exception as e:
            print(f"Chongqing GJJ gsgg fetch error: {e}")

    # 9. 江苏省人社厅 - 最新政策（近24小时）
    run_jiangsu_policy_env = (os.getenv("RUN_JIANGSU_HRSS_POLICY", "1") != "0")
    if run_jiangsu_policy_env:
        try:
            jiangsu_policies = crawl_jiangsu_hrss_policy()
        except Exception as e:
            print(f"Jiangsu HRSS policy fetch error: {e}")

    # 10. 浙江省人社厅 - 行政规范性文件（近24小时）
    run_zhejiang_policy_env = (os.getenv("RUN_ZHEJIANG_HRSS_POLICY", "1") != "0")
    if run_zhejiang_policy_env:
        try:
            zhejiang_policies = crawl_zhejiang_hrss_policy()
        except Exception as e:
            print(f"Zhejiang HRSS policy fetch error: {e}")

    # 11. 安徽省人社厅 - 行政规范性文件 + 其他政策文件（近24小时）
    run_anhui_policy_env = (os.getenv("RUN_ANHUI_HRSS_POLICY", "1") != "0")
    if run_anhui_policy_env:
        try:
            anhui_policies = crawl_anhui_hrss_policy()
        except Exception as e:
            print(f"Anhui HRSS policy fetch error: {e}")

    # 12. 福建省人社厅 - 本部门文件（近24小时）
    run_fujian_policy_env = (os.getenv("RUN_FUJIAN_RST_BBMWJ", "1") != "0")
    if run_fujian_policy_env:
        try:
            fujian_policies = crawl_fujian_rst_bbmwj()
        except Exception as e:
            print(f"Fujian RST BBMWJ fetch error: {e}")

    # 13. 江西省人社厅 - 规范性文件 + 政策文件（近24小时）
    run_jiangxi_policy_env = (os.getenv("RUN_JIANGXI_RST_POLICY", "1") != "0")
    if run_jiangxi_policy_env:
        try:
            jiangxi_policies = crawl_jiangxi_rst_policy()
        except Exception as e:
            print(f"Jiangxi RST policy fetch error: {e}")

    # 14. 山东省人社厅 - 规范性文件 + 鲁人社发（近24小时）
    run_shandong_policy_env = (os.getenv("RUN_SHANDONG_HRSS_POLICY", "1") != "0")
    if run_shandong_policy_env:
        try:
            shandong_policies = crawl_shandong_hrss_policy()
        except Exception as e:
            print(f"Shandong HRSS policy fetch error: {e}")

    # 统一“近24小时”兜底过滤，覆盖所有政策/官网通知来源。
    hit_dynamics = _filter_policy_items_last_24h(hit_dynamics, "mohrss_dynamics", now)
    hit_policies = _filter_policy_items_last_24h(hit_policies, "mohrss_policy", now)
    chinatax_policies = _filter_policy_items_last_24h(chinatax_policies, "chinatax_policy", now)
    beijing_policies = _filter_policy_items_last_24h(beijing_policies, "beijing_policy", now)
    beijing_gjj_policies = _filter_policy_items_last_24h(beijing_gjj_policies, "beijing_gjj_policy", now)
    chengdu_gjj_policies = _filter_policy_items_last_24h(chengdu_gjj_policies, "chengdu_gjj_policy", now)
    guiyang_gjj_policies = _filter_policy_items_last_24h(guiyang_gjj_policies, "guiyang_gjj_policy", now)
    kunming_gjj_policies = _filter_policy_items_last_24h(kunming_gjj_policies, "kunming_gjj_policy", now)
    tianjin_gjj_policies = _filter_policy_items_last_24h(tianjin_gjj_policies, "tianjin_gjj_policy", now)
    cqgjj_gsgg_policies = _filter_policy_items_last_24h(cqgjj_gsgg_policies, "cqgjj_gsgg", now)
    tianjin_policies = _filter_policy_items_last_24h(tianjin_policies, "tianjin_policy", now)
    hebei_policies = _filter_policy_items_last_24h(hebei_policies, "hebei_policy", now)
    shanxi_policies = _filter_policy_items_last_24h(shanxi_policies, "shanxi_policy", now)
    sxjz_policies = _filter_policy_items_last_24h(sxjz_policies, "sxjz_policy", now)
    yuncheng_policies = _filter_policy_items_last_24h(yuncheng_policies, "yuncheng_policy", now)
    sxxz_xzgjj_policies = _filter_policy_items_last_24h(sxxz_xzgjj_policies, "sxxz_xzgjj", now)
    lvliang_policies = _filter_policy_items_last_24h(lvliang_policies, "lvliang_policy", now)
    neimenggu_policies = _filter_policy_items_last_24h(neimenggu_policies, "neimenggu_policy", now)
    jilin_policies = _filter_policy_items_last_24h(jilin_policies, "jilin_policy", now)
    henan_policies = _filter_policy_items_last_24h(henan_policies, "henan_hrss_policy", now)
    hubei_policies = _filter_policy_items_last_24h(hubei_policies, "hubei_rst_policy", now)
    hunan_policies = _filter_policy_items_last_24h(hunan_policies, "hunan_rst_policy", now)
    guangdong_policies = _filter_policy_items_last_24h(guangdong_policies, "guangdong_hrss_policy", now)
    guangxi_policies = _filter_policy_items_last_24h(guangxi_policies, "guangxi_rst_policy", now)
    hainan_policies = _filter_policy_items_last_24h(hainan_policies, "hainan_hrss_policy", now)
    chongqing_policies = _filter_policy_items_last_24h(chongqing_policies, "chongqing_hrss_policy", now)
    sichuan_policies = _filter_policy_items_last_24h(sichuan_policies, "sichuan_rst_policy", now)
    guizhou_policies = _filter_policy_items_last_24h(guizhou_policies, "guizhou_rst_policy", now)
    yunnan_policies = _filter_policy_items_last_24h(yunnan_policies, "yunnan_hrss_policy", now)
    xizang_policies = _filter_policy_items_last_24h(xizang_policies, "xizang_hrss_policy", now)
    shaanxi_policies = _filter_policy_items_last_24h(shaanxi_policies, "shaanxi_rst_policy", now)
    gansu_policies = _filter_policy_items_last_24h(gansu_policies, "gansu_rst_policy", now)
    qinghai_policies = _filter_policy_items_last_24h(qinghai_policies, "qinghai_rst_policy", now)
    ningxia_policies = _filter_policy_items_last_24h(ningxia_policies, "ningxia_hrss_policy", now)
    xinjiang_policies = _filter_policy_items_last_24h(xinjiang_policies, "xinjiang_rst_policy", now)
    hlbe_gjj_policies = _filter_policy_items_last_24h(hlbe_gjj_policies, "hlbe_gjj_policy", now)
    btgjj_policies = _filter_policy_items_last_24h(btgjj_policies, "btgjj_policy", now)
    ordos_gjj_policies = _filter_policy_items_last_24h(ordos_gjj_policies, "ordos_gjj_zxgdw", now)
    whsgjj_zxwj_policies = _filter_policy_items_last_24h(whsgjj_zxwj_policies, "whsgjj_zxwj", now)
    xamzfgjj_zxwj_policies = _filter_policy_items_last_24h(xamzfgjj_zxwj_policies, "xamzfgjj_zxwj", now)
    xlglgjj_dfwj_policies = _filter_policy_items_last_24h(xlglgjj_dfwj_policies, "xlglgjj_dfwj", now)
    alszfgjj_policies = _filter_policy_items_last_24h(alszfgjj_policies, "alszfgjj_policy", now)
    hrvalue_policies = _filter_policy_items_last_24h(hrvalue_policies, "hrvalue_policy", now)
    govcn_policies = _filter_policy_items_last_24h(govcn_policies, "govcn_policy", now)
    heilongjiang_policies = _filter_policy_items_last_24h(heilongjiang_policies, "heilongjiang_hrss_policy", now)
    liaoning_policies = _filter_policy_items_last_24h(liaoning_policies, "liaoning_hrss_policy", now)
    shanghai_policies = _filter_policy_items_last_24h(shanghai_policies, "shanghai_hrss_policy", now)
    shanghai_gjj_policies = _filter_policy_items_last_24h(shanghai_gjj_policies, "shanghai_gjj_policy", now)
    taiyuan_gjj_policies = _filter_policy_items_last_24h(taiyuan_gjj_policies, "taiyuan_gjj_policy", now)
    shijiazhuang_policies = _filter_policy_items_last_24h(shijiazhuang_policies, "shijiazhuang_gjj_policy", now)
    zhengzhou_gjj_policies = _filter_policy_items_last_24h(zhengzhou_gjj_policies, "zhengzhou_gjj_law", now)
    shenyang_gjj_policies = _filter_policy_items_last_24h(shenyang_gjj_policies, "shenyang_gjj_zcfg", now)
    hrbgjj_policies = _filter_policy_items_last_24h(hrbgjj_policies, "hrb_gjj_zxwj", now)
    jlgjj_policies = _filter_policy_items_last_24h(jlgjj_policies, "jlgjj_gfxwj", now)
    hangzhou_gjj_policies = _filter_policy_items_last_24h(hangzhou_gjj_policies, "hangzhou_gjj_xzfg", now)
    hefei_gjj_policies = _filter_policy_items_last_24h(hefei_gjj_policies, "hefei_gjj_policy", now)
    fuzhou_gjj_policies = _filter_policy_items_last_24h(fuzhou_gjj_policies, "fuzhou_gjj_zcfg", now)
    nanchang_gjj_policies = _filter_policy_items_last_24h(nanchang_gjj_policies, "nanchang_gjj_zcfg", now)
    changsha_gjj_policies = _filter_policy_items_last_24h(changsha_gjj_policies, "changsha_gjj_wzjd", now)
    guangzhou_gjj_policies = _filter_policy_items_last_24h(guangzhou_gjj_policies, "guangzhou_gjj_policy", now)
    guilin_gjj_policies = _filter_policy_items_last_24h(guilin_gjj_policies, "guilin_gjj_zxwj", now)
    lanzhou_gjj_policies = _filter_policy_items_last_24h(lanzhou_gjj_policies, "lanzhou_gjj_policy", now)
    yinchuan_gjj_policies = _filter_policy_items_last_24h(yinchuan_gjj_policies, "yinchuan_gjj_policy", now)
    yqgjj_policies = _filter_policy_items_last_24h(yqgjj_policies, "yqgjj_policy", now)
    changzhi_policies = _filter_policy_items_last_24h(changzhi_policies, "changzhi_gjj_zxwj", now)
    jcgov_policies = _filter_policy_items_last_24h(jcgov_policies, "jcgov_policy", now)
    zf365_policies = _filter_policy_items_last_24h(zf365_policies, "zf365_tzgg", now)
    qdgjj_zcjd_policies = _filter_policy_items_last_24h(qdgjj_zcjd_policies, "qdgjj_zcjd", now)
    wuhan_gjj_policies = _filter_policy_items_last_24h(wuhan_gjj_policies, "wuhan_gjj_gfxwj", now)
    jiangsu_policies = _filter_policy_items_last_24h(jiangsu_policies, "jiangsu_hrss_policy", now)
    nanjing_gjj_policies = _filter_policy_items_last_24h(nanjing_gjj_policies, "nanjing_gjj_tzgg", now)
    zhejiang_policies = _filter_policy_items_last_24h(zhejiang_policies, "zhejiang_hrss_policy", now)
    anhui_policies = _filter_policy_items_last_24h(anhui_policies, "anhui_hrss_policy", now)
    fujian_policies = _filter_policy_items_last_24h(fujian_policies, "fujian_rst_bbmwj", now)
    jiangxi_policies = _filter_policy_items_last_24h(jiangxi_policies, "jiangxi_rst_policy", now)
    shandong_policies = _filter_policy_items_last_24h(shandong_policies, "shandong_hrss_policy", now)

    # 政策抓取结果汇总日志（便于排查“是否抓到/是否进入筛选”）
    policy_fetch_stats = [
        ("mohrss_dynamics", len(hit_dynamics)),
        ("mohrss_policy", len(hit_policies)),
        ("chinatax_policy", len(chinatax_policies)),
        ("beijing_policy", len(beijing_policies)),
        ("beijing_gjj_policy", len(beijing_gjj_policies)),
        ("chengdu_gjj_policy", len(chengdu_gjj_policies)),
        ("guiyang_gjj_policy", len(guiyang_gjj_policies)),
        ("kunming_gjj_policy", len(kunming_gjj_policies)),
        ("tianjin_gjj_policy", len(tianjin_gjj_policies)),
        ("cqgjj_gsgg", len(cqgjj_gsgg_policies)),
        ("tianjin_policy", len(tianjin_policies)),
        ("hebei_policy", len(hebei_policies)),
        ("shanxi_policy", len(shanxi_policies)),
        ("neimenggu_policy", len(neimenggu_policies)),
        ("jilin_policy", len(jilin_policies)),
        ("henan_hrss_policy", len(henan_policies)),
        ("hubei_rst_policy", len(hubei_policies)),
        ("hunan_rst_policy", len(hunan_policies)),
        ("guangdong_hrss_policy", len(guangdong_policies)),
        ("guangxi_rst_policy", len(guangxi_policies)),
        ("hainan_hrss_policy", len(hainan_policies)),
        ("chongqing_hrss_policy", len(chongqing_policies)),
        ("sichuan_rst_policy", len(sichuan_policies)),
        ("guizhou_rst_policy", len(guizhou_policies)),
        ("yunnan_hrss_policy", len(yunnan_policies)),
        ("xizang_hrss_policy", len(xizang_policies)),
        ("shaanxi_rst_policy", len(shaanxi_policies)),
        ("gansu_rst_policy", len(gansu_policies)),
        ("qinghai_rst_policy", len(qinghai_policies)),
        ("ningxia_hrss_policy", len(ningxia_policies)),
        ("xinjiang_rst_policy", len(xinjiang_policies)),
        ("hlbe_gjj_policy", len(hlbe_gjj_policies)),
        ("btgjj_policy", len(btgjj_policies)),
        ("ordos_gjj_zxgdw", len(ordos_gjj_policies)),
        ("whsgjj_zxwj", len(whsgjj_zxwj_policies)),
        ("xamzfgjj_zxwj", len(xamzfgjj_zxwj_policies)),
        ("xlglgjj_dfwj", len(xlglgjj_dfwj_policies)),
        ("alszfgjj_policy", len(alszfgjj_policies)),
        ("hrvalue_policy", len(hrvalue_policies)),
        ("govcn_policy", len(govcn_policies)),
        ("heilongjiang_hrss_policy", len(heilongjiang_policies)),
        ("liaoning_hrss_policy", len(liaoning_policies)),
        ("shanghai_hrss_policy", len(shanghai_policies)),
        ("shanghai_gjj_policy", len(shanghai_gjj_policies)),
        ("taiyuan_gjj_policy", len(taiyuan_gjj_policies)),
        ("shijiazhuang_gjj_policy", len(shijiazhuang_policies)),
        ("zhengzhou_gjj_law", len(zhengzhou_gjj_policies)),
        ("shenyang_gjj_zcfg", len(shenyang_gjj_policies)),
        ("hrb_gjj_zxwj", len(hrbgjj_policies)),
        ("jlgjj_gfxwj", len(jlgjj_policies)),
        ("hangzhou_gjj_xzfg", len(hangzhou_gjj_policies)),
        ("fuzhou_gjj_zcfg", len(fuzhou_gjj_policies)),
        ("nanchang_gjj_zcfg", len(nanchang_gjj_policies)),
        ("changsha_gjj_wzjd", len(changsha_gjj_policies)),
        ("guangzhou_gjj_policy", len(guangzhou_gjj_policies)),
        ("guilin_gjj_zxwj", len(guilin_gjj_policies)),
        ("lanzhou_gjj_policy", len(lanzhou_gjj_policies)),
        ("yinchuan_gjj_policy", len(yinchuan_gjj_policies)),
        ("qdgjj_zcjd", len(qdgjj_zcjd_policies)),
        ("wuhan_gjj_gfxwj", len(wuhan_gjj_policies)),
        ("nanjing_gjj_tzgg", len(nanjing_gjj_policies)),
        ("jiangsu_hrss_policy", len(jiangsu_policies)),
        ("zhejiang_hrss_policy", len(zhejiang_policies)),
        ("anhui_hrss_policy", len(anhui_policies)),
        ("fujian_rst_bbmwj", len(fujian_policies)),
        ("jiangxi_rst_policy", len(jiangxi_policies)),
        ("shandong_hrss_policy", len(shandong_policies)),
    ]
    print("[Policy Fetch] 各来源抓取条数：")
    for src, cnt in policy_fetch_stats:
        print(f"  - {src}: {cnt}")

    # 汇总判断
    all_empty = (
        not hit_dynamics and 
        not hit_policies and 
        not chinatax_policies and 
        not beijing_policies and 
        not beijing_gjj_policies and 
        not chengdu_gjj_policies and 
        not guiyang_gjj_policies and 
        not tianjin_policies and 
        not cqgjj_gsgg_policies and
        not hebei_policies and
        not shanxi_policies and
        not neimenggu_policies and
        not jilin_policies and
        not henan_policies and
        not hubei_policies and
        not hunan_policies and
        not guangdong_policies and
        not guangxi_policies and
        not hainan_policies and
        not chongqing_policies and
        not sichuan_policies and
        not guizhou_policies and
        not yunnan_policies and
        not xizang_policies and
        not shaanxi_policies and
        not gansu_policies and
        not qinghai_policies and
        not ningxia_policies and
        not xinjiang_policies and
        not hlbe_gjj_policies and
        not btgjj_policies and
        not ordos_gjj_policies and
        not whsgjj_zxwj_policies and
        not xamzfgjj_zxwj_policies and
        not xlglgjj_dfwj_policies and
        not alszfgjj_policies and
        not hrvalue_policies and
        not govcn_policies and
        not heilongjiang_policies and
        not liaoning_policies and
        not shanghai_policies and
        not shanghai_gjj_policies and
        not taiyuan_gjj_policies and
        not zhengzhou_gjj_policies and
        not shenyang_gjj_policies and
        not hrbgjj_policies and
        not jlgjj_policies and
        not jiangsu_policies and
        not zhejiang_policies and
        not anhui_policies and
        not fujian_policies and
        not jiangxi_policies and
        not shandong_policies
    )

    if all_empty:
        if not run_mohrss and not run_chinatax_env:
             lines.append("（本次未启用）")
        else:
             lines.append("（无更新或本次未命中）")
        return "\n\n".join(lines).strip(), []

    # 进行全局的历史排重
    hit_dynamics = filter_against_history(hit_dynamics, history_file, category="policy")
    hit_policies = filter_against_history(hit_policies, history_file, category="policy")
    chinatax_policies = filter_against_history(chinatax_policies, history_file, category="policy")
    beijing_policies = filter_against_history(beijing_policies, history_file, category="policy")
    beijing_gjj_policies = filter_against_history(beijing_gjj_policies, history_file, category="policy")
    chengdu_gjj_policies = filter_against_history(chengdu_gjj_policies, history_file, category="policy")
    guiyang_gjj_policies = filter_against_history(guiyang_gjj_policies, history_file, category="policy")
    kunming_gjj_policies = filter_against_history(kunming_gjj_policies, history_file, category="policy")
    tianjin_gjj_policies = filter_against_history(tianjin_gjj_policies, history_file, category="policy")
    cqgjj_gsgg_policies = filter_against_history(cqgjj_gsgg_policies, history_file, category="policy")
    tianjin_policies = filter_against_history(tianjin_policies, history_file, category="policy")
    hebei_policies = filter_against_history(hebei_policies, history_file, category="policy")
    shanxi_policies = filter_against_history(shanxi_policies, history_file, category="policy")
    neimenggu_policies = filter_against_history(neimenggu_policies, history_file, category="policy")
    jilin_policies = filter_against_history(jilin_policies, history_file, category="policy")
    henan_policies = filter_against_history(henan_policies, history_file, category="policy")
    hubei_policies = filter_against_history(hubei_policies, history_file, category="policy")
    hunan_policies = filter_against_history(hunan_policies, history_file, category="policy")
    guangdong_policies = filter_against_history(guangdong_policies, history_file, category="policy")
    guangxi_policies = filter_against_history(guangxi_policies, history_file, category="policy")
    hainan_policies = filter_against_history(hainan_policies, history_file, category="policy")
    chongqing_policies = filter_against_history(chongqing_policies, history_file, category="policy")
    sichuan_policies = filter_against_history(sichuan_policies, history_file, category="policy")
    guizhou_policies = filter_against_history(guizhou_policies, history_file, category="policy")
    yunnan_policies = filter_against_history(yunnan_policies, history_file, category="policy")
    xizang_policies = filter_against_history(xizang_policies, history_file, category="policy")
    shaanxi_policies = filter_against_history(shaanxi_policies, history_file, category="policy")
    gansu_policies = filter_against_history(gansu_policies, history_file, category="policy")
    qinghai_policies = filter_against_history(qinghai_policies, history_file, category="policy")
    ningxia_policies = filter_against_history(ningxia_policies, history_file, category="policy")
    xinjiang_policies = filter_against_history(xinjiang_policies, history_file, category="policy")
    hlbe_gjj_policies = filter_against_history(hlbe_gjj_policies, history_file, category="policy")
    btgjj_policies = filter_against_history(btgjj_policies, history_file, category="policy")
    ordos_gjj_policies = filter_against_history(ordos_gjj_policies, history_file, category="policy")
    whsgjj_zxwj_policies = filter_against_history(whsgjj_zxwj_policies, history_file, category="policy")
    xamzfgjj_zxwj_policies = filter_against_history(xamzfgjj_zxwj_policies, history_file, category="policy")
    xlglgjj_dfwj_policies = filter_against_history(xlglgjj_dfwj_policies, history_file, category="policy")
    alszfgjj_policies = filter_against_history(alszfgjj_policies, history_file, category="policy")
    hrvalue_policies = filter_against_history(hrvalue_policies, history_file, category="policy")
    govcn_policies = filter_against_history(govcn_policies, history_file, category="policy")
    heilongjiang_policies = filter_against_history(heilongjiang_policies, history_file, category="policy")
    liaoning_policies = filter_against_history(liaoning_policies, history_file, category="policy")
    shanghai_policies = filter_against_history(shanghai_policies, history_file, category="policy")
    shanghai_gjj_policies = filter_against_history(shanghai_gjj_policies, history_file, category="policy")
    taiyuan_gjj_policies = filter_against_history(taiyuan_gjj_policies, history_file, category="policy")
    zhengzhou_gjj_policies = filter_against_history(zhengzhou_gjj_policies, history_file, category="policy")
    shenyang_gjj_policies = filter_against_history(shenyang_gjj_policies, history_file, category="policy")
    hrbgjj_policies = filter_against_history(hrbgjj_policies, history_file, category="policy")
    jlgjj_policies = filter_against_history(jlgjj_policies, history_file, category="policy")
    hangzhou_gjj_policies = filter_against_history(hangzhou_gjj_policies, history_file, category="policy")
    hefei_gjj_policies = filter_against_history(hefei_gjj_policies, history_file, category="policy")
    fuzhou_gjj_policies = filter_against_history(fuzhou_gjj_policies, history_file, category="policy")
    nanchang_gjj_policies = filter_against_history(nanchang_gjj_policies, history_file, category="policy")
    changsha_gjj_policies = filter_against_history(changsha_gjj_policies, history_file, category="policy")
    guangzhou_gjj_policies = filter_against_history(guangzhou_gjj_policies, history_file, category="policy")
    guilin_gjj_policies = filter_against_history(guilin_gjj_policies, history_file, category="policy")
    lanzhou_gjj_policies = filter_against_history(lanzhou_gjj_policies, history_file, category="policy")
    yinchuan_gjj_policies = filter_against_history(yinchuan_gjj_policies, history_file, category="policy")
    qdgjj_zcjd_policies = filter_against_history(qdgjj_zcjd_policies, history_file, category="policy")
    wuhan_gjj_policies = filter_against_history(wuhan_gjj_policies, history_file, category="policy")
    jiangsu_policies = filter_against_history(jiangsu_policies, history_file, category="policy")
    nanjing_gjj_policies = filter_against_history(nanjing_gjj_policies, history_file, category="policy")
    zhejiang_policies = filter_against_history(zhejiang_policies, history_file, category="policy")
    anhui_policies = filter_against_history(anhui_policies, history_file, category="policy")
    fujian_policies = filter_against_history(fujian_policies, history_file, category="policy")
    jiangxi_policies = filter_against_history(jiangxi_policies, history_file, category="policy")
    shandong_policies = filter_against_history(shandong_policies, history_file, category="policy")

    # 政策文件关键词白名单：仅保留社保/医保/保险/人力资源相关条目
    hit_policies = _filter_policy_items_by_keywords(hit_policies, "mohrss_policy")
    chinatax_policies = _filter_policy_items_by_keywords(chinatax_policies, "chinatax_policy")
    beijing_policies = _filter_policy_items_by_keywords(beijing_policies, "beijing_policy")
    tianjin_policies = _filter_policy_items_by_keywords(tianjin_policies, "tianjin_policy")
    hebei_policies = _filter_policy_items_by_keywords(hebei_policies, "hebei_policy")
    shanxi_policies = _filter_policy_items_by_keywords(shanxi_policies, "shanxi_policy")
    neimenggu_policies = _filter_policy_items_by_keywords(neimenggu_policies, "neimenggu_policy")
    jilin_policies = _filter_policy_items_by_keywords(jilin_policies, "jilin_policy")
    henan_policies = _filter_policy_items_by_keywords(henan_policies, "henan_hrss_policy")
    hubei_policies = _filter_policy_items_by_keywords(hubei_policies, "hubei_rst_policy")
    hunan_policies = _filter_policy_items_by_keywords(hunan_policies, "hunan_rst_policy")
    guangdong_policies = _filter_policy_items_by_keywords(guangdong_policies, "guangdong_hrss_policy")
    guangxi_policies = _filter_policy_items_by_keywords(guangxi_policies, "guangxi_rst_policy")
    qinghai_policies = _filter_policy_items_by_keywords(qinghai_policies, "qinghai_rst_policy")
    gansu_policies = _filter_policy_items_by_keywords(gansu_policies, "gansu_rst_policy")
    ningxia_policies = _filter_policy_items_by_keywords(ningxia_policies, "ningxia_hrss_policy")
    xinjiang_policies = _filter_policy_items_by_keywords(xinjiang_policies, "xinjiang_rst_policy")
    hlbe_gjj_policies = _filter_policy_items_by_keywords(hlbe_gjj_policies, "hlbe_gjj_policy")
    btgjj_policies = _filter_policy_items_by_keywords(btgjj_policies, "btgjj_policy")
    ordos_gjj_policies = _filter_policy_items_by_keywords(ordos_gjj_policies, "ordos_gjj_zxgdw")
    whsgjj_zxwj_policies = _filter_policy_items_by_keywords(whsgjj_zxwj_policies, "whsgjj_zxwj")
    xamzfgjj_zxwj_policies = _filter_policy_items_by_keywords(xamzfgjj_zxwj_policies, "xamzfgjj_zxwj")
    xlglgjj_dfwj_policies = _filter_policy_items_by_keywords(xlglgjj_dfwj_policies, "xlglgjj_dfwj")
    alszfgjj_policies = _filter_policy_items_by_keywords(alszfgjj_policies, "alszfgjj_policy")
    hainan_policies = _filter_policy_items_by_keywords(hainan_policies, "hainan_hrss_policy")
    chongqing_policies = _filter_policy_items_by_keywords(chongqing_policies, "chongqing_hrss_policy")
    sichuan_policies = _filter_policy_items_by_keywords(sichuan_policies, "sichuan_rst_policy")
    guizhou_policies = _filter_policy_items_by_keywords(guizhou_policies, "guizhou_rst_policy")
    yunnan_policies = _filter_policy_items_by_keywords(yunnan_policies, "yunnan_hrss_policy")
    xizang_policies = _filter_policy_items_by_keywords(xizang_policies, "xizang_hrss_policy")
    shaanxi_policies = _filter_policy_items_by_keywords(shaanxi_policies, "shaanxi_rst_policy")
    hrvalue_policies = _filter_policy_items_by_keywords(hrvalue_policies, "hrvalue_policy")
    govcn_policies = _filter_policy_items_by_keywords(govcn_policies, "govcn_policy")
    heilongjiang_policies = _filter_policy_items_by_keywords(heilongjiang_policies, "heilongjiang_hrss_policy")
    liaoning_policies = _filter_policy_items_by_keywords(liaoning_policies, "liaoning_hrss_policy")
    hrbgjj_policies = _filter_policy_items_by_keywords(hrbgjj_policies, "hrb_gjj_zxwj")
    jlgjj_policies = _filter_policy_items_by_keywords(jlgjj_policies, "jlgjj_gfxwj")
    shanghai_policies = _filter_policy_items_by_keywords(shanghai_policies, "shanghai_hrss_policy")
    nanjing_gjj_policies = _filter_policy_items_by_keywords(nanjing_gjj_policies, "nanjing_gjj_tzgg")
    hangzhou_gjj_policies = _filter_policy_items_by_keywords(hangzhou_gjj_policies, "hangzhou_gjj_xzfg")
    hefei_gjj_policies = _filter_policy_items_by_keywords(hefei_gjj_policies, "hefei_gjj_policy")
    fuzhou_gjj_policies = _filter_policy_items_by_keywords(fuzhou_gjj_policies, "fuzhou_gjj_zcfg")
    nanchang_gjj_policies = _filter_policy_items_by_keywords(nanchang_gjj_policies, "nanchang_gjj_zcfg")
    changsha_gjj_policies = _filter_policy_items_by_keywords(changsha_gjj_policies, "changsha_gjj_wzjd")
    guangzhou_gjj_policies = _filter_policy_items_by_keywords(guangzhou_gjj_policies, "guangzhou_gjj_policy")
    guilin_gjj_policies = _filter_policy_items_by_keywords(guilin_gjj_policies, "guilin_gjj_zxwj")
    lanzhou_gjj_policies = _filter_policy_items_by_keywords(lanzhou_gjj_policies, "lanzhou_gjj_policy")
    yinchuan_gjj_policies = _filter_policy_items_by_keywords(yinchuan_gjj_policies, "yinchuan_gjj_policy")
    qdgjj_zcjd_policies = _filter_policy_items_by_keywords(qdgjj_zcjd_policies, "qdgjj_zcjd")
    wuhan_gjj_policies = _filter_policy_items_by_keywords(wuhan_gjj_policies, "wuhan_gjj_gfxwj")
    jiangsu_policies = _filter_policy_items_by_keywords(jiangsu_policies, "jiangsu_hrss_policy")
    zhejiang_policies = _filter_policy_items_by_keywords(zhejiang_policies, "zhejiang_hrss_policy")
    anhui_policies = _filter_policy_items_by_keywords(anhui_policies, "anhui_hrss_policy")
    fujian_policies = _filter_policy_items_by_keywords(fujian_policies, "fujian_rst_bbmwj")
    jiangxi_policies = _filter_policy_items_by_keywords(jiangxi_policies, "jiangxi_rst_policy")
    shandong_policies = _filter_policy_items_by_keywords(shandong_policies, "shandong_hrss_policy")
    kunming_gjj_policies = _filter_policy_items_by_keywords(kunming_gjj_policies, "kunming_gjj_policy")

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
        or beijing_gjj_policies
        or chengdu_gjj_policies
        or guiyang_gjj_policies
        or kunming_gjj_policies
        or lanzhou_gjj_policies
        or yinchuan_gjj_policies
        or tianjin_policies
        or cqgjj_gsgg_policies
        or hebei_policies
        or shanxi_policies
        or neimenggu_policies
        or jilin_policies
        or henan_policies
        or hubei_policies
        or hunan_policies
        or guangdong_policies
        or guangxi_policies
        or hainan_policies
        or chongqing_policies
        or sichuan_policies
        or guizhou_policies
        or yunnan_policies
        or xizang_policies
        or shaanxi_policies
        or gansu_policies
        or qinghai_policies
        or ningxia_policies
        or xinjiang_policies
        or hlbe_gjj_policies
        or btgjj_policies
        or ordos_gjj_policies
        or whsgjj_zxwj_policies
        or xamzfgjj_zxwj_policies
        or xlglgjj_dfwj_policies
        or tlzfgjj_policies
        or cfszfgjj_policies
        or hrvalue_policies
        or govcn_policies
        or heilongjiang_policies
        or liaoning_policies
        or shanghai_policies
        or shanghai_gjj_policies
        or taiyuan_gjj_policies
        or zhengzhou_gjj_policies
        or shenyang_gjj_policies
        or jiangsu_policies
        or zhejiang_policies
        or anhui_policies
        or fujian_policies
        or jiangxi_policies
        or shandong_policies
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
        for it in beijing_gjj_policies:
            title = f"【北京公积金-{it.get('source', '政策文件')}】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in chengdu_gjj_policies:
            title = f"【成都公积金-{it.get('source', '政策文件')}】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in guiyang_gjj_policies:
            title = f"【贵阳公积金-{it.get('source', '政策文件')}】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in kunming_gjj_policies:
            title = f"【昆明公积金-政策文件】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in tianjin_gjj_policies:
            title = f"【天津公积金-{it.get('source', '政策文件')}】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in tianjin_policies:
            title = f"【天津】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in cqgjj_gsgg_policies:
            title = f"【重庆公积金】{it['title']}"
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
        for it in jilin_policies:
            title = f"【吉林】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in henan_policies:
            title = f"【河南】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in hubei_policies:
            title = f"【湖北】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in hunan_policies:
            title = f"【湖南】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in guangdong_policies:
            title = f"【广东】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in guangxi_policies:
            title = f"【广西】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in hainan_policies:
            title = f"【海南】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in chongqing_policies:
            title = f"【重庆】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in sichuan_policies:
            title = f"【四川】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in guizhou_policies:
            title = f"【贵州】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in yunnan_policies:
            title = f"【云南】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in xizang_policies:
            title = f"【西藏】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in shaanxi_policies:
            title = f"【陕西】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in gansu_policies:
            title = f"【甘肃】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in qinghai_policies:
            title = f"【青海】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in ningxia_policies:
            title = f"【宁夏】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in xinjiang_policies:
            title = f"【新疆】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in hlbe_gjj_policies:
            title = f"【呼伦贝尔公积金】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in btgjj_policies:
            title = f"【包头公积金】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in hrvalue_policies:
            title = f"【HR价值网】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in govcn_policies:
            title = f"【中国政府网】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in heilongjiang_policies:
            title = f"【黑龙江】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in liaoning_policies:
            title = f"【辽宁】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in shanghai_policies:
            title = f"【上海】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in shanghai_gjj_policies:
            title = f"【上海公积金-{it.get('source', '政策文件')}】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in taiyuan_gjj_policies:
            title = f"【太原公积金-{it.get('source', '通知公告')}】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in zhengzhou_gjj_policies:
            title = f"【郑州公积金-{it.get('source', '行政规范性文件')}】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in shenyang_gjj_policies:
            title = f"【沈阳公积金-{it.get('source', '政策法规')}】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in hrbgjj_policies:
            title = f"【哈尔滨公积金-{it.get('source', '中心文件')}】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in jlgjj_policies:
            title = f"【吉林公积金-政策文件】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in nanjing_gjj_policies:
            title = f"【南京公积金-通知公告】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in hangzhou_gjj_policies:
            title = f"【杭州公积金-行政规范性文件】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in hefei_gjj_policies:
            title = f"【合肥公积金-政策文件】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in fuzhou_gjj_policies:
            title = f"【福州公积金-政策法规】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in nanchang_gjj_policies:
            title = f"【南昌公积金-政策法规】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in changsha_gjj_policies:
            title = f"【长沙公积金-文字解读】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in guangzhou_gjj_policies:
            title = f"【广州公积金-规范性文件】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in guilin_gjj_policies:
            title = f"【桂林公积金-中心文件】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in tsgjj_policies:
            title = f"【TSGJJ-中心文件】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in lanzhou_gjj_policies:
            title = f"【兰州公积金-政策法规】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in yinchuan_gjj_policies:
            title = f"【银川公积金-政策法规】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in qdgjj_zcjd_policies:
            title = f"【青岛公积金-政策解读】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in qhdgjj_policies:
            title = f"【秦皇岛公积金-通知公告】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in handan_gjj_policies:
            title = f"【邯郸公积金-政策法规】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in xingtai_gjj_policies:
            title = f"【邢台公积金-政策】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in baoding_gjj_policies:
            title = f"【保定公积金-中心文件】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in zjkgjj_policies:
            title = f"【张家口公积金-规范性文件】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in chengde_gjj_policies:
            title = f"【承德公积金-通知公告】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in cangzhou_gjj_policies:
            title = f"【沧州公积金-通知公告】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for item in hszfgjj_policies:
            title = item.get('title', '')
            link = item.get('link', '')
            pub_time = item.get('pub_time', '')
            if title:
                lines.append(f"【衡水公积金-政策法规】{pub_time} {title} {link}")
        for it in lfzfgjj_policies:
            title = f"【廊坊公积金-通知公告】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in tlzfgjj_policies:
            title = f"【通辽公积金-通知公告】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in cfszfgjj_policies:
            title = f"【赤峰公积金-政策法规】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in ordos_gjj_policies:
            title = f"【鄂尔多斯公积金-中心规定文件】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in alszfgjj_policies:
            title = f"【阿拉善盟公积金-政策法规】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in whsgjj_zxwj_policies:
            title = f"【乌海公积金-中心文件】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in xamzfgjj_zxwj_policies:
            title = f"【兴安盟公积金-中心文件】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in xlglgjj_dfwj_policies:
            title = f"【锡盟公积金-地方文件】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in wuhan_gjj_policies:
            title = f"【武汉公积金-规范性文件】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in jiangsu_policies:
            title = f"【江苏】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in zhejiang_policies:
            title = f"【浙江】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in anhui_policies:
            title = f"【安徽】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in fujian_policies:
            title = f"【福建】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in jiangxi_policies:
            title = f"【江西】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1
        for it in shandong_policies:
            title = f"【山东】{it['title']}"
            policy_items_all.append({"title": title, "url": it["url"]})
            lines.append(md_item_with_detail(idx, title, it["url"]))
            idx += 1

        # 政策文件标题统一去掉开头的【】标签，保留纯标题展示。
        for i, line in enumerate(lines):
            lines[i] = re.sub(r"^(\d+\.\s*)【[^】]{1,30}】", r"\1", line)
        for it in policy_items_all:
            it["title"] = _strip_leading_tag((it.get("title") or "").strip())

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
    setup_logging()
    
    # 允许在周末运行

    run_hrloo = (os.getenv("RUN_HRLOO", "1").strip() != "0")
    run_sina = (os.getenv("RUN_SINA", "1").strip() != "0")
    run_mohrss = (os.getenv("RUN_MOHRSS", "1").strip() != "0")
    history_file = os.getenv("INSIGHT_HISTORY_FILE", "insight_history.jsonl")

    enterprise_block, enterprise_items = build_enterprise_block(run_hrloo, run_sina, history_file=history_file)
    policy_block, policy_items = build_policy_block(run_mohrss, history_file=history_file)

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
        # 历史记录拉长到 6 个月 = 180 天
        recent_history = load_recent_history(history_file, days=180)
        enterprise_today_items = [it for it in insight_input_items if it.get("category") == "enterprise"]
        enterprise_today_count = len(enterprise_today_items)
        similar_hits = call_ai_behavior_similarity_hits(enterprise_today_items, recent_history)
        trend_impact_hit, trend_impact_reason = call_ai_industry_trend_impact_hit(enterprise_today_items, recent_history)

        print(
            f"[Insight] 触发检查: 当日高价值新闻={enterprise_today_count}, "
            f"历史相似命中={similar_hits}, 行业趋势影响命中={trend_impact_hit}"
        )

        # 触发阈值：当日至少一条高价值新闻 + (历史相似命中 >=2 或 行业趋势影响命中)
        if enterprise_today_count >= 1 and (similar_hits >= 2 or trend_impact_hit):
            try:
                insight_block = call_ai_daily_insight(insight_input_items, recent_history)
            except Exception as e:
                print(f"[Insight] AI 洞察生成失败: {e}")
                insight_block = ""

            if (not insight_block or insight_block.strip() == INSIGHT_SKIP_TOKEN) and trend_impact_hit:
                insight_block = _build_fallback_insight(trend_impact_reason, enterprise_today_items)
                print("[Insight] AI 返回 NO_INSIGHT，已启用规则兜底洞察")
        else:
            insight_block = INSIGHT_SKIP_TOKEN

    md = build_markdown(enterprise_block, policy_block, insight_block)

    run_date = now_cn().strftime("%Y-%m-%d")
    write_ok = append_history_items(history_file, run_date, insight_input_items)
    verify_ok, missing_items = verify_history_items_written(history_file, insight_input_items)
    can_send_dingtalk = True

    if not write_ok or not verify_ok:
        can_send_dingtalk = False
        print("[History Guard] 检测到历史记录未完整写入，已阻断钉钉发送")
        if missing_items:
            print(f"[History Guard] 缺失条数: {len(missing_items)}")
            for it in missing_items[:5]:
                print(f"[History Guard] 缺失新闻: {(it.get('title') or '').strip()}")

    out_file = os.getenv("OUT_FILE", "daily_all.md")
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(md)

    title = f"{now_cn().strftime('%m-%d')} 每日简报"
    
    if can_send_dingtalk:
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
    else:
        print("⚠️ DingTalk Skip: 历史记录写入校验失败")
        
    print("✅ wrote:", out_file)


if __name__ == "__main__":
    main()
