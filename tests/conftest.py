"""
テストの共通設定・フィクスチャ
DB初期化、テストデータ作成、テストクライアント提供
"""
import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import bcrypt

# テスト用インメモリDB使用
TEST_DATABASE_URL = "sqlite:///./test_reservation.db"

from app.database import Base, get_db
from app.main import app
from app.models import Store, ReservationConfig, HolidayRule, CalendarSlot, Reservation

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)



def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    """テスト用DBを初期化"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def clean_db():
    """各テスト前にデータをクリア"""
    yield
    db = TestingSessionLocal()
    try:
        db.query(Reservation).delete()
        db.query(CalendarSlot).delete()
        db.query(HolidayRule).delete()
        db.query(ReservationConfig).delete()
        db.query(Store).delete()
        db.commit()
    finally:
        db.close()


@pytest.fixture
def db():
    """テスト用DBセッション"""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db):
    """テスト用FastAPIクライアント"""
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


# ============================================================
# テストデータ作成ヘルパー
# ============================================================

def create_test_store(
    db,
    phone_number="090-1234-5678",
    password="testpass123",
    store_name="テスト店舗",
) -> Store:
    """テスト用店舗を作成してDBに登録"""
    store = Store(
        phone_number=phone_number,
        password_hash=bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
        store_name=store_name,
        line_channel_token="test-token",
        line_user_id="U1234567890",
    )
    db.add(store)
    db.commit()
    db.refresh(store)
    return store


def create_test_config(
    db,
    store_id: int,
    slot_type: str = "HOURLY",
    business_start: str = "09:00",
    business_end: str = "18:00",
    slot_interval_minutes: int = 60,
    capacity_per_slot: int = 4,
    box_count: int = 1,
    calendar_months_ahead: int = 3,
) -> ReservationConfig:
    """テスト用予約設定を作成"""
    config = ReservationConfig(
        store_id=store_id,
        slot_type=slot_type,
        business_start=business_start,
        business_end=business_end,
        slot_interval_minutes=slot_interval_minutes,
        capacity_per_slot=capacity_per_slot,
        box_count=box_count,
        calendar_months_ahead=calendar_months_ahead,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


def create_test_calendar_slot(
    db,
    store_id: int,
    slot_date: date = None,
    slot_label: str = "10:00-11:00",
    slot_start: str = "10:00",
    slot_end: str = "11:00",
    max_capacity: int = 4,
    is_available: bool = True,
) -> CalendarSlot:
    """テスト用カレンダースロットを作成"""
    if slot_date is None:
        slot_date = date.today() + timedelta(days=7)

    slot = CalendarSlot(
        store_id=store_id,
        slot_date=slot_date,
        slot_label=slot_label,
        slot_start=slot_start,
        slot_end=slot_end,
        max_capacity=max_capacity,
        is_available=is_available,
    )
    db.add(slot)
    db.commit()
    db.refresh(slot)
    return slot


def create_test_reservation(
    db,
    store_id: int,
    slot_id: int,
    reservation_number: str = "RES-20240101-TEST",
    customer_name: str = "テスト 太郎",
    customer_phone: str = "080-9876-5432",
    customer_email: str = "test@example.com",
    party_size: int = 1,
    status: str = "PENDING",
) -> Reservation:
    """テスト用予約データを作成"""
    import uuid
    reservation = Reservation(
        reservation_number=reservation_number,
        store_id=store_id,
        slot_id=slot_id,
        customer_name=customer_name,
        customer_phone=customer_phone,
        customer_email=customer_email,
        party_size=party_size,
        status=status,
        confirmation_token=str(uuid.uuid4()),
    )
    db.add(reservation)
    db.commit()
    db.refresh(reservation)
    return reservation


@pytest.fixture
def test_store(db):
    """基本テスト店舗フィクスチャ"""
    return create_test_store(db)


@pytest.fixture
def test_store_with_config(db, test_store):
    """設定済みテスト店舗フィクスチャ"""
    create_test_config(db, test_store.id)
    db.refresh(test_store)
    return test_store


@pytest.fixture
def test_slot(db, test_store_with_config):
    """テストスロットフィクスチャ"""
    return create_test_calendar_slot(db, test_store_with_config.id)


@pytest.fixture
def logged_in_client(client, test_store):
    """ログイン済みクライアント"""
    response = client.post(
        "/store/login",
        data={"phone_number": test_store.phone_number, "password": "testpass123"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    return client
