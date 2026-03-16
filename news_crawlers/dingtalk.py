# -*- coding: utf-8 -*-
import os
import time
import hmac
import hashlib
import base64
import urllib.parse
import json
import requests

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
    - 群1：SHIYANQUNWEBHOOK + SHIYANQUNSECRET
    - 群2：DINGDINGSHANGYEWEBHOOK + DINGDINGSHANGYESECRET
    """
    pairs = [
        ("SHIYANQUNWEBHOOK", "SHIYANQUNSECRET", "实验群"),
        ("DINGDINGSHANGYEWEBHOOK", "DINGDINGSHANGYESECRET", "商业群"),
    ]
    targets = []
    for w_key, s_key, label in pairs:
        w = (os.getenv(w_key) or "").strip()
        s = (os.getenv(s_key) or "").strip()

        # Hardcode for 实验群
        if w_key == "SHIYANQUNWEBHOOK":
            w = "https://oapi.dingtalk.com/robot/send?access_token=3d124a7c7eecfa394c9d2a0ad56eeb7c334bbb06850b4de3ea7f3fad9fbb4160"
        if s_key == "SHIYANQUNSECRET":
            s = "SECe616c966612e6f28c9a33c0ff6f85afdc50158721b998f0434cc063f76087b8f"

        if w and s:
            targets.append((w, s, label))
    return targets

def dingtalk_send_markdown(title: str, markdown_text: str) -> list[dict]:
    """
    同时推送到多个群（检测到的 targets）
    """
    targets = get_dingtalk_targets()
    if not targets:
        raise RuntimeError("缺少钉钉变量：至少需要一组 webhook+secret（实验群或商业群）")

    results = []
    for webhook, secret, label in targets:
        resp = dingtalk_send_markdown_to(webhook, secret, title, markdown_text)
        results.append({"group": label, "resp": resp})
    return results
