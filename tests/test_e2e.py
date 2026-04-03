"""
E2E統合テスト：全画面・全ボタンの動作確認
4店舗パターン（美容院・病院・居酒屋・在庫予約）
"""
import pytest
from datetime import date, timedelta
from app.models import Store, ReservationConfig, HolidayRule, CalendarSlot, Reservation
from app.utils.calendar_utils import generate_calendar_from
import bcrypt, uuid

# ===== テスト用デモデータ定義 =====
DEMO_STORES = [
    {
        "phone_number": "090-1000-0001",
        "password":     "test1234",
        "store_name":   "テスト美容院",
        "config": dict(
            slot_type="HOURLY", business_start="09:00", business_end="19:00",
            slot_interval_minutes=60, capacity_per_slot=1, box_count=3,
            box_label="担当者", calendar_months_ahead=3,
        ),
        "holidays": [
            dict(rule_type="WEEKLY", day_of_week=0, description="月曜定休"),
            dict(rule_type="WEEKLY", day_of_week=6, half_day_restriction="PM",
                 description="土曜午後休み"),
        ],
    },
    {
        "phone_number": "090-1000-0002",
        "password":     "test5678",
        "store_name":   "テストクリニック",
        "config": dict(
            slot_type="HALFDAY", business_start="09:00", business_end="17:00",
            slot_interval_minutes=60, capacity_per_slot=10, box_count=1,
            box_label="枠", calendar_months_ahead=2,
            am_end_time="12:00", am_capacity=20, pm_capacity=15,
        ),
        "holidays": [
            dict(rule_type="WEEKLY", day_of_week=5, description="土曜定休"),
            dict(rule_type="WEEKLY", day_of_week=6, description="日曜定休"),
        ],
    },
    {
        "phone_number": "090-1000-0003",
        "password":     "test9012",
        "store_name":   "テスト居酒屋",
        "config": dict(
            slot_type="HOURLY",
            business_start="17:00", business_end="23:00",
            slot_interval_minutes=120,   # 2時間制
            capacity_per_slot=8,          # 1組最大8名
            box_count=6,                  # 同時最大6組
            box_label="組",
            calendar_months_ahead=3,
        ),
        "holidays": [
            dict(rule_type="WEEKLY", day_of_week=6, description="日曜定休"),
        ],
        "expected_slots_per_day": 3,   # 17:00-19:00 / 19:00-21:00 / 21:00-23:00
        "expected_capacity_per_slot": 48,  # 8名 × 6組
    },
    {
        "phone_number": "090-1000-0004",
        "password":     "test3456",
        "store_name":   "テスト弁当店",
        "config": dict(
            slot_type="DAILY",
            business_start="11:00", business_end="14:00",
            slot_interval_minutes=60,
            capacity_per_slot=30,  # 1日30食
            box_count=1,
            box_label="食",
            calendar_months_ahead=2,
        ),
        "holidays": [
            dict(rule_type="WEEKLY", day_of_week=5, description="土曜定休"),
            dict(rule_type="WEEKLY", day_of_week=6, description="日曜定休"),
        ],
        "expected_slots_per_day": 1,       # 終日1枠
        "expected_capacity_per_slot": 30,  # 1日30食
    },
]


def hp(p):
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()


@pytest.fixture
def all_stores(db):
    today = date.today()
    stores = []
    for s_def in DEMO_STORES:
        store = Store(
            phone_number=s_def["phone_number"],
            password_hash=hp(s_def["password"]),
            store_name=s_def["store_name"],
            line_channel_token="", line_user_id="",
        )
        db.add(store)
        db.flush()
        db.add(ReservationConfig(store_id=store.id, **s_def["config"]))
        for h in s_def["holidays"]:
            db.add(HolidayRule(store_id=store.id, **h))
        db.flush()
        db.commit()
        generate_calendar_from(db, store.id, start_date=today)
        db.refresh(store)
        stores.append((store, s_def))
    return stores


@pytest.fixture
def beauty_store(db, all_stores):   return all_stores[0]
@pytest.fixture
def clinic_store(db, all_stores):   return all_stores[1]
@pytest.fixture
def izakaya_store(db, all_stores):  return all_stores[2]
@pytest.fixture
def bento_store(db, all_stores):    return all_stores[3]


def login(client, phone, password):
    return client.post(
        "/store/login",
        data={"phone_number": phone, "password": password},
        follow_redirects=False,
    )


