# -*- coding: utf-8 -*-
import os
import requests
import json
import re
import html

# ===================== AI 智能筛选 =====================
# 优先读取环境变量；如果环境变量不存在或为空字符串，则使用默认的硬编码 Key
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
if not DASHSCOPE_API_KEY:
    DASHSCOPE_API_KEY = "sk-86fa3d1f35784c80a85640bb1df05909"

# 使用更强理解能力的模型进行筛选和摘要
DASHSCOPE_MODEL   = "qwen-plus" 

OTHER_HR_COMPANY_KEYWORDS = [
    "fesco", "中智", "科锐国际", "人瑞人才", "万宝盛华", "得科", "任仕达",
    "前程无忧", "智联招聘", "猎聘", "boss直聘", "58同城", "中华英才网",
]

TECH_BREAKTHROUGH_KEYWORDS = [
    "技术突破", "重大突破", "实现突破", "核心技术", "关键技术", "攻克", "首创", "首个",
    "自主研发", "发布大模型", "技术升级", "工艺突破", "算力突破",
]

LARGE_COMPANY_NEW_BIZ_KEYWORDS = [
    "成立新部门", "新设部门", "成立事业部", "新设事业部", "成立研究院", "新设研究院",
    "成立子公司", "新设子公司", "上线新业务", "发布新业务", "布局新业务", "拓展新业务",
    "进军", "切入", "开辟新赛道",
]

FINANCIAL_NEWS_KEYWORDS = [
    "财报", "业绩", "营收", "收入", "净利润", "归母净利润", "年报", "季报", "半年报",
]

NEGATIVE_FINANCIAL_KEYWORDS = [
    "负增长", "同比下滑", "同比下降", "营收下滑", "收入下滑", "由盈转亏", "亏损", "净亏损",
    "利润下滑", "业绩下滑", "营收下降", "收入下降",
]

LOW_REVENUE_HINT_KEYWORDS = [
    "营收仅", "收入仅", "营收不足", "收入不足", "营收不到", "收入不到", "营收低于", "收入低于",
]

LATE_STAGE_FINANCING_PATTERNS = [
    r"\b[bB]轮\b", r"B\+轮", r"C轮", r"D轮", r"E轮", r"F轮", r"G轮", r"H轮",
    r"战略融资", r"pre-ipo", r"Pre-IPO", r"IPO前", r"上市前融资", r"并购融资",
]

EARLY_STAGE_FINANCING_PATTERNS = [
    r"天使轮", r"种子轮", r"A轮", r"Pre-A", r"pre-a", r"A\+轮",
]

INDUSTRY_TAG_CANDIDATES = [
    "车企", "AI", "半导体", "互联网", "金融", "医药", "能源", "消费",
    "制造", "物流", "地产", "教育", "人力资源", "科技", "创投", "企业",
]

_INDUSTRY_TAG_CACHE: dict[str, str] = {}


def _is_other_hr_company_news(text: str) -> bool:
    """
    硬规则：剔除关于其他人力资源公司（竞品/同行）的公司动态新闻。
    """
    if not text:
        return False
    lowered = text.lower()
    return any(k in lowered for k in OTHER_HR_COMPANY_KEYWORDS)


def _contains_any_keyword(text: str, keywords: list[str]) -> bool:
    return any(k in text for k in keywords)


def _matches_any_pattern(text: str, patterns: list[str]) -> bool:
    return any(re.search(p, text) for p in patterns)


def _is_financial_news(title: str) -> bool:
    return _contains_any_keyword(title, FINANCIAL_NEWS_KEYWORDS)


def _is_hard_keep_by_business_rules(title: str) -> bool:
    """
    用户新增规则中的“必须保留”项：
    1) 技术突破；2) B轮及之后融资；3) 大公司新部门/新业务。
    """
    if not title:
        return False

    if _contains_any_keyword(title, TECH_BREAKTHROUGH_KEYWORDS):
        return True

    if "融资" in title and _matches_any_pattern(title, LATE_STAGE_FINANCING_PATTERNS):
        return True

    if _contains_any_keyword(title, LARGE_COMPANY_NEW_BIZ_KEYWORDS):
        return True

    return False


def _is_hard_drop_by_business_rules(title: str) -> bool:
    """
    用户新增规则中的“必须剔除”项：
    - 财报/营收类中的负增长或明显低收入提示；
    - 融资新闻中的早期轮次（天使/A轮及之前）。
    """
    if not title:
        return False

    if _is_financial_news(title):
        if _contains_any_keyword(title, NEGATIVE_FINANCIAL_KEYWORDS):
            return True
        if _contains_any_keyword(title, LOW_REVENUE_HINT_KEYWORDS):
            return True

    if "融资" in title and _matches_any_pattern(title, EARLY_STAGE_FINANCING_PATTERNS):
        return True

    return False


def _summary_looks_truncated(summary: str) -> bool:
    """
    判断摘要是否像是被模型在句子中途截断。
    """
    cleaned = (summary or "").strip()
    if not cleaned:
        return False

    if re.search(r"\d+\.$", cleaned):
        return True

    if cleaned.endswith(("，", ",", "、", "：", ":", "（", "(", "-", "—", "/")):
        return True

    sentence_endings = "。！？!?…"
    if cleaned[-1] not in sentence_endings:
        if len(cleaned) >= 30 and re.search(r"[，,；;：:]", cleaned):
            return True
        if re.search(r"(支持|帮助|覆盖|面向|针对|服务|用于|聚焦|瞄准|推动|提供|包括|涉及|来自|由|对|向|受)$", cleaned):
            return True

    return bool(re.search(r"(同比|环比|增长|下降|增至|降至|达到|达|至|为|共|约)$", cleaned))


