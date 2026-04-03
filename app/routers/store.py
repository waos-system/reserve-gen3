"""
店舗管理ルーター（設定・定休日・予約状況）
spec.md セクション3.1 / セクション4 店舗管理API参照
"""
from datetime import date, timedelta
from urllib.parse import quote
from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models import Store, ReservationConfig, HolidayRule, CalendarSlot, Reservation
from app.routers.auth import get_current_store
from app.utils.calendar_utils import build_month_weeks, generate_calendar

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _require_auth(request: Request, db: Session):
    store = get_current_store(request, db)
    if not store:
        raise HTTPException(status_code=302, headers={"Location": "/store/login"})
    return store


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    store = _require_auth(request, db)
    today = date.today()

    # 今日の予約数
    today_slots = db.query(CalendarSlot).filter(
        CalendarSlot.store_id == store.id,
        CalendarSlot.slot_date == today,
    ).all()
    today_count = sum(
        r.party_size for slot in today_slots
        for r in slot.reservations if r.status in ("PENDING", "CONFIRMED")
    )

    # 今週の予約数
    week_end = today + timedelta(days=7)
    week_slots = db.query(CalendarSlot).filter(
        CalendarSlot.store_id == store.id,
        CalendarSlot.slot_date >= today,
        CalendarSlot.slot_date <= week_end,
    ).all()
    week_count = sum(
        r.party_size for slot in week_slots
        for r in slot.reservations if r.status in ("PENDING", "CONFIRMED")
    )

    # 未確認予約数
    pending_count = db.query(Reservation).filter(
        Reservation.store_id == store.id,
        Reservation.status == "PENDING",
    ).count()

    return templates.TemplateResponse("store/dashboard.html", {
        "request": request,
        "store": store,
        "today_count": today_count,
        "week_count": week_count,
        "pending_count": pending_count,
        "has_config": store.config is not None,
    })


@router.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request, db: Session = Depends(get_db)):
    store = _require_auth(request, db)
    config = store.config
    return templates.TemplateResponse("store/setup.html", {
        "request": request,
        "store": store,
        "config": config,
        "success": request.query_params.get("success"),
    })


@router.post("/setup", response_class=HTMLResponse)
async def setup_post(
    request: Request,
    db: Session = Depends(get_db),
):
    """フォームデータを request.form() で受け取る（同名フィールド重複対策）"""
    store = _require_auth(request, db)
    form = await request.form()

    def _int(key, default):
        try:
            return int(form.get(key, default))
        except (ValueError, TypeError):
            return default

    def _opt_int(key):
        v = form.get(key)
        try:
            return int(v) if v else None
        except (ValueError, TypeError):
            return None

    store_name        = form.get("store_name", store.store_name)
    slot_type         = form.get("slot_type", "DAILY")
    business_start    = form.get("business_start", "09:00")
    business_end      = form.get("business_end", "18:00")
    line_channel_token = form.get("line_channel_token", "")
    line_user_id_val  = form.get("line_user_id", "")
    box_label         = form.get("box_label", "席")
    am_end_time       = form.get("am_end_time", "12:00")

    slot_interval_minutes = _int("slot_interval_minutes", 60)
    capacity_per_slot     = _int("capacity_per_slot", 10)
    box_count             = _int("box_count", 1)
    calendar_months_ahead = _int("calendar_months_ahead", 3)
    am_capacity           = _opt_int("am_capacity")
    pm_capacity           = _opt_int("pm_capacity")

    # 店舗情報更新
    store.store_name = store_name
    if line_channel_token:
        store.line_channel_token = line_channel_token
    if line_user_id_val:
        store.line_user_id = line_user_id_val

    # 予約設定更新/作成
    config = store.config
    if not config:
        config = ReservationConfig(store_id=store.id)
        db.add(config)

    config.slot_type              = slot_type
    config.business_start         = business_start
    config.business_end           = business_end
    config.slot_interval_minutes  = slot_interval_minutes
    config.capacity_per_slot      = capacity_per_slot
    config.box_count              = box_count
    config.box_label              = box_label
    config.calendar_months_ahead  = calendar_months_ahead
    config.am_end_time            = am_end_time
    config.am_capacity            = am_capacity
    config.pm_capacity            = pm_capacity
    config.close_on_holidays      = form.get("close_on_holidays", "1") == "1"

    db.commit()
    return RedirectResponse("/store/setup?success=1", status_code=303)