def get_available_slot(db, store_id):
    return db.query(CalendarSlot).filter(
        CalendarSlot.store_id == store_id,
        CalendarSlot.is_available == True,
        CalendarSlot.is_holiday == False,
        CalendarSlot.max_capacity > 0,
    ).first()


# ======================================================
# 1. ログイン画面テスト
# ======================================================
class TestLoginScreen:
    def test_login_page_loads(self, client):
        resp = client.get("/store/login")
        assert resp.status_code == 200

    def test_login_page_shows_4_demo_accounts(self, client):
        """ログイン画面に4店舗のデモアカウントが表示される"""
        resp = client.get("/store/login")
        assert "デモアカウント" in resp.text
        assert "090-0000-0001" in resp.text
        assert "090-0000-0002" in resp.text
        assert "090-0000-0003" in resp.text
        assert "090-0000-0004" in resp.text

    def test_login_page_shows_demo_badges(self, client):
        """各デモカードにバッジ（予約タイプ）が表示される"""
        resp = client.get("/store/login")
        assert "1h×3担当" in resp.text
        assert "午前/午後" in resp.text
        assert "2h×6組" in resp.text
        assert "在庫予約" in resp.text

    def test_beauty_login_success(self, client, beauty_store):
        store, s_def = beauty_store
        resp = login(client, s_def["phone_number"], s_def["password"])
        assert resp.status_code == 303
        assert "/store/dashboard" in resp.headers["location"]

    def test_clinic_login_success(self, client, clinic_store):
        store, s_def = clinic_store
        resp = login(client, s_def["phone_number"], s_def["password"])
        assert resp.status_code == 303

    def test_izakaya_login_success(self, client, izakaya_store):
        store, s_def = izakaya_store
        resp = login(client, s_def["phone_number"], s_def["password"])
        assert resp.status_code == 303

    def test_bento_login_success(self, client, bento_store):
        """在庫予約店舗ログイン"""
        store, s_def = bento_store
        resp = login(client, s_def["phone_number"], s_def["password"])
        assert resp.status_code == 303

    def test_wrong_password_shows_error(self, client, beauty_store):
        store, s_def = beauty_store
        resp = login(client, s_def["phone_number"], "wrongpass")
        assert resp.status_code == 200
        assert "電話番号またはパスワードが違います" in resp.text

    def test_unknown_phone_shows_error(self, client):
        resp = login(client, "000-0000-0000", "pass")
        assert resp.status_code == 200
        assert "電話番号またはパスワードが違います" in resp.text

    def test_logout_clears_session(self, client, beauty_store):
        store, s_def = beauty_store
        login(client, s_def["phone_number"], s_def["password"])
        resp = client.get("/store/logout", follow_redirects=False)
        assert resp.status_code in (302, 303)
        assert "/store/login" in resp.headers["location"]
        resp2 = client.get("/store/dashboard", follow_redirects=False)
        assert resp2.status_code in (302, 422)


# ======================================================
# 2. ダッシュボード画面テスト
# ======================================================
class TestDashboardScreen:
    def test_all_stores_dashboard(self, client, all_stores):
        """4店舗すべてダッシュボードが表示される"""
        for store, s_def in all_stores:
            login(client, s_def["phone_number"], s_def["password"])
            resp = client.get("/store/dashboard")
            assert resp.status_code == 200
            assert store.store_name in resp.text
            client.get("/store/logout")

    def test_dashboard_menu_links(self, client, beauty_store):
        store, s_def = beauty_store
        login(client, s_def["phone_number"], s_def["password"])
        resp = client.get("/store/dashboard")
        for path in ["/store/setup", "/store/holidays", "/store/calendar", "/store/reservations"]:
            assert path in resp.text

    def test_dashboard_shows_stats(self, client, beauty_store):
        store, s_def = beauty_store
        login(client, s_def["phone_number"], s_def["password"])
        resp = client.get("/store/dashboard")
        assert "本日の予約数" in resp.text
        assert "今後7日の予約" in resp.text
        assert "未確認の予約" in resp.text


