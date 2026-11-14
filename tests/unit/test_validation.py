import json

import pytest
from errors import ApiError
from validation import parse_order


def valid_payload():
    return json.dumps(
        {
            "customer_id": "CUST-001",
            "items": [{"sku": "SKU-A", "quantity": 2}],
        }
    ).encode()


def assert_api_error(key, raw, status, code):
    with pytest.raises(ApiError) as exc:
        parse_order(key, raw)

    assert exc.value.status == status
    assert exc.value.code == code


@pytest.mark.parametrize(
    "key",
    [
        None,
        "",
        "short",
        "invalid\nkey",
        "x" * 129,
    ],
)
def test_rejects_invalid_idempotency_keys(key):
    assert_api_error(key, valid_payload(), 400, "IDEMPOTENCY_REQUIRED")


def test_accepts_valid_idempotency_key():
    customer_id, items, payload_hash = parse_order("valid-key-001", valid_payload())

    assert customer_id == "CUST-001"
    assert items == {"SKU-A": 2}
    assert len(payload_hash) == 64


def test_rejects_oversized_request_body():
    raw = b" " * (16 * 1024 + 1)
    assert_api_error("valid-key-001", raw, 400, "INVALID_REQUEST")


def test_rejects_malformed_json():
    assert_api_error("valid-key-001", b"{invalid json", 400, "INVALID_JSON")


@pytest.mark.parametrize(
    "body",
    [
        [],
        "not an object",
        None,
        123,
    ],
)
def test_rejects_non_object_json_body(body):
    assert_api_error(
        "valid-key-001",
        json.dumps(body).encode(),
        400,
        "INVALID_REQUEST",
    )


@pytest.mark.parametrize(
    "customer_id",
    [
        None,
        "",
        "x" * 65,
        123,
    ],
)
def test_rejects_invalid_customer_id(customer_id):
    raw = json.dumps(
        {
            "customer_id": customer_id,
            "items": [{"sku": "SKU-A", "quantity": 1}],
        }
    ).encode()

    assert_api_error("valid-key-001", raw, 400, "INVALID_REQUEST")


@pytest.mark.parametrize(
    "items",
    [
        [],
        [{"sku": "SKU-A", "quantity": 1}] * 11,
        "not a list",
        None,
    ],
)
def test_rejects_invalid_item_collections(items):
    raw = json.dumps(
        {
            "customer_id": "CUST-001",
            "items": items,
        }
    ).encode()

    assert_api_error("valid-key-001", raw, 400, "INVALID_REQUEST")


@pytest.mark.parametrize(
    "item",
    [
        {},
        {"sku": "SKU-A"},
        {"quantity": 1},
        "not an object",
    ],
)
def test_rejects_items_missing_required_fields(item):
    raw = json.dumps(
        {
            "customer_id": "CUST-001",
            "items": [item],
        }
    ).encode()

    assert_api_error("valid-key-001", raw, 400, "INVALID_REQUEST")


@pytest.mark.parametrize(
    "quantity",
    [
        0,
        21,
        -1,
        1.5,
        "2",
        True,
        None,
    ],
)
def test_rejects_invalid_quantities(quantity):
    raw = json.dumps(
        {
            "customer_id": "CUST-001",
            "items": [{"sku": "SKU-A", "quantity": quantity}],
        }
    ).encode()

    assert_api_error("valid-key-001", raw, 422, "INVALID_QUANTITY")