@router.get("/holidays", response_class=HTMLResponse)
async def holidays_page(request: Request, db: Session = Depends(get_db)):
    store = _require_auth(request, db)
    return templates.TemplateResponse("store/holidays.html", {
        "request": request,
        "store": store,
        "holiday_rules": store.holiday_rules,
        "success": request.query_params.get("success"),
        "weekday_names": ["月", "火", "水", "木", "金", "土", "日"],
    })


@router.post("/holidays/add")
async def add_holiday(
    request: Request,
    db: Session = Depends(get_db),
    rule_type: str = Form(...),
    day_of_week: Optional[int] = Form(None),
    specific_date: Optional[str] = Form(None),
    half_day_restriction: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
):
    store = _require_auth(request, db)

    rule = HolidayRule(
        store_id=store.id,
        rule_type=rule_type,
        day_of_week=day_of_week if rule_type == "WEEKLY" else None,
        specific_date=date.fromisoformat(specific_date) if specific_date else None,
        half_day_restriction=half_day_restriction or None,
        description=description,
    )
    db.add(rule)
    db.commit()
    return RedirectResponse("/store/holidays?success=1", status_code=302)


@router.post("/holidays/delete/{rule_id}")
async def delete_holiday(rule_id: int, request: Request, db: Session = Depends(get_db)):
    store = _require_auth(request, db)
    rule = db.query(HolidayRule).filter(
        HolidayRule.id == rule_id,
        HolidayRule.store_id == store.id,
    ).first()
    if rule:
        db.delete(rule)
        db.commit()
    return RedirectResponse("/store/holidays", status_code=302)


@router.get("/calendar", response_class=HTMLResponse)
async def calendar_page(
    request: Request,
    db: Session = Depends(get_db),
    year: Optional[int] = None,
    month: Optional[int] = None,
):
    store = _require_auth(request, db)

    today = date.today()
    if not year:
        year = today.year
        month = today.month + 1
        if month > 12:
            year += 1
            month = 1
    if not month:
        month = today.month

    # 月のスロット取得
    from calendar import monthrange
    _, last_day = monthrange(year, month)
    start = date(year, month, 1)
    end = date(year, month, last_day)

    slots = db.query(CalendarSlot).filter(
        CalendarSlot.store_id == store.id,
        CalendarSlot.slot_date >= start,
        CalendarSlot.slot_date <= end,
    ).order_by(CalendarSlot.slot_date, CalendarSlot.slot_start).all()

    # 日付でグループ化（キーを文字列"YYYY-MM-DD"にしてJinja2で扱いやすくする）
    calendar_data = {}  # "YYYY-MM-DD" -> [slot, ...]
    for slot in slots:
        key = slot.slot_date.strftime("%Y-%m-%d")
        if key not in calendar_data:
            calendar_data[key] = []
        calendar_data[key].append(slot)

    # 日別サマリー（カレンダーセル表示用）
    # {"YYYY-MM-DD": {"slots": [...], "total_cap": N, "reserved": N, "is_holiday": bool}}
    day_summary = {}
    for key, day_slots in calendar_data.items():
        reserved = sum(s.reserved_count for s in day_slots)
        day_summary[key] = {
            "slots": day_slots,
            "total_cap": sum(s.max_capacity for s in day_slots),
            "reserved": reserved,
            "is_holiday": any(s.is_holiday for s in day_slots),
            "is_available": any(s.is_available for s in day_slots),
        }

    # カレンダーの週構造生成（各セルに日付文字列を付与）
    raw_weeks = build_month_weeks(year, month, sunday_first=True)
    weeks = []
    for week in raw_weeks:
        row = []
        for day_num in week:
            if day_num == 0:
                row.append({"day": 0, "date_str": None})
            else:
                date_str = "%04d-%02d-%02d" % (year, month, day_num)
                row.append({"day": day_num, "date_str": date_str})
        weeks.append(row)

    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1

    return templates.TemplateResponse("store/calendar.html", {
        "request": request,
        "store": store,
        "year": year,
        "month": month,
        "weeks": weeks,
        "calendar_data": calendar_data,
        "day_summary": day_summary,
        "prev_year": prev_year,
        "prev_month": prev_month,
        "next_year": next_year,
        "next_month": next_month,
        "today": today,
        "today_str": today.strftime("%Y-%m-%d"),
        "has_config": store.config is not None,
    })


