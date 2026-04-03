"""
顧客予約フローのテスト
spec.md セクション3.2 顧客予約フロー参照
"""
import pytest
from datetime import date, timedelta
from app.models import Reservation, CalendarSlot
from tests.conftest import (
    create_test_store,
    create_test_config,
    create_test_calendar_slot,
    create_test_reservation,
)


class TestCustomerBookingFlow:
    def test_booking_index_renders(self, client, test_store_with_config, test_slot):
        """予約トップページが表示される"""
        resp = client.get(f"/book/{test_store_with_config.id}")
        assert resp.status_code == 200
        assert test_store_with_config.store_name in resp.text

    def test_booking_invalid_store(self, client):
        """存在しない店舗IDで404"""
        resp = client.get("/book/99999")
        assert resp.status_code == 404

    def test_slot_list_renders(self, client, test_store_with_config, test_slot):
        """スロット一覧が表示される"""
        resp = client.get(
            f"/book/{test_store_with_config.id}/slots/{test_slot.slot_date.isoformat()}"
        )
        assert resp.status_code == 200
        assert test_slot.slot_label in resp.text

    def test_slot_list_invalid_date(self, client, test_store_with_config):
        """不正な日付で400"""
        resp = client.get(f"/book/{test_store_with_config.id}/slots/not-a-date")
        assert resp.status_code == 400

    def test_booking_form_renders(self, client, test_store_with_config, test_slot):
        """予約フォームが表示される"""
        resp = client.get(f"/book/{test_store_with_config.id}/form/{test_slot.id}")
        assert resp.status_code == 200
        assert "お名前" in resp.text
        assert "電話番号" in resp.text

    def test_booking_form_full_slot(self, client, test_store_with_config, test_slot, db):
        """満員スロットでフォームの代わりに満員ページ"""
        test_slot.max_capacity = 1
        db.commit()
        create_test_reservation(
            db, test_store_with_config.id, test_slot.id,
            reservation_number="RES-FULL-0001",
            party_size=1,
            status="CONFIRMED",
        )
        db.refresh(test_slot)
        resp = client.get(f"/book/{test_store_with_config.id}/form/{test_slot.id}")
        assert resp.status_code == 200
        assert "満員" in resp.text


