"""
カレンダー生成ロジック
spec.md セクション3.1 カレンダー生成参照
翌月から設定月数後の末日までのスロットを生成する
"""
from datetime import date, timedelta
from calendar import monthrange
from typing import List
from sqlalchemy.orm import Session

from app.models import CalendarSlot, ReservationConfig, HolidayRule, Store
from app.utils.holiday_utils import is_japanese_holiday, check_store_holiday


def get_calendar_range(months_ahead: int = 3) -> tuple[date, date]:
    """
    カレンダー生成範囲を計算
    翌月1日〜(months_ahead)ヶ月後の末日
    """
    today = date.today()
    # 翌月1日
    if today.month == 12:
        start = date(today.year + 1, 1, 1)
    else:
        start = date(today.year, today.month + 1, 1)

    # months_ahead ヶ月後の末日
    end_year = start.year + (start.month + months_ahead - 2) // 12
    end_month = (start.month + months_ahead - 1) % 12 or 12
    # 月を正規化
    target_month = start.month + months_ahead
    extra_years = (target_month - 1) // 12
    end_year = start.year + extra_years
    end_month = ((target_month - 1) % 12) + 1
    last_day = monthrange(end_year, end_month)[1]
    end = date(end_year, end_month, last_day)

    return start, end


def generate_time_slots_for_day(config: ReservationConfig) -> List[dict]:
    """
    予約設定に基づき1日分のスロット定義を生成
    Returns: [{"label": "10:00-11:00", "start": "10:00", "end": "11:00", "capacity": N}]
    """
    slots = []

    if config.slot_type == "DAILY":
        capacity = (config.capacity_per_slot or 10) * (config.box_count or 1)
        slots.append({
            "label": "終日",
            "start": config.business_start or "09:00",
            "end": config.business_end or "18:00",
            "capacity": capacity,
        })

    elif config.slot_type == "HALFDAY":
        am_cap = (config.am_capacity or config.capacity_per_slot or 10) * (config.box_count or 1)
        pm_cap = (config.pm_capacity or config.capacity_per_slot or 10) * (config.box_count or 1)
        am_end = config.am_end_time or "12:00"
        slots.append({
            "label": "午前",
            "start": config.business_start or "09:00",
            "end": am_end,
            "capacity": am_cap,
        })
        slots.append({
            "label": "午後",
            "start": am_end,
            "end": config.business_end or "18:00",
            "capacity": pm_cap,
        })

    elif config.slot_type == "HOURLY":
        interval = config.slot_interval_minutes or 60
        capacity_per = (config.capacity_per_slot or 2) * (config.box_count or 1)

        start_h, start_m = map(int, (config.business_start or "09:00").split(":"))
        end_h, end_m = map(int, (config.business_end or "18:00").split(":"))
        start_minutes = start_h * 60 + start_m
        end_minutes = end_h * 60 + end_m

        current = start_minutes
        while current + interval <= end_minutes:
            slot_start = f"{current // 60:02d}:{current % 60:02d}"
            slot_end_min = current + interval
            slot_end = f"{slot_end_min // 60:02d}:{slot_end_min % 60:02d}"
            slots.append({
                "label": f"{slot_start}-{slot_end}",
                "start": slot_start,
                "end": slot_end,
                "capacity": capacity_per,
            })
            current += interval

    return slots


