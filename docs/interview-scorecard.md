# Interview scorecard and question bank

Use a blank notes file per attempt. Do not copy the answer first. A successful apply or a green pod is worth less than a defensible diagnosis and a clean teardown.

## Score one mission out of 100

| Dimension | Points | Evidence |
|---|---:|---|
| Describe the system and intended behavior | 10 | Resource/data/control paths before touching it |
| Implement or reproduce the failure | 15 | Exact command, inputs and observed result |
| Diagnose with evidence | 25 | Competing hypotheses, discriminating commands, root cause |
| Make the smallest durable repair | 20 | HCL/YAML change, plan/diff, no unexplained privilege increase |
| Verify behavior and failure boundaries | 15 | Positive and negative checks; restart/rollout where relevant |
| Explain production tradeoffs | 5 | Cost, availability, access and operational ownership |
| Tear down and prove deletion | 10 | State plus service-native resource checks |

A hints-free 80+ with a clear explanation is a strong practice result, not an employment prediction. Repeat later with different names/values so you demonstrate reasoning rather than memorized edits. Record help used: none / diagnostic hint / targeted hint / solution.

## Investigation transcript template

```text
Mission / timestamp / budget remaining:
Expected behavior:
Observed behavior (exact status/event/log):
Hypothesis 1 and evidence that would disprove it:
Hypothesis 2 and evidence that would disprove it:
Next smallest diagnostic command:
Root cause:
Change made in source:
Proof of recovery:
Negative check / remaining limitation:
Production version of this design:
Deleted resources and evidence:
```

## Terraform: mid-senior prompts

1. What does a saved plan authorize? What information in a plan/state is sensitive even when CLI output redacts it?
2. Explain configuration, state, refresh and the remote API as distinct sources of information. Why doesn't `refresh-only` accept drift into HCL?
3. Why is changing a `for_each` key an identity change? Compare that to reordering a list used by `count`.
4. A dependency can be inferred through a resource attribute. When is explicit `depends_on` justified, and how can excessive use make plans less precise?
5. How do provider constraints and `.terraform.lock.hcl` differ? Why can a module version change without changing a provider lockfile?
6. Explain the S3 backend bootstrap cycle. What remains local, where is the lock, and who can delete it? When would force-unlock be justified?
7. A resource exists but is absent from state. Compare import, replacement, state rm and moved blocks. Which changes live infrastructure?
8. How would you recover from a failed apply that created half the graph? Why is deleting the state file the wrong first step?
9. When does `create_before_destroy` fail to solve downtime? Discuss unique names, quotas, dependencies and stateful storage.
10. What should a reusable VPC/EKS module expose? Why not output credentials, every resource attribute or the entire child module?
11. How would CI authenticate with short-lived federation, review plans and serialize applies? What changes between pull-request planning and trusted apply execution?
12. Is `terraform validate` enough? Distinguish syntax/schema validation, mocked tests, plan against AWS and live integration tests.

## EKS and Kubernetes: explain the distinction

| Prompt | Strong answer should distinguish |
|---|---|
| Pod is Pending | Scheduling failure, PVC binding, image pull/container startup, and which event identifies the stage |
| ImagePullBackOff | A current backoff state versus the underlying registry/tag/auth/network error |
| CrashLoopBackOff | Container exits and restarts versus a probe killing a running process; previous logs and termination reason |
| CreateContainerConfigError | Kubernetes cannot construct the container configuration; often no application logs yet |
| Running but not Ready | Process state versus readiness and Service endpoint eligibility |
| Service is unreachable | Label selector, EndpointSlice readiness, targetPort, process bind address, DNS and routing |
| AccessDenied in a pod | Kubernetes RBAC versus AWS IAM; actual caller identity; Pod Identity association and SDK credential chain |
| PVC never binds | StorageClass name/provisioner, delayed binding, CSI health/IAM and volume topology |
| Eviction blocked | PDB voluntary-disruption protection versus scheduler capacity and unavoidable node failures |
| OOMKilled | Memory cgroup limit versus node pressure, application allocation and why raising limits may only defer failure |

Follow-ups: requests drive scheduling; limits constrain runtime, and CPU throttling differs from memory OOM. A PDB is not a guarantee against involuntary disruption. Node count does not equal pod capacity: kube-system overhead, ENI/IP limits and per-pod requests matter. HPA needs metrics; scaling replicas does not scale nodes by itself.

## AWS design defense

- Draw or explain the public-worker lab packet path: node → internet gateway for image pulls, node → private EKS API, operator → restricted public API. What changes in a private-worker production design?
- Compare NAT, VPC endpoints and public egress on cost, failure modes and operational complexity. Why can several interface endpoints cost more than a short lab cluster?
- Distinguish EKS access entries, Kubernetes RBAC, the node IAM role, Pod Identity roles and IRSA. Who authenticates whom at each step?
- A pod can access S3 through a node role. Why is that a concerning false positive? How does the reference limit IMDS credential fallback?
- Why does an EBS volume constrain AZ placement? Explain WaitForFirstConsumer, ReadWriteOnce and reclaim policy. Does RWO mean one pod universally?
- Which resources are owned by Terraform, EKS, an Auto Scaling group or a Kubernetes controller? How does that change deletion order?
- Atomic increment succeeded but the client timed out. What happens on retry? Design idempotency without promising impossible guarantees.
- What is missing for production: multiple nodes/AZs, private-node design, upgrade testing, policy controls, secrets management, observability, backups, workload protection and measured capacity?

## Additional design-only senior drills

These deliberately avoid adding AWS cost. Write a one-page design or plan review, then defend it aloud.

1. **Upgrade review:** propose a Kubernetes minor upgrade sequence, deprecated-API checks, add-on compatibility, node rollout, PDB interactions and rollback limitations. A managed EKS control-plane downgrade is not your rollback strategy.
2. **Autoscaling incident:** replicas grow but pods remain Pending. Explain HPA, metrics, node autoscaling, max-node limits, affinity, IP availability and quotas as separate layers. Avoid installing a whole autoscaler merely to memorize it.
3. **State split:** move networking and workloads into separate states without two active owners, loss of access, or a destructive plan. Describe locks and maintenance coordination.
4. **GitHub Actions design:** outline OIDC role trust scoped to repository/environment, plan artifact sensitivity, protected approval, least-privilege apply and concurrency lock. No real repository or cloud trust is created by this drill.
5. **Cost postmortem:** a $20 practice account reached $120. Work backward from regional service charges and ownership to resource IDs; explain why tags, state, budgets and timers were each insufficient alone.
6. **Module review:** identify inputs that make misuse expensive. Write validation for CIDRs and node limits; choose which defaults belong in a tutorial versus a production module.

Source references are in each mission. Use Kubernetes events/logs and AWS APIs as evidence; a memorized status-to-fix table is only a starting hypothesis.
