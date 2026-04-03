"""
Email sending helpers.
"""
import os
import smtplib
from email.message import EmailMessage


def send_reservation_access_email(
    to_email: str,
    store_name: str,
    reservation_number: str,
    customer_name: str,
    slot_date: str,
    slot_label: str,
    access_url: str,
) -> bool:
    if not to_email:
        return False

    smtp_host = os.getenv("SMTP_HOST", "").strip()
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
    smtp_from = os.getenv("SMTP_FROM", smtp_user or "noreply@example.com").strip()
    smtp_from_name = os.getenv("SMTP_FROM_NAME", store_name).strip()
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

    if not smtp_host:
        print(f"[EMAIL Mock] confirmed access url -> {to_email}: {access_url}")
        return True

    message = EmailMessage()
    message["Subject"] = f"[{store_name}] ご予約確定のお知らせ"
    message["From"] = f"{smtp_from_name} <{smtp_from}>"
    message["To"] = to_email
    message.set_content(
        "\n".join([
            f"{customer_name} 様",
            "",
            f"{store_name} のご予約が確定しました。",
            f"予約番号: {reservation_number}",
            f"日付: {slot_date}",
            f"時間: {slot_label}",
            "",
            "あとで予約内容を確認する場合は、以下のURLをご利用ください。",
            access_url,
            "",
            "このメールは自動送信です。",
        ])
    )

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as smtp:
            if use_tls:
                smtp.starttls()
            if smtp_user:
                smtp.login(smtp_user, smtp_password)
            smtp.send_message(message)
        return True
    except Exception as exc:
        print(f"[EMAIL Error] {exc}")
        return False