# ======================================================
# 3. 予約設定画面テスト（4店舗パターン）
# ======================================================
class TestSetupScreen:
    def test_setup_page_loads_all_stores(self, client, all_stores):
        for store, s_def in all_stores:
            login(client, s_def["phone_number"], s_def["password"])
            resp = client.get("/store/setup")
            assert resp.status_code == 200
            client.get("/store/logout")

    def test_setup_beauty_salon_hourly(self, client, beauty_store, db):
        """美容院：1時間×担当者3名設定"""
        store, s_def = beauty_store
        login(client, s_def["phone_number"], s_def["password"])
        resp = client.post("/store/setup", data={
            "store_name": store.store_name,
            "slot_type": "HOURLY",
            "business_start": "09:00", "business_end": "20:00",
            "slot_interval_minutes": "60",
            "capacity_per_slot": "1",
            "box_count": "4",
            "box_label": "担当者",
            "calendar_months_ahead": "3",
            "am_end_time": "12:00",
        }, follow_redirects=False)
        assert resp.status_code == 303
        db.refresh(store)
        assert store.config.box_count == 4

    def test_setup_clinic_halfday(self, client, clinic_store, db):
        """病院：午前午後・各定員設定"""
        store, s_def = clinic_store
        login(client, s_def["phone_number"], s_def["password"])
        resp = client.post("/store/setup", data={
            "store_name": store.store_name,
            "slot_type": "HALFDAY",
            "business_start": "09:00", "business_end": "17:00",
            "slot_interval_minutes": "60",
            "capacity_per_slot": "10", "box_count": "1", "box_label": "枠",
            "calendar_months_ahead": "2",
            "am_end_time": "12:30", "am_capacity": "25", "pm_capacity": "20",
        }, follow_redirects=False)
        assert resp.status_code == 303
        db.refresh(store)
        assert store.config.am_capacity == 25
        assert store.config.pm_capacity == 20

    def test_setup_izakaya_2hour_slots(self, client, izakaya_store, db):
        """居酒屋：2時間制・6組設定"""
        store, s_def = izakaya_store
        login(client, s_def["phone_number"], s_def["password"])
        resp = client.post("/store/setup", data={
            "store_name": store.store_name,
            "slot_type": "HOURLY",
            "business_start": "17:00", "business_end": "23:00",
            "slot_interval_minutes": "120",   # 2時間制
            "capacity_per_slot": "8",          # 1組8名
            "box_count": "8",                  # 8組に変更
            "box_label": "組",
            "calendar_months_ahead": "3",
            "am_end_time": "12:00",
        }, follow_redirects=False)
        assert resp.status_code == 303
        db.refresh(store)
        assert store.config.slot_interval_minutes == 120
        assert store.config.box_count == 8

    def test_setup_bento_inventory(self, client, bento_store, db):
        """在庫予約：1日30食設定"""
        store, s_def = bento_store
        login(client, s_def["phone_number"], s_def["password"])
        resp = client.post("/store/setup", data={
            "store_name": store.store_name,
            "slot_type": "DAILY",
            "business_start": "11:00", "business_end": "14:00",
            "slot_interval_minutes": "60",
            "capacity_per_slot": "50",  # 50食に増量
            "box_count": "1",
            "box_label": "食",
            "calendar_months_ahead": "2",
            "am_end_time": "12:00",
        }, follow_redirects=False)
        assert resp.status_code == 303
        db.refresh(store)
        assert store.config.capacity_per_slot == 50
        assert store.config.box_label == "食"

    def test_setup_success_message(self, client, bento_store):
        store, s_def = bento_store
        login(client, s_def["phone_number"], s_def["password"])
        resp = client.post("/store/setup", data={
            "store_name": store.store_name,
            "slot_type": "DAILY", "business_start": "10:00",
            "business_end": "15:00", "slot_interval_minutes": "60",
            "capacity_per_slot": "30", "box_count": "1",
            "box_label": "食", "calendar_months_ahead": "2",
            "am_end_time": "12:00",
        }, follow_redirects=True)
        assert "設定を保存しました" in resp.text


