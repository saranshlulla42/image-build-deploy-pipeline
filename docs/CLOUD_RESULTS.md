# Azure and GitHub validation — 25 October 2026

**The complete automatic deployment passed. The separate public update traffic experiment recorded one timeout and failed its zero-failed-request criterion.**

- Application: http://20.200.216.35
- Successful run: https://github.com/saranshlulla42/image-build-deploy-pipeline/actions/runs/40193351697
- Deployed application source: `f1b50f27a1e3d4415c1ae723ec7ed2109c09d017`.
- Published and deployed digest: `ghcr.io/saranshlulla42/image-build-deploy-pipeline@sha256:b81631e647ac2dd7d2d20d9219e7265ef24287b1374b9808104af1e528c3e925`.
- Target: `rg-image-pipeline-demo-kr` / `image-pipeline-vm`, Korea Central, Ubuntu 24.04, amd64, k3s v1.37.1+k3s1.

## Observations

| Check | Recorded result |
|---|---|
| GitHub application, release, security-policy and Azure guest-evidence tests | 47 passed |
| Compiled Bicep startup payload | Verified against actual source files; original encoding bug rejected by regression check |
| Container build and restricted smoke | Passed |
| Actual Trivy policy | Passed; 0 fixable HIGH/CRITICAL findings; 44 unfixed HIGH package findings retained |
| Temporary kind integration | All five scenarios passed in 145.695 s |
| Publish | Uploaded the exact tested amd64 artifact; no rebuild |
| GitHub-to-Azure identity | OIDC sign-in passed; no client secret or exported administrator kubeconfig |
| Automatic Azure release | `succeeded`; 27.715 s inside the guest release transaction |
| Public identity and readiness check | Verified expected commit |
| Complete GitHub workflow | Passed in 378 s from recorded start to final update |
| Cloud wrong-version experiment | `failed_rolled_back`; prior commit `0e5dca8355538796ccb409ed5b228b212a71beba` restored |
| Cloud recovery duration | 18.081 s after detected failure; excludes waiting for verification to fail |
| Traffic during wrong-version attempt and recovery | 644 requests, 0 failures over 190.603 s; expected command exit 1 observed |
| Traffic through the automatic update window | 694 requests, 1 timeout over 205.622 s; workflow exit 0; traffic check `passed=false` |
| Final server inspection | Two available pods, both running with zero restarts; nginx recorded 1,357 HTTP 200 responses and no HTTP error statuses |

The first cloud baseline was deployed by the operator through the same release command using the already-tested image for `0e5dca8355538796ccb409ed5b228b212a71beba`. A deliberate mismatch paired that image with the different real source commit `869d8575e4edef86b4b0630f66688c7ed56d6a63`; the embedded version check rejected it and rollback restored the baseline. The final app change was then deployed automatically by GitHub Actions.

The public update samples observed the old commit 478 times and the new commit 215 times. One request exceeded the client's two-second timeout. Server logs did not identify its cause, so this remains an unexplained client-observed timeout. It is retained, not replaced by a repeat chosen for a better result. A successful deployment does not establish zero downtime or a general availability guarantee.

The final scan contains 170 package findings: 44 HIGH, 63 MEDIUM, 62 LOW, and 1 UNKNOWN. The 44 HIGH occurrences are unfixed, may repeat CVEs across packages, and are permitted by the declared policy. Passing this policy does not mean vulnerability-free.

## Scope and costs

The main-branch-only `demo` GitHub environment can read and run commands on this dedicated VM. Run Command is root access on that VM. Only port 80 is publicly allowed; SSH, Kubernetes API and NodePort have no public allow rules. Two pods share one VM, and the demo uses HTTP for non-sensitive app data.

Automatic shutdown is enabled daily at **23:00 India Standard Time**, with no automatic startup. Retail estimate: about **$1.32 per full running day**, before disk operations, transfer, tax and conversion. Disk and public IP charges continue while stopped. This estimate is not a spending cap. The discarded Malaysia resource group and its custom role were removed.

The application source commit above remains the runtime identity; a later documentation/evidence commit does not rebuild or alter the running image.

## Evidence

- [Successful guest release and public check](evidence/github-azure/azure-release.json)
- [GitHub workflow metadata](evidence/github-cloud-run-summary.json)
- [CI tests](evidence/github-validation/unit-tests.xml)
- [CI scan and decision](evidence/github-validation/security-decision.json)
- [CI integration summary](evidence/github-validation/integration-summary.json)
- [Initial cloud release](evidence/azure-initial-release.json)
- [Cloud mismatch and verified rollback](evidence/azure-wrong-version-release.json)
- [Guest verification and recovery log](evidence/azure-wrong-version-guest.log)
- [Cloud rollback traffic](evidence/azure-wrong-version-traffic.json)
- [Cloud update traffic, including timeout](evidence/azure-update-traffic.json)
- [Final server inspection](evidence/azure-final-inspection.json)
- [Cloud resource inventory](evidence/azure-resource-inventory.json)
