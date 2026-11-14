# Part 7: CI and supply-chain verification

| Requirement | Verification |
| --- | --- |
| Pull requests to main run lint, tests, and Docker build with a fresh Compose checker | Configured in the workflow. Locally: Ruff passed, 53 team tests passed, and the checker passed 15/0/0 with concurrency and stress. |
| Blocking scan and documented policy | Trivy checks both images; the policy explains which findings block publication. The reports are retained as artifacts. |
| CycloneDX SBOM | One required artifact per image: sbom-api and sbom-worker. Missing SBOM files fail the job. |
| Publish gated by all checks | Only a push to main can publish. Publication requires lint, tests, the checker/build, and both image scans to pass. The summary records each commit-SHA tag and digest. |
| Reviewed action versions and least privilege | Versioned actions, read access by default, and package write access only for publish. Checkout does not persist its credential. |
| Hosted red-to-green evidence | Earlier failed run verified. The corrected PR run and main publication still need to be captured. |

[Hosted red run](https://github.com/Nguyen-ClaraAngeline/DevOps-Lab-6/actions/runs/43554816017): the checker reported 6 passed, 5 failed, 4 skipped because the fresh database had no catalog rows; scan and publish were skipped. Migration 004 seeds all three products without resetting existing stock. The [local verification log](evidence/part7-local-ci.txt) shows the corrected stack without a manual seed.

After pushing the fix, open or update the PR to main and record the green run and both SBOMs and scan reports. After the reviewed PR merges, record the successful main run and both GHCR digests from its summary. If the assessor requires a deliberately injected red run, use a disposable PR, revert the fault before merging, and keep both run links. Check the repository's required status checks if it must prevent merging a red PR.

Local supply-chain smoke check: Trivy 0.70.0 returned 0 for both images with the blocking policy (fixable HIGH/CRITICAL). It generated valid CycloneDX 1.6 JSON for the API (132 components) and worker (112 components). These were local results; hosted artifact upload and GHCR publication were not exercised.
