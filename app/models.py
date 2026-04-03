"""
SQLAlchemy ORM モデル定義
spec.md セクション2 テーブル設計参照
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Date,
    ForeignKey, Text, UniqueConstraint
)
from sqlalchemy.orm import relationship
from app.database import Base


class Store(Base):
    """店舗アカウント"""
    __tablename__ = "stores"

    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String(20), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    store_name = Column(String(100), nullable=False)
    line_channel_token = Column(Text, nullable=True)
    line_user_id = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relations
    config = relationship("ReservationConfig", back_populates="store", uselist=False)
    holiday_rules = relationship("HolidayRule", back_populates="store")
    calendar_slots = relationship("CalendarSlot", back_populates="store")
    reservations = relationship("Reservation", back_populates="store")
    settings = relationship("SystemSetting", back_populates="store")


class ReservationConfig(Base):
    """予約設定（タイプ・営業時間・ボックス）"""
    __tablename__ = "reservation_configs"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    # DAILY: 1日単位 / HOURLY: 時間単位 / HALFDAY: 午前午後
    slot_type = Column(String(20), nullable=False, default="DAILY")
    business_start = Column(String(5), nullable=False, default="09:00")
    business_end = Column(String(5), nullable=False, default="18:00")
    slot_interval_minutes = Column(Integer, nullable=True, default=60)
    # 1スロットあたりの収容人数（ボックスなしの場合）
    capacity_per_slot = Column(Integer, nullable=False, default=10)
    # ボックス数（席数・担当者数等）
    box_count = Column(Integer, nullable=True, default=1)
    box_label = Column(String(50), nullable=True, default="席")
    # 祝日を自動休業にするか（False=祝日でも予約可能）
    close_on_holidays = Column(Boolean, nullable=False, default=True)
    # カレンダー作成月数（翌月から何ヶ月後の末日まで）
    calendar_months_ahead = Column(Integer, nullable=False, default=3)
    # 午前終了時間（HALFDAY時に使用）
    am_end_time = Column(String(5), nullable=True, default="12:00")
    # 午前・午後各キャパシティ（HALFDAY時）
    am_capacity = Column(Integer, nullable=True)
    pm_capacity = Column(Integer, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    store = relationship("Store", back_populates="config")


class HolidayRule(Base):
    """定休日ルール"""
    __tablename__ = "holiday_rules"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    # WEEKLY: 毎週 / SPECIFIC: 特定日
    rule_type = Column(String(20), nullable=False)
    # 0=月曜, 1=火曜, ..., 6=日曜（WEEKLY時）
    day_of_week = Column(Integer, nullable=True)
    specific_date = Column(Date, nullable=True)
    # NULL=終日休み / AM=午前休み / PM=午後休み
    half_day_restriction = Column(String(10), nullable=True)
    description = Column(String(100), nullable=True)

    store = relationship("Store", back_populates="holiday_rules")


class CalendarSlot(Base):
    """予約カレンダーのスロット（日付×時間帯）"""
    __tablename__ = "calendar_slots"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    slot_date = Column(Date, nullable=False, index=True)
    # 表示ラベル（例: "10:00-11:00", "午前", "終日"）
    slot_label = Column(String(50), nullable=False)
    slot_start = Column(String(5), nullable=True)  # HH:MM
    slot_end = Column(String(5), nullable=True)    # HH:MM
    max_capacity = Column(Integer, nullable=False, default=0)
    is_available = Column(Boolean, default=True)
    is_holiday = Column(Boolean, default=False)
    holiday_reason = Column(String(100), nullable=True)
    override_note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("store_id", "slot_date", "slot_label", name="uq_slot"),
    )

    store = relationship("Store", back_populates="calendar_slots")
    reservations = relationship("Reservation", back_populates="slot")

    @property
    def reserved_count(self):
        return sum(
            r.party_size for r in self.reservations
            if r.status in ("PENDING", "CONFIRMED")
        )

    @property
    def remaining_capacity(self):
        return max(0, self.max_capacity - self.reserved_count)


class Reservation(Base):
    """予約"""
    __tablename__ = "reservations"

    id = Column(Integer, primary_key=True, index=True)
    reservation_number = Column(String(20), unique=True, nullable=False, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    slot_id = Column(Integer, ForeignKey("calendar_slots.id"), nullable=False)
    customer_name = Column(String(100), nullable=False)
    customer_phone = Column(String(20), nullable=False)
    customer_email = Column(String(255), nullable=True)
    party_size = Column(Integer, nullable=False, default=1)
    # PENDING: 仮予約 / CONFIRMED: 確定 / CANCELLED: キャンセル
    status = Column(String(20), nullable=False, default="PENDING")
    confirmation_token = Column(String(100), nullable=True, unique=True)
    line_user_id = Column(String(100), nullable=True)
    qr_code_path = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    confirmed_at = Column(DateTime, nullable=True)

    store = relationship("Store", back_populates="reservations")
    slot = relationship("CalendarSlot", back_populates="reservations")


class SystemSetting(Base):
    """システム設定（店舗別KVストア）"""
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    key = Column(String(100), nullable=False)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("store_id", "key", name="uq_setting"),
    )

    store = relationship("Store", back_populates="settings")
