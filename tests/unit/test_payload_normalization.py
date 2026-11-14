import json

from validation import parse_order


def make_payload(customer_id="CUST-001", items=None):
    if items is None:
        items = [{"sku": "SKU-A", "quantity": 2}]
    return json.dumps(
        {
            "customer_id": customer_id,
            "items": items,
        }
    ).encode()


def test_duplicate_skus_are_aggregated():
    raw = make_payload(
        items=[
            {"sku": "SKU-A", "quantity": 2},
            {"sku": "SKU-B", "quantity": 1},
            {"sku": "SKU-A", "quantity": 3},
        ]
    )

    customer_id, aggregated, payload_hash = parse_order("idempotency-001", raw)

    assert customer_id == "CUST-001"
    assert aggregated == {"SKU-A": 5, "SKU-B": 1}
    assert len(payload_hash) == 64


def test_item_order_does_not_change_payload_hash():
    first = make_payload(
        items=[
            {"sku": "SKU-A", "quantity": 2},
            {"sku": "SKU-B", "quantity": 1},
        ]
    )
    second = make_payload(
        items=[
            {"sku": "SKU-B", "quantity": 1},
            {"sku": "SKU-A", "quantity": 2},
        ]
    )

    assert parse_order("idempotency-001", first)[2] == parse_order("idempotency-001", second)[2]


def test_duplicate_skus_produce_same_hash_as_aggregated_quantity():
    duplicate_items = make_payload(
        items=[
            {"sku": "SKU-A", "quantity": 2},
            {"sku": "SKU-A", "quantity": 3},
        ]
    )
    aggregated_item = make_payload(
        items=[
            {"sku": "SKU-A", "quantity": 5},
        ]
    )

    assert (
        parse_order("idempotency-001", duplicate_items)[2]
        == parse_order("idempotency-001", aggregated_item)[2]
    )


def test_payload_hash_changes_when_order_contents_change():
    first = make_payload(items=[{"sku": "SKU-A", "quantity": 2}])
    second = make_payload(items=[{"sku": "SKU-A", "quantity": 3}])

    assert parse_order("idempotency-001", first)[2] != parse_order("idempotency-001", second)[2]
