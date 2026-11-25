# Container supply chain

Container assurance checks the complete fetched Git history with Gitleaks using redacted output. It builds the same two images used by Compose, validates their default non-root users, produces CycloneDX SBOMs, and reports every high or critical Trivy finding. An available fix at either severity fails the gate. The core workflow continues to audit Python and Node dependencies. Temporary reports stay on the runner.

Run the same image checks from the repository root on a disposable Linux runner with Docker, BuildKit, Git, curl, and jq.

```bash
bash scripts/container-assurance.sh
```

The workflow uses standard GitHub-hosted runners for the public repository. The release lane accepts a published stable semantic-version release whose target is reachable from `main`. An explicit workflow dispatch on `main` can validate the same publication and attestation path with immutable `candidate-<commit-sha>` image tags before adding a release tag. It scans the actual images before pushing, rejects existing release tags, and records the content digests. GitHub attestations bind provenance and SBOMs to those digests. Review the gate output and use digest references for deployment.

The Product Owner must explicitly accept material residual risks for the exact proposed image digests before publishing a stable release. Review individual CVEs, affected runtime components and upstream fixes in the [security risk register](security-risk-register.md).

GHCR currently provides free container image storage and bandwidth. The first push creates a private package by default. In each package's settings, verify linkage to this public repository and choose public visibility before including anonymous pulls in acceptance. Check the policy again before each publication. [GitHub Packages billing](https://docs.github.com/en/billing/concepts/product-billing/github-packages) · [GHCR visibility](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry) · [GitHub artifact attestations](https://docs.github.com/en/actions/concepts/security/artifact-attestations)