@router.post("/calendar/generate")
async def generate_calendar_route(request: Request, db: Session = Depends(get_db)):
    store = _require_auth(request, db)
    if not store.config:
        return RedirectResponse("/store/setup", status_code=302)

    form = await request.form()

    # 生成開始日の指定（任意）
    start_date_str = form.get("start_date", "")
    if start_date_str:
        try:
            from app.utils.calendar_utils import generate_calendar_from
            result = generate_calendar_from(db, store.id, start_date=date.fromisoformat(start_date_str))
        except Exception:
            result = generate_calendar(db, store.id)
    else:
        result = generate_calendar(db, store.id)

    # 生成結果の月にリダイレクト
    if start_date_str:
        try:
            sd = date.fromisoformat(start_date_str)
            return RedirectResponse(
                f"/store/calendar?year={sd.year}&month={sd.month}&generated={result.get('created', 0)}",
                status_code=303
            )
        except Exception:
            pass
    return RedirectResponse(f"/store/calendar?generated={result.get('created', 0)}", status_code=303)


@router.post("/calendar/slot/{slot_id}/toggle")
async def toggle_slot(slot_id: int, request: Request, db: Session = Depends(get_db)):
    store = _require_auth(request, db)
    slot = db.query(CalendarSlot).filter(
        CalendarSlot.id == slot_id,
        CalendarSlot.store_id == store.id,
    ).first()
    if slot:
        slot.is_available = not slot.is_available
        db.commit()
    form = await request.form()
    redirect_url = form.get("redirect_url", "/store/calendar")
    return RedirectResponse(redirect_url, status_code=302)


@router.post("/calendar/slot/{slot_id}/update")
async def update_slot(slot_id: int, request: Request, db: Session = Depends(get_db)):
    store = _require_auth(request, db)
    form_data = await request.form()
    slot = db.query(CalendarSlot).filter(
        CalendarSlot.id == slot_id,
        CalendarSlot.store_id == store.id,
    ).first()
    if slot:
        try:
            slot.max_capacity = int(form_data.get("max_capacity", slot.max_capacity))
        except (ValueError, TypeError):
            pass
        note = form_data.get("override_note", "")
        slot.override_note = note if note else None
        db.commit()
    redirect_url = form_data.get("redirect_url", "/store/calendar")
    return RedirectResponse(redirect_url, status_code=303)


