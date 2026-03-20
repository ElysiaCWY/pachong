# -*- coding: utf-8 -*-
import requests
import json
import re

# ===================== AI 智能筛选 =====================
DASHSCOPE_API_KEY = "sk-86fa3d1f35784c80a85640bb1df05909"
# 使用更强理解能力的模型进行筛选和摘要
DASHSCOPE_MODEL   = "qwen-plus" 

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
        "3. **HRO行业竞品动态**：\n"
        "   - 专指：FESCO、中智、科锐国际、人瑞人才、万宝盛华、得科、任仕达、趣活等直接竞争对手的并购、财报、新产品发布。\n"
        "4. **用工模式变革**：\n"
        "   - 涉及零工经济平台、共享员工、众包模式的监管或数据报告。\n\n"
        "【必须无情剔除的噪音】（凡是沾边的一律False）：\n"
        "- **内训与职场鸡汤**：'如何提升领导力'、'职场沟通技巧'、'HR如何做绩效'（这是给甲方HR看的，外包公司不关心）。\n"
        "- **无关宏观与个股**：'某公司股价涨跌'、'GDP预测'、'某行业大会召开'（除非明确讲就业规模变化）。\n"
        "- **普通企业新闻**：'某公司发布新手机'、'某车企销量夺冠'（除非提到扩招/裁员/建厂）。\n"
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
    if not summary or len(summary) < 10:
        return True # 如果没有摘要，默认保留，以免误删
        
    system_prompt = (
        "你是一位人力资源行业的高级情报官。请基于新闻标题和摘要，进行二次严格审查。\n"
        "判断该新闻是否对**人力资源外包、招聘、派遣、薪酬社保、劳动法合规**等业务有实质性影响。\n\n"
        "【判定标准】\n"
        "1. **保留** (True)：\n"
        "   - 涉及企业裁员、大规模招聘、迁址、用工纠纷。\n"
        "   - 涉及社保公积金、个税、最低工资、劳动法政策变化。\n"
        "   - 涉及人力资源服务商（竞品）动态。\n"
        "   - 涉及灵活用工、零工经济平台监管。\n"
        "2. **剔除** (False)：\n"
        "   - 纯粹的股市/财报新闻（除非明确提到大幅裁员/扩招）。\n"
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
        content = data["choices"][0]["message"]["content"].strip().lower()
        
        if "true" in content:
            return True
        if "false" in content:
            return False
        return True # 默认保留
        
    except Exception as e:
        print(f"[AI Check] 二次筛选调用失败: {e}，默认保留。")
        return True

def filter_by_ai_batch(items):
    """
    输入：列表，每个元素为 {"title": "...", "url": "...", "source": "..."}
    输出：AI 筛选后的列表
    """
    if not items:
        return []
    
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
                if dropped_count <= 3: # 避免刷屏太多
                     print(f"  -> 筛掉: {it['title']}")
                     
        if dropped_count > 3:
             print(f"  -> ... (及其它 {dropped_count - 3} 条被筛掉)")

        print(f"  -> {src}: 保留 {kept_count} / {len(group_items)}")
        
    return final_filtered

def call_ai_summary(content: str) -> str:
    """
    调用 DashScope 给文章生成 90 字摘要（确保不超过 100 字）。
    """
    if not content or len(content) < 50:
        return ""

    system_prompt = (
        "你是一个专业的文章摘要助手。请阅读以下文章内容，提取并总结其中的重要事实，**生成一段严格限制在 90 字以内**的精炼摘要。"
        "\n\n要求："
        "\n1. 必须概括核心事实、关键数据（裁员人数、涨薪幅度等）或结论，去除所有废话。"
        "\n2. 语言客观、极度简洁，禁止使用'本文'、'作者'、'文章指出'等套话，直接陈述事实。"
        "\n3. **字数必须控制在 90 字以内**，绝对不能超过 100 字。"
    )

    headers = {
        "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": DASHSCOPE_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"文章内容：\n{content}"}
        ],
        "temperature": 0.3  # 摘要需要相对确定，稍微低一点
    }

    try:
        url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()

        data = resp.json()
        summary = data["choices"][0]["message"]["content"].strip()
        # 清理可能的多余换行
        summary = re.sub(r"\s+", " ", summary)
        
        # 强制截断兜底
        if len(summary) > 100:
            summary = summary[:99] + "…"
            
        return summary
    except Exception as e:
        print(f"[AI Summary] 生成失败: {e}")
        return ""


def call_ai_shorten_title(title: str) -> str:
    """
    如果标题超过30字，调用AI进行缩写，保持原意，不超过30字。
    """
    title = title.strip()
    if len(title) <= 30:
        return title
        
    system_prompt = (
        "你是一个资深新闻编辑。请将用户的**新闻标题进行极度精简**。\n"
        "要求：\n"
        "1. **必须缩写到 30 字以内**。\n"
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

