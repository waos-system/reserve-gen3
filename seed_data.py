#!/usr/bin/env python
"""
デモデータ作成スクリプト
美容院・病院・居酒屋・在庫予約の4店舗を作成し、カレンダーも生成する
"""
import sys, os
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)
sys.path.insert(0, script_dir)

import bcrypt, uuid
from datetime import date, timedelta
from app.database import SessionLocal, init_db
from app.models import Store, ReservationConfig, HolidayRule, CalendarSlot, Reservation

def hp(p): return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()

STORES = [
    # ── 1. 美容院 ─────────────────────────────────────────
    {
        "phone_number": "090-0000-0001",
        "password":     "demo1234",
        "store_name":   "✂️ サンプル美容院 Hair&Nail BLOOM",
        "config": dict(
            slot_type="HOURLY",
            business_start="09:00", business_end="19:00",
            slot_interval_minutes=60,
            capacity_per_slot=1,   # 担当者1人が1枠1名対応
            box_count=3,           # 担当者3名
            box_label="担当者",
            calendar_months_ahead=3,
        ),
        "holidays": [
            dict(rule_type="WEEKLY", day_of_week=0, description="定休日（月曜）"),
            dict(rule_type="WEEKLY", day_of_week=6, half_day_restriction="PM",
                 description="土曜午後休み"),
        ],
        "note": "1時間枠×担当者3名(同時3組) / 月曜定休・土曜午後休み",
    },

    # ── 2. 内科クリニック ─────────────────────────────────
    {
        "phone_number": "090-0000-0002",
        "password":     "demo5678",
        "store_name":   "🏥 さくら内科クリニック",
        "config": dict(
            slot_type="HALFDAY",
            business_start="09:00", business_end="17:00",
            slot_interval_minutes=60,
            capacity_per_slot=10, box_count=1, box_label="枠",
            calendar_months_ahead=2,
            am_end_time="12:00", am_capacity=20, pm_capacity=15,
        ),
        "holidays": [
            dict(rule_type="WEEKLY", day_of_week=5, description="土曜定休"),
            dict(rule_type="WEEKLY", day_of_week=6, description="日曜定休"),
            dict(rule_type="WEEKLY", day_of_week=2, half_day_restriction="PM",
                 description="水曜午後休診"),
        ],
        "note": "午前20名・午後15名 / 土日休み・水曜午後休診",
    },

    # ── 3. 居酒屋（2時間制・組予約） ──────────────────────
    {
        "phone_number": "090-0000-0003",
        "password":     "demo9012",
        "store_name":   "🍻 大衆居酒屋 串八番",
        "config": dict(
            slot_type="HOURLY",
            business_start="17:00", business_end="23:00",
            slot_interval_minutes=120,   # ★ 2時間制
            capacity_per_slot=8,          # ★ 1組最大8名
            box_count=6,                  # ★ 同時最大6組
            box_label="組",
            calendar_months_ahead=3,
        ),
        "holidays": [
            dict(rule_type="WEEKLY", day_of_week=0, description="日曜定休"),
        ],
        "note": "2時間制×最大6組(各8名まで) / 17:00〜23:00 / 日曜定休",
        # 例: 17:00-19:00, 19:00-21:00, 21:00-23:00 の3枠 × 6組 = 18組/日
    },

    # ── 4. 在庫予約（お弁当・ケーキ・日替わり商品） ─────────
    {
        "phone_number": "090-0000-0004",
        "password":     "demo3456",
        "store_name":   "🍱 手作り弁当 まかないや",
        "config": dict(
            slot_type="DAILY",
            business_start="11:00", business_end="14:00",
            slot_interval_minutes=60,
            capacity_per_slot=30,  # ★ 1日30食まで
            box_count=1,
            box_label="食",
            calendar_months_ahead=2,
        ),
        "holidays": [
            dict(rule_type="WEEKLY", day_of_week=5, description="土曜定休"),
            dict(rule_type="WEEKLY", day_of_week=6, description="日曜定休"),
        ],
        "note": "1日30食限定の在庫予約 / 土日休み",
    },
]

