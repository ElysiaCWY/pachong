# -*- coding: utf-8 -*-
import os
import time
import hmac
import hashlib
import base64
import urllib.parse
import json
import requests


def _pick_env(*keys: str) -> str:
    for key in keys:
        val = (os.getenv(key) or "").strip()
        if val:
            return val
    return ""

# ===================== 钉钉（加签） =====================
def extract_access_token(token_or_webhook: str) -> str:
    s = (token_or_webhook or "").strip()
    if not s:
        return ""
    if "access_token=" in s:
        u = urllib.parse.urlparse(s)
        q = urllib.parse.parse_qs(u.query)
        return (q.get("access_token") or [""])[0].strip()
    return s

def dingtalk_signed_url(webhook_or_token: str, secret: str) -> str:
    """
    兼容：WEBHOOK 既可以传整条 webhook，也可以只传 access_token
    """
    raw = (webhook_or_token or "").strip()
    token = extract_access_token(raw)
    if not token:
        raise RuntimeError("Webhook/token 为空（可填整条 webhook 或 access_token）")

    ts = str(int(time.time() * 1000))
    to_sign = f"{ts}\n{secret}"
    sign = urllib.parse.quote_plus(
        base64.b64encode(
            hmac.new(secret.encode("utf-8"), to_sign.encode("utf-8"), hashlib.sha256).digest()
        )
    )
    return f"https://oapi.dingtalk.com/robot/send?access_token={token}&timestamp={ts}&sign={sign}"

def dingtalk_send_markdown_to(webhook: str, secret: str, title: str, markdown_text: str) -> dict:
    url = dingtalk_signed_url(webhook, secret)
    payload = {"msgtype": "markdown", "markdown": {"title": title, "text": markdown_text}}
    r = requests.post(url, json=payload, timeout=25)
    r.raise_for_status()
    data = r.json()
    if str(data.get("errcode")) != "0":
        raise RuntimeError(f"钉钉发送失败：{data}")
    return data

def get_dingtalk_targets():
    """
    支持多群推送：只要环境变量成对存在，就会推送。
    - 群1：DINGTALK_GROUP1_WEBHOOK + DINGTALK_GROUP1_SECRET
    - 群2：DINGTALK_GROUP2_WEBHOOK + DINGTALK_GROUP2_SECRET
    兼容旧变量名：SHIYANQUN* / DINGDINGSHANGYE* / DINGTALK_SHIYANQUN* / DINGTALK_SHANGYE*
    """
    pairs = [
        (("DINGTALK_GROUP1_WEBHOOK", "SHIYANQUNWEBHOOK", "DINGTALK_SHIYANQUNWEBHOOK"), ("DINGTALK_GROUP1_SECRET", "SHIYANQUNSECRET", "DINGTALK_SHIYANQUNSECRET"), "群1"),
        (("DINGTALK_GROUP2_WEBHOOK", "DINGDINGSHANGYEWEBHOOK", "DINGTALK_SHANGYEWEBHOOK"), ("DINGTALK_GROUP2_SECRET", "DINGDINGSHANGYESECRET", "DINGTALK_SHANGYESECRET"), "群2"),
    ]
    targets = []
    for w_keys, s_keys, label in pairs:
        w = _pick_env(*w_keys)
        s = _pick_env(*s_keys)
        if w and s:
            targets.append((w, s, label))
    return targets

def dingtalk_send_markdown(title: str, markdown_text: str) -> list[dict]:
    """
    同时推送到多个群（检测到的 targets）
    """
    targets = get_dingtalk_targets()
    if not targets:
        raise RuntimeError("缺少钉钉变量：至少需要一组 webhook+secret（群1或群2）")

    results = []
    for webhook, secret, label in targets:
        resp = dingtalk_send_markdown_to(webhook, secret, title, markdown_text)
        results.append({"group": label, "resp": resp})
    return results