def _strip_html_tags(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _duckduckgo_search_snippets(query: str, max_results: int = 5) -> list[str]:
    """
    轻量联网搜索：抓取 DuckDuckGo HTML 搜索页标题与摘要片段。
    """
    if not query:
        return []

    url = "https://duckduckgo.com/html/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        resp = requests.get(url, params={"q": query, "kl": "cn-zh"}, headers=headers, timeout=12)
        resp.raise_for_status()
        page = resp.text

        title_matches = re.findall(r'<a[^>]*class="result__a"[^>]*>(.*?)</a>', page, flags=re.I | re.S)
        snippet_matches = re.findall(r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>', page, flags=re.I | re.S)

        merged = []
        for i in range(min(max_results, max(len(title_matches), len(snippet_matches)))):
            t = _strip_html_tags(title_matches[i]) if i < len(title_matches) else ""
            s = _strip_html_tags(snippet_matches[i]) if i < len(snippet_matches) else ""
            line = f"{t} | {s}".strip(" |")
            if line:
                merged.append(line)
        return merged
    except Exception:
        return []


def _normalize_industry_tag(raw_tag: str) -> str:
    if not raw_tag:
        return "企业"
    cleaned = raw_tag.strip().replace("【", "").replace("】", "")
    for tag in INDUSTRY_TAG_CANDIDATES:
        if tag in cleaned:
            return tag
    return "企业"


def call_ai_industry_tag_with_web(title: str, summary: str = "", url: str = "") -> str:
    """
    使用“联网搜索片段 + AI”识别公司行业标签。
    返回值限制在 INDUSTRY_TAG_CANDIDATES 内。
    """
    if not title:
        return "企业"

    cache_key = re.sub(r"\s+", " ", f"{title}|{summary}|{url}").strip().lower()
    if cache_key in _INDUSTRY_TAG_CACHE:
        return _INDUSTRY_TAG_CACHE[cache_key]

    query = re.sub(r"^【[^】]{1,12}】", "", title).strip()
    search_lines = _duckduckgo_search_snippets(f"{query} 公司 行业", max_results=5)
    if not search_lines and url:
        search_lines = _duckduckgo_search_snippets(f"{query} {url} 公司", max_results=5)

    web_context = "\n".join(f"- {x}" for x in search_lines) if search_lines else "- （未获取到有效搜索结果）"

    system_prompt = (
        "你是企业行业分类助手。请基于新闻标题、摘要和联网搜索片段判断公司行业。\n"
        "可选标签仅限：车企、AI、半导体、互联网、金融、医药、能源、消费、制造、物流、地产、教育、人力资源、科技、创投、企业。\n"
        "输出要求：只输出1个标签，不要解释。"
    )
    user_prompt = (
        f"标题：{title}\n"
        f"摘要：{summary or '（无）'}\n"
        f"原文链接：{url or '（无）'}\n"
        f"联网搜索片段：\n{web_context}\n"
        "请输出唯一行业标签："
    )

    headers = {
        "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": DASHSCOPE_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0,
    }

    try:
        api_url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
        resp = requests.post(api_url, headers=headers, json=payload, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        _log_token_usage(data, "IndustryTag")
        content = data["choices"][0]["message"]["content"].strip()
        tag = _normalize_industry_tag(content)
        _INDUSTRY_TAG_CACHE[cache_key] = tag
        return tag
    except Exception:
        return "企业"

def _log_token_usage(response_data: dict, context: str):
    """
    Log token usage from DashScope API response.
    """
    try:
        usage = response_data.get("usage", {})
        total_tokens = usage.get("total_tokens", 0)
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        if total_tokens > 0:
            print(f"[Token Usage] {context}: {total_tokens} (In: {input_tokens}, Out: {output_tokens})")
    except Exception:
        pass

def call_ai_filter(titles: list[str]) -> list[bool]:
    """
    通过 DashScope API 筛选有利于人力资源公司（尤其是人力资源外包）的信息。
    """
    if not titles:
        return []
    
    # 构造 Prompt
    system_prompt = (
        "你是一位服务于'人力资源外包（HRO）'企业的资深情报分析师。你的唯一任务是筛选出**直接影响人力资源外包业务**的新闻。"
        "哪怕新闻看起来很热门，只要不影响外包生意（派遣/外包/薪酬社保代理/RPO），统统剔除。宁缺毋滥。\n\n"
        "【必须保留的高价值情报】（符合任一即保留）：\n"
        "1. **甲方用工剧变（直接商机/风险）**：\n"
        "   - 头部企业（如互联网/制造/能源大厂）的大规模招聘（RPO机会）、大裁员（裁员辅助/合规风险）、搬迁或新设工厂（蓝领外包机会）。\n"
        "   - 明确提及'人员外包'、'灵活用工'、'劳务派遣'、'业务外包'招标或需求的动态。\n"
        "2. **硬核政策法规（成本与合规）**：\n"
        "   - 只有涉及：社保/公积金费率调整、最低工资、个税政策、劳动法修订、劳务派遣暂行规定修缮、特殊工时审批等直接改变**用工成本**或**合规底线**的政策。\n"
        "3. **用工模式变革**：\n"
        "   - 涉及零工经济平台、共享员工、众包模式的监管或数据报告。\n"
        "4. **企业技术突破**：\n"
        "   - 只要明确出现关键技术突破、核心技术攻克、行业首创等信息，保留。\n"
        "5. **企业财报/营收（有条件保留）**：\n"
        "   - 仅保留营收体量较大或增长明显的企业财报/营收新闻。\n"
        "   - 负增长、亏损扩大、收入规模明显偏小的一律剔除。\n"
        "6. **企业融资（轮次门槛）**：\n"
        "   - 保留 B 轮及之后（B/C/D/E/战略融资/Pre-IPO 等）融资新闻。\n"
        "   - 天使轮、种子轮、A轮及更早轮次默认剔除。\n"
        "7. **大公司组织与业务扩张**：\n"
        "   - 大公司成立新部门、事业部、研究院，或发布/布局新业务，保留。\n\n"
        "【必须无情剔除的噪音】（凡是沾边的一律False）：\n"
        "- **其他人力资源公司动态**：FESCO、中智、科锐国际、人瑞人才、万宝盛华、得科、任仕达等同行公司的财报、融资、并购、发布会、人事变动。\n"
        "- **内训与职场鸡汤**：'如何提升领导力'、'职场沟通技巧'、'HR如何做绩效'（这是给甲方HR看的，外包公司不关心）。\n"
        "- **无关宏观与个股**：'某公司股价涨跌'、'GDP预测'、'某行业大会召开'（除非明确讲就业规模变化）。\n"
        "- **普通企业新闻**：'某公司发布新手机'、'某车企销量夺冠'（除非提到扩招/裁员/建厂/技术突破/新业务）。\n"
        "- **海外无关动态**：发生在海外且未提及对华影响的罢工、政策或人事变动。\n"
        "- **泛SaaS/技术**：'某公司上线新OA'、'AI技术原理'（除非是专门的招聘/算薪SaaS竞品）。\n"
        "- **民生福利**：人才公寓、一般性人才补贴（除非直接补贴给企业/外包商）。\n\n"
        "【输出要求】\n"
        "请返回一个 JSON 数组，长度与输入数组严格一致，只包含 true 或 false。\n"
        "true = 这是一个影响外包生意的关键情报。\n"
        "false = 这对做外包业务没啥用。\n"
        "例如：[true, false, true...]"
    )
    
    # 将 list 转 json string
    user_content = json.dumps(titles, ensure_ascii=False)
    
    headers = {
        "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": DASHSCOPE_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"新闻标题列表：\n{user_content}"}
        ],
        "temperature": 0.1
    }
    
    try:
        # 使用 dashscope 兼容 OpenAI 的 endpoint
        url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
        resp = requests.post(url, headers=headers, json=payload, timeout=20)
        resp.raise_for_status()
        
        data = resp.json()
        _log_token_usage(data, "Filter")
        content = data["choices"][0]["message"]["content"]
        
        # 清洗可能存在的 markdown 代码块
        content = re.sub(r"```json|```", "", content).strip()
        
        # 解析 JSON
        flags = json.loads(content)
        
        if isinstance(flags, list) and len(flags) == len(titles):
            return [bool(f) for f in flags]
        
        print(f"[AI Filter] 警告：返回长度 ({len(flags)}) 与输入 ({len(titles)}) 不一致，保留全部。")
        return [True] * len(titles)
        
    except Exception as e:
        print(f"[AI Filter] 调用失败：{e}，保留全部。")
        return [True] * len(titles)

def call_ai_check_relevance(title: str, summary: str) -> bool:
    """
    二次筛选：基于标题和摘要，判断文章是否对人力资源行业有实际影响。
    用于在摘要生成后，踢出看起来有关但实际内容无关的新闻。
    """
    if _is_other_hr_company_news(f"{title}\n{summary}"):
        return False

    if not summary or len(summary) < 10:
        return True # 如果没有摘要，默认保留，以免误删
        
    system_prompt = (
        "你是一位人力资源行业的高级情报官。请基于新闻标题和摘要，进行二次严格审查。\n"
        "判断该新闻是否对**人力资源外包、招聘、派遣、薪酬社保、劳动法合规**等业务有实质性影响。\n\n"
        "【判定标准】\n"
        "1. **保留** (True)：\n"
        "   - 涉及企业裁员、大规模招聘、迁址、用工纠纷。\n"
        "   - 涉及社保公积金、个税、最低工资、劳动法政策变化。\n"
        "   - 涉及灵活用工、零工经济平台监管。\n"
        "   - 涉及企业明确的技术突破。\n"
        "   - 涉及 B 轮及之后融资（B/C/D/E/战略融资/Pre-IPO）。\n"
        "   - 涉及大公司成立新部门、事业部、研究院或布局新业务。\n"
        "   - 涉及财报/营收且属于高收入或高增长企业。\n"
        "2. **剔除** (False)：\n"
        "   - 其他人力资源公司（竞品/同行）的公司动态新闻。\n"
        "   - 财报/营收中出现负增长、亏损扩大、收入偏小。\n"
        "   - 天使轮、种子轮、A轮融资新闻。\n"
        "   - 纯粹的产品发布会（如发布新手机/新车，未提及工厂招工）。\n"
        "   - 泛泛的宏观经济分析（GDP、CPI等，未落实到就业）。\n"
        "   - 职场鸡汤、管理心得、内训资料。\n"
        "   - 与中国市场无关的海外新闻。\n\n"
        "【输出要求】\n"
        "仅输出 true 或 false，不要输出任何解释或标点符号。\n"
        "true = 保留\n"
        "false = 删除"
    )
    
    user_content = f"标题：{title}\n摘要：{summary}"
    
    headers = {
        "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": DASHSCOPE_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        "temperature": 0.1
    }
    
    try:
        url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
        resp = requests.post(url, headers=headers, json=payload, timeout=20)
        resp.raise_for_status()
        
        data = resp.json()
        _log_token_usage(data, "Check Relevance")
        content = data["choices"][0]["message"]["content"].strip().lower()
        
        if "true" in content:
            return True
        if "false" in content:
            return False
        return True # 默认保留
        
    except Exception as e:
        print(f"[AI Check] 二次筛选调用失败: {e}，默认保留。")
        return True

def call_ai_deduplicate(items: list[dict]) -> list[dict]:
    """
    对最终的新闻列表进行去重。
    将所有新闻标题+摘要发给 AI，让 AI 识别是否报道了同一件事。
    如果有重复，保留信息量最大的一条。
    返回去重后的 items 列表。
    """
    if not items or len(items) < 2:
        return items

    print(f"[AI Deduplicate]正在对 {len(items)} 条新闻进行去重检查...")
    
    # 构造输入列表，带上索引
    # 格式：
    # 1. <Title>
    #    <Summary>
    prompt_text = ""
    for i, it in enumerate(items):
        t = it.get("title", "无标题")
        s = it.get("summary", "")[:100] # 摘要截取前100字避免过长
        src = it.get("source", "未知网站")
        prompt_text += f"No.{i}\nTitle: {t}\nSummary: {s}\nSource: {src}\n\n"

    system_prompt = (
        "你是一个极其严格的新闻去重专家。你的任务是找出**核心事件或报道主体完全一致**的重复新闻，尤其是那些来自不同网站或相同网站但表述略有差异的相似报道。\n"
        "【判断标准】\n"
        "1. **完全重复（不同网站的相同新闻，或同网站的类似新闻）**：\n"
        "   - 针对同一个具体的事件或核心主体（如“某公司发布财报”、“某公司发布新产品”、“某地出台新政策”）。\n"
        "   - 即使新闻的具体内容、字数有一定区别，或者不同网站的标题写法不同，只要报道的核心主旨、主体内容一致，即视为重复。\n"
        "   - 例子：“贾国龙新品牌落地北京” 与 “西贝贾国龙推新品牌” -> 核心都是贾国龙推新品牌事件，算重复。\n"
        "2. **非重复**：\n"
        "   - 同一公司的完全不同的独立事件（如“A公司发财报”与“A公司高管变更”，虽然公司相同但事件不同）。\n"
        "   - 相似话题但通过的政策/发生的地点完全不同。\n\n"
        "【操作】\n"
        "对于重复的一组新闻，只保留**信息量最丰富或最权威**（通常摘要更详细或标题更完整）的那一条。\n"
        "对于不重复的新闻，全部保留。\n\n"
        "【输出格式】\n"
        "请返回一个 JSON 数组，包含由你**保留**的新闻的编号（No.后面的数字）。\n"
        "例如：[0, 2, 5, 8]\n"
        "只返回数字列表，不要任何废话。"
    )

    headers = {
        "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": DASHSCOPE_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt_text}
        ],
        "temperature": 0.1
    }

    try:
        url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
        resp = requests.post(url, headers=headers, json=payload, timeout=40)
        resp.raise_for_status()
        
        data = resp.json()
        _log_token_usage(data, "Deduplicate")
        content = data["choices"][0]["message"]["content"]
        content = re.sub(r"```json|```", "", content).strip()
        
        # 尝试解析
        keep_indices = json.loads(content)
        if not isinstance(keep_indices, list):
            print("[AI Deduplicate] 返回格式错误(不是list)，跳过去重。")
            return items
            
        # 过滤出合法的 index
        valid_indices = set()
        for idx in keep_indices:
            try:
                idx_int = int(idx)
                if 0 <= idx_int < len(items):
                    valid_indices.add(idx_int)
            except:
                pass
        
        if not valid_indices:
            print("[AI Deduplicate] 解析后无有效索引，跳过去重。")
            return items

        # 按原顺序重组
        deduplicated = []
        for i in range(len(items)):
            if i in valid_indices:
                deduplicated.append(items[i])
            else:
                print(f"  -> [Duplicate] 剔除重复/低质项: {items[i].get('title', '')}")
                
        print(f"[AI Deduplicate] 去重完成：{len(items)} -> {len(deduplicated)}")
        return deduplicated

    except Exception as e:
        print(f"[AI Deduplicate] 调用失败: {e}，跳过去重。")
        return items


