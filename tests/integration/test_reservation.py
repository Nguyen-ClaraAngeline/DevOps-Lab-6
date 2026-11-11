def make_payload(items=None, customer_id="CUST-001"):
    if items is None:
        items = [
            {"sku": "KIT-100", "quantity": 2},
            {"sku": "PART-200", "quantity": 3},
        ]

    return {
        "customer_id": customer_id,
        "items": items,
    }


def place_order(client, key, payload):
    return client.post(
        "/api/v1/orders",
        headers={"Idempotency-Key": key},
        json=payload,
    )


def test_creates_order_and_reserves_stock(client, reset_test_db):
    response = place_order(
        client,
        "reservation-001",
        make_payload(),
    )

    assert response.status_code == 202
    result = response.json()
    assert result["status"] == "queued"

    order_id = result["order_id"]

    details = client.get(f"/api/v1/orders/{order_id}")
    assert details.status_code == 200

    order = details.json()
    assert order["customer_id"] == "CUST-001"
    assert order["total_cents"] == 4395
    assert order["status"] == "queued"
    assert order["items"] == [
        {"sku": "KIT-100", "quantity": 2},
        {"sku": "PART-200", "quantity": 3},
    ]

    assert client.get("/api/v1/inventory/KIT-100").json()["available"] == 5
    assert client.get("/api/v1/inventory/PART-200").json()["available"] == 9


def test_duplicate_request_returns_same_order_without_double_reservation(
    client, reset_test_db
):
    payload = make_payload()

    first = place_order(client, "reservation-002", payload)
    second = place_order(client, "reservation-002", payload)

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["order_id"] == second.json()["order_id"]

    assert client.get("/api/v1/inventory/KIT-100").json()["available"] == 5
    assert client.get("/api/v1/inventory/PART-200").json()["available"] == 9


def test_reusing_key_with_different_payload_returns_conflict(
    client, reset_test_db
):
    first = place_order(
        client,
        "reservation-003",
        make_payload(),
    )

    second = place_order(
        client,
        "reservation-003",
        make_payload(items=[{"sku": "PACK-300", "quantity": 1}]),
    )

    assert first.status_code == 202
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"

    assert client.get("/api/v1/inventory/KIT-100").json()["available"] == 5
    assert client.get("/api/v1/inventory/PACK-300").json()["available"] == 5


def test_unknown_sku_is_rejected_without_reserving_stock(
    client, reset_test_db
):
    response = place_order(
        client,
        "reservation-004",
        make_payload(items=[{"sku": "UNKNOWN-999", "quantity": 1}]),
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_SKU"

    assert client.get("/api/v1/inventory/KIT-100").json()["available"] == 7


def test_insufficient_stock_rolls_back_entire_reservation(
    client, reset_test_db
):
    response = place_order(
        client,
        "reservation-005",
        make_payload(items=[
            {"sku": "KIT-100", "quantity": 2},
            {"sku": "PACK-300", "quantity": 6},
        ]),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "OUT_OF_STOCK"

    assert client.get("/api/v1/inventory/KIT-100").json()["available"] == 7
    assert client.get("/api/v1/inventory/PACK-300").json()["available"] == 5