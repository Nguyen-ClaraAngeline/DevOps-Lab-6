# Part 9: rollout, rollback and latency evidence

The integrated drill used the Part 8 disposable kind cluster and a temporary real Git repository containing the integrated Kubernetes manifests. The team GitHub repository was not changed. The original team rehearsal and raw captures are retained.

| Step | Integrated result |
| --- | --- |
| Good rollout | Git revision 109e02f became 6d98b1c after an innocuous API pod annotation. The rollout became Synced and Healthy during the 06:24:06–06:24:36 UTC probe on 14 November 2026; 121 requests, no failures. |
| Broken rollout | Revision 29a34b0 used a nonexistent readiness path. The new pod failed with HTTP 404 and rollout status timed out. Argo CD was Synced but Progressing. Two old pods stayed Ready; the 30-second service probe had 121 successes and no failures. |
| Rollback | Git revert e7dfae3 was published at 06:25:22 UTC. Argo CD became Synced and Healthy at 06:25:31 UTC. Before/after SQL lists match for both committed order IDs; the order tested through the API was still completed with the same total. |
| Latency and SLO | The integrated run recorded 250 samples, p95 10.2 ms, and zero errors. The original run recorded 250 samples, p95 33.4 ms. Both are below the proposed 300 ms local target. |

[Full transcript](evidence/part9-integrated-rollout.txt) · [Good rollout probe](evidence/part9-integrated-good.csv) · [Stalled rollout probe](evidence/part9-integrated-stalled.csv) · [Latency CSV](evidence/part9-integrated-p95.csv) · [SLO and limits](slo.md) · [Postmortem](incident-postmortem.md)

The original direct port-forward dropped two connections when its pod changed. The clean integrated probe used the same local endpoint throughout via kubectl proxy to the Kubernetes Service. That measures Service availability across pod replacement. The short local windows do not establish production availability.

## Reproduce

1. Start the [Part 8 lab](part8-report.md). Point Argo CD to a disposable Git branch and let it reach Synced and Healthy. Submit an order and capture its ID plus the full sorted list of committed IDs from PostgreSQL.
2. Keep the Service endpoint running with `kubectl --context kind-fulfillops proxy --port=18080`. Start the probe below, then publish a harmless API pod-template annotation. Record the Git revisions, the probe window, and the Argo health transition.
3. Publish a wrong readiness path on the disposable branch. Start a second probe with a separate output file. Capture `kubectl -n fulfillops rollout status deployment/api --timeout=10s`, the pod readiness state, and pod events. Expect the rollout to stall while old replicas keep serving.
4. Revert the fault in Git and publish the revert to the disposable branch. Let Argo CD reconcile; save its final Sync and Health status. Query the same sorted order IDs and confirm the order's status and total are unchanged.

```text
python assessment/fulfillops_rollout_probe.py --base-url http://127.0.0.1:18080 --path /api/v1/namespaces/fulfillops/services/http:api:8080/proxy/health/ready --duration 30 --interval 0.25 --output local-rollout.csv
python scripts/measure-p95.py --base-url http://127.0.0.1:18080/api/v1/namespaces/fulfillops/services/http:api:8080/proxy --samples 250 --output local-p95.csv
```

Integration checks: Ruff passed; the [local verification log](evidence/part9-local-ci.txt) records 53 passing team tests and a public checker result of 15 passed, 0 failed, 0 skipped.
