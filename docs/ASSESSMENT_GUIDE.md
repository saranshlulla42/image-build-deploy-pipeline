# Demonstrate the complete project

## Before class

1. Sign into Azure, open resource group `rg-image-pipeline-demo-kr`, select `image-pipeline-vm`, and click **Start** if it is stopped. Allow a few minutes for Kubernetes and the app to recover.
2. Open [the public application](http://20.200.216.35), [readiness](http://20.200.216.35/health), and [deployed version](http://20.200.216.35/version). Readiness should say `healthy`.
3. Open [GitHub Actions](https://github.com/saranshlulla42/image-build-deploy-pipeline/actions). Keep the latest successful full run and its downloadable evidence ready.
4. Keep the saved evidence available in case the classroom network is unreliable. The local kind demonstration is an additional fallback, not the Azure service.

## Suggested presentation: 8–10 minutes, plus pipeline waiting time

**Explain the purpose.** “A code change automatically becomes a tested container image. The pipeline scans it, publishes the exact tested image, deploys it to Azure, checks the running version, and restores the previous release if verification fails.” Here, image means a Docker container image.

**Show the live Azure application.** Open `/version` and identify its full source commit. Show the VM in Azure and the two Kubernetes app replicas in the retained deployment evidence. Explain that two pods on one VM protect rolling updates, not VM failure.

**Show the pipeline.** Walk through application/failure tests, infrastructure startup validation, Docker build, restricted-container smoke test, vulnerability policy, actual kind experiments, publishing, and Azure deployment. The build happens once; the publishing job transfers and uploads the tested artifact instead of rebuilding it.

**Trigger a real change.** In the GitHub repository, open `app/app.py`, edit only the greeting in `message=`, and commit to `main`. Follow the new Actions run. It must complete all checks and the “Deploy and verify on Azure” job. Refresh the public app and `/version`: the greeting should change and the reported commit must match the run. Allow several minutes for the complete pipeline.

**Show recovery evidence.** The validation artifact contains an unhealthy-readiness experiment, wrong-version rejection, and a failed first deployment. Show `failed_rolled_back` with the restored version. A failed attempted release returns failure even if rollback succeeds. The project also records an actual Azure image/version mismatch test and public traffic sampling; distinguish those results from the local kind tests. Use the supplied local failure demonstration if the evaluator wants a live readiness fault.

**Explain security and limits.** Public GHCR images need no stored registry password. GitHub uses a short-lived Azure sign-in token; Azure permissions apply only to this dedicated VM. Kubernetes administrator credentials stay on the VM. The scan policy blocks fixable HIGH/CRITICAL vulnerabilities and reports unfixed ones. This student demo has one VM and public HTTP; it is not a highly available production service.

## Files to show

- `docs/AZURE_SETUP.md`: cloud architecture, identity, costs, startup and teardown.
- `infra/azure/main.bicep`: infrastructure as code.
- `.github/workflows/pipeline.yml`: complete automation.
- `scripts/release.py`: verification, release lock and rollback.
- `docs/RESULTS.md` and `docs/evidence/`: measured outcomes.
- Actions artifacts `validation-evidence` and `azure-release-evidence`: evidence from the actual run.

## Prepare these answers

- A **commit** identifies source code; an **image digest** identifies the actual published container bytes.
- **CI** checks and builds a candidate; **CD** publishes and deploys a verified candidate.
- **Readiness** controls whether a pod receives traffic; **liveness** controls restarting an unhealthy process.
- Kubernetes reports rollout failure; the release script explicitly restores and verifies the previous Deployment spec.
- A ConfigMap lock prevents overlapping releases. An interrupted release may require operator inspection of the lock and verified state.
- The rollback covers the Deployment spec. It does not undo network/IAM changes or database migrations.
- Credit balance, a budget estimate, and an automatic shutdown are not hard spending caps.

## After class

Use Azure's **Stop** action and confirm the VM is **Stopped (deallocated)** to release compute allocation. Disks and the public IP still incur charges. Automatic shutdown is configured for **11 p.m. India Standard Time daily**, with no automatic startup. Start and check the app again before every demonstration. Delete the dedicated resource group only when the assessment is finished and evidence is saved.

Credit the [starter repository](https://github.com/2023ninadhatwalne-lab/image-build-deploy-pipeline) and disclose coding-agent assistance according to your course rules.