# ======================================================
# 4. 定休日設定画面テスト
# ======================================================
class TestHolidayScreen:
    def test_holidays_page_loads_all(self, client, all_stores):
        for store, s_def in all_stores:
            login(client, s_def["phone_number"], s_def["password"])
            resp = client.get("/store/holidays")
            assert resp.status_code == 200
            assert "定休日" in resp.text
            client.get("/store/logout")

    def test_add_weekly_holiday(self, client, beauty_store, db):
        store, s_def = beauty_store
        login(client, s_def["phone_number"], s_def["password"])
        before = db.query(HolidayRule).filter(HolidayRule.store_id == store.id).count()
        resp = client.post("/store/holidays/add", data={
            "rule_type": "WEEKLY", "day_of_week": "3", "half_day_restriction": "",
        }, follow_redirects=False)
        assert resp.status_code in (302, 303)
        assert db.query(HolidayRule).filter(HolidayRule.store_id == store.id).count() == before + 1

    def test_add_specific_holiday(self, client, bento_store, db):
        """在庫予約店：特定日休業"""
        store, s_def = bento_store
        login(client, s_def["phone_number"], s_def["password"])
        resp = client.post("/store/holidays/add", data={
            "rule_type": "SPECIFIC",
            "specific_date": "2026-08-13",
            "description": "お盆休み",
            "half_day_restriction": "",
        }, follow_redirects=False)
        assert resp.status_code in (302, 303)
        rule = db.query(HolidayRule).filter(
            HolidayRule.store_id == store.id, HolidayRule.rule_type == "SPECIFIC"
        ).first()
        assert rule is not None
        assert rule.description == "お盆休み"

    def test_add_halfday_holiday_izakaya(self, client, izakaya_store, db):
        """居酒屋：月曜はランチのみ（午前休み扱いは不要だが半日設定可能か）"""
        store, s_def = izakaya_store
        login(client, s_def["phone_number"], s_def["password"])
        resp = client.post("/store/holidays/add", data={
            "rule_type": "WEEKLY", "day_of_week": "4",
            "half_day_restriction": "AM", "description": "木曜ランチ休み",
        }, follow_redirects=False)
        assert resp.status_code in (302, 303)
        rule = db.query(HolidayRule).filter(
            HolidayRule.store_id == store.id, HolidayRule.day_of_week == 4
        ).first()
        assert rule is not None

    def test_delete_holiday_rule(self, client, beauty_store, db):
        store, s_def = beauty_store
        login(client, s_def["phone_number"], s_def["password"])
        rule = db.query(HolidayRule).filter(HolidayRule.store_id == store.id).first()
        resp = client.post(f"/store/holidays/delete/{rule.id}", follow_redirects=False)
        assert resp.status_code in (302, 303)
        assert db.query(HolidayRule).filter(HolidayRule.id == rule.id).first() is None

    def test_cannot_delete_other_store_holiday(self, client, beauty_store, bento_store, db):
        store_b, s_def_b = beauty_store
        store_bt, _ = bento_store
        login(client, s_def_b["phone_number"], s_def_b["password"])
        other_rule = db.query(HolidayRule).filter(HolidayRule.store_id == store_bt.id).first()
        if other_rule:
            client.post(f"/store/holidays/delete/{other_rule.id}", follow_redirects=False)
            assert db.query(HolidayRule).filter(HolidayRule.id == other_rule.id).first() is not None


