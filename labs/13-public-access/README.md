# 13 · Healthy pods, broken public path

**Time box:** 25–35 minutes. **Difficulty:** mid–senior network diagnosis. **Depends on:** the running one-node [Game 07 arena](../07-eks-foundation/README.md). **Cost:** reuse its existing node, public IPv4 and control plane; no new load balancer, NAT gateway, VM or public address. The arena continues billing while you investigate. Reserve about $0.15 for an additional half hour, within the $20 total practice budget. A handful of tiny HTTP responses has negligible additional transfer cost; do not load test it.

An application is Ready and serves requests inside Kubernetes. A stakeholder says “the URL doesn't work.” Your task is to prove where the public path breaks, repair it through Terraform, then prove the access is closed again. The starter contains one deliberate networking fault.

This creates a **real internet path restricted to the current public IPv4 of your laptop**. It is not a world-accessible website. The URL is plain HTTP and serves a harmless fixed response, `arcade-public-ok`, only. Do not send credentials or add sensitive content. A production public service needs a different design: HTTPS encryption, a managed load balancer, a domain name, multiple nodes and appropriate authentication.

## The path you must prove

`laptop → internet gateway → node public IPv4 → security group → NodePort 30080 → Service port 80 → Pod port 8080`

The EKS public API endpoint is a separate management path. Restricting it to a `/32` (one IPv4 address) allows that machine to reach the Kubernetes API; it does not expose an application. A Ready pod also says nothing about your laptop's path. A port-forward travels through the API and bypasses the path this incident tests.

Game 07's launch template has no custom security group override, so its managed node receives the cluster security group. This exercise checks that attachment before creating **one standalone ingress rule** on that group. It never takes ownership of the whole group or edits its existing rules. AWS documents the [cluster group attachments](https://docs.aws.amazon.com/eks/latest/userguide/sec-group-reqs.html) and the [custom launch template exception](https://docs.aws.amazon.com/eks/latest/userguide/launch-templates.html).

## Prepare from your laptop

Run these commands on the machine that will perform the external `curl`. If a VPN changes your source IP, rerun preflight and review the resulting `/32` change. Proxies are bypassed for these probes so a configured HTTP proxy does not become a different source unexpectedly.

```bash
source "$HOME/work/eks-terraform-examples/scripts/env.sh"
: "${AWS_PROFILE:?Export the profile used for Game 07}"
: "${TF_VAR_expected_account_id:?Export the intended 12-digit AWS account ID}"
: "${TF_VAR_lab_id:?Export the SAME lab_id used for Game 07}"
: "${CLUSTER_NAME:?Export the Game 07 cluster name}"
: "${LAB_KUBE_CONTEXT:?Export the Game 07 context}"
export AWS_REGION=us-west-2
export TF_VAR_region="$AWS_REGION"
export TF_VAR_cluster_name="$CLUSTER_NAME"
export TF_VAR_aws_profile="$AWS_PROFILE"
export LAB13_RUN="$LAB_ROOT/run/13-public-access"
mkdir -p "$LAB13_RUN/access" "$LAB13_RUN/workload/workload-module"
bash "$LAB_ROOT/labs/13-public-access/preflight.sh" > "$LAB13_RUN/preflight.json"
jq . "$LAB13_RUN/preflight.json"
```

The read-only preflight checks STS account, Game 07 cluster tags, kubeconfig endpoint, exactly one Ready `role=lab` node, its EC2 provider ID, public IPv4, VPC, attached cluster group and instance role. It stops on an ambiguous or unrelated node. It needs read access to EKS, EC2 and IAM instance profiles, plus Kubernetes node reads. If access is denied, resolve that permission; do not bypass the check. Existing unrelated account resources are outside both new Terraform states.

Keep the preflight output local. It contains resource IDs and network addresses, not credentials. Prepare two Terraform roots so you can close public access while leaving the healthy workload available for a comparison:

```bash
cp "$LAB_ROOT/labs/13-public-access/starter/"*.tf "$LAB13_RUN/access/"
cp "$LAB_ROOT/labs/13-public-access/starter/.terraform.lock.hcl" "$LAB13_RUN/access/"
cp "$LAB_ROOT/modules/kubernetes-exercise/root-template/"*.tf "$LAB13_RUN/workload/"
cp "$LAB_ROOT/modules/kubernetes-exercise/root-template/.terraform.lock.hcl" "$LAB13_RUN/workload/"
cp "$LAB_ROOT/modules/kubernetes-exercise/"*.tf "$LAB13_RUN/workload/workload-module/"
cp "$LAB_ROOT/labs/13-public-access/starter/workload.yaml" "$LAB13_RUN/workload/candidate.yaml"
jq '{expected_account_id: .account, region, lab_id, aws_profile, cluster_name, node_instance_id, allowed_cidr}' \
  "$LAB13_RUN/preflight.json" > "$LAB13_RUN/access/terraform.tfvars.json"
jq '{expected_account_id: .account, region, cluster_name, aws_profile}' \
  "$LAB13_RUN/preflight.json" > "$LAB13_RUN/workload/terraform.tfvars.json"
```

