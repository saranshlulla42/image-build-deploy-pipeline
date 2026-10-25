# Recorded validation results

Local validation: **Passed**. Generated 2026-10-25T10:41:37.059719+00:00.

Environment: macOS arm64 Docker host, Linux arm64 application container, one local kind node. Application runtime: Python 3.12. Unit tests were run with the local Python interpreter; see the JUnit report.

| Check | Observed result |
|---|---|
| Application, release, scan-policy and traffic tests | 47 tests; 0 failures; 0 errors (latest unit suite; earlier local integration measurements retained below) |
| Initial verified release | succeeded; 8.596 s |
| Rolling update | succeeded; 16.782 s |
| Rolling-update traffic | 175 requests; 0 failures; 17.935 s; 9.76 req/s |
| Unhealthy candidate | failed_rolled_back |
| Unhealthy candidate recovery | 3.362 s from detected failure to verified restoration |
| Traffic during failed release/recovery | 322 requests; 0 failures; 32.945 s |
| Wrong expected source version | failed_rolled_back; recovery 15.09 s |
| First release failure | failed_first_deployment |
| Promotion between real source revisions | succeeded; 17.108 s; 179 requests; 0 failures |
| Cached-layer build observation | 2.307 s; not a cold-build benchmark |
| Image size | 213129866 bytes (203.26 MiB reported by Docker) |
| Actual vulnerability scan | 170 package findings: HIGH=44, LOW=62, MEDIUM=63, UNKNOWN=1 |
| Security policy | 0 fixable HIGH/CRITICAL blocked findings; 44 unfixed HIGH/CRITICAL package findings retained |
| Persistent cloud deployment | Azure account connected; replacement region deployment awaiting approval |
| Updated GitHub workflow execution | Remote runs 40189592572 and 40190881842 passed; Azure deployment job remained gated |
| GHCR publishing of updated code | Tested amd64 images published to public GHCR by GitHub Actions |

Five-scenario integration artifact source: `27c19b837e93cd5d9c44dc83a5af48d0e7ba39a6`. Latest built artifact source: `b2a0fbdee683813bfded6626cde0fb333933fa2d`.

Observed source revisions during the final promotion:

- `27c19b837e93cd5d9c44dc83a5af48d0e7ba39a6`: 96 requests
- `b2a0fbdee683813bfded6626cde0fb333933fa2d`: 83 requests

## Interpretation

These are single local experiment runs, not statistical availability guarantees. The first rolling-update test uses two tags for one artifact to isolate rollout mechanics. The final promotion, when recorded above, uses two real Git revisions and separately built artifacts. Traffic uses NodePort routing throughout the command, including verification/recovery and a final observation interval.

Recovery time starts after failure detection; it excludes the time spent waiting for rollout/verification failure. Failed release reports deliberately record nonzero command results even when recovery succeeds.

Security policy permits unfixed HIGH/CRITICAL findings while reporting them. The image is not vulnerability-free; findings are package-level occurrences and can repeat the same vulnerability across packages. No intentionally vulnerable image was deployed to demonstrate the policy. Fixture tests simulate rejection separately.

No cold/warm-cache comparison, cloud uptime measurement, provider bill, is claimed. Two remote Actions runs passed validation and publishing. Earlier inconsistent benchmark figures have been replaced by these retained measurements.

## Retained evidence

- [container-build.json](evidence/container-build.json)
- [container-smoke.log](evidence/container-smoke.log)
- [failed-release.json](evidence/failed-release.json)
- [failure-traffic.json](evidence/failure-traffic.json)
- [first-release-failure.json](evidence/first-release-failure.json)
- [initial-release.json](evidence/initial-release.json)
- [integration-summary.json](evidence/integration-summary.json)
- [integration.log](evidence/integration.log)
- [security-decision.json](evidence/security-decision.json)
- [source-change-release.json](evidence/source-change-release.json)
- [source-change-traffic.json](evidence/source-change-traffic.json)
- [trivy-full.json](evidence/trivy-full.json)
- [unit-tests.xml](evidence/unit-tests.xml)
- [update-release.json](evidence/update-release.json)
- [update-traffic.json](evidence/update-traffic.json)
- [wrong-version-release.json](evidence/wrong-version-release.json)