def _call_ai_extract_company_names(items: list[dict]) -> list[str]:
    """
    为每条新闻提取公司名（无法判断则返回空字符串）。
    返回长度必须与 items 一致。
    """
    if not items:
        return []

    prompt_text = ""
    for i, it in enumerate(items):
        t = it.get("title", "无标题")
        s = (it.get("summary", "") or "")[:120]
        prompt_text += f"No.{i}\nTitle: {t}\nSummary: {s}\n\n"

    system_prompt = (
        "你是企业识别助手。请从每条新闻中提取核心公司主体名称。\n"
        "要求：\n"
        "1) 输出 JSON 数组，长度与输入严格一致。\n"
        "2) 每个元素是公司名字符串，例如“长安汽车”“比亚迪”。\n"
        "3) 如果无法判断公司，输出空字符串。\n"
        "4) 不要输出任何解释。"
    )

    headers = {
        "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": DASHSCOPE_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt_text}
        ],
        "temperature": 0
    }

    try:
        url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        _log_token_usage(data, "CompanyNameExtract")
        content = data["choices"][0]["message"]["content"]
        content = re.sub(r"```json|```", "", content).strip()
        names = json.loads(content)
        if isinstance(names, list) and len(names) == len(items):
            return [str(x).strip() for x in names]
    except Exception:
        pass

    return [""] * len(items)


