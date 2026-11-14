def calculate_total_cents(aggregated_items, prices):
    return sum(prices[sku] * quantity for sku, quantity in aggregated_items.items())