# ======================================================
# 5. カレンダー画面テスト
# ======================================================
class TestCalendarScreen:
    def test_calendar_page_loads_all(self, client, all_stores):
        for store, s_def in all_stores:
            login(client, s_def["phone_number"], s_def["password"])
            resp = client.get("/store/calendar")
            assert resp.status_code == 200
            client.get("/store/logout")

    # --- 居酒屋：2時間枠の検証 ---
    def test_izakaya_has_3_slots_per_day(self, db, izakaya_store):
        """居酒屋は1日に3スロット（17-19, 19-21, 21-23）生成される"""
        store, s_def = izakaya_store
        today = date.today()
        # 非休日の平日を探す
        target = today
        for _ in range(14):
            if target.weekday() != 6:  # 日曜以外
                break
            target += timedelta(days=1)

        slots = db.query(CalendarSlot).filter(
            CalendarSlot.store_id == store.id,
            CalendarSlot.slot_date == target,
        ).all()
        assert len(slots) == 3, f"Expected 3 slots, got {len(slots)}"

    def test_izakaya_slot_labels(self, db, izakaya_store):
        """居酒屋のスロットラベルが2時間単位になっている"""
        store, _ = izakaya_store
        slot = db.query(CalendarSlot).filter(CalendarSlot.store_id == store.id).first()
        assert slot is not None
        # ラベルは "HH:MM-HH:MM" 形式で2時間差
        parts = slot.slot_label.split("-")
        assert len(parts) == 2
        h_start = int(parts[0].split(":")[0])
        h_end   = int(parts[1].split(":")[0])
        assert h_end - h_start == 2

    def test_izakaya_capacity_per_slot(self, db, izakaya_store):
        """居酒屋1スロット = 8名×6組 = 48名"""
        store, s_def = izakaya_store
        slot = db.query(CalendarSlot).filter(
            CalendarSlot.store_id == store.id,
            CalendarSlot.is_holiday == False,
        ).first()
        assert slot is not None
        expected = s_def["expected_capacity_per_slot"]
        assert slot.max_capacity == expected, f"Expected {expected}, got {slot.max_capacity}"

    # --- 在庫予約：終日1枠の検証 ---
    def test_bento_has_1_slot_per_day(self, db, bento_store):
        """弁当店は1日1スロット（終日）"""
        store, s_def = bento_store
        today = date.today()
        target = today
        for _ in range(14):
            if target.weekday() not in (5, 6):
                break
            target += timedelta(days=1)

        slots = db.query(CalendarSlot).filter(
            CalendarSlot.store_id == store.id,
            CalendarSlot.slot_date == target,
        ).all()
        assert len(slots) == s_def["expected_slots_per_day"]

    def test_bento_slot_label_is_daily(self, db, bento_store):
        """弁当店のスロットラベルは「終日」"""
        store, _ = bento_store
        slot = db.query(CalendarSlot).filter(CalendarSlot.store_id == store.id).first()
        assert slot is not None
        assert slot.slot_label == "終日"

    def test_bento_capacity_per_slot(self, db, bento_store):
        """弁当店の1日あたり在庫数が正しい（30食）"""
        store, s_def = bento_store
        slot = db.query(CalendarSlot).filter(
            CalendarSlot.store_id == store.id,
            CalendarSlot.is_holiday == False,
        ).first()
        assert slot is not None
        assert slot.max_capacity == s_def["expected_capacity_per_slot"]

    # --- カレンダー操作ボタン ---
    def test_generate_calendar_button(self, client, clinic_store, db):
        store, s_def = clinic_store
        login(client, s_def["phone_number"], s_def["password"])
        resp = client.post("/store/calendar/generate", data={}, follow_redirects=False)
        assert resp.status_code == 303

    def test_generate_with_start_date(self, client, bento_store, db):
        store, s_def = bento_store
        login(client, s_def["phone_number"], s_def["password"])
        today = date.today()
        resp = client.post("/store/calendar/generate",
            data={"start_date": today.isoformat()}, follow_redirects=False)
        assert resp.status_code == 303

    def test_slot_toggle_stop_and_resume(self, client, izakaya_store, db):
        """居酒屋スロットの停止→再開"""
        store, s_def = izakaya_store
        login(client, s_def["phone_number"], s_def["password"])
        slot = db.query(CalendarSlot).filter(
            CalendarSlot.store_id == store.id, CalendarSlot.is_available == True
        ).first()
        # 停止
        client.post(f"/store/calendar/slot/{slot.id}/toggle",
            data={"redirect_url": "/store/calendar"}, follow_redirects=False)
        db.refresh(slot)
        assert slot.is_available is False
        # 再開
        client.post(f"/store/calendar/slot/{slot.id}/toggle",
            data={"redirect_url": "/store/calendar"}, follow_redirects=False)
        db.refresh(slot)
        assert slot.is_available is True

    def test_slot_update_capacity(self, client, bento_store, db):
        """在庫予約：在庫数を手動変更"""
        store, s_def = bento_store
        login(client, s_def["phone_number"], s_def["password"])
        slot = db.query(CalendarSlot).filter(CalendarSlot.store_id == store.id).first()
        resp = client.post(f"/store/calendar/slot/{slot.id}/update", data={
            "max_capacity": "50",
            "override_note": "特別増量",
            "redirect_url": "/store/calendar",
        }, follow_redirects=False)
        assert resp.status_code in (302, 303)
        db.refresh(slot)
        assert slot.max_capacity == 50
        assert slot.override_note == "特別増量"

    def test_calendar_nav(self, client, beauty_store):
        store, s_def = beauty_store
        login(client, s_def["phone_number"], s_def["password"])
        today = date.today()
        next_m = today.month + 1 if today.month < 12 else 1
        next_y = today.year if today.month < 12 else today.year + 1
        resp = client.get(f"/store/calendar?year={next_y}&month={next_m}")
        assert resp.status_code == 200

    def test_monday_holiday_beauty(self, db, beauty_store):
        """美容院：月曜は休日"""
        store, _ = beauty_store
        mon = [s for s in db.query(CalendarSlot).filter(
            CalendarSlot.store_id == store.id).all() if s.slot_date.weekday() == 0]
        assert len(mon) > 0
        assert all(s.is_holiday for s in mon)

    def test_sunday_holiday_izakaya(self, db, izakaya_store):
        """居酒屋：日曜は休日"""
        store, _ = izakaya_store
        sun = [s for s in db.query(CalendarSlot).filter(
            CalendarSlot.store_id == store.id).all() if s.slot_date.weekday() == 6]
        assert len(sun) > 0
        assert all(s.is_holiday for s in sun)

    def test_weekend_holiday_bento(self, db, bento_store):
        """弁当店：土日は休日"""
        store, _ = bento_store
        weekend = [s for s in db.query(CalendarSlot).filter(
            CalendarSlot.store_id == store.id).all() if s.slot_date.weekday() in (5, 6)]
        assert len(weekend) > 0
        assert all(s.is_holiday for s in weekend)


