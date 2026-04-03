"""
顧客予約ルーター
spec.md セクション3.2 顧客予約フロー参照
"""
import os
import uuid
from datetime import date, datetime, timedelta
from calendar import monthrange
from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models import Store, CalendarSlot, Reservation
from app.utils.calendar_utils import build_month_weeks
from app.utils.email_utils import send_reservation_access_email
from app.utils.qr_utils import generate_reservation_qr
from app.utils.line_api import (
    send_pending_reservation_notice,
    send_confirmation_notice,
    send_store_notification,
)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")


def _generate_reservation_number() -> str:
    """予約番号生成: RES-YYYYMMDD-XXXX"""
    today = date.today().strftime("%Y%m%d")
    suffix = uuid.uuid4().hex[:4].upper()
    return f"RES-{today}-{suffix}"


@router.get("/{store_id}", response_class=HTMLResponse)
async def booking_top(
    store_id: int,
    request: Request,
    db: Session = Depends(get_db),
    year: Optional[int] = None,
    month: Optional[int] = None,
):
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="店舗が見つかりません")

    today = date.today()
    if not year:
        year = today.year
        month = today.month
    if not month:
        month = today.month

    _, last_day = monthrange(year, month)
    start = date(year, month, 1)
    end = date(year, month, last_day)

    slots = db.query(CalendarSlot).filter(
        CalendarSlot.store_id == store_id,
        CalendarSlot.slot_date >= max(start, today),
        CalendarSlot.slot_date <= end,
        CalendarSlot.is_available == True,
    ).order_by(CalendarSlot.slot_date, CalendarSlot.slot_start).all()

    # 日別利用可能状況まとめ
    available_dates = {}
    for slot in slots:
        d = slot.slot_date
        remaining = slot.remaining_capacity
        if d not in available_dates:
            available_dates[d] = {"total": 0, "has_available": False}
        available_dates[d]["total"] += remaining
        if remaining > 0:
            available_dates[d]["has_available"] = True

    weeks = _build_calendar_weeks(year, month, today, available_dates)

    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1

    return templates.TemplateResponse("customer/index.html", {
        "request": request,
        "store": store,
        "year": year,
        "month": month,
        "weeks": weeks,
        "available_dates": available_dates,
        "today": today,
        "prev_year": prev_year,
        "prev_month": prev_month,
        "next_year": next_year,
        "next_month": next_month,
    })


@router.get("/{store_id}/slots/{slot_date}", response_class=HTMLResponse)
async def slot_list(
    store_id: int,
    slot_date: str,
    request: Request,
    db: Session = Depends(get_db),
):
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404)

    try:
        d = date.fromisoformat(slot_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="日付形式が正しくありません")

    slots = db.query(CalendarSlot).filter(
        CalendarSlot.store_id == store_id,
        CalendarSlot.slot_date == d,
        CalendarSlot.is_available == True,
    ).order_by(CalendarSlot.slot_start).all()

    return templates.TemplateResponse("customer/slots.html", {
        "request": request,
        "store": store,
        "slots": slots,
        "slot_date": d,
    })


