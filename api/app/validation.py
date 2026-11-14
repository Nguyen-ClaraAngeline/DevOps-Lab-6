import hashlib
import json
import re

from errors import ApiError

KEY_RE = re.compile(r"[\x20-\x7E]{8,128}")
MAX_BODY = 16 * 1024


def parse_order(key, raw: bytes):
    if not key or not KEY_RE.fullmatch(key):
        raise ApiError(
            400,
            "IDEMPOTENCY_REQUIRED",
            "Idempotency-Key header must be 8-128 printable ASCII characters",
        )
    if len(raw) > MAX_BODY:
        raise ApiError(400, "INVALID_REQUEST", "Request body too large")
    try:
        body = json.loads(raw)
    except ValueError:
        raise ApiError(400, "INVALID_JSON", "Malformed JSON body")
    bad = lambda m: ApiError(400, "INVALID_REQUEST", m)
    if not isinstance(body, dict):
        raise bad("Body must be an object")
    cid, items = body.get("customer_id"), body.get("items")
    if not isinstance(cid, str) or not 1 <= len(cid) <= 64:
        raise bad("customer_id must be a string of 1-64 characters")
    if not isinstance(items, list) or not 1 <= len(items) <= 10:
        raise bad("items must contain 1-10 entries")
    for it in items:
        if not isinstance(it, dict) or not isinstance(it.get("sku"), str) or "quantity" not in it:
            raise bad("Each item needs sku and quantity")
    for it in items:
        q = it["quantity"]
        if type(q) is not int or not 1 <= q <= 20:
            raise ApiError(422, "INVALID_QUANTITY", "quantity must be an integer between 1 and 20")
    agg = {}
    for it in items:
        agg[it["sku"]] = agg.get(it["sku"], 0) + it["quantity"]
    canonical = json.dumps(
        {"customer_id": cid, "items": sorted(agg.items())}, sort_keys=True, separators=(",", ":")
    )
    return cid, agg, hashlib.sha256(canonical.encode()).hexdigest()