def _call_ai_pick_max_impact_index_for_same_company(company: str, group_items: list[dict]) -> int:
    """
    对同一家公司的一组新闻，返回“影响最大”的组内索引（0-based）。
    失败时返回 -1。
    """
    if not group_items:
        return -1
    if len(group_items) == 1:
        return 0

    prompt_text = ""
    for i, it in enumerate(group_items):
        t = it.get("title", "无标题")
        s = (it.get("summary", "") or "")[:150]
        src = it.get("source", "")
        prompt_text += f"No.{i}\nTitle: {t}\nSummary: {s}\nSource: {src}\n\n"

    system_prompt = (
        "你是人力资源外包（HRO）行业情报分析师。\n"
        f"以下新闻都属于同一家公司：{company or '同一公司'}。\n"
        "请只选择其中对人力资源外包行业影响最大的一条。\n"
        "判断优先级：用工规模变化、招聘外包需求、裁员/扩招、用工合规风险、业务外包机会。\n"
        "输出要求：仅输出一个整数编号（No.后面的数字），不要解释。"
    )

    headers = {
        "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": DASHSCOPE_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt_text}
        ],
        "temperature": 0.1
    }

    try:
        url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        _log_token_usage(data, "CompanyImpactPickOne")
        content = data["choices"][0]["message"]["content"].strip()
        content = re.sub(r"```json|```|```", "", content).strip()
        m = re.search(r"-?\d+", content)
        if not m:
            return -1
        idx = int(m.group())
        if 0 <= idx < len(group_items):
            return idx
        return -1
    except Exception:
        return -1