def generate_calendar(db: Session, store_id: int, force: bool = False) -> dict:
    """
    店舗の予約カレンダーを生成・更新する。
    既存スロットは上書きしない（force=Trueで強制再生成）
    Returns: {"created": N, "skipped": N, "total": N}
    """
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store or not store.config:
        return {"error": "店舗設定が見つかりません"}

    config = store.config
    holiday_rules = store.holiday_rules
    months_ahead = config.calendar_months_ahead or 3

    start_date, end_date = get_calendar_range(months_ahead)
    day_slots = generate_time_slots_for_day(config)

    created = 0
    skipped = 0
    current = start_date

    while current <= end_date:
        # 日本祝日チェック
        is_jp_holiday, jp_holiday_name = is_japanese_holiday(current)
        # 祝日を休業にするかは店舗設定で決まる
        close_on_holidays = getattr(config, 'close_on_holidays', True)

        for slot_def in day_slots:
            # 既存スロット確認
            existing = db.query(CalendarSlot).filter(
                CalendarSlot.store_id == store_id,
                CalendarSlot.slot_date == current,
                CalendarSlot.slot_label == slot_def["label"],
            ).first()

            if existing and not force:
                skipped += 1
                continue

            # 店舗定休日チェック（time_slot はラベルを使う）
            is_store_hol, store_hol_reason = check_store_holiday(
                current, holiday_rules,
                time_slot=slot_def["label"] if config.slot_type == "HALFDAY" else None
            )

            # 祝日フラグ: 表示用（常にセット）
            # 予約可否: 店舗設定 close_on_holidays に従う
            is_holiday_flag = (is_jp_holiday and close_on_holidays) or is_store_hol
            holiday_reason = (jp_holiday_name if is_jp_holiday else None) or store_hol_reason

            if existing and force:
                existing.max_capacity = slot_def["capacity"]
                existing.slot_start = slot_def["start"]
                existing.slot_end = slot_def["end"]
                existing.is_holiday = is_holiday_flag
                existing.is_available = not is_holiday_flag
                existing.holiday_reason = holiday_reason
                skipped += 1
            else:
                slot = CalendarSlot(
                    store_id=store_id,
                    slot_date=current,
                    slot_label=slot_def["label"],
                    slot_start=slot_def["start"],
                    slot_end=slot_def["end"],
                    max_capacity=slot_def["capacity"],
                    is_available=not is_holiday_flag,
                    is_holiday=is_holiday_flag,
                    holiday_reason=holiday_reason,
                )
                db.add(slot)
                created += 1

        current += timedelta(days=1)

    db.commit()
    total = created + skipped
    return {"created": created, "skipped": skipped, "total": total}


def generate_calendar_from(db, store_id: int, start_date: "date" = None, force: bool = False) -> dict:
    """
    任意の開始日からカレンダーを生成する。
    start_date が None の場合は generate_calendar() と同じ動作（翌月から）。
    """
    from datetime import date as _date
    from app.models import Store
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store or not store.config:
        return {"error": "店舗設定が見つかりません"}

    config = store.config
    months_ahead = config.calendar_months_ahead or 3

    if start_date is None:
        start_date, end_date = get_calendar_range(months_ahead)
    else:
        # 指定開始日〜(months_ahead)ヶ月後末日
        from calendar import monthrange
        end_year = start_date.year + (start_date.month + months_ahead - 2) // 12
        end_month = ((start_date.month + months_ahead - 1) % 12) or 12
        target_month = start_date.month + months_ahead
        extra_years = (target_month - 1) // 12
        end_year = start_date.year + extra_years
        end_month = ((target_month - 1) % 12) + 1
        last_day = monthrange(end_year, end_month)[1]
        end_date = _date(end_year, end_month, last_day)

    holiday_rules = store.holiday_rules
    day_slots = generate_time_slots_for_day(config)

    from datetime import timedelta
    from app.models import CalendarSlot
    from app.utils.holiday_utils import is_japanese_holiday, check_store_holiday

    created = 0
    skipped = 0
    current = start_date

    close_on_holidays = getattr(config, 'close_on_holidays', True)

    while current <= end_date:
        is_jp_holiday, jp_holiday_name = is_japanese_holiday(current)
        for slot_def in day_slots:
            existing = db.query(CalendarSlot).filter(
                CalendarSlot.store_id == store_id,
                CalendarSlot.slot_date == current,
                CalendarSlot.slot_label == slot_def["label"],
            ).first()

            if existing and not force:
                skipped += 1
                continue

            is_store_hol, store_hol_reason = check_store_holiday(
                current, holiday_rules,
                time_slot=slot_def["label"] if config.slot_type == "HALFDAY" else None
            )
            is_holiday = (is_jp_holiday and close_on_holidays) or is_store_hol
            holiday_reason = (jp_holiday_name if is_jp_holiday else None) or store_hol_reason

            if existing and force:
                existing.max_capacity = slot_def["capacity"]
                existing.slot_start = slot_def["start"]
                existing.slot_end = slot_def["end"]
                existing.is_holiday = is_holiday
                existing.is_available = not is_holiday
                existing.holiday_reason = holiday_reason
                skipped += 1
            else:
                slot = CalendarSlot(
                    store_id=store_id,
                    slot_date=current,
                    slot_label=slot_def["label"],
                    slot_start=slot_def["start"],
                    slot_end=slot_def["end"],
                    max_capacity=slot_def["capacity"],
                    is_available=not is_holiday,
                    is_holiday=is_holiday,
                    holiday_reason=holiday_reason,
                )
                db.add(slot)
                created += 1
        current += timedelta(days=1)

    db.commit()
    return {"created": created, "skipped": skipped, "total": created + skipped}
