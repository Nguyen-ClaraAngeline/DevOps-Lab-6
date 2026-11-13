import csv, math, time, urllib.request, urllib.error

BASE = "http://localhost:8080"
PATHS = ["/api/v1/catalog", "/api/v1/inventory/KIT-100", "/api/v1/inventory/PART-200", "/health/ready"]
N = 250
rows = []
for i in range(N):
    path = PATHS[i % len(PATHS)]
    t = time.perf_counter()
    try:
        with urllib.request.urlopen(BASE + path, timeout=5) as r:
            status = r.status
            r.read()
    except urllib.error.HTTPError as e:
        status = e.code
    except Exception:
        status = 0
    rows.append((path, status, (time.perf_counter() - t) * 1000))

with open("docs/p95_samples.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["path", "status", "latency_ms"])
    w.writerows(rows)

lat = sorted(r[2] for r in rows)
pct = lambda p: lat[math.ceil(p * len(lat)) - 1]
errors = sum(1 for r in rows if not 200 <= r[1] < 300)
print(f"samples={len(lat)} errors={errors} p50={pct(.5):.1f}ms p95={pct(.95):.1f}ms p99={pct(.99):.1f}ms max={lat[-1]:.1f}ms")
