# Incident postmortem (blameless)

## Summary

Two controlled drills checked recovery when a worker dies and when a release never becomes ready. The order was preserved in the worker drill. The first rollout rehearsal compared order counts; the integrated rerun records the individual order IDs.

## Incident 1: worker killed during processing

- **Injection (14 November, 03:58:18.858 UTC):** we killed the worker holding the job on attempt one. The second worker was already running.
- **Detection and recovery:** the job stayed in PostgreSQL until its 20-second lease expired. The second worker reclaimed it at 03:58:38.356 UTC and completed it at 03:58:38.613 UTC on attempt two.
- **Impact:** completion was delayed about 20 seconds. The recovery worker recorded one completion and stock moved from five to four, consistent with one reservation.
- **Prevention:** keep lease-expiry and ownership checks covered by the [crash drill](evidence/part5-worker-crash-scripted.txt). Alert on jobs stuck beyond their expected lease plus retry window.

## Incident 2: faulty API release

- **Fault:** the original rehearsal changed the readiness path to /health/readyy in 4c480f5 (13 November, 08:34:47 UTC, commit time).
- **Detection:** the replacement pod remained unready and kubelet reported HTTP 404 on the probe. The rollout timed out. The two old pods stayed Ready with maxUnavailable set to zero; the [stall probe](rollout_failure_probe.csv) recorded no failures during the sampled interval.
- **Recovery:** 6f08a27 reverted the fault (08:51:40 UTC, commit time). Argo CD reconciled the known-good Git state. The first rehearsal recorded identical counts before and after (five completed, six failed); that comparison alone cannot prove order identity.
- **Why rollback:** the fault was limited to readiness configuration and the previous version was compatible with the existing database. Consider fix-forward if an irreversible migration has made the old application incompatible.
- **Prevention:** keep readiness probes on the real route and require a successful readiness check during rollout. A successful sync alone is insufficient; a deployment must also become Healthy.

In the [integrated reenactment](evidence/part9-integrated-rollout.txt), revision 29a34b0 again stalled with a readiness 404 and two old Ready pods. All 121 probe requests succeeded during the stall. We published revert e7dfae3 at 06:25:22 UTC; Argo CD returned to Synced and Healthy at 06:25:31 UTC. Both committed order IDs were identical before and after; the completed order retained its status and total.

## Unplanned incident A - API crash loop (image v1)
- Observation: pods api-86554c4c76 in CrashLoopBackOff; liveness and readiness returned 500.
- Root cause: metrics.py in the image was empty, so the request middleware raised AttributeError (no attribute http_requests) on every request.
- Fix: metrics defined in the source, image rebuilt as v2, deployed through Git (commits 0ba72bf and 0829d99).
- Prevention: a CI step that starts the container and calls /health/live before publishing the image.

## Unplanned incident B - Argo CD sync blocked
- Root cause: the migrate Job used sync option Replace=true; Kubernetes rejected the replacement ("field is immutable"), so the sync failed before the API wave and the cluster stayed on v1.
- Fix: the Job became an Argo Sync hook with hook-delete-policy BeforeHookCreation.
- Prevention: use hooks for one-shot Jobs; check `argocd` sync errors after every change.

## Unplanned incident C - worker wrote an invalid job state (dead-letter evidence)
- Observation: first order claimed; five attempts failed; job became dead; order failed.
- Root cause: worker code wrote state 'done' but the jobs_state_check constraint allows queued, processing, completed, dead.
- Behaviour that worked as designed: bounded retries (5 attempts, no infinite loop), dead-letter state kept, order marked failed, reserved stock kept for manual reconciliation (no automatic restock).
- Fix: the worker now writes 'completed' (worker image v2).
- Prevention: an integration test that completes one job end to end in CI.
- Evidence: docs/evidence/dead_jobs_before_fix.txt.

## Unplanned incident D - empty product table
- Root cause: migration 002_seed_products.sql was empty yet recorded as applied.
- Fix: migration 004 now adds the missing catalog without overwriting stock.
- Prevention: add a migration test asserting the seed rows exist.

## What went well
- Rolling update with maxUnavailable 0 kept the service up through the broken revision.
- Bounded retries and the dead-letter state behaved as specified.
- GitOps revert restored the known-good state without manual cluster edits.

## What we would improve
- Test the container start-up in CI before publishing an image.
- Keep the seed in migrations and run the checker against a fresh database.
- Replace port-forward based probing with an in-cluster probe.
