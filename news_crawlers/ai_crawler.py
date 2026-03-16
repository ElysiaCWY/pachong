# -*- coding: utf-8 -*-
import requests
import json
import re

# ===================== AI 智能筛选 (通义千问 Qwen3.5-Flash) =====================
DASHSCOPE_API_KEY = "sk-86fa3d1f35784c80a85640bb1df05909"
# Qwen3.5-Flash 的 API 模型 ID 通常为 "qwen-turbo" (代表最新的快速模型) 或 "qwen-flash"
# 这里根据你的要求改为 "qwen-turbo" (目前该模型在 DashScope 上对应 Flash 级别的速度和成本)
DASHSCOPE_MODEL   = "qwen-turbo" 

def call_ai_filter(titles: list[str]) -> list[bool]:
    """
    通过 DashScope API 筛选有利于人力资源公司（尤其是人力资源外包）的信息。
    """
    if not titles:
        return []
    
    # 构造 Prompt
    system_prompt = (
        "你是一个资深的人力资源行业专家。请从给定的新闻标题列表中，筛选出对'人力资源公司'（特别是'人力资源外包'业务）"
        "有利、有价值或相关性高的信息。\n"
        "筛选标准：\n"
        "1. 涉及劳动法、社保、公积金、个税等政策调整（利于外包合规或需求增加）；\n"
        "2. 涉及灵活用工、劳务派遣、外包服务的利好政策或趋势；\n"
        "3. 涉及企业用工成本、招聘难、裁员潮（利于外包机会）；\n"
        "4. 行业标杆（如人瑞、科锐等）的重大积极动态；\n"
        "5. 头部公司（如互联网大厂、各行业巨头）的重大财经动态（如市值大幅蒸发、市场份额滑落、重大战略收缩或扩张），因为这通常意味着用工规模或策略的重大调整；\n"
        "6. 排除无关的娱乐、纯技术细节、甚至负面或无价值的通稿。\n\n"
        "请返回一个 JSON 数组，长度与输入数组一致，只包含 true 或 false。"
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
        "你是一个专业的文章摘要助手。请阅读以下文章内容，生成一段 100 字以内的精炼摘要。"
        "要求：\n"
        "1. 概括核心事实、关键数据或结论；\n"
        "2. 语言客观、简洁，不要使用'本文' '作者'等词，直接陈述事实；\n"
        "3. 控制在 100 字以内。"
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
    return filtered