@router.get("/reservations", response_class=HTMLResponse)
async def reservations_list(
    request: Request,
    db: Session = Depends(get_db),
    status: Optional[str] = None,
    target_date: Optional[str] = None,
    view: Optional[str] = "calendar",
    year: Optional[int] = None,
    month: Optional[int] = None,
    slot_id: Optional[int] = None,
):
    store = _require_auth(request, db)

    query = db.query(Reservation).filter(Reservation.store_id == store.id)

    if status:
        query = query.filter(Reservation.status == status)

    if target_date:
        try:
            d = date.fromisoformat(target_date)
            query = query.join(CalendarSlot).filter(CalendarSlot.slot_date == d)
        except ValueError:
            pass

    reservations = query.order_by(Reservation.created_at.desc()).limit(100).all()

    today = date.today()
    parsed_target_date = None
    if target_date:
        try:
            parsed_target_date = date.fromisoformat(target_date)
        except ValueError:
            parsed_target_date = None

    if not year:
        year = parsed_target_date.year if parsed_target_date else today.year
    if not month:
        month = parsed_target_date.month if parsed_target_date else today.month

    from calendar import monthrange
    _, last_day = monthrange(year, month)
    month_start = date(year, month, 1)
    month_end = date(year, month, last_day)

    monthly_slots = db.query(CalendarSlot).filter(
        CalendarSlot.store_id == store.id,
        CalendarSlot.slot_date >= month_start,
        CalendarSlot.slot_date <= month_end,
    ).order_by(CalendarSlot.slot_date, CalendarSlot.slot_start).all()

    reservation_slots = {}
    day_summary = {}
    for slot in monthly_slots:
        day_key = slot.slot_date.strftime("%Y-%m-%d")
        reservation_slots.setdefault(day_key, []).append(slot)
        summary = day_summary.setdefault(day_key, {
            "slot_count": 0,
            "reservation_count": 0,
            "confirmed_count": 0,
            "pending_count": 0,
        })
        summary["slot_count"] += 1
        slot_reservations = [r for r in slot.reservations if not status or r.status == status]
        summary["reservation_count"] += len(slot_reservations)
        summary["confirmed_count"] += sum(1 for r in slot_reservations if r.status == "CONFIRMED")
        summary["pending_count"] += sum(1 for r in slot_reservations if r.status == "PENDING")

    weeks = []
    for week in build_month_weeks(year, month, sunday_first=True):
        row = []
        for day_num in week:
            if day_num == 0:
                row.append({"day": 0, "date_str": None})
            else:
                row.append({"day": day_num, "date_str": f"{year:04d}-{month:02d}-{day_num:02d}"})
        weeks.append(row)

    selected_date = None
    if parsed_target_date:
        selected_date = parsed_target_date.strftime("%Y-%m-%d")
    if not selected_date:
        selected_date = next((key for key, summary in sorted(day_summary.items()) if summary["reservation_count"] > 0), None)

    selected_slots = reservation_slots.get(selected_date, []) if selected_date else []
    if status:
        selected_slots = [
            slot for slot in selected_slots
            if any(res.status == status for res in slot.reservations)
        ]

    selected_slot_groups = []
    for slot in selected_slots:
        filtered_reservations = [
            reservation for reservation in slot.reservations
            if not status or reservation.status == status
        ]
        filtered_reservations.sort(key=lambda reservation: reservation.created_at)
        selected_slot_groups.append({
            "slot": slot,
            "reservations": filtered_reservations,
            "reservation_count": len(filtered_reservations),
        })

    selected_slot = None
    if slot_id:
        selected_slot = next((slot for slot in selected_slots if slot.id == slot_id), None)
    if not selected_slot and selected_slots:
        selected_slot = selected_slots[0]

    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1

    return_url = str(request.url.path) + (f"?{request.url.query}" if request.url.query else "")

    return templates.TemplateResponse("store/reservations.html", {
        "request": request,
        "store": store,
        "reservations": reservations,
        "filter_status": status,
        "filter_date": target_date,
        "view_mode": view or "list",
        "weeks": weeks,
        "day_summary": day_summary,
        "selected_date": selected_date,
        "selected_slots": selected_slots,
        "selected_slot_groups": selected_slot_groups,
        "selected_slot": selected_slot,
        "year": year,
        "month": month,
        "prev_year": prev_year,
        "prev_month": prev_month,
        "next_year": next_year,
        "next_month": next_month,
        "return_url": return_url,
        "return_url_quoted": quote(return_url, safe=""),
    })


# ======================================================
# 予約編集（店舗側）
# ======================================================

