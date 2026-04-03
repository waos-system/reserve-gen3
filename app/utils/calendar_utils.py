"""
Calendar generation utilities.
"""
from calendar import Calendar, monthrange
from datetime import date, timedelta
from typing import List

from sqlalchemy.orm import Session

from app.models import CalendarSlot, ReservationConfig, Store
from app.utils.holiday_utils import check_store_holiday, is_japanese_holiday


def get_calendar_range(months_ahead: int = 3) -> tuple[date, date]:
    """Return the default generation range."""
    today = date.today()
    if today.month == 12:
        start = date(today.year + 1, 1, 1)
    else:
        start = date(today.year, today.month + 1, 1)

    target_month = start.month + months_ahead
    extra_years = (target_month - 1) // 12
    end_year = start.year + extra_years
    end_month = ((target_month - 1) % 12) + 1
    last_day = monthrange(end_year, end_month)[1]
    end = date(end_year, end_month, last_day)
    return start, end


def build_month_weeks(year: int, month: int, sunday_first: bool = True) -> list[list[int]]:
    """Return month weeks with Sunday or Monday as the first day."""
    firstweekday = 6 if sunday_first else 0
    calendar_obj = Calendar(firstweekday=firstweekday)
    return calendar_obj.monthdayscalendar(year, month)


def generate_time_slots_for_day(config: ReservationConfig) -> List[dict]:
    """Build time slots from a store config."""
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
    """Generate slots using the store's default calendar range."""
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store or not store.config:
        return {"error": "store config not found"}

    config = store.config
    holiday_rules = store.holiday_rules
    months_ahead = config.calendar_months_ahead or 3

    start_date, end_date = get_calendar_range(months_ahead)
    day_slots = generate_time_slots_for_day(config)

    created = 0
    skipped = 0
    current = start_date

    while current <= end_date:
        is_jp_holiday, jp_holiday_name = is_japanese_holiday(current)
        close_on_holidays = getattr(config, "close_on_holidays", True)

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
                current,
                holiday_rules,
                time_slot=slot_def["label"] if config.slot_type == "HALFDAY" else None,
            )

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
    return {"created": created, "skipped": skipped, "total": created + skipped}


def generate_calendar_from(db, store_id: int, start_date: "date" = None, force: bool = False) -> dict:
    """Generate slots starting from an arbitrary date."""
    from datetime import date as _date

    store = db.query(Store).filter(Store.id == store_id).first()
    if not store or not store.config:
        return {"error": "store config not found"}

    config = store.config
    months_ahead = config.calendar_months_ahead or 3

    if start_date is None:
        start_date, end_date = get_calendar_range(months_ahead)
    else:
        target_month = start_date.month + months_ahead
        extra_years = (target_month - 1) // 12
        end_year = start_date.year + extra_years
        end_month = ((target_month - 1) % 12) + 1
        last_day = monthrange(end_year, end_month)[1]
        end_date = _date(end_year, end_month, last_day)

    holiday_rules = store.holiday_rules
    day_slots = generate_time_slots_for_day(config)

    created = 0
    skipped = 0
    current = start_date
    close_on_holidays = getattr(config, "close_on_holidays", True)

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
                current,
                holiday_rules,
                time_slot=slot_def["label"] if config.slot_type == "HALFDAY" else None,
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