@router.get("/{store_id}/form/{slot_id}", response_class=HTMLResponse)
async def booking_form(
    store_id: int,
    slot_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    store = db.query(Store).filter(Store.id == store_id).first()
    slot = db.query(CalendarSlot).filter(
        CalendarSlot.id == slot_id,
        CalendarSlot.store_id == store_id,
    ).first()

    if not store or not slot:
        raise HTTPException(status_code=404)

    if not slot.is_available or slot.remaining_capacity <= 0:
        return templates.TemplateResponse("customer/full.html", {
            "request": request,
            "store": store,
            "slot": slot,
        })

    return templates.TemplateResponse("customer/form.html", {
        "request": request,
        "store": store,
        "slot": slot,
        "error": None,
    })


@router.post("/{store_id}/create", response_class=HTMLResponse)
async def create_reservation(
    store_id: int,
    request: Request,
    db: Session = Depends(get_db),
    slot_id: int = Form(...),
    customer_name: str = Form(...),
    customer_phone: str = Form(...),
    customer_email: Optional[str] = Form(None),
    party_size: int = Form(1),
    notes: Optional[str] = Form(None),
    line_user_id: Optional[str] = Form(None),
):
    store = db.query(Store).filter(Store.id == store_id).first()
    slot = db.query(CalendarSlot).filter(
        CalendarSlot.id == slot_id,
        CalendarSlot.store_id == store_id,
    ).first()

    if not store or not slot:
        raise HTTPException(status_code=404)

    # 空き確認
    if slot.remaining_capacity < party_size:
        return templates.TemplateResponse("customer/form.html", {
            "request": request,
            "store": store,
            "slot": slot,
            "error": f"ご希望の人数({party_size}名)は予約できません。残り{slot.remaining_capacity}名分です。",
        })

    # 予約作成
    reservation_number = _generate_reservation_number()
    confirmation_token = str(uuid.uuid4())

    reservation = Reservation(
        reservation_number=reservation_number,
        store_id=store_id,
        slot_id=slot_id,
        customer_name=customer_name,
        customer_phone=customer_phone,
        customer_email=customer_email or None,
        party_size=party_size,
        status="PENDING",
        confirmation_token=confirmation_token,
        line_user_id=line_user_id or None,
        notes=notes or None,
    )
    db.add(reservation)
    db.commit()
    db.refresh(reservation)

    # QRコード生成
    qr_data = generate_reservation_qr(reservation_number, BASE_URL)
    reservation.qr_code_path = qr_data
    db.commit()

    # LINE通知（仮予約）
    confirm_url = f"{BASE_URL}/confirm/{confirmation_token}"
    if store.line_channel_token and line_user_id:
        send_pending_reservation_notice(
            channel_token=store.line_channel_token,
            line_user_id=line_user_id,
            reservation_number=reservation_number,
            customer_name=customer_name,
            slot_date=str(slot.slot_date),
            slot_label=slot.slot_label,
            store_name=store.store_name,
            confirm_url=confirm_url,
        )

    return RedirectResponse(
        f"/book/complete/{reservation_number}",
        status_code=302,
    )


@router.get("/complete/{reservation_number}", response_class=HTMLResponse)
async def booking_complete(
    reservation_number: str,
    request: Request,
    db: Session = Depends(get_db),
):
    reservation = db.query(Reservation).filter(
        Reservation.reservation_number == reservation_number
    ).first()

    if not reservation:
        raise HTTPException(status_code=404)

    store = reservation.store
    slot = reservation.slot

    return templates.TemplateResponse("customer/complete.html", {
        "request": request,
        "reservation": reservation,
        "store": store,
        "slot": slot,
        "confirm_url": f"{BASE_URL}/confirm/{reservation.confirmation_token}",
        "access_url": f"{BASE_URL}/book/view/{reservation.reservation_number}",
    })


@router.get("/view/{reservation_number}", response_class=HTMLResponse)
async def view_reservation(
    reservation_number: str,
    request: Request,
    db: Session = Depends(get_db),
):
    reservation = db.query(Reservation).filter(
        Reservation.reservation_number == reservation_number
    ).first()

    if not reservation:
        raise HTTPException(status_code=404)

    template_name = "customer/confirmed.html" if reservation.status == "CONFIRMED" else "customer/view.html"
    return templates.TemplateResponse(template_name, {
        "request": request,
        "reservation": reservation,
        "store": reservation.store,
        "slot": reservation.slot,
        "already": reservation.status == "CONFIRMED",
        "access_url": f"{BASE_URL}/book/view/{reservation.reservation_number}",
    })


@router.get("/confirm/{token}", response_class=HTMLResponse)
async def confirm_reservation(
    token: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """LINE確認URLクリック時の処理"""
    reservation = db.query(Reservation).filter(
        Reservation.confirmation_token == token
    ).first()

    if not reservation:
        return templates.TemplateResponse("customer/confirm_error.html", {
            "request": request,
            "message": "予約が見つかりません",
        })

    if reservation.status == "CONFIRMED":
        return templates.TemplateResponse("customer/confirmed.html", {
            "request": request,
            "reservation": reservation,
            "store": reservation.store,
            "slot": reservation.slot,
            "already": True,
            "access_url": f"{BASE_URL}/book/view/{reservation.reservation_number}",
        })

    if reservation.status == "CANCELLED":
        return templates.TemplateResponse("customer/confirm_error.html", {
            "request": request,
            "message": "この予約はキャンセル済みです",
        })

    # 予約確定処理
    reservation.status = "CONFIRMED"
    reservation.confirmed_at = datetime.utcnow()
    if not reservation.qr_code_path:
        reservation.qr_code_path = generate_reservation_qr(
            reservation.reservation_number,
            BASE_URL,
        )
    db.commit()

    store = reservation.store
    slot = reservation.slot
    access_url = f"{BASE_URL}/book/view/{reservation.reservation_number}"

    # 確定通知（顧客）
    if store.line_channel_token and reservation.line_user_id:
        send_confirmation_notice(
            channel_token=store.line_channel_token,
            line_user_id=reservation.line_user_id,
            reservation_number=reservation.reservation_number,
            customer_name=reservation.customer_name,
            slot_date=str(slot.slot_date),
            slot_label=slot.slot_label,
            store_name=store.store_name,
            access_url=access_url,
        )

    if reservation.customer_email:
        send_reservation_access_email(
            to_email=reservation.customer_email,
            store_name=store.store_name,
            reservation_number=reservation.reservation_number,
            customer_name=reservation.customer_name,
            slot_date=str(slot.slot_date),
            slot_label=slot.slot_label,
            access_url=access_url,
        )

    # 店舗への通知
    if store.line_channel_token and store.line_user_id:
        send_store_notification(
            channel_token=store.line_channel_token,
            store_line_user_id=store.line_user_id,
            reservation_number=reservation.reservation_number,
            customer_name=reservation.customer_name,
            customer_phone=reservation.customer_phone,
            slot_date=str(slot.slot_date),
            slot_label=slot.slot_label,
            party_size=reservation.party_size,
        )

    return templates.TemplateResponse("customer/confirmed.html", {
        "request": request,
        "reservation": reservation,
        "store": store,
        "slot": slot,
        "already": False,
        "access_url": access_url,
    })


def _build_calendar_weeks(year, month, today, available_dates):
    """カレンダーの週構造を構築"""
    weeks_raw = build_month_weeks(year, month, sunday_first=True)
    weeks = []
    for week in weeks_raw:
        week_days = []
        for day_num in week:
            if day_num == 0:
                week_days.append({"day": 0, "date": None, "status": "empty"})
            else:
                d = date(year, month, day_num)
                if d < today:
                    status = "past"
                elif d in available_dates and available_dates[d]["has_available"]:
                    status = "available"
                elif d in available_dates:
                    status = "full"
                else:
                    status = "closed"
                week_days.append({"day": day_num, "date": d, "status": status})
        weeks.append(week_days)
    return weeks
