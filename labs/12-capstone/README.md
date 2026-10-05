# Game 12 — Ninety-minute platform interview

Deliver a small EKS platform slice, explain its choices, recover an incident, make one controlled change, and remove everything you provisioned. This is an integration exercise over Games 07–11. It intentionally contains no second copy of the cluster code.

Use a distinct lab ID and reviewed plans in your intended account, the same `LAB_ROOT`, the `arcade-lab` context, and the cost guide. The $20 allowance covers the whole curriculum, not an additional $20 for this game. A 90-minute session on one worker is roughly $0.23 of base EKS/node/disk/IPv4 charges; allow extra billable time for provisioning and teardown plus the tiny service/storage costs. Track against the eight-hour planning scenario; it is not a cost ceiling or guarantee.

**Entry conditions:** complete Game 07 once and understand its outputs. If you destroyed it after the previous session, rebuild using [Game 07](../07-eks-foundation/README.md). Start the interview timer when the node and required foundation add-ons are Ready. Provisioning remains part of billable time. Read Games 08–10 beforehand but start this timed run with their workloads removed. Never leave an earlier session's cluster running just to save preparation time.

```bash
: "${LAB_ROOT:?Set the absolute extracted kit path}"
export LAB_KUBE_CONTEXT="${LAB_KUBE_CONTEXT:-arcade-lab}"
aws sts get-caller-identity
kubectl --context "$LAB_KUBE_CONTEXT" get nodes -o wide
kubectl --context "$LAB_KUBE_CONTEXT" get pods -A
mkdir -p "$LAB_ROOT/run/capstone"
date -u +%FT%TZ > "$LAB_ROOT/run/capstone/started-at.txt"
# This directory holds evidence only, never another Terraform owner of arcade-app.
```

Save brief answers and command output under `$LAB_ROOT/run/capstone/`. Keep secrets and service-account tokens out of your evidence.

| Time | Task | Points |
|---|---|---:|
| 00–10 | Explain the foundation's plan, state boundaries, networking, identity, and cost model | 15 |
| 10–30 | Deploy and verify the application release using Game 08 | 20 |
| 30–45 | Prove least-privilege AWS access using Game 09 | 15 |
| 45–55 | Prove persistence and understand volume lifecycle using Game 10 | 10 |
| 55–70 | Diagnose and repair one randomly selected Game 11 scenario | 20 |
| 70–80 | Make and verify a controlled application change | 10 |
| 80–90 | Begin and verify ordered teardown; continue until deletion really completes | 10 |

The timer measures your process; it never overrides safe deletion. If deletion takes longer than ten minutes, report the pending resources and keep going. Do not call cleanup complete because the interview timer expired.

1. **Foundation defense.** Show the already applied Game 07 Terraform configuration and explain its dependencies. Identify what still costs money if pods are deleted or worker count reaches zero. Explain why this lab has no NAT gateway or load balancer, and what a production private-node design would change. Explain public/private API access, IAM principal versus Kubernetes RBAC, and why Terraform state deserves access controls. Follow Game 07's documented variable/preflight commands if checking a plan; do not invent a new root or pass another game's state to it.
2. **Application.** Follow the exact apply and verification commands in [Game 08](../08-kubernetes-release/README.md). Show rollout status, probes, Service endpoints, and a working request through the Service from the Terraform-managed diagnostic Pod. Local port-forward is additional browser access; it is not public internet exposure. The optional [Game 13](../13-public-access/README.md) extension tests the real public boundary. Demonstrate the prescribed restricted user's permitted and denied operations. Explain what one-node availability cannot promise.
3. **AWS access.** Follow [Game 09](../09-pod-identity/README.md). Show the expected successful AWS operation and the intended denied operation from its workload. Explain every step from Kubernetes ServiceAccount to AWS role to resource permission. Name which failure evidence would make you inspect trust, association, or the resource policy first.
4. **Persistent storage.** Follow [Game 10](../10-ebs-storage/README.md). Record its writer-created marker and PV identity, replace only the Deployment through Terraform using that game's commands, and verify the new Pod reads the same volume. Explain the CSI controller's identity, binding mode, zone constraint, reclaim policy, and what happens after PVC deletion.
5. **Incident.** Choose a scenario before opening its hints/answer. Run its README, capture decisive evidence, repair the source YAML through a reviewed Terraform plan, verify recovery, then destroy that workload state. Never run multiple incidents simultaneously.
6. **Change.** Add a ConfigMap named `web-content` in `arcade-app` whose `index.html` contains `arcade-release-v2`. Mount it read-only at `/usr/share/nginx/html` in Game 08's web Deployment, preserving probes, resources and ClusterIP networking. Change a Pod-template annotation to trigger a rollout. Prove a request through the Service returns the new marker, then restore the original release. A complete reference manifest and exact verification/rollback commands are in `ANSWERS.md`; write your own first. Use the existing Game 08 Terraform state for both changes; do not create a second state managing `arcade-app`. Explain how Terraform removes a previously tracked ConfigMap when it is omitted from the restored candidate, and why an imperative Deployment rollback alone would not restore that whole release.
7. **Teardown.** Destroy the Game 08 and Game 09 workload Terraform roots, then perform Game 10's PVC/backing-volume cleanup while the CSI driver and node still exist. Destroy the Game 09 Terraform resources using its own root, then the Game 07 foundation. Follow each game's teardown exactly; dependency order matters. Inspect leftovers with the root cost/cleanup guide. Destroy any remaining earlier-game resources you created during the session. Keep state until cleanup succeeds.

Random incident selection (Bash; no cloud mutation until you follow that scenario):

```bash
INCIDENT=$(printf '%02d' "$((RANDOM % 10 + 1))")
cat "$LAB_ROOT/labs/11-incident-gauntlet/scenario-$INCIDENT/README.md"
```

Use [HINTS.md](HINTS.md) only if blocked. The [answer/rubric](ANSWERS.md) describes what strong evidence looks like. [SCORECARD.md](SCORECARD.md) is the interviewer sheet. You are not graded on memorizing one exact CLI flag; you are graded on choosing evidence, controlling scope, explaining tradeoffs, and finishing cleanup.

Official reference reading: [EKS cluster deletion](https://docs.aws.amazon.com/eks/latest/userguide/delete-cluster.html), [Kubernetes deployments](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/), [persistent volumes](https://kubernetes.io/docs/concepts/storage/persistent-volumes/), [pod disruption budgets](https://kubernetes.io/docs/concepts/workloads/pods/disruptions/).
