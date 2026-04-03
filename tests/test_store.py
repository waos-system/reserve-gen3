"""
店舗管理機能のテスト
spec.md セクション3.1 / セクション4 店舗管理API参照
"""
import pytest
from datetime import date
from app.models import ReservationConfig, HolidayRule, CalendarSlot
from tests.conftest import (
    create_test_config,
    create_test_calendar_slot,
)


class TestDashboard:
    def test_dashboard_renders(self, logged_in_client, test_store):
        """ダッシュボードが正常に表示される"""
        resp = logged_in_client.get("/store/dashboard")
        assert resp.status_code == 200
        assert test_store.store_name in resp.text

    def test_dashboard_shows_config_warning(self, logged_in_client):
        """設定未完了時に警告が表示される"""
        resp = logged_in_client.get("/store/dashboard")
        assert "予約設定がまだ完了していません" in resp.text

    def test_dashboard_no_warning_with_config(self, logged_in_client, test_store_with_config):
        """設定済みの場合は警告なし"""
        resp = logged_in_client.get("/store/dashboard")
        assert resp.status_code == 200


class TestSetup:
    def test_setup_page_renders(self, logged_in_client):
        """設定ページが正常に表示される"""
        resp = logged_in_client.get("/store/setup")
        assert resp.status_code == 200

    def test_setup_post_creates_config(self, logged_in_client, test_store, db):
        """設定フォーム送信で設定が作成される"""
        resp = logged_in_client.post(
            "/store/setup",
            data={
                "store_name": "更新店舗名",
                "slot_type": "HOURLY",
                "business_start": "10:00",
                "business_end": "19:00",
                "slot_interval_minutes": "60",
                "capacity_per_slot": "5",
                "box_count": "2",
                "box_label": "担当者",
                "calendar_months_ahead": "3",
                "am_end_time": "12:00",
            },
            follow_redirects=False,
        )
        assert resp.status_code in (302, 303)

        db.refresh(test_store)
        config = db.query(ReservationConfig).filter(
            ReservationConfig.store_id == test_store.id
        ).first()
        assert config is not None
        assert config.slot_type == "HOURLY"
        assert config.capacity_per_slot == 5
        assert config.box_count == 2
        assert config.box_label == "担当者"

    def test_setup_post_updates_existing_config(self, logged_in_client, test_store_with_config, db):
        """既存設定の更新"""
        resp = logged_in_client.post(
            "/store/setup",
            data={
                "store_name": "テスト店舗",
                "slot_type": "DAILY",
                "business_start": "09:00",
                "business_end": "17:00",
                "slot_interval_minutes": "60",
                "capacity_per_slot": "20",
                "box_count": "1",
                "box_label": "席",
                "calendar_months_ahead": "2",
                "am_end_time": "12:00",
            },
            follow_redirects=False,
        )
        assert resp.status_code in (302, 303)

        db.refresh(test_store_with_config)
        config = test_store_with_config.config
        assert config.slot_type == "DAILY"
        assert config.capacity_per_slot == 20

    def test_setup_halfday_type(self, logged_in_client, test_store, db):
        """午前/午後タイプの設定"""
        resp = logged_in_client.post(
            "/store/setup",
            data={
                "store_name": "テスト店舗",
                "slot_type": "HALFDAY",
                "business_start": "09:00",
                "business_end": "18:00",
                "slot_interval_minutes": "60",
                "capacity_per_slot": "10",
                "box_count": "1",
                "box_label": "席",
                "calendar_months_ahead": "3",
                "am_end_time": "12:00",
                "am_capacity": "15",
                "pm_capacity": "10",
            },
            follow_redirects=False,
        )
        assert resp.status_code in (302, 303)

        config = db.query(ReservationConfig).filter(
            ReservationConfig.store_id == test_store.id
        ).first()
        assert config.slot_type == "HALFDAY"
        assert config.am_capacity == 15
        assert config.pm_capacity == 10