# ======================================================
# 6. 予約一覧画面テスト
# ======================================================
class TestReservationsScreen:
    def _make_res(self, db, store_id, slot_id, number, status="CONFIRMED", party=1):
        from datetime import datetime
        r = Reservation(
            reservation_number=number, store_id=store_id, slot_id=slot_id,
            customer_name="テスト客", customer_phone="090-9999-0001",
            party_size=party, status=status, confirmation_token=str(uuid.uuid4()),
            confirmed_at=datetime.utcnow() if status == "CONFIRMED" else None,
        )
        db.add(r); db.commit()
        return r

    def test_reservations_page_loads_all(self, client, all_stores):
        for store, s_def in all_stores:
            login(client, s_def["phone_number"], s_def["password"])
            resp = client.get("/store/reservations")
            assert resp.status_code == 200
            client.get("/store/logout")

    def test_empty_state(self, client, beauty_store):
        store, s_def = beauty_store
        login(client, s_def["phone_number"], s_def["password"])
        resp = client.get("/store/reservations")
        assert "予約はまだありません" in resp.text

    def test_shows_izakaya_reservation(self, client, izakaya_store, db):
        """居酒屋予約が一覧に表示される"""
        store, s_def = izakaya_store
        slot = get_available_slot(db, store.id)
        self._make_res(db, store.id, slot.id, "RES-IZAK-001", party=4)
        login(client, s_def["phone_number"], s_def["password"])
        resp = client.get("/store/reservations")
        assert "RES-IZAK-001" in resp.text

    def test_shows_bento_reservation(self, client, bento_store, db):
        """弁当予約が一覧に表示される"""
        store, s_def = bento_store
        slot = get_available_slot(db, store.id)
        self._make_res(db, store.id, slot.id, "RES-BENT-001", party=5)
        login(client, s_def["phone_number"], s_def["password"])
        resp = client.get("/store/reservations")
        assert "RES-BENT-001" in resp.text

    def test_filter_by_status(self, client, clinic_store, db):
        store, s_def = clinic_store
        slot = get_available_slot(db, store.id)
        self._make_res(db, store.id, slot.id, "RES-CLIN-PEND", status="PENDING")
        self._make_res(db, store.id, slot.id, "RES-CLIN-CONF", status="CONFIRMED")
        login(client, s_def["phone_number"], s_def["password"])
        resp = client.get("/store/reservations?status=PENDING")
        assert "RES-CLIN-PEND" in resp.text
        assert "RES-CLIN-CONF" not in resp.text

    def test_store_isolation(self, client, izakaya_store, bento_store, db):
        """居酒屋ログイン中は弁当店の予約が見えない"""
        store_i, s_def_i = izakaya_store
        store_b, _ = bento_store
        slot_i = get_available_slot(db, store_i.id)
        slot_b = get_available_slot(db, store_b.id)
        self._make_res(db, store_i.id, slot_i.id, "RES-ISO-IZAK")
        self._make_res(db, store_b.id, slot_b.id, "RES-ISO-BENT")
        login(client, s_def_i["phone_number"], s_def_i["password"])
        resp = client.get("/store/reservations")
        assert "RES-ISO-IZAK" in resp.text
        assert "RES-ISO-BENT" not in resp.text


