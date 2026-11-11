import pytest

from services.totals import calculate_total_cents


def test_calculates_total_for_multiple_products():
    items = {
        "SKU-A": 2,
        "SKU-B": 3,
    }
    prices = {
        "SKU-A": 500,
        "SKU-B": 1200,
    }

    assert calculate_total_cents(items, prices) == 4600


def test_calculates_total_for_single_product():
    items = {"SKU-A": 4}
    prices = {"SKU-A": 250}

    assert calculate_total_cents(items, prices) == 1000


def test_calculates_zero_for_empty_items():
    assert calculate_total_cents({}, {}) == 0


@pytest.mark.parametrize(
    "items, prices, expected",
    [
        ({"SKU-A": 1}, {"SKU-A": 999}, 999),
        ({"SKU-A": 2, "SKU-B": 1}, {"SKU-A": 100, "SKU-B": 350}, 550),
        ({"SKU-A": 5}, {"SKU-A": 1}, 5),
    ],
)
def test_calculates_expected_total(items, prices, expected):
    assert calculate_total_cents(items, prices) == expected