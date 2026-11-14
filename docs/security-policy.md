# Container vulnerability and publishing policy

The Part 7 workflow tests, builds, and scans the API and worker images. Trivy checks operating system and language packages in both images.

- **Blocking:** a HIGH or CRITICAL vulnerability with an available fix. A scanner failure also prevents publication.
- **Informational:** the all-severity report includes lower-severity and unfixed findings. Review these and track a fix when one becomes available.
- **Artifacts:** each image produces a CycloneDX SBOM and a vulnerability report bundle. The report upload also runs when the blocking scan fails so the finding can be reviewed.

The PR workflow does not publish. On a push to main, the publish job uses the same images that passed the checker and scans in that run. It publishes each image to GHCR with the commit SHA tag and lists the registry digest in the job summary. Use the digest when referring to the exact released image. The publish job is the only job granted package write permission.

See [Trivy's action documentation](https://github.com/aquasecurity/trivy-action/tree/v0.36.0) and [GitHub's container registry documentation](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).