Use this initial copy step once in a fresh run directory; later edits belong to the copied candidate files. Terraform `-chdir` makes every following command work regardless of your shell's current directory. Keep both directories and their states until cleanup is verified.

## Create the incident through Terraform

The shared workload module owns the namespace, manifest resources and a temporary `arcade-diagnostics` client pod. It uses the selected AWS profile to reach the existing EKS cluster. All Kubernetes mutations in this lab go through Terraform.

```bash
terraform -chdir="$LAB13_RUN/workload" init -lockfile=readonly
terraform -chdir="$LAB13_RUN/workload" validate
terraform -chdir="$LAB13_RUN/workload" plan -out=create.tfplan
terraform -chdir="$LAB13_RUN/workload" show create.tfplan
# Expect only resources in namespace arcade-public, including the diagnostic pod.
terraform -chdir="$LAB13_RUN/workload" apply create.tfplan
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-public rollout status deployment/public-demo --timeout=180s
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-public wait pod/arcade-diagnostics --for=condition=Ready --timeout=180s

terraform -chdir="$LAB13_RUN/access" init -lockfile=readonly
terraform -chdir="$LAB13_RUN/access" validate
terraform -chdir="$LAB13_RUN/access" plan -out=create.tfplan
terraform -chdir="$LAB13_RUN/access" show create.tfplan
# Expect exactly one new aws_vpc_security_group_ingress_rule.laptop; no changes to Game 07.
terraform -chdir="$LAB13_RUN/access" apply create.tfplan
export PUBLIC_URL="$(terraform -chdir="$LAB13_RUN/access" output -raw public_url)"
curl --noproxy '*' -4 -fsS --connect-timeout 5 --max-time 10 "$PUBLIC_URL"
```

The last command should fail. A connection timeout is the expected symptom, not an HTTP 500. Record the URL, UTC time, exit status and hypothesis. If it succeeds before any repair, **the fault was bypassed**: inspect all security groups attached to the node for an existing broader rule. Do not remove unfamiliar rules from this shared account. Stop and use a fresh Game 07 arena if its network has been modified.

If workload scheduling fails, inspect `kubectl describe` and events first. Image failures, Pod Security admission or an already-allocated NodePort are separate incidents; none is evidence of the intended security group fault. The preflight and Terraform checks do not prove that every external route or firewall is correct.

## Diagnose from the inside out

```bash
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-public get pods,services -o wide
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-public get endpointslices \
  -l kubernetes.io/service-name=public-demo -o yaml
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-public exec deployment/public-demo -- \
  python -c 'import urllib.request; print(urllib.request.urlopen("http://127.0.0.1:8080/", timeout=5).read().decode(), end="")'
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-public exec arcade-diagnostics -- \
  wget -q -T 5 -O - http://public-demo.arcade-public.svc.cluster.local/
export NODE_SG="$(terraform -chdir="$LAB13_RUN/access" output -raw cluster_security_group_id)"
aws ec2 describe-security-group-rules --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --filters "Name=group-id,Values=$NODE_SG" \
  --query 'SecurityGroupRules[].{id:SecurityGroupRuleId,egress:IsEgress,protocol:IpProtocol,from:FromPort,to:ToPort,source:CidrIpv4}'
```

