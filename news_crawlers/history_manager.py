# -*- coding: utf-8 -*-
import os
import json
import re
from difflib import SequenceMatcher
from datetime import date, timedelta
from .common import now_cn


def _strip_leading_tag(title: str) -> str:
    if not title:
        return ""
    return re.sub(r"^【[^】]{1,12}】", "", title).strip()


def _normalize_text(text: str) -> str:
    if not text:
        return ""
    text = _strip_leading_tag(text)
    text = text.lower()
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[^0-9a-z\u4e00-\u9fff]", "", text)
    return text


def _char_bigrams(text: str) -> set[str]:
    if len(text) < 2:
        return set()
    return {text[i:i + 2] for i in range(len(text) - 1)}


def _jaccard_similarity(a: str, b: str) -> float:
    sa = _char_bigrams(a)
    sb = _char_bigrams(b)
    if not sa or not sb:
        return 0.0
    union = sa | sb
    if not union:
        return 0.0
    return len(sa & sb) / len(union)


def _extract_key_numbers(text: str) -> set[str]:
    nums = set(re.findall(r"\d+(?:\.\d+)?", text or ""))
    # 过滤过短数字，保留更有区分度的关键数值（如 8809、1300、2025）
    return {n for n in nums if len(n) >= 3}


def _looks_like_same_event(current_item: dict, history_item: dict) -> bool:
    c_title = _normalize_text(current_item.get("title", ""))
    h_title = _normalize_text(history_item.get("title", ""))
    if not c_title or not h_title:
        return False

    # 标题完全一致或明显包含关系
    if c_title == h_title:
        return True
    if len(c_title) >= 10 and c_title in h_title:
        return True
    if len(h_title) >= 10 and h_title in c_title:
        return True

    # 标题字符相似度
    title_ratio = SequenceMatcher(None, c_title, h_title).ratio()
    if title_ratio >= 0.80:
        return True

    # 合并摘要后做语义近似（字面）判断
    c_mix = _normalize_text(f"{current_item.get('title', '')} {current_item.get('summary', '')}")
    h_mix = _normalize_text(f"{history_item.get('title', '')} {history_item.get('summary', '')}")
    if not c_mix or not h_mix:
        return False

    mix_ratio = SequenceMatcher(None, c_mix, h_mix).ratio()
    jac = _jaccard_similarity(c_mix, h_mix)
    if mix_ratio >= 0.72 or jac >= 0.58:
        return True

    # 关键数字一致 + 有较长公共片段（用于“华为 2025 营收 8809亿”这类改写标题）
    c_nums = _extract_key_numbers(c_mix)
    h_nums = _extract_key_numbers(h_mix)
    overlap_nums = c_nums & h_nums
    if overlap_nums:
        longest_common = SequenceMatcher(None, c_mix, h_mix).find_longest_match(0, len(c_mix), 0, len(h_mix)).size
        if longest_common >= 6 and jac >= 0.30:
            return True

    return False

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


def filter_against_history(items: list[dict], history_file: str, category: str = "unknown") -> list[dict]:
    """
    过滤掉已经在历史记录中存在的新闻。
    规则同追加：若 url 存在且长度>5，通过 url 去重；
    否则，通过 (category, title) 去重。
    """
    cutoff_date = now_cn().date() - timedelta(days=180)
    existing_keys = set()
    recent_records = []

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
                        try:
                            d_obj = date.fromisoformat(d_str)
                        except ValueError:
                            continue
                        
                        if d_obj >= cutoff_date:
                            i_url = (item.get("url") or "").strip()
                            i_title = (item.get("title") or "").strip()
                            i_cat = item.get("category", "")

                            recent_records.append(
                                {
                                    "category": i_cat,
                                    "title": i_title,
                                    "summary": (item.get("summary") or "").strip(),
                                    "url": i_url,
                                }
                            )
                            
                            if i_url and len(i_url) > 5:
                                key = i_url
                            else:
                                key = (i_cat, i_title)
                            
                            existing_keys.add(key)
                    except Exception:
                        continue
        except Exception as e:
            print(f"[History] 读取历史文件用于排重失败: {e}")

    filtered_items = []
    for it in items:
        title = (it.get("title") or "").strip()
        url = (it.get("url") or "").strip()
        # 注意：crawler 里的抓取结果字典中通常没有 category，这里提供一个参数使其能和历史的 category 对齐
        cat = it.get("category", category)

        if url and len(url) > 5:
            key = url
        else:
            key = (cat, title)

        if key in existing_keys:
            print(f"[History Filter] 拦截已发布过的新闻: {title}")
            continue

        # 模糊排重：不同网站/同网站改写标题但核心事件一致时，仅保留一条
        hit_similar = False
        for old in recent_records:
            old_cat = old.get("category") or ""
            if old_cat and cat and old_cat != cat:
                continue
            if _looks_like_same_event(it, old):
                print(f"[History Filter] 拦截近似重复新闻: {title} | 历史: {old.get('title', '')}")
                hit_similar = True
                break

        if hit_similar:
            continue
        
        filtered_items.append(it)

    return filtered_items


def verify_history_items_written(history_file: str, items: list[dict]) -> tuple[bool, list[dict]]:
    """
    校验待发送新闻是否都已存在于历史文件。
    优先使用 URL 作为唯一键，URL 不可用时回退为 (category, title)。
    """
    if not items:
        return True, []

    if not os.path.exists(history_file):
        return False, items

    existing_keys = set()
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

                i_url = (item.get("url") or "").strip()
                i_title = (item.get("title") or "").strip()
                i_cat = item.get("category", "")
                if i_url and len(i_url) > 5:
                    key = i_url
                else:
                    key = (i_cat, i_title)
                existing_keys.add(key)
    except Exception as e:
        print(f"[Insight] 校验历史文件失败: {e}")
        return False, items

    missing_items = []
    for it in items:
        title = (it.get("title") or "").strip()
        if not title:
            continue

        url = (it.get("url") or "").strip()
        cat = it.get("category", "unknown")
        if url and len(url) > 5:
            key = url
        else:
            key = (cat, title)

        if key not in existing_keys:
            missing_items.append(it)

    return len(missing_items) == 0, missing_items


def append_history_items(history_file: str, run_date: str, items: list[dict]):
    if not items:
        return True

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
        return True
    except Exception as e:
        print(f"[Insight] 写入历史文件失败: {e}")
        return False