class TestCreateReservation:
    def test_create_reservation_success(self, client, test_store_with_config, test_slot, db):
        """正常な予約作成"""
        resp = client.post(
            f"/book/{test_store_with_config.id}/create",
            data={
                "slot_id": str(test_slot.id),
                "customer_name": "田中 花子",
                "customer_phone": "080-1111-2222",
                "customer_email": "hanako@example.com",
                "party_size": "2",
                "notes": "",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "/book/complete/" in resp.headers["location"]

        reservation = db.query(Reservation).filter(
            Reservation.customer_phone == "080-1111-2222"
        ).first()
        assert reservation is not None
        assert reservation.customer_name == "田中 花子"
        assert reservation.party_size == 2
        assert reservation.status == "PENDING"

    def test_create_reservation_exceeds_capacity(
        self, client, test_store_with_config, test_slot, db
    ):
        """定員超過の予約はエラーメッセージ表示"""
        test_slot.max_capacity = 2
        db.commit()

        resp = client.post(
            f"/book/{test_store_with_config.id}/create",
            data={
                "slot_id": str(test_slot.id),
                "customer_name": "テスト 太郎",
                "customer_phone": "080-0000-1111",
                "party_size": "5",
            },
        )
        assert resp.status_code == 200
        assert "予約できません" in resp.text

    def test_create_generates_qr_code(self, client, test_store_with_config, test_slot, db):
        """予約作成時にQRコードが生成される"""
        client.post(
            f"/book/{test_store_with_config.id}/create",
            data={
                "slot_id": str(test_slot.id),
                "customer_name": "鈴木 次郎",
                "customer_phone": "090-3333-4444",
                "party_size": "1",
            },
            follow_redirects=False,
        )
        reservation = db.query(Reservation).filter(
            Reservation.customer_phone == "090-3333-4444"
        ).first()
        assert reservation is not None
        assert reservation.qr_code_path is not None
        assert reservation.qr_code_path.startswith("data:image/png;base64,")

    def test_reservation_number_format(self, client, test_store_with_config, test_slot, db):
        """予約番号のフォーマット確認（RES-YYYYMMDD-XXXX）"""
        client.post(
            f"/book/{test_store_with_config.id}/create",
            data={
                "slot_id": str(test_slot.id),
                "customer_name": "山田 三郎",
                "customer_phone": "070-5555-6666",
                "party_size": "1",
            },
            follow_redirects=False,
        )
        reservation = db.query(Reservation).filter(
            Reservation.customer_phone == "070-5555-6666"
        ).first()
        assert reservation.reservation_number.startswith("RES-")
        parts = reservation.reservation_number.split("-")
        assert len(parts) == 3


class TestReservationComplete:
    def test_complete_page_renders(self, client, test_store_with_config, test_slot, db):
        """完了ページが表示される"""
        reservation = create_test_reservation(
            db, test_store_with_config.id, test_slot.id,
            reservation_number="RES-COMPLETE-0001",
        )
        resp = client.get(f"/book/complete/{reservation.reservation_number}")
        assert resp.status_code == 200
        assert reservation.reservation_number in resp.text
        assert reservation.customer_name in resp.text

    def test_complete_page_not_found(self, client):
        """存在しない予約番号で404"""
        resp = client.get("/book/complete/RES-INVALID-9999")
        assert resp.status_code == 404

    def test_complete_page_hides_qr(self, client, test_store_with_config, test_slot, db):
        """完了ページにQRコードが表示される"""
        reservation = create_test_reservation(
            db, test_store_with_config.id, test_slot.id,
            reservation_number="RES-QR-0001",
        )
        reservation.qr_code_path = "data:image/png;base64,iVBORw0KGgo="
        db.commit()
        resp = client.get(f"/book/complete/{reservation.reservation_number}")
        assert "data:image/png;base64" not in resp.text
        assert "予約を確定する" in resp.text


class TestConfirmReservation:
    def test_confirm_via_token(self, client, test_store_with_config, test_slot, db):
        """確認トークンで予約が確定する"""
        reservation = create_test_reservation(
            db, test_store_with_config.id, test_slot.id,
            reservation_number="RES-CONFIRM-0001",
            status="PENDING",
        )
        token = reservation.confirmation_token

        resp = client.get(f"/confirm/{token}")
        assert resp.status_code == 200

        db.refresh(reservation)
        assert reservation.status == "CONFIRMED"
        assert reservation.confirmed_at is not None

    def test_confirm_already_confirmed(self, client, test_store_with_config, test_slot, db):
        """既に確定済みの予約を再確認しても正常応答"""
        from datetime import datetime
        reservation = create_test_reservation(
            db, test_store_with_config.id, test_slot.id,
            reservation_number="RES-ALREADY-0001",
            status="CONFIRMED",
        )
        reservation.confirmed_at = datetime.utcnow()
        db.commit()

        resp = client.get(f"/confirm/{reservation.confirmation_token}")
        assert resp.status_code == 200
        assert "確定" in resp.text

    def test_confirm_invalid_token(self, client):
        """無効なトークンでエラーページ"""
        resp = client.get("/confirm/invalid-token-xyz")
        assert resp.status_code == 200
        assert "見つかりません" in resp.text

    def test_confirm_cancelled_reservation(self, client, test_store_with_config, test_slot, db):
        """キャンセル済み予約の確認でエラーページ"""
        reservation = create_test_reservation(
            db, test_store_with_config.id, test_slot.id,
            reservation_number="RES-CANCEL-0001",
            status="CANCELLED",
        )
        resp = client.get(f"/confirm/{reservation.confirmation_token}")
        assert resp.status_code == 200
        assert "キャンセル" in resp.text


class TestViewReservation:
    def test_view_reservation(self, client, test_store_with_config, test_slot, db):
        """予約詳細ページが表示される"""
        reservation = create_test_reservation(
            db, test_store_with_config.id, test_slot.id,
            reservation_number="RES-VIEW-0001",
        )
        resp = client.get(f"/book/view/{reservation.reservation_number}")
        assert resp.status_code == 200
        assert reservation.reservation_number in resp.text

    def test_view_nonexistent_reservation(self, client):
        """存在しない予約番号で404"""
        resp = client.get("/book/view/RES-NONEXISTENT-9999")
        assert resp.status_code == 404


class TestCapacityManagement:
    def test_capacity_decreases_after_reservation(
        self, client, test_store_with_config, test_slot, db
    ):
        """予約後に残り容量が減る"""
        initial_capacity = test_slot.max_capacity
        create_test_reservation(
            db, test_store_with_config.id, test_slot.id,
            reservation_number="RES-CAP-0001",
            party_size=2,
            status="CONFIRMED",
        )
        db.refresh(test_slot)
        assert test_slot.remaining_capacity == initial_capacity - 2

    def test_cancelled_reservation_frees_capacity(
        self, client, test_store_with_config, test_slot, db
    ):
        """キャンセルされた予約は容量をカウントしない"""
        create_test_reservation(
            db, test_store_with_config.id, test_slot.id,
            reservation_number="RES-CANCEL-CAP-0001",
            party_size=3,
            status="CANCELLED",
        )
        db.refresh(test_slot)
        assert test_slot.remaining_capacity == test_slot.max_capacity

    def test_multiple_reservations_count(
        self, client, test_store_with_config, test_slot, db
    ):
        """複数予約の合計が正しくカウントされる"""
        create_test_reservation(
            db, test_store_with_config.id, test_slot.id,
            reservation_number="RES-MULTI-0001",
            party_size=1,
            status="CONFIRMED",
        )
        create_test_reservation(
            db, test_store_with_config.id, test_slot.id,
            reservation_number="RES-MULTI-0002",
            party_size=2,
            status="PENDING",
        )
        db.refresh(test_slot)
        assert test_slot.reserved_count == 3
        assert test_slot.remaining_capacity == test_slot.max_capacity - 3
