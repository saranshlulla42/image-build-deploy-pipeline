# Connect a persistent cloud target

## Current status

No cloud account or cluster has been supplied. No billable resources have been created, and no cloud deployment has been verified. Leave `PERSISTENT_DEPLOY_ENABLED` unset until the following prerequisites work.

The existing stack can be retained: GHCR for images and an existing persistent Kubernetes cluster for runtime. You do not need to replace it with ECR.

## Choose and prepare a target

1. Obtain a cloud/student account and confirm credits and billing.
2. Provision a persistent Kubernetes environment appropriate to the course. A dedicated single VM running Kubernetes is a lower-complexity demo choice; managed clusters can carry additional fees. A single node is not highly available.
3. This workflow produces Linux amd64 images. Use amd64 nodes. It pins kubectl 1.37.1; choose a compatible supported server version or adjust the pin according to the documented Kubernetes version-skew policy.
4. Provide authenticated, TLS-verified API access from the deployment runner. GitHub-hosted runners need network reachability. For a private API, use a suitably secured runner in that network and change only the deployment job's runner labels.
5. Expose the demo Service appropriately. The supplied NodePort is 30080. Limit inbound access to the audience/network needed for the demo; add HTTPS before handling sensitive content.
6. Keep the application namespace dedicated to this project. Deploying workloads is a powerful permission even within a namespace; do not share it with unrelated secrets or services.

## Bootstrap permissions

Using an administrator identity on the intended cluster:

```bash
kubectl --context YOUR_CLOUD_ADMIN_CONTEXT apply -f k8s/bootstrap.yaml
```

This creates `image-pipeline`, a release ServiceAccount and namespace-scoped permissions. The release role does not grant cluster administration, reading secrets, pod exec or namespace creation.

Construct a kubeconfig using your provider's supported authentication approach, referencing the intended server and its trusted CA. Do not disable TLS verification. For a short assessment demonstration, a short-lived ServiceAccount token can be used:

```bash
kubectl --context YOUR_CLOUD_ADMIN_CONTEXT -n image-pipeline \
  create token pipeline-deployer --duration=1h
```

Keep the token private and place it only in the release kubeconfig. Providers may limit the requested lifetime. Expired tokens must be renewed; do not present this manual token setup as permanent unattended credential management. A later provider-specific improvement should exchange GitHub OIDC for short-lived cloud/cluster credentials automatically.

Verify permissions with the release kubeconfig before adding it to GitHub:

```bash
kubectl --kubeconfig YOUR_RELEASE_KUBECONFIG --context YOUR_RELEASE_CONTEXT \
  -n image-pipeline auth can-i patch deployments
kubectl --kubeconfig YOUR_RELEASE_KUBECONFIG --context YOUR_RELEASE_CONTEXT \
  -n image-pipeline get deployments
```

The config must work noninteractively on a Linux runner. If it uses an exec authentication plugin, that plugin must be explicitly installed in the workflow. Never copy a general cluster-admin kubeconfig into GitHub.

## Configure GitHub

Create the `demo` GitHub environment and restrict allowed deployment branches to `main`. Enable required reviewers if available and appropriate for your repository plan.

- Environment secret `KUBECONFIG_B64`: base64 of the dedicated release kubeconfig, with no line wrapping.
- Environment variable `KUBE_CONTEXT`: its exact context name.
- Repository variable `PERSISTENT_DEPLOY_ENABLED`: `true`, only after setup is complete.

Base64 is an encoding, not encryption. Store the encoded value in Secrets, never in source code, screenshots, shell history committed to Git, or public logs. The workflow writes it to a temporary file with restricted permissions and removes it afterward.

GHCR packages are not automatically public just because the source repository is public. Change the package visibility explicitly to public for this workflow. The cloud job checks anonymous access before deploying, so pods can restart after the publishing job token expires. Private-image deployments need a separately managed, scoped registry credential and imagePullSecret; do not use an expiring job token as permanent node credentials.

## Validate the actual cloud release

Merge a small app change and verify:

1. Application tests, image smoke test, scan and kind experiments passed.
2. Publishing reused the tested artifact and recorded a registry digest.
3. The persistent job ran, rather than being skipped.
4. Its report says `succeeded` with the expected digest and source commit.
5. The cloud URL serves that version after the GitHub job finishes.
6. A subsequent release updates the same environment.
7. A controlled failure restores and verifies the previous release.

Fault injection in the supplied demo CLI is deliberately restricted to local kind/minikube contexts. Exercise cloud recovery in an isolated assessment namespace using a reviewed failing artifact and suitable permissions, rather than weakening production guardrails.

## Interrupted releases and recovery

Deployment commands use a ConfigMap named `pipeline-release-lock`. If a runner is killed, inspect deployment status, pod images, the recorded verified state and the latest run before removing a stale lock. First confirm no other deployment process is active.

```bash
kubectl --context YOUR_RELEASE_CONTEXT -n image-pipeline get configmap pipeline-release-lock -o yaml
kubectl --context YOUR_RELEASE_CONTEXT -n image-pipeline get deployment app-deployment -o yaml
kubectl --context YOUR_RELEASE_CONTEXT -n image-pipeline get configmap pipeline-release-state -o yaml
```

Only after that inspection, an operator may delete the stale lock and run a verified release again. If configuration drift prevents preflight, investigate it; do not delete the verified record to bypass the guard.

Retain the running and previous images in GHCR. Deleting a rollback image can prevent recovery on a new node.

## Costs and teardown

Record provider, region, VM/cluster runtime, disks, public IPs, transfer, registry and log costs. A budget alert is not a spending cap.

Destroy the resources you created after the assessment, including disks/IPs that remain after a VM stops. Do not run generic destructive cluster commands against an unspecified context. Retain reports/screenshots first. Removing only the demo namespace does not stop cloud infrastructure billing.
