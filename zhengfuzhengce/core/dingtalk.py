import os
import time
import hmac
import hashlib
import base64
import urllib.parse
import requests

def _pick_env(*keys):
    for key in keys:
        val = (os.getenv(key) or "").strip()
        if val:
            return val
    return ""


def _signed_url(webhook, secret):
    timestamp = str(round(time.time() * 1000))
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(
        secret.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code).decode("utf-8"))
    return f"{webhook}&timestamp={timestamp}&sign={sign}"


def _targets():
    pairs = [
        (("DINGTALK_GROUP1_WEBHOOK", "DINGTALK_SHIYANQUNWEBHOOK", "SHIYANQUNWEBHOOK"), ("DINGTALK_GROUP1_SECRET", "DINGTALK_SHIYANQUNSECRET", "SHIYANQUNSECRET"), "群1"),
        (("DINGTALK_GROUP2_WEBHOOK", "DINGTALK_SHANGYEWEBHOOK", "DINGDINGSHANGYEWEBHOOK"), ("DINGTALK_GROUP2_SECRET", "DINGTALK_SHANGYESECRET", "DINGDINGSHANGYESECRET"), "群2"),
    ]
    targets = []
    for w_keys, s_keys, label in pairs:
        webhook = _pick_env(*w_keys)
        secret = _pick_env(*s_keys)
        if webhook and secret:
            targets.append((webhook, secret, label))
    return targets


def send_markdown(title, text):
    targets = _targets()

    if not targets:
        print(text)
        return

    data = {
        "msgtype": "markdown",
        "markdown": {
            "title": title,
            "text": text
        }
    }

    for webhook, secret, label in targets:
        url = _signed_url(webhook, secret)
        resp = requests.post(url, json=data, timeout=25)
        try:
            detail = resp.json()
        except Exception:
            detail = {"http_status": resp.status_code}
        if str(detail.get("errcode", "0")) != "0":
            print(f"[DingTalk] 推送失败({label}): {detail}")
