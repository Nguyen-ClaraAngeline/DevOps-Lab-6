def test_duplicate_sku_lines_are_combined_in_created_order(
    client, reset_test_db
):
    response = client.post(
        "/api/v1/orders",
        headers={"Idempotency-Key": "regression-duplicate-001"},
        json={
            "customer_id": "CUST-REGRESSION",
            "items": [
                {"sku": "KIT-100", "quantity": 2},
                {"sku": "KIT-100", "quantity": 3},
            ],
        },
    )

    assert response.status_code == 202
    order_id = response.json()["order_id"]

    details = client.get(f"/api/v1/orders/{order_id}")
    assert details.status_code == 200

    order = details.json()
    assert order["total_cents"] == 6495
    assert order["items"] == [
        {"sku": "KIT-100", "quantity": 5},
    ]

    inventory = client.get("/api/v1/inventory/KIT-100")
    assert inventory.json()["available"] == 2