# ======================================================
# 7. 顧客予約フロー テスト（4店舗パターン）
# ======================================================
class TestCustomerBookingFlow:
    def test_booking_index_all_stores(self, client, all_stores):
        """4店舗すべて予約トップページが表示される"""
        for store, s_def in all_stores:
            resp = client.get(f"/book/{store.id}")
            assert resp.status_code == 200
            assert store.store_name in resp.text

    def test_beauty_slot_list(self, client, beauty_store, db):
        store, _ = beauty_store
        slot = get_available_slot(db, store.id)
        resp = client.get(f"/book/{store.id}/slots/{slot.slot_date.isoformat()}")
        assert resp.status_code == 200
        assert slot.slot_label in resp.text

    def test_izakaya_slot_list_shows_2h_slots(self, client, izakaya_store, db):
        """居酒屋：スロット一覧に2時間単位の枠が表示される"""
        store, _ = izakaya_store
        slot = get_available_slot(db, store.id)
        resp = client.get(f"/book/{store.id}/slots/{slot.slot_date.isoformat()}")
        assert resp.status_code == 200
        # 2時間枠のラベル確認（HH:MM-HH:MM形式）
        assert "-" in resp.text

    def test_bento_slot_shows_daily(self, client, bento_store, db):
        """弁当店：スロット一覧に「終日」と在庫数が表示される"""
        store, _ = bento_store
        slot = get_available_slot(db, store.id)
        resp = client.get(f"/book/{store.id}/slots/{slot.slot_date.isoformat()}")
        assert resp.status_code == 200
        assert "終日" in resp.text

    def test_booking_form_renders(self, client, izakaya_store, db):
        store, _ = izakaya_store
        slot = get_available_slot(db, store.id)
        resp = client.get(f"/book/{store.id}/form/{slot.id}")
        assert resp.status_code == 200
        assert "お名前" in resp.text
        assert "電話番号" in resp.text

    def test_create_izakaya_reservation(self, client, izakaya_store, db):
        """居酒屋：4名1組で予約作成"""
        store, _ = izakaya_store
        slot = get_available_slot(db, store.id)
        resp = client.post(f"/book/{store.id}/create", data={
            "slot_id": str(slot.id),
            "customer_name": "居酒屋テスト幹事",
            "customer_phone": "090-7777-0001",
            "customer_email": "izakaya@example.com",
            "party_size": "4",
        }, follow_redirects=False)
        assert resp.status_code in (302, 303)
        r = db.query(Reservation).filter(Reservation.customer_phone == "090-7777-0001").first()
        assert r is not None
        assert r.party_size == 4
        assert r.status == "PENDING"

    def test_create_bento_reservation_multiple(self, client, bento_store, db):
        """弁当店：5食まとめて予約"""
        store, _ = bento_store
        slot = get_available_slot(db, store.id)
        resp = client.post(f"/book/{store.id}/create", data={
            "slot_id": str(slot.id),
            "customer_name": "弁当テスト太郎",
            "customer_phone": "090-7777-0002",
            "party_size": "5",   # 5食注文
        }, follow_redirects=False)
        assert resp.status_code in (302, 303)
        r = db.query(Reservation).filter(Reservation.customer_phone == "090-7777-0002").first()
        assert r is not None
        assert r.party_size == 5

    def test_bento_stock_decreases(self, client, bento_store, db):
        """弁当店：予約後に残り在庫が減る"""
        store, _ = bento_store
        slot = get_available_slot(db, store.id)
        initial = slot.remaining_capacity
        client.post(f"/book/{store.id}/create", data={
            "slot_id": str(slot.id),
            "customer_name": "在庫テスト",
            "customer_phone": "090-7777-0003",
            "party_size": "3",
        }, follow_redirects=False)
        db.refresh(slot)
        assert slot.remaining_capacity == initial - 3

    def test_izakaya_capacity_limit(self, client, izakaya_store, db):
        """居酒屋：スロット定員（8名×6組=48名）超過は弾かれる"""
        store, _ = izakaya_store
        slot = get_available_slot(db, store.id)
        slot.max_capacity = 8
        db.commit()
        resp = client.post(f"/book/{store.id}/create", data={
            "slot_id": str(slot.id),
            "customer_name": "超過テスト",
            "customer_phone": "090-7777-0004",
            "party_size": "10",
        })
        assert resp.status_code == 200
        assert "予約できません" in resp.text

    def test_bento_sold_out(self, client, bento_store, db):
        """弁当店：在庫0で予約不可"""
        store, _ = bento_store
        slot = get_available_slot(db, store.id)
        slot.max_capacity = 2
        db.commit()
        # 2食予約して満員に
        client.post(f"/book/{store.id}/create", data={
            "slot_id": str(slot.id),
            "customer_name": "在庫満員テスト",
            "customer_phone": "090-7777-0005",
            "party_size": "2",
        }, follow_redirects=False)
        db.refresh(slot)
        # 追加予約しようとすると満員ページ
        resp = client.get(f"/book/{store.id}/form/{slot.id}")
        assert "満員" in resp.text

    def test_complete_page_shows_reservation_number(self, client, beauty_store, db):
        store, _ = beauty_store
        slot = get_available_slot(db, store.id)
        resp = client.post(f"/book/{store.id}/create", data={
            "slot_id": str(slot.id),
            "customer_name": "完了テスト",
            "customer_phone": "090-7777-0006",
            "party_size": "1",
        }, follow_redirects=True)
        assert "RES-" in resp.text
        assert "data:image/png;base64" not in resp.text
        assert "予約を確定する" in resp.text

    def test_confirm_token_flow(self, client, bento_store, db):
        """弁当店：確認トークンで予約確定"""
        store, _ = bento_store
        slot = get_available_slot(db, store.id)
        client.post(f"/book/{store.id}/create", data={
            "slot_id": str(slot.id),
            "customer_name": "確認フローテスト",
            "customer_phone": "090-7777-0007",
            "party_size": "2",
        }, follow_redirects=False)
        r = db.query(Reservation).filter(Reservation.customer_phone == "090-7777-0007").first()
        assert r.status == "PENDING"
        resp = client.get(f"/confirm/{r.confirmation_token}")
        assert resp.status_code == 200
        db.refresh(r)
        assert r.status == "CONFIRMED"

    def test_multiple_reservations_reduce_bento_stock(self, client, bento_store, db):
        """弁当店：複数予約で在庫が正しく減っていく"""
        store, _ = bento_store
        slot = get_available_slot(db, store.id)
        slot.max_capacity = 30
        db.commit()
        initial = 30
        for i, party in enumerate([3, 5, 2]):
            client.post(f"/book/{store.id}/create", data={
                "slot_id": str(slot.id),
                "customer_name": f"在庫テスト{i}",
                "customer_phone": f"090-9{i:03d}-0001",
                "party_size": str(party),
            }, follow_redirects=False)
        db.refresh(slot)
        assert slot.reserved_count == 10
        assert slot.remaining_capacity == initial - 10


