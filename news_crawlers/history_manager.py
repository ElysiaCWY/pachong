# -*- coding: utf-8 -*-
import os
import json
from datetime import date, timedelta
from .common import now_cn

def load_recent_history(history_file: str, days: int = 180) -> list[dict]:
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

    # 1) 读取现有历史记录，并过滤保留最近 6 个月（180 天）
    #    "从头依次覆盖" -> 意味着只保留设定时间窗内的数据，旧数据丢弃
    cutoff_date = now_cn().date() - timedelta(days=180)
    preserved_records = []
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
                        d_str = item.get("date", "")
                        # 解析日期以便过滤
                        try:
                            d_obj = date.fromisoformat(d_str)
                        except ValueError:
                            continue
                        
                        # 只保留 cutoff_date 之后的
                        if d_obj >= cutoff_date:
                            # 优化去重逻辑：优先使用 URL 去重，忽略日期（避免同一新闻不同日期重复入库）
                            # 只有当 URL 为空时，才使用 (category, title)
                            i_url = (item.get("url") or "").strip()
                            i_title = (item.get("title") or "").strip()
                            i_cat = item.get("category", "")
                            
                            if i_url and len(i_url) > 5:
                                key = i_url
                            else:
                                key = (i_cat, i_title)

                            # 防止历史文件中本身有重复记录
                            if key not in existing_keys:
                                preserved_records.append(item)
                                existing_keys.add(key)
                    except Exception:
                        continue
        except Exception as e:
            print(f"[Insight] 读取/清理历史文件失败: {e}")

    # 2) 追加新记录（去重）
    new_records_count = 0
    for it in items:
        title = (it.get("title") or "").strip()
        if not title:
            continue
        
        url = (it.get("url") or "").strip()
        cat = it.get("category", "unknown")

        rec = {
            "date": run_date,
            "category": cat,
            "title": title,
            "summary": (it.get("summary") or "").strip(),
            "url": url,
        }
        
        if url and len(url) > 5:
            key = url
        else:
            key = (cat, title)

        if key in existing_keys:
            continue
        
        preserved_records.append(rec)
        existing_keys.add(key)
        new_records_count += 1
    
    # 3) 全量覆盖写入（保留最近 6 个月）
    try:
        with open(history_file, "w", encoding="utf-8") as f:
            for rec in preserved_records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        if new_records_count > 0:
            print(f"[Insight] 已更新历史记录文件（新增 {new_records_count} 条，保留最近 6 个月）")
    except Exception as e:
        print(f"[Insight] 写入历史文件失败: {e}")
