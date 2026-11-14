# FulfillOps Part 5 report text

## Section 3 Concurrency and idempotency

On 14 November 2026, we ran two API instances on ports 8080 and 8081 against the same isolated PostgreSQL database. Eight simultaneous requests used the same idempotency key, with four requests sent to each instance. All eight returned HTTP 202 and order ID `111647ed-27b7-40e8-bbd4-dbd901d98ea4`. The first reservation reduced `KIT-100` stock from seven to six. Replaying the request on port 8081 after the reported restart returned the same order ID and left stock at six. The saved output shows the restart prompt and successful replay; it does not include the API process stop and startup logs.

We then sent twelve simultaneous requests with distinct keys. Six were accepted and six returned `409 OUT_OF_STOCK`. The final inventory query showed zero `KIT-100` units. The idempotency query showed seven rows: one for the shared key and six for the accepted distinct keys.

Evidence: [timestamped responses and SQL output](evidence/part5-api-replicas.txt). Reproduction: [replica drill script](../scripts/drill-cross-replica-idempotency.py).

## Section 4 Durable worker and failure handling

**Worker recovery.** In the scripted run, `part5-slow` claimed order `460d36b5-40c5-4881-8c79-e02b842fa766` on attempt one. We confirmed that `part5-recovery` was running before killing `part5-slow`. After the lease expired, `part5-recovery` claimed the same job on attempt two and completed it. SQL showed the order and job both `completed`, and the recovery worker's Prometheus counter recorded one completion. `PACK-300` dropped from five to four, consistent with exactly one reservation. See the [scripted crash log](evidence/part5-worker-crash-scripted.txt).

**Poison job.** With test mode enabled, worker `part5-poison` began processing order `83ce0d21-fcff-4420-a1fd-56b4c9bd8448` at 03:49:05 UTC on 14 November 2026. Its fifth attempt failed at 03:49:25 UTC. Two SQL checks showed the order `failed`, the job `dead`, five of five attempts used, and `poison job (test mode)` as the last error. `PACK-300` stayed at four, compared with five in the earlier replica-drill inventory output. The observed result is consistent with retaining the reserved unit for manual reconciliation.

The [scripted poison run](evidence/part5-poison-job-scripted.txt) reproduced the same result on a new database. Prometheus exposed `fulfillops_worker_retries_total 4.0`: the first attempt plus four retries consumed the five-attempt budget. The second SQL check confirmed no additional attempts and no restock. The rehearsal [worker log](evidence/part5-poison-job.txt) and [SQL checks](evidence/part5-poison-job-db.txt) are also available.

## Section 9 Incident 1 Worker interruption

On 14 November 2026 at 03:58:18.858 UTC, we confirmed that `part5-slow` held the job on attempt one and forcibly stopped the process. The recovery worker was already running. The job was reclaimed at 03:58:38.356 UTC after the 20-second lease expired, and it completed at 03:58:38.613 UTC. The customer order remained in PostgreSQL during recovery. The final database row and the recovery worker's completion metric show one completion without another stock reservation. See the [timestamped handoff](evidence/part5-worker-crash-scripted.txt).

## Reproduce the worker drills

From the repository root in the activated Python environment, with Docker running:

```powershell
python scripts/drill-worker.py crash
python scripts/drill-worker.py poison
```

Each run starts a fresh, isolated PostgreSQL 16 container, migrates and seeds it, starts the API and the required workers, and cleans up its own resources on exit. The script verifies the worker log sequence, final SQL state, stock, and a worker metric. It prints UTC timestamps and exits nonzero if a check fails.
