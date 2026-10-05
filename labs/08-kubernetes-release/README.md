# 08 · A deployment that will not become healthy

**Time box:** 25 minutes. **Difficulty:** mid–senior Kubernetes release debugging. **Depends on:** live lab 07. **Incremental AWS cost:** no extra billable AWS resource; the existing EKS/node hourly clock continues. Keep one replica except during its short rolling surge. No LoadBalancer Service.

You have a release manifest from another engineer. A readiness probe decides whether a Pod can receive Service traffic; a liveness probe decides when Kubernetes should restart its container. The Service is the stable address that routes requests to selected healthy Pods. It applies, but the deployment never becomes ready. Restore useful service, preserve a health check, and prove that an observer can inspect workloads without reading Secrets or changing releases. Do not inspect `solution/` or `ANSWERS.md` until you have a theory.

## Start the incident

```bash
: "${LAB_ROOT:?Complete docs/setup.md first}"
export LAB_KUBE_CONTEXT=arcade-lab
export TF_VAR_aws_profile="${AWS_PROFILE:?Set the authenticated profile}"
: "${TF_VAR_expected_account_id:?Set the intended account ID}"
export TF_VAR_cluster_name="$(terraform -chdir="$LAB_ROOT/run/07-eks-foundation" output -raw cluster_name)"
export TF_VAR_region="$(terraform -chdir="$LAB_ROOT/run/07-eks-foundation" output -raw region)"
arcade start 08
cd "$LAB_ROOT/run/08-kubernetes-release"
terraform init -lockfile=readonly
terraform validate
terraform plan -out=broken.tfplan
terraform show broken.tfplan
terraform apply broken.tfplan
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-app rollout status deployment/web --timeout=90s
```

Terraform owns the Namespace, workload, RBAC and diagnostic Pod. It does not wait for workload readiness; that rollout timeout is the intended first failure. Do not wait endlessly, scale the node group, disable all probes or add a public load balancer. Locate the actual failing boundary and edit the file in `run/`.

## Investigate, write the repair, apply

```bash
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-app get pods,deploy,rs,svc
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-app describe pods -l app=arcade-web
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-app logs deployment/web --tail=30
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-app get events --sort-by=.lastTimestamp
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-app get endpointslices -l kubernetes.io/service-name=web -o yaml
# Edit candidate.yaml, state a hypothesis, then review and apply the Terraform repair.
terraform plan -out=repair.tfplan
terraform show repair.tfplan
terraform apply repair.tfplan
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-app rollout status deployment/web --timeout=180s
```

Write a 4-line incident note: symptom; evidence; root cause; the smallest durable change. Explain why readiness failure and liveness failure have different effects, and why `Running` is not enough to call this successful.

## Prove service routing and authorization

Use the diagnostic Pod already created by Terraform so the request traverses Service DNS and endpoint selection:

```bash
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-app wait --for=condition=Ready pod/arcade-diagnostics --timeout=90s
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-app exec arcade-diagnostics -- \
  sh -ec 'wget -T 10 -qO- http://web.arcade-app.svc.cluster.local | grep "Welcome to nginx"'
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-app auth can-i get pods --as=system:serviceaccount:arcade-app:observer
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-app auth can-i get secrets --as=system:serviceaccount:arcade-app:observer
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-app auth can-i patch deployments --as=system:serviceaccount:arcade-app:observer
```

Pass: rollout completes, HTTP body contains `Welcome to nginx`, authorization results are **yes / no / no**. The two `no` checks intentionally exit nonzero. You need admin impersonation rights for these checks, provided by lab 07's access entry. The same diagnostic Pod can repeat this read without recreating it. Repair only `candidate.yaml` or the Terraform configuration, then plan/apply; console edits and imperative Kubernetes patches do not count.

For browser inspection use `kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-app port-forward service/web 8080:80`, then open `http://localhost:8080`. Port-forward alone does not prove ClusterIP routing; keep the in-cluster test above. Neither is public internet exposure. Continue to [Game 13](../13-public-access/README.md) to create, break and fix an actual public endpoint with Terraform.

## Cleanup, healthy or broken

```bash
terraform -chdir="$LAB_ROOT/run/08-kubernetes-release" plan -destroy -out=destroy.tfplan
terraform -chdir="$LAB_ROOT/run/08-kubernetes-release" show destroy.tfplan
terraform -chdir="$LAB_ROOT/run/08-kubernetes-release" apply destroy.tfplan
terraform -chdir="$LAB_ROOT/run/08-kubernetes-release" state list
kubectl --context "$LAB_KUBE_CONTEXT" get namespace arcade-app
```

The Terraform state listing should be empty and the namespace lookup should report `NotFound`. Keep the cluster only while actively continuing; finish lab 07 teardown at the end of the session.

[Layered hints](HINTS.md) · [Answer and exact repair](ANSWERS.md)

Sources: [probe behavior](https://kubernetes.io/docs/concepts/configuration/liveness-readiness-startup-probes/), [debugging Services](https://kubernetes.io/docs/tasks/debug/debug-application/debug-service/), [RBAC](https://kubernetes.io/docs/reference/access-authn-authz/rbac/).