Both internal HTTP probes should return `arcade-public-ok`. A Service chooses pods by matching labels; an EndpointSlice records the pods and ports behind that Service. Check that the labels match, the recorded port is where the app listens, and the security group allows the port your laptop calls. The external request targets the node's port, not the container's port. [Kubernetes NodePort behavior](https://kubernetes.io/docs/concepts/services-networking/service/#type-nodeport) explains the mapping.

Then examine the source files under `access/`. Make the smallest source change, keep `/32`, and use a saved plan:

```bash
terraform -chdir="$LAB13_RUN/access" fmt
terraform -chdir="$LAB13_RUN/access" validate
terraform -chdir="$LAB13_RUN/access" plan -out=repair.tfplan
terraform -chdir="$LAB13_RUN/access" show repair.tfplan
# Only this lab's ingress rule may change. No cluster, node, VPC or unrelated rule changes.
terraform -chdir="$LAB13_RUN/access" apply repair.tfplan
curl --noproxy '*' -4 -fsS --connect-timeout 5 --max-time 10 "$PUBLIC_URL"
test "$(curl --noproxy '*' -4 -fsS --connect-timeout 5 --max-time 10 "$PUBLIC_URL")" = arcade-public-ok
terraform -chdir="$LAB13_RUN/access" plan -detailed-exitcode
```

Expected: the exact marker through the public address, then exit code `0` for no further Terraform differences. Exit `2` means drift or unapplied source changes. If the public IPv4 changed because the managed node was replaced, rerun preflight, update the explicit instance ID and URL, and review the plan before proceeding.

## Close the public path, then remove the workload

Save the exact rule ID before destroying it. This state owns only the rule; Game 07 remains alive and continues billing.

```bash
export PUBLIC_RULE_ID="$(terraform -chdir="$LAB13_RUN/access" output -raw security_group_rule_id)"
printf '%s\n' "$PUBLIC_RULE_ID" > "$LAB13_RUN/removed-rule-id.txt"
terraform -chdir="$LAB13_RUN/access" plan -destroy -out=destroy.tfplan
terraform -chdir="$LAB13_RUN/access" show destroy.tfplan
# Expect one rule deletion, no other managed resources.
terraform -chdir="$LAB13_RUN/access" apply destroy.tfplan
terraform -chdir="$LAB13_RUN/access" state list
```

Prove that the exact rule is absent. AWS authorization errors and expired credentials are **inconclusive**, not proof of deletion:

```bash
(
  set -euo pipefail
  if RULE_LOOKUP="$(aws ec2 describe-security-group-rules --profile "$AWS_PROFILE" --region "$AWS_REGION" \
    --security-group-rule-ids "$PUBLIC_RULE_ID" --output json 2>&1)"; then
    printf '%s\n' "$RULE_LOOKUP"
    printf 'FAIL: the exact access rule still exists.\n' >&2
    exit 1
  elif [[ "$RULE_LOOKUP" == *InvalidSecurityGroupRuleId.NotFound* ]]; then
    printf 'PASS: the exact access rule is absent.\n'
  else
    printf 'INCONCLUSIVE: %s\n' "$RULE_LOOKUP" >&2
    exit 1
  fi
)
# Internal path should still work before deleting the workload:
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-public exec arcade-diagnostics -- \
  wget -q -T 5 -O - http://public-demo.arcade-public.svc.cluster.local/
(
  if curl --noproxy '*' -4 -sS -o /dev/null -H 'Connection: close' --connect-timeout 5 --max-time 10 "$PUBLIC_URL"; then
    printf 'FAIL: a new external connection is still allowed; inspect other attached SG rules.\n' >&2
    exit 1
  else
    printf 'External connection failed; pair this observation with the exact rule absence and successful internal probe.\n'
  fi
)
terraform -chdir="$LAB13_RUN/workload" plan -destroy -out=destroy.tfplan
terraform -chdir="$LAB13_RUN/workload" show destroy.tfplan
terraform -chdir="$LAB13_RUN/workload" apply destroy.tfplan
terraform -chdir="$LAB13_RUN/workload" state list
kubectl --context "$LAB_KUBE_CONTEXT" get namespace arcade-public --ignore-not-found
```

The negative probe deliberately omits `--fail`: receiving an HTTP 404 or 500 still proves the public path is open. A timeout remains only one observation, so pair it with the exact rule absence and a working internal probe. Empty namespace output with a successful API call confirms removal; an API error does not. Run the external probe as a new process as shown: security groups track connections, so an already-established connection can behave differently after a rule changes. AWS describes these [rule and connection-tracking effects](https://docs.aws.amazon.com/vpc/latest/userguide/security-group-rules.html).

**Finish by following Game 07's Terraform destroy and absence checks.** An empty access/workload state is not proof that the control plane, node, disk or IPv4 charge stopped. Keep this cleanup dependency order: access rule → workload namespace → Game 07 arena.

## Interview scorecard

- Distinguish readiness, localhost HTTP, Service HTTP and external HTTP evidence.
- Trace `30080 → 80 → 8080`; explain the different roles of `port`, `targetPort` and `nodePort`.
- Separate the EKS API allowlist from application ingress; explain which security groups attach to the node and why a broader rule in any of them can allow traffic.
- Repair the narrowest owned Terraform resource without broadening the source CIDR.
- Name uncertainties: a company firewall blocking outbound traffic, a VPN changing your source IP, a replacement node, routing, and subnet firewall rules (network ACLs).
- Demonstrate cleanup by resource identity plus fresh traffic behavior, then stop the arena's billing.

**Validation status:** HCL/schema checks, shell syntax, and an offline fixture test suite can validate the authored contract. Actual internet reachability requires the live Game 07 cluster and the outside-client probes above; it is not claimed by local tests.
