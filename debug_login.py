#!/usr/bin/env python
"""ログイン診断・修復スクリプト"""
import sys, os
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)
sys.path.insert(0, script_dir)

print("=" * 50)
print("🔍 ログイン診断ツール")
print("=" * 50)
print(f"📂 作業ディレクトリ: {os.getcwd()}")

import bcrypt
from app.database import SessionLocal, init_db
from app.models import Store, ReservationConfig, HolidayRule

def hash_password(p): return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
def verify_password(p, h): return bcrypt.checkpw(p.encode(), h.encode())

init_db()
db = SessionLocal()

stores = db.query(Store).all()
print(f"\n📊 DB内の店舗数: {len(stores)}")
for s in stores:
    print(f"  ID={s.id} | 電話番号='{s.phone_number}' | 店舗名='{s.store_name}'")

store = db.query(Store).filter(Store.phone_number == "090-0000-0001").first()
if store:
    ok = verify_password("demo1234", store.password_hash)
    print(f"\n🔐 パスワード検証: {'✅ 一致' if ok else '❌ 不一致'}")
    if not ok:
        store.password_hash = hash_password("demo1234")
        db.commit()
        print("   → パスワードを 'demo1234' にリセットしました")
else:
    print("\n⚠️  アカウントなし → 今すぐ作成します...")
    new_store = Store(
        phone_number="090-0000-0001",
        password_hash=hash_password("demo1234"),
        store_name="サンプル美容院",
        line_channel_token="", line_user_id="",
    )
    db.add(new_store)
    db.flush()
    db.add(ReservationConfig(
        store_id=new_store.id, slot_type="HOURLY",
        business_start="09:00", business_end="19:00",
        slot_interval_minutes=60, capacity_per_slot=2,
        box_count=3, box_label="担当者", calendar_months_ahead=3,
    ))
    db.add(HolidayRule(
        store_id=new_store.id, rule_type="WEEKLY",
        day_of_week=0, description="定休日（月曜）",
    ))
    db.commit()
    print(f"   ✅ アカウント作成完了 (ID: {new_store.id})")

db.close()
print("\n" + "=" * 50)
print("✅ 完了 → python run.py でサーバーを起動してログインしてください")
print("   電話番号 : 090-0000-0001")
print("   パスワード: demo1234")
print("=" * 50)
