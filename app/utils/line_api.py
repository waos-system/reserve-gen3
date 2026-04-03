"""
LINE Messaging API helpers.
"""
from typing import Optional

import requests


LINE_API_URL = "https://api.line.me/v2/bot/message/push"


def _get_headers(token: str) -> dict:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }


def send_pending_reservation_notice(
    channel_token: str,
    line_user_id: str,
    reservation_number: str,
    customer_name: str,
    slot_date: str,
    slot_label: str,
    store_name: str,
    confirm_url: str,
    qr_base64: Optional[str] = None,
) -> bool:
    if not channel_token or channel_token == "your-line-channel-access-token":
        print(f"[LINE Mock] pending reservation -> {line_user_id}: {reservation_number}")
        return True

    messages = [{
        "type": "text",
        "text": (
            f"[{store_name}] 仮予約を受け付けました\n\n"
            f"予約番号: {reservation_number}\n"
            f"お名前: {customer_name}\n"
            f"日付: {slot_date}\n"
            f"時間: {slot_label}\n\n"
            "以下のURLから予約を確定してください。\n"
            f"{confirm_url}"
        ),
    }]

    payload = {"to": line_user_id, "messages": messages}
    try:
        resp = requests.post(
            LINE_API_URL, json=payload, headers=_get_headers(channel_token), timeout=10
        )
        return resp.status_code == 200
    except Exception as exc:
        print(f"[LINE Error] {exc}")
        return False


def send_confirmation_notice(
    channel_token: str,
    line_user_id: str,
    reservation_number: str,
    customer_name: str,
    slot_date: str,
    slot_label: str,
    store_name: str,
    access_url: str,
) -> bool:
    if not channel_token or channel_token == "your-line-channel-access-token":
        print(f"[LINE Mock] confirmed reservation -> {line_user_id}: {reservation_number} {access_url}")
        return True

    messages = [{
        "type": "text",
        "text": (
            f"[{store_name}] ご予約が確定しました\n\n"
            f"予約番号: {reservation_number}\n"
            f"お名前: {customer_name}\n"
            f"日付: {slot_date}\n"
            f"時間: {slot_label}\n\n"
            "あとで予約内容を確認するURL:\n"
            f"{access_url}"
        ),
    }]

    payload = {"to": line_user_id, "messages": messages}
    try:
        resp = requests.post(
            LINE_API_URL, json=payload, headers=_get_headers(channel_token), timeout=10
        )
        return resp.status_code == 200
    except Exception as exc:
        print(f"[LINE Error] {exc}")
        return False


def send_store_notification(
    channel_token: str,
    store_line_user_id: str,
    reservation_number: str,
    customer_name: str,
    customer_phone: str,
    slot_date: str,
    slot_label: str,
    party_size: int,
) -> bool:
    if not channel_token or channel_token == "your-line-channel-access-token":
        print(f"[LINE Mock] store notification -> {store_line_user_id}: {reservation_number}")
        return True

    messages = [{
        "type": "text",
        "text": (
            "[新規予約]\n\n"
            f"予約番号: {reservation_number}\n"
            f"お名前: {customer_name}\n"
            f"電話番号: {customer_phone}\n"
            f"日付: {slot_date}\n"
            f"時間: {slot_label}\n"
            f"人数: {party_size}名"
        ),
    }]

    payload = {"to": store_line_user_id, "messages": messages}
    try:
        resp = requests.post(
            LINE_API_URL, json=payload, headers=_get_headers(channel_token), timeout=10
        )
        return resp.status_code == 200
    except Exception as exc:
        print(f"[LINE Error] {exc}")
        return False
