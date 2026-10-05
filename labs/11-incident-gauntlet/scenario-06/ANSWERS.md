# Answer — scenario 06

**The authenticated ServiceAccount lacks the `get` verb.** The inspector authenticates using its projected ServiceAccount token and the cluster CA, then requests one named ConfigMap. The Role grants only `list`; that does not authorize `get`. The repair grants `get` on `configmaps` with `resourceNames: [app-settings]` in this namespace. This is Kubernetes RBAC, separate from EKS access entries and AWS IAM/Pod Identity. Granting cluster-admin would conceal the authorization design problem.

Run the scenario README first so `NS`, `SCENARIO_DIR`, `LAB_ROOT`, and `LAB_KUBE_CONTEXT` are set.

Check the denial with the actual ServiceAccount identity. This impersonation check requires the lab operator's administrative permission; the Job logs remain the source of truth if your operator cannot impersonate.

```bash
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" auth can-i get configmap/app-settings --as="system:serviceaccount:$NS:inspector"
# Expected before repair: no (exit status 1).
cd "$LAB_ROOT/run/scenario-06"
cp "$SCENARIO_DIR/solution/fixed.yaml" candidate.yaml
terraform plan -out=repair.tfplan
terraform show repair.tfplan
terraform apply repair.tfplan
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" auth can-i get configmap/app-settings --as="system:serviceaccount:$NS:inspector"
# Expected after repair: yes. The Role changed; the unchanged failed Job needs an explicit Terraform rerun.
terraform plan -replace='module.exercise.kubernetes_manifest.job["Job/inspect"]' -out=rerun.tfplan
terraform show rerun.tfplan
terraform apply rerun.tfplan
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" wait --for=condition=complete job/inspect --timeout=120s
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" logs job/inspect
# Expected output: arcade ready
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" auth can-i list secrets --as="system:serviceaccount:$NS:inspector"
# Expected: no. Do not widen the Role to change that result.
```

A Job's pod template is generally immutable. The module replaces a Job automatically when its manifest content changes. Here only the Role changed, so the explicit Terraform `-replace` reruns the unchanged Job after authorization is fixed. Capture failed logs first; replacement removes the old Job and its Pods.

Explain what observation would have proved your initial diagnosis wrong. What check would prevent this regression before a production rollout? Diff your candidate against the answer; a correct alternative does not need to be byte-identical.

```bash
diff -u "$SCENARIO_DIR/starter/broken.yaml" "$SCENARIO_DIR/solution/fixed.yaml"
# diff exits 1 when it finds changes; that is expected here.
terraform -chdir="$LAB_ROOT/run/scenario-06" plan -destroy -out=destroy.tfplan
terraform -chdir="$LAB_ROOT/run/scenario-06" show destroy.tfplan
terraform -chdir="$LAB_ROOT/run/scenario-06" apply destroy.tfplan
terraform -chdir="$LAB_ROOT/run/scenario-06" state list
kubectl --context "$LAB_KUBE_CONTEXT" get namespace "$NS"
```

Cleanup must show an empty state and a namespace NotFound response before starting another incident. An authorization or connection error is not absence evidence. Follow Game 07 teardown at session end; removing these workloads does not stop EKS billing.

Official reference: [Kubernetes documentation](https://kubernetes.io/docs/reference/access-authn-authz/rbac/).