def call_ai_keep_max_impact_per_company(items: list[dict]) -> list[dict]:
    """
    仅针对“同一公司有多条新闻”的情况进行影响力比较并保留1条。
    只有1条新闻的公司直接保留，不做影响力判断。
    """
    if not items or len(items) < 2:
        return items

    print(f"[AI CompanyImpact] 检查同公司多新闻影响力：共 {len(items)} 条...")

    company_names = _call_ai_extract_company_names(items)
    if len(company_names) != len(items):
        print("[AI CompanyImpact] 公司识别结果异常，跳过该步骤。")
        return items

    groups: dict[str, list[int]] = {}
    for i, name in enumerate(company_names):
        key = (name or "").strip().lower()
        if not key:
            key = f"__single_{i}"  # 无法识别公司时按独立公司处理，确保不参与比较
        groups.setdefault(key, []).append(i)

    keep_indices = set()
    multi_groups = []
    for gkey, idx_list in groups.items():
        if len(idx_list) <= 1:
            keep_indices.update(idx_list)
        else:
            multi_groups.append((gkey, idx_list))

    if not multi_groups:
        print("[AI CompanyImpact] 未发现同公司多条新闻，跳过影响力比较。")
        return items

    for gkey, idx_list in multi_groups:
        group_items = [items[i] for i in idx_list]
        company_display = company_names[idx_list[0]] or "同一公司"
        chosen_local_idx = _call_ai_pick_max_impact_index_for_same_company(company_display, group_items)
        if chosen_local_idx == -1:
            # 兜底：本组全部保留，避免误删
            keep_indices.update(idx_list)
            print(f"[AI CompanyImpact] 组内比较失败，保留该公司全部新闻: {company_display}")
            continue
        keep_indices.add(idx_list[chosen_local_idx])

    result = []
    for i, it in enumerate(items):
        if i in keep_indices:
            result.append(it)
        else:
            print(f"  -> [CompanyImpact] 剔除同公司低影响项: {it.get('title', '')}")

    print(f"[AI CompanyImpact] 完成：{len(items)} -> {len(result)}")
    return result

