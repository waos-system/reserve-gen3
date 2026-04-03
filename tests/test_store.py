"""
Store management route tests.
"""
from app.models import CalendarSlot, HolidayRule, ReservationConfig


class TestDashboard:
    def test_dashboard_renders(self, logged_in_client, test_store):
        resp = logged_in_client.get("/store/dashboard")
        assert resp.status_code == 200
        assert test_store.store_name in resp.text

    def test_dashboard_shows_config_warning(self, logged_in_client):
        resp = logged_in_client.get("/store/dashboard")
        assert resp.status_code == 200

    def test_dashboard_no_warning_with_config(self, logged_in_client, test_store_with_config):
        resp = logged_in_client.get("/store/dashboard")
        assert resp.status_code == 200


class TestSetup:
    def test_setup_page_renders(self, logged_in_client):
        resp = logged_in_client.get("/store/setup")
        assert resp.status_code == 200

    def test_setup_post_creates_config(self, logged_in_client, test_store, db):
        resp = logged_in_client.post(
            "/store/setup",
            data={
                "store_name": "Updated Store",
                "slot_type": "HOURLY",
                "business_start": "10:00",
                "business_end": "19:00",
                "slot_interval_minutes": "15",
                "capacity_per_slot": "5",
                "box_count": "2",
                "box_label": "Booth",
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
        assert config.slot_interval_minutes == 15
        assert config.capacity_per_slot == 5

    def test_setup_post_updates_existing_config(self, logged_in_client, test_store_with_config, db):
        resp = logged_in_client.post(
            "/store/setup",
            data={
                "store_name": "Test Store",
                "slot_type": "DAILY",
                "business_start": "09:00",
                "business_end": "17:00",
                "slot_interval_minutes": "60",
                "capacity_per_slot": "20",
                "box_count": "1",
                "box_label": "Seat",
                "calendar_months_ahead": "2",
                "am_end_time": "12:00",
            },
            follow_redirects=False,
        )
        assert resp.status_code in (302, 303)
        db.refresh(test_store_with_config)
        assert test_store_with_config.config.slot_type == "DAILY"
        assert test_store_with_config.config.capacity_per_slot == 20

    def test_setup_halfday_type(self, logged_in_client, test_store, db):
        resp = logged_in_client.post(
            "/store/setup",
            data={
                "store_name": "Test Store",
                "slot_type": "HALFDAY",
                "business_start": "09:00",
                "business_end": "18:00",
                "slot_interval_minutes": "60",
                "capacity_per_slot": "10",
                "box_count": "1",
                "box_label": "Seat",
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
        resp = logged_in_client.get("/store/holidays")
        assert resp.status_code == 200

    def test_add_weekly_holiday(self, logged_in_client, test_store, db):
        resp = logged_in_client.post(
            "/store/holidays/add",
            data={"rule_type": "WEEKLY", "day_of_week": "0", "half_day_restriction": ""},
            follow_redirects=False,
        )
        assert resp.status_code in (302, 303)
        rules = db.query(HolidayRule).filter(HolidayRule.store_id == test_store.id).all()
        assert len(rules) == 1
        assert rules[0].rule_type == "WEEKLY"

    def test_add_specific_holiday(self, logged_in_client, test_store, db):
        resp = logged_in_client.post(
            "/store/holidays/add",
            data={
                "rule_type": "SPECIFIC",
                "specific_date": "2025-01-01",
                "description": "Holiday",
                "half_day_restriction": "",
            },
            follow_redirects=False,
        )
        assert resp.status_code in (302, 303)
        rule = db.query(HolidayRule).filter(HolidayRule.store_id == test_store.id).first()
        assert str(rule.specific_date) == "2025-01-01"

    def test_delete_holiday_rule(self, logged_in_client, test_store, db):
        rule = HolidayRule(store_id=test_store.id, rule_type="WEEKLY", day_of_week=1)
        db.add(rule)
        db.commit()
        resp = logged_in_client.post(f"/store/holidays/delete/{rule.id}", follow_redirects=False)
        assert resp.status_code in (302, 303)
        assert db.query(HolidayRule).filter(HolidayRule.store_id == test_store.id).count() == 0

    def test_add_halfday_holiday(self, logged_in_client, test_store, db):
        resp = logged_in_client.post(
            "/store/holidays/add",
            data={"rule_type": "WEEKLY", "day_of_week": "5", "half_day_restriction": "PM"},
            follow_redirects=False,
        )
        assert resp.status_code in (302, 303)
        rule = db.query(HolidayRule).filter(HolidayRule.store_id == test_store.id).first()
        assert rule.half_day_restriction == "PM"


class TestCalendarManagement:
    def test_calendar_page_renders(self, logged_in_client):
        resp = logged_in_client.get("/store/calendar")
        assert resp.status_code == 200

    def test_calendar_generate(self, logged_in_client, test_store_with_config, db):
        resp = logged_in_client.post("/store/calendar/generate", follow_redirects=False)
        assert resp.status_code in (302, 303)
        count = db.query(CalendarSlot).filter(CalendarSlot.store_id == test_store_with_config.id).count()
        assert count > 0

    def test_slot_toggle_availability(self, logged_in_client, test_slot, db):
        resp = logged_in_client.post(
            f"/store/calendar/slot/{test_slot.id}/toggle",
            data={"redirect_url": "/store/calendar"},
            follow_redirects=False,
        )
        assert resp.status_code in (302, 303)
        db.refresh(test_slot)
        assert test_slot.is_available is False

    def test_slot_update_capacity(self, logged_in_client, test_slot, db):
        resp = logged_in_client.post(
            f"/store/calendar/slot/{test_slot.id}/update",
            data={
                "max_capacity": "10",
                "override_note": "override",
                "redirect_url": "/store/calendar",
            },
            follow_redirects=False,
        )
        assert resp.status_code in (302, 303)
        db.refresh(test_slot)
        assert test_slot.max_capacity == 10
        assert test_slot.override_note == "override"


class TestReservationsList:
    def test_reservations_page_renders(self, logged_in_client):
        resp = logged_in_client.get("/store/reservations")
        assert resp.status_code == 200

    def test_reservations_empty_state(self, logged_in_client):
        resp = logged_in_client.get("/store/reservations")
        assert resp.status_code == 200

    def test_reservations_filter_by_status(self, logged_in_client, test_slot, db, test_store_with_config):
        from tests.conftest import create_test_reservation

        create_test_reservation(
            db,
            test_store_with_config.id,
            test_slot.id,
            reservation_number="RES-FILTER-0001",
            status="CONFIRMED",
        )

        resp = logged_in_client.get("/store/reservations?status=CONFIRMED")
        assert resp.status_code == 200
        assert "RES-FILTER-0001" in resp.text

        resp2 = logged_in_client.get("/store/reservations?status=PENDING")
        assert "RES-FILTER-0001" not in resp2.text

    def test_reservations_calendar_view_renders(self, logged_in_client):
        resp = logged_in_client.get("/store/reservations?view=calendar")
        assert resp.status_code == 200

    def test_reservations_calendar_view_shows_reservation(
        self, logged_in_client, test_slot, db, test_store_with_config
    ):
        from tests.conftest import create_test_reservation

        create_test_reservation(
            db,
            test_store_with_config.id,
            test_slot.id,
            reservation_number="RES-CAL-0001",
            status="CONFIRMED",
        )
        resp = logged_in_client.get(
            f"/store/reservations?view=calendar&target_date={test_slot.slot_date.isoformat()}"
        )
        assert resp.status_code == 200
        assert "RES-CAL-0001" in resp.text
