"""
カレンダー生成・祝日ユーティリティのテスト
spec.md セクション3.1 カレンダー生成参照
"""
import pytest
from datetime import date, timedelta
from calendar import monthrange

from app.utils.calendar_utils import (
    build_month_weeks,
    get_calendar_range,
    generate_time_slots_for_day,
    generate_calendar,
)
from app.utils.holiday_utils import (
    is_japanese_holiday,
    check_store_holiday,
    get_holidays_in_range,
)
from app.models import ReservationConfig, CalendarSlot
from tests.conftest import create_test_store, create_test_config


class TestCalendarRange:
    def test_build_month_weeks_starts_sunday(self):
        weeks = build_month_weeks(2025, 6, sunday_first=True)
        assert weeks[0][0] == 1

    def test_range_starts_next_month(self):
        """カレンダーは翌月1日から始まる"""
        today = date.today()
        start, end = get_calendar_range(3)
        # 翌月1日
        if today.month == 12:
            expected_start = date(today.year + 1, 1, 1)
        else:
            expected_start = date(today.year, today.month + 1, 1)
        assert start == expected_start

    def test_range_ends_on_last_day(self):
        """カレンダーは指定月数後の末日に終わる"""
        start, end = get_calendar_range(3)
        # 末日チェック（翌月の1日の前日 = 末日）
        next_month_first = date(end.year + (1 if end.month == 12 else 0),
                                1 if end.month == 12 else end.month + 1, 1)
        assert end == next_month_first - timedelta(days=1)

    def test_range_1_month(self):
        """1ヶ月の場合も正しく計算される"""
        start, end = get_calendar_range(1)
        assert start.day == 1
        assert end.day == monthrange(end.year, end.month)[1]

    def test_range_6_months(self):
        """6ヶ月の場合も正しく計算される"""
        start, end = get_calendar_range(6)
        total_days = (end - start).days + 1
        assert total_days > 150  # 少なくとも5ヶ月分以上


class TestTimeSlotGeneration:
    def test_hourly_slots_count(self, db):
        """HOURLY: 9時〜18時、1時間間隔で9スロット生成"""
        config = ReservationConfig(
            store_id=999,  # dummy
            slot_type="HOURLY",
            business_start="09:00",
            business_end="18:00",
            slot_interval_minutes=60,
            capacity_per_slot=4,
            box_count=1,
        )
        slots = generate_time_slots_for_day(config)
        assert len(slots) == 9

    def test_hourly_slots_labels(self, db):
        """HOURLY: スロットラベルが正しい"""
        config = ReservationConfig(
            store_id=999,
            slot_type="HOURLY",
            business_start="10:00",
            business_end="12:00",
            slot_interval_minutes=60,
            capacity_per_slot=2,
            box_count=1,
        )
        slots = generate_time_slots_for_day(config)
        assert len(slots) == 2
        assert slots[0]["label"] == "10:00-11:00"
        assert slots[1]["label"] == "11:00-12:00"

    def test_hourly_capacity_with_boxes(self):
        """HOURLY: ボックス数×収容人数で計算"""
        config = ReservationConfig(
            store_id=999,
            slot_type="HOURLY",
            business_start="09:00",
            business_end="10:00",
            slot_interval_minutes=60,
            capacity_per_slot=4,
            box_count=3,
        )
        slots = generate_time_slots_for_day(config)
        assert slots[0]["capacity"] == 12  # 4 × 3

    def test_daily_slot(self):
        """DAILY: 1スロットのみ生成"""
        config = ReservationConfig(
            store_id=999,
            slot_type="DAILY",
            capacity_per_slot=10,
            box_count=1,
        )
        slots = generate_time_slots_for_day(config)
        assert len(slots) == 1
        assert slots[0]["label"] == "終日"
        assert slots[0]["capacity"] == 10

    def test_halfday_slots(self):
        """HALFDAY: 午前・午後の2スロット生成"""
        config = ReservationConfig(
            store_id=999,
            slot_type="HALFDAY",
            business_start="09:00",
            business_end="18:00",
            am_end_time="12:00",
            am_capacity=15,
            pm_capacity=10,
            box_count=1,
        )
        slots = generate_time_slots_for_day(config)
        assert len(slots) == 2
        assert slots[0]["label"] == "午前"
        assert slots[1]["label"] == "午後"
        assert slots[0]["capacity"] == 15
        assert slots[1]["capacity"] == 10

    def test_30min_interval(self):
        """30分間隔のスロット生成"""
        config = ReservationConfig(
            store_id=999,
            slot_type="HOURLY",
            business_start="09:00",
            business_end="11:00",
            slot_interval_minutes=30,
            capacity_per_slot=2,
            box_count=1,
        )
        slots = generate_time_slots_for_day(config)
        assert len(slots) == 4  # 9:00, 9:30, 10:00, 10:30

    def test_10min_interval(self):
        config = ReservationConfig(
            store_id=999,
            slot_type="HOURLY",
            business_start="09:00",
            business_end="09:30",
            slot_interval_minutes=10,
            capacity_per_slot=2,
            box_count=1,
        )
        slots = generate_time_slots_for_day(config)
        assert [slot["label"] for slot in slots] == ["09:00-09:10", "09:10-09:20", "09:20-09:30"]

    def test_15min_interval(self):
        config = ReservationConfig(
            store_id=999,
            slot_type="HOURLY",
            business_start="09:00",
            business_end="10:00",
            slot_interval_minutes=15,
            capacity_per_slot=2,
            box_count=1,
        )
        slots = generate_time_slots_for_day(config)
        assert len(slots) == 4
        assert slots[0]["label"] == "09:00-09:15"


