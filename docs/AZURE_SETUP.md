# Azure student deployment

## Design

GitHub validates an amd64 image once, scans it, exercises actual Kubernetes recovery paths, and publishes that same image to public GHCR. The Azure job signs in with OIDC, then sends the release code and immutable image digest to a dedicated VM through Azure Run Command. It verifies both the guest's release report and the app's public HTTP route. A successful Azure API response alone cannot mark a failed guest release successful.

The VM runs Ubuntu 24.04, pinned k3s v1.37.1+k3s1, and nginx. Two app pods share one node. Only port 80 is publicly allowed; the Kubernetes API, SSH, and NodePort are not publicly exposed. This is a student demonstration with no sensitive traffic, no TLS endpoint, and no protection against VM failure.

On each release, a namespace-scoped Kubernetes token is minted on the VM for 30 minutes. Its temporary kubeconfig is deleted afterward. Administrator credentials stay on the VM. Azure Run Command executes as root: compromise of a trusted deployment workflow can control this dedicated VM. The custom Azure role grants only VM read and Run Command actions, assigned on this VM; it does not grant subscription Contributor.

## Provision

Inspect `infra/azure/main.bicep` and `bootstrap.sh` first. Confirm credit balance, allowed-region policy, SKU availability, and quota. The selected assessment configuration is B2als v2 in Malaysia West, with a 32 GB Standard SSD and a Standard static public IP.

Using Azure CLI and Bicep:

```bash
az login
az account show
az group create --name rg-image-pipeline-demo --location malaysiawest
# Generate and retain a local SSH key. Supply only its public half below.
# GitHub IDs can be read with: gh api repos/OWNER/REPOSITORY
az deployment group what-if --resource-group rg-image-pipeline-demo \
  --template-file infra/azure/main.bicep \
  --parameters sshPublicKey="$(cat YOUR_PUBLIC_KEY.pub)" \
    githubSubject='repo:OWNER@OWNER_ID/REPOSITORY@REPOSITORY_ID:environment:demo'
# After reviewing the preview, repeat with `az deployment group create`.
```

GitHub repositories created after July 15, 2026 use immutable subject IDs by default. Match the actual OIDC subject for your repository; older repositories may use the older subject format. The federated credential trusts the `demo` environment. Restrict that environment to `main` before enabling it.

Register Microsoft.Compute, Microsoft.Network, Microsoft.ManagedIdentity and Microsoft.DevTestLab if the subscription has not used them before. The VM's cloud-init installs packages, verifies the pinned k3s binary checksum, starts the cluster, applies `k8s/bootstrap.yaml`, configures nginx, and writes `/var/lib/image-pipeline/bootstrap-complete`. Infrastructure deployment finishing does not prove cloud-init has finished. Check `cloud-init status --wait` through Run Command, and inspect `/var/log/cloud-init-output.log` on failure.

## GitHub configuration

Make the GHCR container package public; source repository visibility does not automatically make packages public. The workflow checks anonymous download before deployment.

Create environment `demo`, permitting `main` only. Populate its variables from the Bicep deployment outputs:

| Variable | Value |
|---|---|
| `AZURE_CLIENT_ID` | `githubClientId` output |
| `AZURE_TENANT_ID` | `tenantId` output |
| `AZURE_SUBSCRIPTION_ID` | `subscriptionId` output |
| `AZURE_RESOURCE_GROUP` | `rg-image-pipeline-demo` |
| `AZURE_VM_NAME` | `image-pipeline-vm` |
| `DEMO_URL` | `publicUrl` output |

Set repository variables `DEPLOY_TARGET=azure-vm` and `PERSISTENT_DEPLOY_ENABLED=true` after bootstrap is ready. No `AZURE_CLIENT_SECRET` or `KUBECONFIG_B64` is needed for this target. Push to `main` or manually dispatch the pipeline. Retain `validation-evidence` and `azure-release-evidence` from Actions.

The job refuses superseded commits, deploys a GHCR digest, checks the version embedded during the image build, and restores the prior Deployment spec on failure. It checks nginx locally inside that transaction and public reachability independently from GitHub. A public network failure after successful guest promotion fails CI but does not itself trigger a second remote rollback. Diagnose connectivity before retrying.

The full release logs and JSON reports remain under `/var/lib/image-pipeline/releases/` on the VM. CI retains a compact report because Azure action Run Command only returns the last 4096 output bytes. Missing, duplicated, mismatched, or failed guest evidence fails CI.

## Demonstration and recovery

Show the source commit, Actions checks, registry digest, Azure release report, and public `/version` response. Commit a small app change, let the next full run deploy it, and show that the cloud URL now serves the new commit. Use the disposable kind experiment to demonstrate controlled readiness failure and automatic rollback; the release CLI forbids fault injection on the cloud context.

If a release is interrupted, inspect pod images, Deployment status, `pipeline-release-state`, and `pipeline-release-lock` before retrying. Never remove a lock until you know no release process remains active. Do not erase the verified state to bypass drift protection. Retain both the running and previous GHCR images so rollback remains possible.

## Costs, starting, stopping, and cleanup

Retail USD rates checked October 25, 2026: VM $0.0428/hour allocated; Standard IPv4 $0.005/hour retained; 32 GB E4 LRS disk $2.40/month; disk operations $0.002 per 10,000. Roughly $1.23/day continuously running, or $37.30/730-hour month, before operations, transfer, tax and conversion. This is an estimate, not a cap. Credit expiry and subscription spending limits are controlled by Azure.

Daily automatic shutdown is configured at **23:00 India Standard Time**. There is no automatic startup. Before an assessment:

```bash
az vm start --resource-group rg-image-pipeline-demo --name image-pipeline-vm
# Verify /health and /version before presenting.
```

Between sessions, release compute allocation:

```bash
az vm deallocate --resource-group rg-image-pipeline-demo --name image-pipeline-vm
```

Disk and public IP charges continue while stopped. To remove the assessment after saving evidence, first set GitHub `PERSISTENT_DEPLOY_ENABLED=false`, then delete only the dedicated `rg-image-pipeline-demo` resource group. This destroys its VM, disk, IP, network and identity. Check for a retained custom role definition afterward. Do not delete resources needed for an upcoming assessment.

## References

- [Azure action Run Command: limits and access](https://learn.microsoft.com/en-us/azure/virtual-machines/linux/run-command)
- [Official Azure login GitHub action](https://github.com/Azure/login)
- [GitHub OIDC reference and immutable subjects](https://docs.github.com/en/actions/reference/security/oidc)
- [Azure public retail pricing API](https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices)
- [k3s installation requirements](https://docs.k3s.io/installation/requirements)