# サンプル予約データ（店舗ごとにリアルな人数・組数を設定）
SAMPLE_CUSTOMERS = [
    ("田中 太郎",   "090-1111-0001", "tanaka@example.com",    2),
    ("佐藤 花子",   "080-2222-0002", "sato@example.com",      1),
    ("鈴木 次郎",   "070-3333-0003", None,                    3),
    ("高橋 美咲",   "090-4444-0004", "takahashi@example.com", 2),
    ("伊藤 健一",   "080-5555-0005", None,                    1),
    ("渡辺 優子",   "090-6666-0006", "watanabe@example.com",  4),
    ("山本 大輔",   "070-7777-0007", None,                    2),
    ("中村 さくら", "080-8888-0008", "nakamura@example.com",  1),
]
STATUSES = ["CONFIRMED", "CONFIRMED", "CONFIRMED", "PENDING",
            "CONFIRMED", "CANCELLED", "CONFIRMED", "PENDING"]


def create_sample_reservations(db, store, slots):
    """各店舗にサンプル予約データを作成"""
    from datetime import datetime
    created = 0
    for i, slot in enumerate(slots[:min(8, len(slots))]):
        if slot.max_capacity == 0:
            continue
        cust = SAMPLE_CUSTOMERS[i % len(SAMPLE_CUSTOMERS)]
        status = STATUSES[i % len(STATUSES)]
        party = min(cust[3], slot.max_capacity)
        res = Reservation(
            reservation_number=f"RES-DEMO-{store.id:02d}{i+1:03d}",
            store_id=store.id,
            slot_id=slot.id,
            customer_name=cust[0],
            customer_phone=cust[1],
            customer_email=cust[2],
            party_size=party,
            status=status,
            confirmation_token=str(uuid.uuid4()),
            confirmed_at=datetime.utcnow() if status == "CONFIRMED" else None,
        )
        db.add(res)
        created += 1
    return created


def seed():
    print("🔧 DBテーブルを初期化中...")
    init_db()
    db = SessionLocal()
    try:
        from app.utils.calendar_utils import generate_calendar_from
        today = date.today()

        for s_def in STORES:
            existing = db.query(Store).filter(
                Store.phone_number == s_def["phone_number"]
            ).first()
            if existing:
                print(f"  ✅ 既存: {s_def['store_name']} (ID:{existing.id})")
                continue

            # 店舗作成
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

            # カレンダー生成
            result = generate_calendar_from(db, store.id, start_date=today)
            print(f"  ✅ {s_def['store_name']} (ID:{store.id}) → {result.get('created',0)}スロット生成")

            # サンプル予約作成
            future_slots = db.query(CalendarSlot).filter(
                CalendarSlot.store_id == store.id,
                CalendarSlot.slot_date >= today,
                CalendarSlot.slot_date <= today + timedelta(days=14),
                CalendarSlot.is_available == True,
                CalendarSlot.is_holiday == False,
            ).order_by(CalendarSlot.slot_date, CalendarSlot.slot_start).limit(10).all()

            res_count = create_sample_reservations(db, store, future_slots)
            db.commit()
            print(f"             → サンプル予約 {res_count}件作成")

        db.commit()
        print("\n" + "=" * 60)
        print("✅ デモデータ作成完了！")
        print("=" * 60)
        stores = db.query(Store).all()
        for st in stores:
            for s_def in STORES:
                if st.phone_number == s_def["phone_number"]:
                    print(f"\n  {st.store_name}")
                    print(f"    ログイン電話番号 : {s_def['phone_number']}")
                    print(f"    パスワード       : {s_def['password']}")
                    print(f"    店舗ID           : {st.id}")
                    print(f"    予約ページ        : http://localhost:8000/book/{st.id}")
                    print(f"    設定             : {s_def['note']}")
        print("\n  ログインURL: http://localhost:8000/store/login")
        print("=" * 60)
    finally:
        db.close()


if __name__ == "__main__":
    seed()