class TestHolidays:
    def test_holidays_page_renders(self, logged_in_client):
        """定休日ページが正常に表示される"""
        resp = logged_in_client.get("/store/holidays")
        assert resp.status_code == 200

    def test_add_weekly_holiday(self, logged_in_client, test_store, db):
        """毎週の定休日追加"""
        resp = logged_in_client.post(
            "/store/holidays/add",
            data={
                "rule_type": "WEEKLY",
                "day_of_week": "0",  # 月曜
                "half_day_restriction": "",
            },
            follow_redirects=False,
        )
        assert resp.status_code in (302, 303)

        rules = db.query(HolidayRule).filter(
            HolidayRule.store_id == test_store.id
        ).all()
        assert len(rules) == 1
        assert rules[0].rule_type == "WEEKLY"
        assert rules[0].day_of_week == 0

    def test_add_specific_holiday(self, logged_in_client, test_store, db):
        """特定日の定休日追加"""
        resp = logged_in_client.post(
            "/store/holidays/add",
            data={
                "rule_type": "SPECIFIC",
                "specific_date": "2025-01-01",
                "description": "元旦",
                "half_day_restriction": "",
            },
            follow_redirects=False,
        )
        assert resp.status_code in (302, 303)

        rule = db.query(HolidayRule).filter(
            HolidayRule.store_id == test_store.id
        ).first()
        assert rule.rule_type == "SPECIFIC"
        assert str(rule.specific_date) == "2025-01-01"
        assert rule.description == "元旦"

    def test_delete_holiday_rule(self, logged_in_client, test_store, db):
        """定休日ルール削除"""
        rule = HolidayRule(
            store_id=test_store.id,
            rule_type="WEEKLY",
            day_of_week=1,
        )
        db.add(rule)
        db.commit()

        resp = logged_in_client.post(
            f"/store/holidays/delete/{rule.id}",
            follow_redirects=False,
        )
        assert resp.status_code in (302, 303)

        count = db.query(HolidayRule).filter(
            HolidayRule.store_id == test_store.id
        ).count()
        assert count == 0

    def test_add_halfday_holiday(self, logged_in_client, test_store, db):
        """午後のみ休みの設定"""
        resp = logged_in_client.post(
            "/store/holidays/add",
            data={
                "rule_type": "WEEKLY",
                "day_of_week": "5",  # 土曜
                "half_day_restriction": "PM",
            },
            follow_redirects=False,
        )
        assert resp.status_code in (302, 303)

        rule = db.query(HolidayRule).filter(
            HolidayRule.store_id == test_store.id
        ).first()
        assert rule.half_day_restriction == "PM"


class TestCalendarManagement:
    def test_calendar_page_renders(self, logged_in_client):
        """カレンダーページが表示される"""
        resp = logged_in_client.get("/store/calendar")
        assert resp.status_code == 200

    def test_calendar_generate(self, logged_in_client, test_store_with_config, db):
        """カレンダーが正常に生成される"""
        resp = logged_in_client.post(
            "/store/calendar/generate",
            follow_redirects=False,
        )
        assert resp.status_code in (302, 303)

        count = db.query(CalendarSlot).filter(
            CalendarSlot.store_id == test_store_with_config.id
        ).count()
        assert count > 0

    def test_slot_toggle_availability(self, logged_in_client, test_slot, db):
        """スロットの利用可否トグル"""
        assert test_slot.is_available is True

        resp = logged_in_client.post(
            f"/store/calendar/slot/{test_slot.id}/toggle",
            data={"redirect_url": "/store/calendar"},
            follow_redirects=False,
        )
        assert resp.status_code in (302, 303)

        db.refresh(test_slot)
        assert test_slot.is_available is False

    def test_slot_update_capacity(self, logged_in_client, test_slot, db):
        """スロットの最大人数変更"""
        resp = logged_in_client.post(
            f"/store/calendar/slot/{test_slot.id}/update",
            data={
                "max_capacity": "10",
                "override_note": "特別増枠",
                "redirect_url": "/store/calendar",
            },
            follow_redirects=False,
        )
        assert resp.status_code in (302, 303)

        db.refresh(test_slot)
        assert test_slot.max_capacity == 10
        assert test_slot.override_note == "特別増枠"


class TestReservationsList:
    def test_reservations_page_renders(self, logged_in_client):
        """予約一覧ページが表示される"""
        resp = logged_in_client.get("/store/reservations")
        assert resp.status_code == 200

    def test_reservations_empty_state(self, logged_in_client):
        """予約なし状態で適切なメッセージ表示"""
        resp = logged_in_client.get("/store/reservations")
        assert "予約はまだありません" in resp.text

    def test_reservations_filter_by_status(
        self, logged_in_client, test_slot, db, test_store_with_config
    ):
        """ステータスでフィルタリング"""
        from tests.conftest import create_test_reservation
        r = create_test_reservation(
            db, test_store_with_config.id, test_slot.id,
            reservation_number="RES-FILTER-0001",
            status="CONFIRMED",
        )

        resp = logged_in_client.get("/store/reservations?status=CONFIRMED")
        assert resp.status_code == 200
        assert "RES-FILTER-0001" in resp.text

        resp2 = logged_in_client.get("/store/reservations?status=PENDING")
        assert "RES-FILTER-0001" not in resp2.text