def filter_by_ai_batch(items):
    """
    输入：列表，每个元素为 {"title": "...", "url": "...", "source": "..."}
    输出：AI 筛选后的列表
    """
    if not items:
        return []

    # 硬规则预处理：先做“强制保留/强制剔除”，其余再交给 AI
    pre_kept_items = []
    prefiltered_items = []
    for it in items:
        title = it.get("title", "")

        if _is_hard_keep_by_business_rules(title):
            pre_kept_items.append(it)
            print(f"  -> [Hard Keep] 命中新规则保留: {title}")
            continue

        if _is_hard_drop_by_business_rules(title):
            print(f"  -> [Hard Filter] 命中新规则剔除: {title}")
            continue

        if _is_other_hr_company_news(title):
            print(f"  -> [Hard Filter] 剔除其他HR公司新闻: {it.get('title', '')}")
            continue

        prefiltered_items.append(it)

    items = prefiltered_items
    if not items:
        return pre_kept_items
    
    # 按来源分组
    grouped = {}
    for it in items:
        src = it.get("source", "unknown")
        if src not in grouped:
            grouped[src] = []
        grouped[src].append(it)
        
    final_filtered = []
    
    for src, group_items in grouped.items():
        print(f"\n[AI Filter] 正在筛选来源: {src} (共 {len(group_items)} 条) ...")
        
        # 分批处理
        BATCH_SIZE = 10
        group_flags = []
        group_titles = [x["title"] for x in group_items]
        
        for i in range(0, len(group_titles), BATCH_SIZE):
            batch_titles = group_titles[i : i + BATCH_SIZE]
            batch_flags = call_ai_filter(batch_titles)
            group_flags.extend(batch_flags)
            
        if len(group_flags) != len(group_items):
             print(f"[AI Filter] 严重错误：分批汇总后长度仍不一致 ({len(group_flags)} vs {len(group_items)})，保留该来源全部。")
             final_filtered.extend(group_items)
             continue
             
        dropped_count = 0
        kept_count = 0
        for flag, it in zip(group_flags, group_items):
            if flag:
                final_filtered.append(it)
                kept_count += 1
            else:
                dropped_count += 1
                print(f"  -> 筛掉: {it['title']}")

        print(f"  -> {src}: 保留 {kept_count} / {len(group_items)}")
        
    return pre_kept_items + final_filtered

def call_ai_summary(content: str) -> str:
    """
    调用 DashScope 给文章生成“只保留最主要信息”的精简摘要。
    不做硬截断，避免出现句子突然被截断。
    """
    if not content or len(content) < 50:
        return ""

    system_prompt = (
        "你是一个专业的文章摘要助手。请阅读文章内容，仅保留最主要的信息，生成 1 句精炼摘要。"
        "\n\n要求："
        "\n1. 只保留一个核心事实（谁做了什么、结果是什么），能带关键数字就带关键数字。"
        "\n2. 语言客观、简洁，禁止使用'本文'、'作者'、'文章指出'等套话。"
        "\n3. 建议 50-80 字；若信息很多，也要优先压缩，不要罗列次要背景。"
    )

    headers = {
        "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
        "Content-Type": "application/json"
    }
    url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

    def _request_summary(request_payload: dict, timeout: int, context: str) -> tuple[str, str]:
        resp = requests.post(url, headers=headers, json=request_payload, timeout=timeout)
        resp.raise_for_status()

        data = resp.json()
        _log_token_usage(data, context)
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        content_text = re.sub(r"\s+", " ", (message.get("content") or "").strip())
        finish_reason = (choice.get("finish_reason") or "").strip().lower()
        return content_text, finish_reason

    payload = {
        "model": DASHSCOPE_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"文章内容：\n{content}"}
        ],
        "temperature": 0.3,  # 摘要需要相对确定，稍微低一点
        "max_tokens": 220,
    }

    try:
        summary, finish_reason = _request_summary(payload, timeout=30, context="Summary")

        if finish_reason == "length" or _summary_looks_truncated(summary):
            retry_prompt = (
                "你是一个专业的文章摘要助手。请阅读文章内容，仅保留最主要的信息，生成 1 句完整的精炼摘要。"
                "\n\n要求："
                "\n1. 只保留一个核心事实（谁做了什么、结果是什么），能带关键数字就带关键数字。"
                "\n2. 必须完整结束句子，不能输出半句，尤其不能截断小数、百分比、金额和人数。"
                "\n3. 建议 50-80 字，不要罗列次要背景，不要解释。"
            )
            retry_payload = {
                "model": DASHSCOPE_MODEL,
                "messages": [
                    {"role": "system", "content": retry_prompt},
                    {"role": "user", "content": f"文章内容：\n{content}"}
                ],
                "temperature": 0.1,
                "max_tokens": 260,
            }
            retry_summary, retry_finish_reason = _request_summary(retry_payload, timeout=30, context="SummaryRetry")
            if retry_summary and retry_finish_reason != "length" and not _summary_looks_truncated(retry_summary):
                summary = retry_summary
                finish_reason = retry_finish_reason

        # 当返回过长时，二次压缩为“单句核心信息”，避免直接硬截断导致断句。
        if len(summary) > 95:
            compact_prompt = (
                "请把下面这段新闻摘要压缩成一句话，只保留最主要的信息。"
                "不要截断句子，不要补充新信息，建议 50-80 字。\n\n"
                f"原摘要：{summary}"
            )
            compact_payload = {
                "model": DASHSCOPE_MODEL,
                "messages": [
                    {"role": "system", "content": "你是新闻摘要压缩助手。"},
                    {"role": "user", "content": compact_prompt}
                ],
                "temperature": 0.1,
                "max_tokens": 160,
            }
            try:
                compact_summary, compact_finish_reason = _request_summary(compact_payload, timeout=20, context="SummaryCompact")
                if compact_summary and compact_finish_reason != "length" and not _summary_looks_truncated(compact_summary):
                    summary = compact_summary
            except Exception:
                pass

        if _summary_looks_truncated(summary):
            print(f"[AI Summary] 检测到半句摘要，放弃该结果: {summary}")
            return ""

        summary = summary.strip(" \n\t。；;，,")
        if summary:
            summary = summary + "。"
            
        return summary
    except Exception as e:
        print(f"[AI Summary] 生成失败: {e}")
        return ""