class TestJapaneseHolidays:
    def test_new_years_is_holiday(self):
        """1月1日は元日として祝日判定される"""
        is_hol, name = is_japanese_holiday(date(2025, 1, 1))
        assert is_hol is True
        assert name is not None

    def test_normal_day_not_holiday(self):
        """通常の平日は祝日ではない"""
        # 月曜日で祝日でない日を選ぶ
        is_hol, name = is_japanese_holiday(date(2025, 1, 6))
        assert is_hol is False

    def test_holidays_in_range(self):
        """期間内の祝日一覧取得"""
        holidays = get_holidays_in_range(date(2025, 1, 1), date(2025, 1, 31))
        assert len(holidays) >= 1  # 元日が含まれる
        assert date(2025, 1, 1) in holidays

    def test_constitution_day(self):
        """憲法記念日（5月3日）が祝日判定"""
        is_hol, name = is_japanese_holiday(date(2025, 5, 3))
        assert is_hol is True


class TestStoreHolidayCheck:
    def test_weekly_holiday_matches(self, db, test_store):
        """毎週月曜日が休日として判定される"""
        from app.models import HolidayRule
        rule = HolidayRule(
            store_id=test_store.id,
            rule_type="WEEKLY",
            day_of_week=0,  # 月曜
        )
        db.add(rule)
        db.commit()

        # 2025-01-06は月曜日
        monday = date(2025, 1, 6)
        is_hol, reason = check_store_holiday(monday, [rule])
        assert is_hol is True
        assert reason is not None

    def test_weekly_holiday_non_matching(self, db, test_store):
        """月曜休みのルールで火曜は休日にならない"""
        from app.models import HolidayRule
        rule = HolidayRule(
            store_id=test_store.id,
            rule_type="WEEKLY",
            day_of_week=0,  # 月曜
        )
        db.add(rule)
        db.commit()

        tuesday = date(2025, 1, 7)
        is_hol, reason = check_store_holiday(tuesday, [rule])
        assert is_hol is False

    def test_specific_holiday(self, db, test_store):
        """特定日の休日判定"""
        from app.models import HolidayRule
        rule = HolidayRule(
            store_id=test_store.id,
            rule_type="SPECIFIC",
            specific_date=date(2025, 8, 15),
            description="夏期休暇",
        )
        db.add(rule)
        db.commit()

        is_hol, reason = check_store_holiday(date(2025, 8, 15), [rule])
        assert is_hol is True

    def test_halfday_restriction(self, db, test_store):
        """午後のみ休みの判定"""
        from app.models import HolidayRule
        rule = HolidayRule(
            store_id=test_store.id,
            rule_type="WEEKLY",
            day_of_week=5,  # 土曜
            half_day_restriction="PM",
        )
        db.add(rule)
        db.commit()

        saturday = date(2025, 1, 4)  # 土曜
        is_am_hol, _ = check_store_holiday(saturday, [rule], time_slot="AM")
        is_pm_hol, _ = check_store_holiday(saturday, [rule], time_slot="PM")
        assert is_am_hol is False
        assert is_pm_hol is True


class TestCalendarGeneration:
    def test_generate_creates_slots(self, db, test_store_with_config):
        """カレンダー生成でスロットが作成される"""
        result = generate_calendar(db, test_store_with_config.id)
        assert "error" not in result
        assert result["created"] > 0

    def test_generate_skips_existing(self, db, test_store_with_config):
        """既存スロットはスキップされる"""
        result1 = generate_calendar(db, test_store_with_config.id)
        result2 = generate_calendar(db, test_store_with_config.id)
        assert result2["created"] == 0
        assert result2["skipped"] > 0

    def test_generate_no_config_returns_error(self, db, test_store):
        """設定なしのカレンダー生成はエラーを返す"""
        result = generate_calendar(db, test_store.id)
        assert "error" in result

    def test_holiday_slots_not_available(self, db, test_store_with_config):
        """祝日のスロットは予約不可として生成される"""
        # 2025年1月1日（元日）を含む範囲でテスト
        result = generate_calendar(db, test_store_with_config.id)

        slots = db.query(CalendarSlot).filter(
            CalendarSlot.store_id == test_store_with_config.id,
            CalendarSlot.is_holiday == True,
        ).all()
        for slot in slots:
            assert slot.is_available is False

    def test_weekly_holiday_applied(self, db, test_store_with_config):
        """週次定休日が適用される"""
        from app.models import HolidayRule
        # 毎週月曜定休
        rule = HolidayRule(
            store_id=test_store_with_config.id,
            rule_type="WEEKLY",
            day_of_week=0,
        )
        db.add(rule)
        db.commit()

        generate_calendar(db, test_store_with_config.id)

        # 月曜日のスロットは休日フラグが立つ
        monday_slots = db.query(CalendarSlot).filter(
            CalendarSlot.store_id == test_store_with_config.id,
        ).all()

        for slot in monday_slots:
            if slot.slot_date.weekday() == 0:  # 月曜
                assert slot.is_holiday is True
                break
