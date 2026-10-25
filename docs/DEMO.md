# Assessment demonstration

## Before presenting

Run the tests and local demo, inspect the generated JSON reports, and retain a screen recording. Explain whether the environment is local kind or an actual persistent cloud cluster. Never describe localhost as a deployed cloud service.

## Suggested sequence

1. Explain: source -> tests -> image -> scan -> registry -> deployment -> verification/recovery.
2. Show the app's embedded source commit at `/version`.
3. Show application tests and the scan decision, including any unfixed findings.
4. Run a rolling update and show the full-command traffic report.
5. Run the deliberately unhealthy candidate. Show the release exiting 1, the report `failed_rolled_back`, and the previous version still serving.
6. Show wrong-version rejection and first-release failure handling.
7. Explain the successful local experiments, their sample sizes, and limitations.
8. If cloud access has been configured, show the cloud URL still responding after the Actions job has ended.

## Questions to prepare for

- Why does a SHA-shaped tag still differ from an image digest?
- Why is readiness different from liveness?
- Why does Kubernetes rollout failure not itself perform rollback?
- Why is a temporary kind job an integration test?
- How do we prevent concurrent deployments?
- What is restored by rollback, and what is outside its scope?
- Which scan findings block a release?
- What have you actually measured, and what remains unverified?

A measured run with zero failed samples is useful evidence. It is not proof that every future request, network failure or node failure will have zero downtime.
