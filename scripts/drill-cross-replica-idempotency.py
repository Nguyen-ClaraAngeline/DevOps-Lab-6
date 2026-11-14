import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

APIS = ("http://127.0.0.1:8080", "http://127.0.0.1:8081")
RUN_ID = uuid4().hex[:12]
PAYLOAD = {"customer_id": "CUST-PART5", "items": [{"sku": "KIT-100", "quantity": 1}]}


def log(message):
    print(f"{datetime.now(UTC).isoformat()} {message}", flush=True)


def request(api, path, key=None):
    headers = {}
    data = None
    if key is not None:
        headers = {"Content-Type": "application/json", "Idempotency-Key": key}
        data = json.dumps(PAYLOAD).encode()

    try:
        response = urlopen(Request(api + path, data=data, headers=headers), timeout=15)
    except HTTPError as exc:
        response = exc

    with response:
        return response.code, json.load(response)


def stock():
    status, body = request(APIS[0], "/api/v1/inventory/KIT-100")
    assert status == 200, (status, body)
    return body["available"]


def race(keys):
    barrier = Barrier(len(keys), timeout=10)

    def submit(index, key):
        api = APIS[index % len(APIS)]
        barrier.wait()
        status, body = request(api, "/api/v1/orders", key)
        log(f"{api} key={key} HTTP {status} {body}")
        return status, body

    with ThreadPoolExecutor(max_workers=len(keys)) as pool:
        futures = [pool.submit(submit, i, key) for i, key in enumerate(keys)]
        return [future.result() for future in futures]


assert stock() == 7, "Start with a fresh isolated database with 7 KIT-100 units."
same_key = f"part5-{RUN_ID}-same"

log("Sending 8 identical requests, 4 to each API")
same = race([same_key] * 8)
assert all(status == 202 for status, _ in same), same
order_ids = {body["order_id"] for _, body in same}
assert len(order_ids) == 1, order_ids
order_id = next(iter(order_ids))
assert stock() == 6
log(f"PASS: one order ID {order_id}; stock 7 -> 6")

input("Restart the API on port 8081, confirm it is ready, then press Enter here: ")
status, replay = request(APIS[1], "/api/v1/orders", same_key)
assert status == 202 and replay["order_id"] == order_id, (status, replay)
assert stock() == 6
log(f"PASS: restart replay returned the same order ID {order_id}; stock stayed at 6")

log("Sending 12 competing orders with distinct keys")
distinct = race([f"part5-{RUN_ID}-{i:02}" for i in range(12)])
assert sorted(status for status, _ in distinct) == [202] * 6 + [409] * 6
assert all(body["error"]["code"] == "OUT_OF_STOCK" for status, body in distinct if status == 409)
assert stock() == 0
log(f"PASS: 6 accepted, 6 rejected as OUT_OF_STOCK, stock 0; SQL key prefix: part5-{RUN_ID}-")
