"""
QRコード生成ユーティリティ
spec.md セクション3.2 予約完了参照
"""
import os
import qrcode
from io import BytesIO
import base64
from pathlib import Path


def generate_qr_code(data: str) -> str:
    """
    QRコードを生成してBase64エンコードされた画像データを返す
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#1a1a2e", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    b64 = base64.b64encode(buffer.read()).decode("utf-8")
    return f"data:image/png;base64,{b64}"


def generate_reservation_qr(reservation_number: str, base_url: str) -> str:
    """予約番号からQRコードを生成（確認URL）"""
    url = f"{base_url}/book/view/{reservation_number}"
    return generate_qr_code(url)