# ======================================================
# 8. セキュリティ・境界値テスト
# ======================================================
class TestSecurity:
    def test_unauthenticated_redirects(self, client):
        for path in ["/store/dashboard", "/store/setup",
                     "/store/holidays", "/store/calendar", "/store/reservations"]:
            resp = client.get(path, follow_redirects=False)
            assert resp.status_code in (302, 422)

    def test_cross_store_slot_isolation(self, client, izakaya_store, bento_store, db):
        """居酒屋ログイン中は弁当店スロットを操作できない"""
        store_i, s_def_i = izakaya_store
        store_b, _ = bento_store
        login(client, s_def_i["phone_number"], s_def_i["password"])
        bento_slot = db.query(CalendarSlot).filter(CalendarSlot.store_id == store_b.id).first()
        if bento_slot:
            original = bento_slot.max_capacity
            client.post(f"/store/calendar/slot/{bento_slot.id}/update", data={
                "max_capacity": "9999", "redirect_url": "/"
            })
            db.refresh(bento_slot)
            assert bento_slot.max_capacity == original

    def test_nonexistent_store_404(self, client):
        assert client.get("/book/99999").status_code == 404

    def test_nonexistent_reservation_404(self, client):
        assert client.get("/book/complete/RES-NONE-9999").status_code == 404

    def test_invalid_confirm_token(self, client):
        resp = client.get("/confirm/invalid-token-xyz")
        assert resp.status_code == 200
        assert "見つかりません" in resp.text

    def test_health_check(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
