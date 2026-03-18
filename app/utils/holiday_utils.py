"""
日本祝日・定休日ユーティリティ
spec.md セクション3.1 カレンダー生成参照
"""
from datetime import date, timedelta
from typing import Optional
import jpholiday


def is_japanese_holiday(target_date: date) -> tuple[bool, Optional[str]]:
    """日本の祝日判定。(is_holiday, holiday_name) を返す"""
    name = jpholiday.is_holiday_name(target_date)
    if name:
        return True, name
    return False, None


def get_holidays_in_range(start: date, end: date) -> dict[date, str]:
    """指定期間の祝日一覧を返す {date: holiday_name}"""
    holidays = {}
    current = start
    while current <= end:
        is_hol, name = is_japanese_holiday(current)
        if is_hol:
            holidays[current] = name
        current += timedelta(days=1)
    return holidays


def check_store_holiday(
    target_date: date,
    holiday_rules: list,
    time_slot: Optional[str] = None
) -> tuple[bool, Optional[str]]:
    """
    店舗の定休日ルールに基づき休日判定。
    time_slot: None=終日 / 'AM' / 'PM' / 'HH:MM'
    Returns: (is_holiday, reason)
    """
    day_of_week = target_date.weekday()  # 0=月曜

    for rule in holiday_rules:
        if rule.rule_type == "WEEKLY":
            if rule.day_of_week == day_of_week:
                # 半日制限チェック
                if rule.half_day_restriction is None:
                    return True, f"定休日（{_weekday_name(day_of_week)}）"
                elif time_slot and rule.half_day_restriction == time_slot:
                    return True, f"定休（{rule.half_day_restriction}）"

        elif rule.rule_type == "SPECIFIC":
            if rule.specific_date == target_date:
                if rule.half_day_restriction is None:
                    return True, rule.description or "臨時休業"
                elif time_slot and rule.half_day_restriction == time_slot:
                    return True, rule.description or f"臨時休業（{rule.half_day_restriction}）"

    return False, None


def _weekday_name(day_of_week: int) -> str:
    names = ["月曜", "火曜", "水曜", "木曜", "金曜", "土曜", "日曜"]
    return names[day_of_week] if 0 <= day_of_week <= 6 else "不明"