def call_ai_shorten_title(title: str) -> str:
    """
    如果标题超过50字，调用AI进行缩写，保持原意，不超过50字。
    """
    title = title.strip()
    if len(title) <= 50:
        return title
        
    system_prompt = (
        "你是一个资深新闻编辑。请将用户的**新闻标题进行极度精简**。\n"
        "要求：\n"
        "1. **必须缩写到 50 字以内**。\n"
        "2. 保留最核心的主语、动词和结果（如：某公司裁员多少人，某政策发布等）。\n"
        "3. 去除无意义的修饰词、虚词。\n"
        "4. 直接输出缩写后的标题，不要任何标点符号外的解释。"
    )
    
    headers = {
        "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": DASHSCOPE_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"原标题：{title}"}
        ],
        "temperature": 0.1
    }
    
    try:
        url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        resp.raise_for_status()
        
        data = resp.json()
        _log_token_usage(data, "Shorten Title")
        new_title = data["choices"][0]["message"]["content"].strip()
        # 清理可能的多余引号或解释
        new_title = re.sub(r"^['\"]|['\"]$", "", new_title)
        return new_title
        
    except Exception as e:
        print(f"[AI Shorten] 标题缩写失败: {e}")
        return title


def call_ai_daily_insight(current_items: list[dict], recent_history_items: list[dict]) -> str:
    """
    基于当日已筛选新闻与近 3 个月历史样本，生成每日洞察。
    若判断为无明显趋势或对人力资源外包行业影响有限，返回 NO_INSIGHT。
    """
    if not current_items:
        return "NO_INSIGHT"

    current_text_lines = []
    for it in current_items:
        title = (it.get("title") or "").strip()
        if not title:
            continue
        category = (it.get("category") or "unknown").strip()
        summary = (it.get("summary") or "").strip()
        current_text_lines.append(f"- [{category}] {title} | 摘要: {summary}")

    if not current_text_lines:
        return "NO_INSIGHT"

    # 控制上下文长度，优先使用最近样本
    history_lines = []
    for it in recent_history_items[-180:]:
        d = (it.get("date") or "").strip()
        title = (it.get("title") or "").strip()
        if not d or not title:
            continue
        category = (it.get("category") or "unknown").strip()
        summary = re.sub(r"\s+", " ", (it.get("summary") or "").strip())
        if summary:
            summary = summary[:120]
        history_lines.append(f"- {d} [{category}] {title} | 摘要: {summary}")

    system_prompt = (
        "你是人力资源外包(HRO)行业的情报专家。请基于【今日新闻】与【近3个月历史趋势】，提炼出一段极简的行业洞察。\n\n"
        "要求：\n"
        "1. **形式**：只输出**一段话**，不要分段，不要列表，不要标题。\n"
        "2. **内容**：直击痛点。指出当前市场最核心的变化（如：大厂裁员潮、政策合规收紧、灵活用工需求爆发等），并一针见血地指出这对 HRO 公司的**直接机会或风险**是什么。\n"
        "3. **字数**：严格控制在 **200字以内**。\n"
        "4. **门槛**：仅当发现对 HRO 行业有显著影响的信号时输出；若无重要信号，直接返回 NO_INSIGHT。\n\n"
        "范例风格：\n"
        "近期多家互联网大厂缩减招聘预算，与此同时制造业灵活用工需求回升，显示出‘白领收缩、蓝领回暖’的结构性分化。对 HRO 企业而言，高端猎头业务短期承压，建议迅速通过蓝领外包与灵活用工平台业务对冲风险，重点关注新能源车企的产线扩招机会。"
    )

    user_content = (
        "【今日已筛选新闻】\n"
        + "\n".join(current_text_lines)
        + "\n\n【近3个月历史新闻样本】\n"
        + ("\n".join(history_lines) if history_lines else "- 无历史样本")
    )

    headers = {
        "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": DASHSCOPE_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        "temperature": 0.2
    }

    try:
        url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
        resp = requests.post(url, headers=headers, json=payload, timeout=35)
        resp.raise_for_status()

        data = resp.json()
        _log_token_usage(data, "Daily Insight")
        content = data["choices"][0]["message"]["content"].strip()
        content = re.sub(r"```markdown|```", "", content).strip()
        if content == "NO_INSIGHT":
            return "NO_INSIGHT"
        return content
    except Exception as e:
        print(f"[AI Insight] 生成失败: {e}")
        return ""


