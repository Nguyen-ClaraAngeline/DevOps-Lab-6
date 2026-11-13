# SLO definition and measurement

## Objectives (proposed)
| SLI | Definition | Target |
|---|---|---|
| Availability | non-5xx responses / all responses, from `fulfillops_http_requests_total` | 99.5% over the evaluation window |
| Latency | p95 of request duration | < 300 ms in the isolated local test |

Error budget: 0.5% of requests, i.e. 5 failed requests per 1000.

## Observed evidence
- Availability: on the API pod behind the port-forward, `fulfillops_http_requests_total` showed 1361 requests, all with status 200 (993 readiness, 178 liveness, 125 inventory, 63 catalog, 1 order read, 1 metrics). Observed non-5xx ratio: 100%.
- Rolling update probe (kubectl proxy, 30 s, good release): 24 samples, 0 failures.
- Earlier probe through kubectl port-forward (30 s, rollout inside the window): 119 samples, 2 failures (HTTP status 0, port-forward switching pods). Kept as evidence in docs/evidence/.
- Stalled broken release: the two old pods stayed Ready while the new pod stayed at 0/1.
- Latency, client side: 250 sequential requests (docs/p95_samples.csv): p50 16.3 ms, p95 33.4 ms, p99 54.3 ms, max 76.5 ms, 0 errors. Target met (33.4 ms < 300 ms).
- Latency, server side: histogram `fulfillops_http_request_duration_seconds` for /health/ready had 958 of 993 observations at or below 5 ms, so the server-side p95 is below 5 ms.

## Calculation
- Availability = 1 - (5xx responses / all responses) = 1 - 0/1361 = 100%.
- p95 = the value at rank ceil(0.95 * 250) = 238 of the sorted latencies.
- PromQL equivalent: `histogram_quantile(0.95, sum(rate(fulfillops_http_request_duration_seconds_bucket[5m])) by (le))`.

## Limitations
- One laptop, one kind node, no real network path.
- Client latency includes kubectl port-forward and Python overhead; server-side latency is much lower.
- Small dataset, warm caches, no concurrent load, mostly read endpoints.
- Counters are per pod and reset on restart; the sample covers only the pod behind the port-forward.
- Short measurement windows: this shows the implementation works, not production capacity.
