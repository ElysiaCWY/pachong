# -*- coding: utf-8 -*-

def render_markdown(title, items):
    """
    title: 模块标题（如 北京要闻）
    items: [{title, url, date}]
    """
    if not items:
        return f"### {title}\n\n近一周暂无更新"

    lines = [f"### {title}", ""]
    for i, it in enumerate(items, 1):
        lines.append(
            f"{i}. {it['title']}（{it['date']}） [详情]({it['url']})"
        )
    return "\n".join(lines)
