# Toolchain and release checks

Checked **October 4, 2026**. The kit pins the versions below so the same exercise can be repeated. “Latest” means the newest release in the selected supported channel on that date, not a promise that a saved ZIP will keep updating. [toolchain.json](../toolchain.json) is the machine-readable record used by the web app.

| Component | Selected version | Release decision and source |
| --- | --- | --- |
| Terraform CLI | 1.16.5 | Latest stable in the [HashiCorp release index](https://releases.hashicorp.com/terraform/); 1.17 entries were prereleases. |
| HashiCorp AWS provider | 6.67.0 | Latest stable [registry release](https://registry.terraform.io/providers/hashicorp/aws/6.67.0); already current, with locks refreshed against the current constraints. |
| HashiCorp Kubernetes provider | 3.3.0 | Latest [official registry release](https://registry.terraform.io/providers/hashicorp/kubernetes/3.3.0), published October 1, 2026; signed provider install, module/template validation and mocked workload plans passed. |
| HashiCorp archive provider | 2.8.1 | Latest stable [registry release](https://registry.terraform.io/providers/hashicorp/archive/2.8.1). |
| AWS CLI v2 | 2.37.9 | Latest release in the [official changelog](https://raw.githubusercontent.com/aws/aws-cli/v2/CHANGELOG.rst); used by the pinned installer and Pod Identity image. |
| Amazon EKS | 1.36 | Latest EKS minor in [standard support](https://docs.aws.amazon.com/eks/latest/userguide/kubernetes-versions.html); standard support ends August 2, 2027. |
| kubectl | 1.36.5 | Latest patch in the [matching 1.36 release channel](https://dl.k8s.io/release/stable-1.36.txt). |
| jq | 1.8.2 | Latest [official jq release](https://github.com/jqlang/jq/releases/tag/jq-1.8.2); installed project-locally for JSON commands. |
| kubeconform | 0.8.0 | Latest [upstream release](https://github.com/yannh/kubeconform/releases/tag/v0.8.0); validation targets Kubernetes 1.36.0 schemas. |
| Lambda Python runtime | python3.14 | Latest generally available Python runtime in the [Lambda runtime table](https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html). Python 3.15 was preview and is excluded. |
| Python incident container | 3.14.8-alpine | Latest stable Python image listed in the [Docker Official Images manifest](https://github.com/docker-library/official-images/blob/master/library/python). |
| NGINX container | 1.30.5-alpine | Latest [NGINX stable release](https://nginx.org/en/download.html); mainline 1.31.6 is a separate channel. |
| Alpine helper container | 3.24.2 | Latest stable [Alpine release](https://alpinelinux.org/releases/), supplying the shell, wget, and file utilities used by labs 08, 10, and 12. |
| DOMPurify browser sanitizer | 3.4.16 | Latest [official release](https://github.com/cure53/DOMPurify/releases/tag/3.4.16); vendored locally and used in browser rendering/sanitizer checks. |
| Marked browser parser | 18.0.14 | Latest [official release](https://github.com/markedjs/marked/releases/tag/v18.0.14); npm distribution integrity verified, `marked.parse` API and existing code-block output checked locally. |

Upstream Kubernetes was **1.37.1**, as reported by its [stable channel](https://dl.k8s.io/release/stable.txt). EKS 1.36 is the AWS-supported target. Copying the upstream latest minor directly into the EKS configuration would skip AWS availability and add-on compatibility checks. The client matches the EKS minor and obeys the [kubectl version-skew policy](https://kubernetes.io/releases/version-skew-policy/).

Standalone BusyBox 1.38.0 is newer than the old helper image but is labeled unstable by [its maintainers](https://busybox.net/). The latest explicitly stable standalone BusyBox release is 1.36.1 from 2023. The helpers therefore use the current stable Alpine distribution and its maintained BusyBox package instead of switching to the unstable standalone image or reverting to an old one.

The web app needs Python 3.10 or newer and only uses the standard library. Its minimum supported runtime is separate from the newest Python release; no system Python upgrade is necessary to run the UI. Host Python 3.12.3 and Node 22.16.0 were pre-existing development/test tools, not newly installed release pins. Node is not required to run the delivered app. Lambda's selected runtime is managed by AWS. Local unit tests do not emulate that managed runtime or its included SDK.

## What passed locally

The project-local bootstrap installed AWS CLI 2.37.9 after verifying its AWS GPG signature and jq 1.8.2 after verifying its official SHA-256 checksum. `arcade doctor` passed in a fresh Bash login from `/tmp`. A read-only STS identity check confirmed local authentication; it did not exercise resource permissions.

The Terraform 1.16.5, kubectl 1.36.5, and kubeconform 0.8.0 downloads matched their publishers’ SHA-256 checksums. All **11 complete Terraform solution roots** passed `init -backend=false -input=false -upgrade` and `validate` in scratch copies, then their updated provider locks were copied back. Terraform contract tests passed **3/3**. Lambda handler unit tests passed **3/3** on host Python 3.12.3. All **94 resources in 23 YAML files** passed strict Kubernetes 1.36 schema validation. A subsequent AWS-backed Game 05 plan passed with 5 creates, 0 changes and 0 destroys; no cloud apply has run.

The subsequent expansion passed **8/8 local Terraform contracts**, **39 mocked workload tests**, and strict checks for **117 resources in 30 lab YAML files**. Game 13 adds a validated AWS access-rule root and the portable Kubernetes root. The original counts above describe the earlier baseline.

The reusable Kubernetes workload module decodes multi-document YAML while preserving block-scalar content and has its own pinned lock. Its tests use mocked Kubernetes resources: they verify manifest ownership and planned immutable-resource replacements without contacting a cluster. A real workload plan still requires a reachable EKS API; see [Terraform workload workflow](terraform-workloads.md).

## Before you create a cluster

Run the version/support check in [setup](setup.md). It queries your selected region and stops if EKS 1.36 is absent or outside `STANDARD_SUPPORT`. The Terraform cluster keeps `upgrade_policy.support_type = "STANDARD"` to avoid opting into paid extended support. This setting does not delete a cluster or stop ordinary cluster charges; the teardown checklist still applies.

Managed EKS add-ons use `aws_eks_addon_version` with `most_recent = true` and the **actual cluster Kubernetes version**. AWS selects the latest compatible build at plan time. Exact add-on builds and AL2023 node AMI releases are therefore not invented or frozen in this file. Read their resolved versions in the saved plan, then record what actually ran. A later fresh plan may choose newer add-ons; review that change before applying.

```bash
aws eks describe-addon-versions --kubernetes-version 1.36 \
  --addon-name eks-pod-identity-agent --region "$AWS_REGION" \
  --query 'addons[].addonVersions[].{Version:addonVersion,Architectures:architecture,Compatibility:compatibilities}'
aws eks list-addons --cluster-name "$CLUSTER_NAME" --region "$AWS_REGION"
kubectl --context "$LAB_KUBE_CONTEXT" get nodes \
  -o custom-columns=NAME:.metadata.name,KUBELET:.status.nodeInfo.kubeletVersion,OS:.status.nodeInfo.osImage
```

These commands are for your authenticated lab session. They were not run against an AWS account while authoring the kit.

## Image evidence

Anonymous Public ECR manifest checks returned **HTTP 200** for all four healthy image pins. The deliberately missing `python:arcade-does-not-exist-7f4c2a` returned **HTTP 404** and remains unchanged. Manifest availability proves the tag exists; it does not prove a pod can pull, start, or pass its probes on your cluster. The Alpine image layer was additionally downloaded with digest verification: its extracted musl loader and BusyBox binary passed shell/wget/grep HTTP probing and an idempotent file fixture check as local host processes. No container or Kubernetes runtime was involved.

| Image | Manifest digest observed on the check date |
| --- | --- |
| public.ecr.aws/aws-cli/aws-cli:2.37.9 | `sha256:92de75724b6a746951f0e8b915d86bbccd7cb55aff96cd0cb4f7017272160780` |
| public.ecr.aws/docker/library/python:3.14.8-alpine | `sha256:f6a589d43c42b9e7f7dc67a12d37132491f362859a5d750607710cc56da3bc72` |
| public.ecr.aws/docker/library/nginx:1.30.5-alpine | `sha256:0985e772fb9f729e6fa0980da05fca5d9c468e870eed43071545afa9d2e27d94` |
| public.ecr.aws/docker/library/alpine:3.24.2 | `sha256:294b683cb724975bec92580e1e685676bd4b50bda910ddb8c51d4cabeaec77e6` |

The exercises use readable patch tags. Tags can be republished; record each running container's `imageID` when collecting evidence. Promoting immutable digest references across environments is a useful interview follow-up.

## Refreshing this kit later

Check the official sources above first, then change the selected Terraform/EKS/client/runtime/image versions together. Do not mass-replace every occurrence of “latest”: a tool's stable release, EKS-supported release, compatible add-on build, and supported runtime are different decisions. Keep the nonexistent image tag broken in scenario 01.

After editing, initialize each complete solution root in a disposable copy and refresh its lock file:

```bash
terraform init -backend=false -input=false -upgrade
terraform validate
terraform providers
```

Review the selected provider versions and commit the resulting `.terraform.lock.hcl` alongside the code. For ordinary exercise runs, use `terraform init` without `-upgrade` so those selections remain reproducible. Then run local contract/Python tests and validate all manifests against the target minor:

```bash
terraform fmt -check -recursive labs
terraform -chdir=labs/00-terraform-contracts/solution init -backend=false
terraform -chdir=labs/00-terraform-contracts/solution test
python3 -m unittest discover -s labs/05-serverless-counter/solution -p 'test_*.py' -v
kubeconform -strict -summary -kubernetes-version 1.36.0 labs
```

See [VALIDATION.md](VALIDATION.md) for execution evidence and the limits of local validation. AWS account permissions, availability, admission behavior, provisioning, pod failures, and teardown must still be proved in a real disposable AWS session.
