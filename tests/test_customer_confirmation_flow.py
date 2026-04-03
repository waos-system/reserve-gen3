from tests.conftest import create_test_reservation


def test_confirmed_screen_shows_contact_info_and_access_url(
    client, test_store_with_config, test_slot, db, monkeypatch
):
    calls = {"email": 0}

    def fake_send_email(**kwargs):
        calls["email"] += 1
        assert kwargs["to_email"] == "confirmed@example.com"
        assert "/book/view/RES-CONF-SCREEN-0001" in kwargs["access_url"]
        return True

    monkeypatch.setattr("app.routers.customer.send_reservation_access_email", fake_send_email)

    reservation = create_test_reservation(
        db,
        test_store_with_config.id,
        test_slot.id,
        reservation_number="RES-CONF-SCREEN-0001",
        status="PENDING",
        customer_name="Confirmed User",
        customer_phone="090-7777-8888",
        customer_email="confirmed@example.com",
    )

    resp = client.get(f"/confirm/{reservation.confirmation_token}")

    assert resp.status_code == 200
    assert "Confirmed User" in resp.text
    assert "090-7777-8888" in resp.text
    assert "confirmed@example.com" in resp.text
    assert "/book/view/RES-CONF-SCREEN-0001" in resp.text
    assert "data:image/png;base64" in resp.text
    assert calls["email"] == 1


def test_view_confirmed_reservation_uses_confirmed_screen(
    client, test_store_with_config, test_slot, db
):
    reservation = create_test_reservation(
        db,
        test_store_with_config.id,
        test_slot.id,
        reservation_number="RES-VIEW-CONF-0001",
        status="CONFIRMED",
        customer_name="View User",
        customer_phone="090-1111-9999",
        customer_email="view@example.com",
    )
    reservation.qr_code_path = "data:image/png;base64,iVBORw0KGgo="
    db.commit()

    resp = client.get(f"/book/view/{reservation.reservation_number}")

    assert resp.status_code == 200
    assert "予約は確定済みです" in resp.text
    assert "view@example.com" in resp.text
    assert "data:image/png;base64" in resp.text
