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
        "你是一位深耕人力资源外包（HRO/BPO/RPO）领域的资深战略咨询顾问。你的核心任务是从海量新闻标题中，"
        "精准筛选出对'人力资源外包业务'具有极高商业价值的情报。\n\n"
        "【地域优先级】\n"
        "- 默认优先保留中国境内新闻（政策、企业、行业、就业、用工与合规）。\n"
        "- 海外新闻默认从严筛选，仅当其主体为全球或区域头部企业，且事件会对中国市场的人才需求、用工结构、薪酬水平、外包需求或合规环境产生显著传导影响时才保留。\n"
        "- 仅是海外本地经营动态、与中国无明显关联的新闻，一律剔除。\n\n"
        "【高价值判断标准】（只要符合任意一条即保留）：\n"
        "1. **政策红利与风险**：涉及劳动法、社保、公积金、个税、灵活用工监管等直接影响用工成本或合规性的政策变动（这是外包服务的核心痛点）。\n"
        "2. **甲方需求信号**：头部企业（互联网大厂、制造业巨头等）的大规模裁员（Outplacement机会）、招聘冻结、或大规模扩张（RPO/派遣机会）、业务外包招标信息。\n"
        "3. **行业竞争情报**：主要竞争对手（如FESCO、中智、人瑞、科锐、万宝盛华、得科等）的战略动作、投融资、并购或重大产品发布。\n"
        "4. **用工趋势**：灵活用工、零工经济、共享员工等新兴用工模式的数据报告或趋势分析。\n"
        "5. **技术冲击**：AI、数字化对招聘、薪酬管理等HR流程的颠覆性影响。\n\n"
        "【必须剔除的内容】：\n"
        "- 纯粹的职场鸡汤、管理技巧分享（如'如何搞好团队关系'）。\n"
        "- 与劳动力市场无关的宏观经济新闻或个股波动（除非是巨头崩盘影响就业）。\n"
        "- 纯技术层面的IT新闻，除非涉及HR SaaS。\n"
        "- 创业空间建设、人才公寓/住房保障、园区配套等民生或招商类信息；除非明确直接影响企业用工成本、劳动合规或外包需求。\n"
        "- 与中国市场无实质关联的海外一般性企业新闻。\n"
        "- 无实质内容的通稿或广告。\n\n"
        "请返回一个 JSON 数组，长度与输入数组严格一致，只包含 true 或 false。\n"
        "True表示极具价值，False表示一般或无价值。\n"
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

def filter_by_ai_batch(items):
    """
    输入：列表，每个元素为 {"title": "...", "url": "...", ...}
    输出：AI 筛选后的列表
    """
    if not items:
        return []
    
    titles = [x["title"] for x in items]
    flags = call_ai_filter(titles)
    
    if len(flags) != len(items):
        # 兜底：长度不一致时，全部通过
        print(f"[AI Filter] 长度不符 ({len(flags)} vs {len(items)})，保留全部。")
        return items

    filtered = []
    dropped_count = 0
    for flag, it in zip(flags, items):
        if flag:
            filtered.append(it)
        else:
            dropped_count += 1
            print(f"[AI Filter] 筛掉: {it['title']}")
            
    print(f"[AI Filter] 共 {len(items)} 条，筛掉 {dropped_count} 条，保留 {len(filtered)} 条。")
    return filtered

def call_ai_summary(content: str) -> str:
    """
    调用 DashScope 给文章生成 100 字摘要。
    """
    if not content or len(content) < 50:
        return ""

    system_prompt = (
        "你是一个专业的文章摘要助手。请阅读以下文章内容，提取并总结其中的重要语句，生成一段 150 字以内的精炼摘要。"
        "要求：\n"
        "1. 概括核心事实、关键数据或结论，只保留最有价值的信息；\n"
        "2. 语言客观、简洁，不要使用'本文' '作者'等词，直接陈述事实；\n"
        "3. 控制在 150 字以内。"
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
        return summary
    except Exception as e:
        print(f"[AI Summary] 生成失败: {e}")
        return ""


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
        "你是人力资源外包行业研究员。请根据【今日已筛选新闻】与【近3个月历史新闻样本】进行结构化洞察。\n\n"
        "分析原则：\n"
        "1. 必须先浏览历史记录，并把有联系的事件归并为 2-4 个‘主题簇’（例如：招聘收缩、用工合规收紧、薪酬与社保成本变化、AI替代与岗位重构）。\n"
        "2. 每个主题簇需要体现时间延续性（至少包含今天信号+历史信号），避免把孤立事件当趋势。\n"
        "3. 重点分析‘当下行业市场状态’：需求强弱、预算倾向、用工结构、风险偏好、合规压力、竞争格局。\n"
        "4. 在趋势判断基础上，给出 1-3 个月的短期预测，必须写清‘上行/下行/分化’方向与触发条件。\n"
        "5. 仅当趋势对中国人力资源外包行业有显著影响时输出洞察；若证据不足或影响有限，仅返回 NO_INSIGHT（必须完全一致，不要附加任何文字）。\n\n"
        "若输出洞察，使用简洁 Markdown，结构如下：\n"
        "- **关联主题簇（历史+当下）**：每簇 1-2 条\n"
        "- **当下行业市场分析**：1 段\n"
        "- **趋势预测（1-3个月）**：2-3 条\n"
        "- **建议动作**：2-3 条\n"
        "总字数控制在 260-420 字，聚焦中国市场，不写空话。"
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

