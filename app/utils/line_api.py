"""
LINE Messaging API 連携
spec.md セクション3.2 LINE通知フロー参照
"""
import os
import requests
from typing import Optional


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
    """
    仮予約通知をLINEで送信。
    顧客が確認URLをタップすると予約が確定する。
    """
    if not channel_token or channel_token == "your-line-channel-access-token":
        print(f"[LINE Mock] 仮予約通知 → {line_user_id}: {reservation_number}")
        return True

    messages = [
        {
            "type": "flex",
            "altText": f"【{store_name}】仮予約を受け付けました",
            "contents": {
                "type": "bubble",
                "header": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "text",
                            "text": store_name,
                            "weight": "bold",
                            "color": "#ffffff",
                            "size": "sm",
                        }
                    ],
                    "backgroundColor": "#1a1a2e",
                    "paddingAll": "12px",
                },
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "text",
                            "text": "仮予約を受け付けました",
                            "weight": "bold",
                            "size": "md",
                            "margin": "md",
                        },
                        {
                            "type": "separator",
                            "margin": "md",
                        },
                        {
                            "type": "box",
                            "layout": "vertical",
                            "margin": "md",
                            "spacing": "sm",
                            "contents": [
                                _info_row("予約番号", reservation_number),
                                _info_row("お名前", customer_name),
                                _info_row("日付", slot_date),
                                _info_row("時間帯", slot_label),
                            ],
                        },
                        {
                            "type": "text",
                            "text": "下のボタンから予約を確定してください",
                            "size": "sm",
                            "color": "#888888",
                            "margin": "lg",
                            "wrap": True,
                        },
                    ],
                },
                "footer": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "button",
                            "style": "primary",
                            "color": "#e94560",
                            "action": {
                                "type": "uri",
                                "label": "予約を確定する",
                                "uri": confirm_url,
                            },
                        }
                    ],
                },
            },
        }
    ]

    payload = {"to": line_user_id, "messages": messages}
    try:
        resp = requests.post(
            LINE_API_URL, json=payload, headers=_get_headers(channel_token), timeout=10
        )
        return resp.status_code == 200
    except Exception as e:
        print(f"[LINE Error] {e}")
        return False


def send_confirmation_notice(
    channel_token: str,
    line_user_id: str,
    reservation_number: str,
    customer_name: str,
    slot_date: str,
    slot_label: str,
    store_name: str,
) -> bool:
    """予約確定通知（顧客向け）"""
    if not channel_token or channel_token == "your-line-channel-access-token":
        print(f"[LINE Mock] 予約確定通知 → {line_user_id}: {reservation_number}")
        return True

    messages = [
        {
            "type": "text",
            "text": (
                f"【{store_name}】予約が確定しました！\n\n"
                f"予約番号: {reservation_number}\n"
                f"お名前: {customer_name}\n"
                f"日付: {slot_date}\n"
                f"時間帯: {slot_label}\n\n"
                "ご来店をお待ちしております 🎉"
            ),
        }
    ]

    payload = {"to": line_user_id, "messages": messages}
    try:
        resp = requests.post(
            LINE_API_URL, json=payload, headers=_get_headers(channel_token), timeout=10
        )
        return resp.status_code == 200
    except Exception as e:
        print(f"[LINE Error] {e}")
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
    """店舗への予約通知"""
    if not channel_token or channel_token == "your-line-channel-access-token":
        print(f"[LINE Mock] 店舗通知 → {store_line_user_id}: {reservation_number}")
        return True

    messages = [
        {
            "type": "text",
            "text": (
                f"【新規予約】\n\n"
                f"予約番号: {reservation_number}\n"
                f"お名前: {customer_name}\n"
                f"電話: {customer_phone}\n"
                f"日付: {slot_date}\n"
                f"時間帯: {slot_label}\n"
                f"人数: {party_size}名"
            ),
        }
    ]

    payload = {"to": store_line_user_id, "messages": messages}
    try:
        resp = requests.post(
            LINE_API_URL, json=payload, headers=_get_headers(channel_token), timeout=10
        )
        return resp.status_code == 200
    except Exception as e:
        print(f"[LINE Error] {e}")
        return False


def _info_row(label: str, value: str) -> dict:
    return {
        "type": "box",
        "layout": "horizontal",
        "contents": [
            {
                "type": "text",
                "text": label,
                "size": "sm",
                "color": "#888888",
                "flex": 2,
            },
            {
                "type": "text",
                "text": value,
                "size": "sm",
                "weight": "bold",
                "flex": 3,
                "wrap": True,
            },
        ],
    }
