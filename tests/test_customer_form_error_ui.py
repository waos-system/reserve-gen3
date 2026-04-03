from tests.conftest import create_test_reservation


def test_capacity_error_hides_submit_and_shows_recovery_actions(
    client, test_store_with_config, test_slot, db
):
    test_slot.max_capacity = 2
    db.commit()

    create_test_reservation(
        db,
        test_store_with_config.id,
        test_slot.id,
        reservation_number="RES-ERR-UI-0001",
        party_size=2,
        status="CONFIRMED",
    )

    resp = client.post(
        f"/book/{test_store_with_config.id}/create",
        data={
            "slot_id": str(test_slot.id),
            "customer_name": "Error User",
            "customer_phone": "080-0000-1111",
            "party_size": "3",
        },
    )

    assert resp.status_code == 200
    assert "予約の確認へ" not in resp.text
    assert "別の時間を選ぶ" in resp.text
    assert "日付選択に戻る" in resp.text