def call_ai_behavior_similarity_hits(current_enterprise_items: list[dict], recent_history_items: list[dict]) -> int:
    """
    使用 AI 判断“不同公司是否出现相同行为模式”，并返回历史命中数。
    示例：多家头部企业共同裁员/招聘冻结/组织收缩等。
    """
    if not current_enterprise_items or not recent_history_items:
        return 0

    current_lines = []
    for it in current_enterprise_items[:40]:
        title = (it.get("title") or "").strip()
        if title:
            summary = (it.get("summary") or "").strip()
            current_lines.append(f"- {title} | 摘要: {summary}")

    history_lines = []
    for it in recent_history_items[-200:]:
        if it.get("category") != "enterprise":
            continue
        d = (it.get("date") or "").strip()
        title = (it.get("title") or "").strip()
        if d and title:
            history_lines.append(f"- {d} | {title}")

    if not current_lines or not history_lines:
        return 0

    system_prompt = (
        "你是商业情报分析师。请识别‘不同公司发生相同行为’的历史命中数量。\n\n"
        "判定规则：\n"
        "1. 相同行为是指同一类企业动作，如：裁员、招聘冻结、组织优化、降本增效、业务收缩、业务剥离、关闭业务线、加速招聘扩张等。\n"
        "2. 必须是不同公司之间的同类行为，不能把同一公司重复事件当作跨公司命中。\n"
        "3. 只统计近3个月历史样本中，能与今日行为形成可比关系的历史事件条数。\n"
        "4. 输出必须是 JSON 对象，不要输出其他文字，格式：\n"
        "{\"similar_hit_count\": 3, \"patterns\": [\"多家头部企业裁员\", \"互联网公司招聘冻结\"]}"
    )

    user_content = (
        "【今日企业新闻】\n"
        + "\n".join(current_lines)
        + "\n\n【近3个月历史企业样本】\n"
        + "\n".join(history_lines)
    )

    headers = {
        "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": DASHSCOPE_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        "temperature": 0.1
    }

    try:
        url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
        resp = requests.post(url, headers=headers, json=payload, timeout=35)
        resp.raise_for_status()

        data = resp.json()
        _log_token_usage(data, "Behavior Similarity")
        content = data["choices"][0]["message"]["content"].strip()
        content = re.sub(r"```json|```", "", content).strip()

        # 尝试直接解析 JSON；若模型有冗余文本，则截取首尾大括号兜底
        obj = None
        try:
            obj = json.loads(content)
        except Exception:
            m = re.search(r"\{[\s\S]*\}", content)
            if m:
                obj = json.loads(m.group(0))

        if not isinstance(obj, dict):
            return 0

        hit_count = int(obj.get("similar_hit_count", 0) or 0)
        if hit_count < 0:
            hit_count = 0
        return hit_count
    except Exception as e:
        print(f"[AI Similarity] 判断失败: {e}")
        return 0


def call_ai_industry_trend_impact_hit(current_enterprise_items: list[dict], recent_history_items: list[dict]) -> tuple[bool, str]:
    """
    基于新闻前置标签（如【AI】、【车企】）与近 6 个月历史样本，
    判断“今日行业趋势是否已对人力资源外包(HRO)行业形成明确影响信号”。
    """
    if not current_enterprise_items:
        return False, ""

    tag_re = re.compile(r"^【([^】]{1,12})】")

    def _pick_tag(title: str) -> str:
        m = tag_re.match((title or "").strip())
        if not m:
            return "未标注"
        return m.group(1).strip() or "未标注"

    today_lines = []
    for it in current_enterprise_items[:60]:
        title = (it.get("title") or "").strip()
        if not title:
            continue
        summary = re.sub(r"\s+", " ", (it.get("summary") or "").strip())
        tag = _pick_tag(title)
        today_lines.append(f"- [{tag}] {title} | 摘要: {summary}")

    history_lines = []
    for it in recent_history_items[-260:]:
        if (it.get("category") or "").strip() != "enterprise":
            continue
        d = (it.get("date") or "").strip()
        title = (it.get("title") or "").strip()
        if not d or not title:
            continue
        tag = _pick_tag(title)
        history_lines.append(f"- {d} [{tag}] {title}")

    if not today_lines:
        return False, ""

    system_prompt = (
        "你是人力资源外包(HRO)行业趋势分析师。请基于‘今日行业标签分布’与‘历史样本标签趋势’，判断今天是否出现了会影响 HRO 的行业变化。\n\n"
        "判定口径：\n"
        "1. 必须结合新闻前置标签分析（如【AI】、【车企】、【制造】、【消费】、【政策】等）。\n"
        "2. 影响可以是机会或风险（如招聘需求结构变化、灵活用工波动、合规成本变化、交付压力变化等）。\n"
        "3. 只有在‘影响明确且可落到 HRO 业务’时返回 true；否则返回 false。\n"
        "4. 输出必须是 JSON，不要输出其他文字："
        "{\"impact\": true, \"reason\": \"一句话说明\"}"
    )

    user_content = (
        "【今日企业新闻（含标签）】\n"
        + "\n".join(today_lines)
        + "\n\n【近6个月历史企业样本（含标签）】\n"
        + ("\n".join(history_lines) if history_lines else "- 无历史样本")
    )

    headers = {
        "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": DASHSCOPE_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        "temperature": 0.1
    }

    try:
        url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
        resp = requests.post(url, headers=headers, json=payload, timeout=35)
        resp.raise_for_status()

        data = resp.json()
        _log_token_usage(data, "Industry Trend Impact")
        content = data["choices"][0]["message"]["content"].strip()
        content = re.sub(r"```json|```", "", content).strip()

        obj = None
        try:
            obj = json.loads(content)
        except Exception:
            m = re.search(r"\{[\s\S]*\}", content)
            if m:
                obj = json.loads(m.group(0))

        if not isinstance(obj, dict):
            return False, ""

        impact = obj.get("impact", False)
        if isinstance(impact, str):
            impact = impact.strip().lower() in {"true", "1", "yes", "y"}

        if bool(impact):
            reason = (obj.get("reason") or "").strip()
            if reason:
                print(f"[Insight] 行业趋势影响命中: {reason}")
            else:
                print("[Insight] 行业趋势影响命中")
            return True, reason
        return False, ""
    except Exception as e:
        print(f"[AI Trend Impact] 判断失败: {e}")
        return False, ""

