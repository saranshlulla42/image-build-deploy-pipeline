# Validation results

The earlier unlabelled benchmark numbers have been removed because they could not be tied to reproducible evidence.

Implementation validation is in progress. This file will be updated from actual local test artifacts. No persistent cloud deployment has been performed: the project owner currently has no cloud account.

| Check | Current evidence |
|---|---|
| Application, release failure paths, traffic and scan policy | 28 local tests passed on 25 October 2026 |
| Container build and smoke test | Pending |
| Kubernetes rolling update and recovery | Pending |
| Actual image vulnerability scan | Pending |
| Persistent cloud deployment | Not configured |

The local test suite covers deliberately simulated failure paths. Real cluster experiments and actual vulnerability reports are separate evidence categories. No result should be described as a universal availability guarantee.
