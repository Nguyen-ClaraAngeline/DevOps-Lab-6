# Incident postmortem (blameless)

## Summary
Four problems surfaced while bringing the stack up and running the Part 9 drills. Two were unplanned (API image crash loop, worker state mismatch), one was an intentional fault (broken readiness path, Incident 2), and one is the planned worker-crash drill (Incident 1). No committed order was lost in any of them.

## Incident 1 - worker killed during processing (planned drill)
[Fill from the Part 5 evidence: UTC injection time, detection, recovery, order completed once, evidence in docs/evidence/.]

## Incident 2 - faulty API release (planned drill)
- Fault: readiness probe path changed to /health/readyy (commit 4c480f5, [UTC time]).
- Detection: new pod stayed 0/1 for about 8 minutes, kubelet events showed "Readiness probe failed: HTTP probe failed with statuscode: 404", `rollout status` timed out, Argo CD showed Progressing.
- Impact: none for users. maxUnavailable 0 kept the two old pods serving; probe during the stall: [failures=0 / see docs/rollout_failure_probe.csv].
- Recovery: `git revert` (commit 6f08a27, [UTC time]) pushed and synced by Argo CD. No manual kubectl patch left in place.
- Result: 2 API pods Ready, Argo Synced and Healthy on 6f08a27. Order counts identical before and after (5 completed, 6 failed).
- Rollback vs fix-forward: rollback was chosen because the change was configuration-only, the previous revision was known good, and no schema or data changed. Fix-forward is preferable when a migration has already been applied that the old version cannot run against.

## Unplanned incident A - API crash loop (image v1)
- Timeline: [UTC] pods api-86554c4c76 in CrashLoopBackOff; liveness and readiness returned 500.
- Root cause: metrics.py in the image was empty, so the request middleware raised AttributeError (no attribute http_requests) on every request.
- Fix: metrics defined in the source, image rebuilt as v2, deployed through Git (commits 0ba72bf and 0829d99).
- Prevention: a CI step that starts the container and calls /health/live before publishing the image.

## Unplanned incident B - Argo CD sync blocked
- Root cause: the migrate Job used sync option Replace=true; Kubernetes rejected the replacement ("field is immutable"), so the sync failed before the API wave and the cluster stayed on v1.
- Fix: the Job became an Argo Sync hook with hook-delete-policy BeforeHookCreation.
- Prevention: use hooks for one-shot Jobs; check `argocd` sync errors after every change.

## Unplanned incident C - worker wrote an invalid job state (dead-letter evidence)
- Timeline: [UTC] first order claimed; five attempts failed; job became dead; order failed.
- Root cause: worker code wrote state 'done' but the jobs_state_check constraint allows queued, processing, completed, dead.
- Behaviour that worked as designed: bounded retries (5 attempts, no infinite loop), dead-letter state kept, order marked failed, reserved stock kept for manual reconciliation (no automatic restock).
- Fix: the worker now writes 'completed' (worker image v2).
- Prevention: an integration test that completes one job end to end in CI.
- Evidence: docs/evidence/dead_jobs_before_fix.txt.

## Unplanned incident D - empty product table
- Root cause: migration 002_seed_products.sql was empty yet recorded as applied.
- Fix: the three products were inserted manually (ON CONFLICT DO NOTHING); a permanent seed migration is still to be committed.
- Prevention: add a migration test asserting the seed rows exist.

## What went well
- Rolling update with maxUnavailable 0 kept the service up through the broken revision.
- Bounded retries and the dead-letter state behaved as specified.
- GitOps revert restored the known-good state without manual cluster edits.

## What we would improve
- Test the container start-up in CI before publishing an image.
- Add a reproducible reset script and seed migration.
- Replace port-forward based probing with an in-cluster probe.