@router.get("/reservations/{reservation_id}/edit", response_class=HTMLResponse)
async def edit_reservation_page(
    reservation_id: int, request: Request, db: Session = Depends(get_db)
):
    store = _require_auth(request, db)
    reservation = db.query(Reservation).filter(
        Reservation.id == reservation_id,
        Reservation.store_id == store.id,
    ).first()
    if not reservation:
        raise HTTPException(status_code=404)
    return_url = request.query_params.get("return_url") or request.headers.get("referer") or "/store/reservations?view=calendar"
    return templates.TemplateResponse("store/reservation_edit.html", {
        "request": request,
        "store": store,
        "reservation": reservation,
        "slot": reservation.slot,
        "success": request.query_params.get("success"),
        "return_url": return_url,
        "return_url_quoted": quote(return_url, safe=""),
    })


@router.post("/reservations/{reservation_id}/update")
async def update_reservation(
    reservation_id: int, request: Request, db: Session = Depends(get_db)
):
    store = _require_auth(request, db)
    reservation = db.query(Reservation).filter(
        Reservation.id == reservation_id,
        Reservation.store_id == store.id,
    ).first()
    if not reservation:
        raise HTTPException(status_code=404)

    form = await request.form()
    reservation.customer_name  = form.get("customer_name", reservation.customer_name)
    reservation.customer_phone = form.get("customer_phone", reservation.customer_phone)
    reservation.customer_email = form.get("customer_email") or None
    try:
        reservation.party_size = int(form.get("party_size", reservation.party_size))
    except (ValueError, TypeError):
        pass
    new_status = form.get("status")
    if new_status in ("PENDING", "CONFIRMED", "CANCELLED"):
        reservation.status = new_status
        if new_status == "CONFIRMED" and not reservation.confirmed_at:
            from datetime import datetime
            reservation.confirmed_at = datetime.utcnow()
    reservation.notes = form.get("notes") or None
    db.commit()
    return_url = form.get("return_url") or "/store/reservations?view=calendar"
    return RedirectResponse(
        f"/store/reservations/{reservation_id}/edit?success=1&return_url={quote(return_url, safe='')}", status_code=303
    )


@router.post("/reservations/{reservation_id}/delete")
async def delete_reservation(
    reservation_id: int, request: Request, db: Session = Depends(get_db)
):
    store = _require_auth(request, db)
    reservation = db.query(Reservation).filter(
        Reservation.id == reservation_id,
        Reservation.store_id == store.id,
    ).first()
    form = await request.form()
    return_url = form.get("return_url") or "/store/reservations?view=calendar"
    if reservation:
        db.delete(reservation)
        db.commit()
    return RedirectResponse(return_url, status_code=303)


# ======================================================
# 新規店舗登録
# ======================================================

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """新規店舗登録画面（未ログイン状態でアクセス可）"""
    if request.session.get("store_id"):
        return RedirectResponse("/store/dashboard", status_code=302)
    return templates.TemplateResponse("store/register.html", {
        "request": request,
        "error": None,
    })


@router.post("/register")
async def register_post(request: Request, db: Session = Depends(get_db)):
    import bcrypt as _bcrypt
    form = await request.form()

    store_name   = form.get("store_name", "").strip()
    phone_number = form.get("phone_number", "").strip()
    password     = form.get("password", "")
    password2    = form.get("password2", "")

    def err(msg):
        return templates.TemplateResponse("store/register.html", {
            "request": request, "error": msg,
            "store_name": store_name, "phone_number": phone_number,
        })

    if not store_name:
        return err("店舗名を入力してください")
    if not phone_number:
        return err("電話番号を入力してください")
    if len(password) < 6:
        return err("パスワードは6文字以上で入力してください")
    if password != password2:
        return err("パスワードが一致しません")

    existing = db.query(Store).filter(Store.phone_number == phone_number).first()
    if existing:
        return err("この電話番号は既に登録されています")

    pw_hash = _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()
    store = Store(
        phone_number=phone_number,
        password_hash=pw_hash,
        store_name=store_name,
        line_channel_token="", line_user_id="",
    )
    db.add(store)
    db.commit()
    db.refresh(store)

    request.session["store_id"] = str(store.id)
    request.session["store_name"] = store.store_name
    return RedirectResponse("/store/setup", status_code=303)
