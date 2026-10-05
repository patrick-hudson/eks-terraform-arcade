# Answer — scenario 07

**The process allocates 256MiB inside a 64Mi container limit.** The memory cgroup cannot accommodate that allocation and normally records OOMKilled with exit code 137. The answer reduces the bounded allocation to 8MiB and retains the 64Mi limit. This is a controlled container OOM, not a node stress test. Explain the distinction between a container hitting its limit, node-pressure eviction, and an externally delivered SIGKILL. Exit 137 alone does not establish which occurred.

Run the scenario README first so `NS`, `SCENARIO_DIR`, `LAB_ROOT`, and `LAB_KUBE_CONTEXT` are set.

Capture the previous termination before replacing the pod:

```bash
POD=$(kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" get pods -l app=incident -o jsonpath='{.items[0].metadata.name}')
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" get pod "$POD" -o jsonpath='{.status.containerStatuses[0].lastState.terminated}{"\n"}'
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" logs "$POD" -c app --previous
```

If the first restart has not happened, `--previous` has no instance to read yet; inspect current logs and retry after the restart. The OOM case may log only the message preceding allocation.

Apply the full reference repair and wait for the new revision:

```bash
cd "$LAB_ROOT/run/scenario-07"
cp "$SCENARIO_DIR/solution/fixed.yaml" candidate.yaml
terraform plan -out=repair.tfplan
terraform show repair.tfplan
terraform apply repair.tfplan
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" rollout status deployment/app --timeout=180s
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" get pods -o wide
```

Verify the bounded process stays running and the new pod does not restart:

```bash
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" logs deployment/app
# Expected: allocated=8388608
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" get pods -l app=incident -o jsonpath='{range .items[*]}{.metadata.name}{" restarts="}{.status.containerStatuses[0].restartCount}{"\n"}{end}'
# Observe for one minute, then rerun the preceding command. New-pod restart count should remain 0.
```

Explain what observation would have proved your initial diagnosis wrong. What check would prevent this regression before a production rollout? Diff your candidate against the answer; a correct alternative does not need to be byte-identical.

```bash
diff -u "$SCENARIO_DIR/starter/broken.yaml" "$SCENARIO_DIR/solution/fixed.yaml"
# diff exits 1 when it finds changes; that is expected here.
terraform -chdir="$LAB_ROOT/run/scenario-07" plan -destroy -out=destroy.tfplan
terraform -chdir="$LAB_ROOT/run/scenario-07" show destroy.tfplan
terraform -chdir="$LAB_ROOT/run/scenario-07" apply destroy.tfplan
terraform -chdir="$LAB_ROOT/run/scenario-07" state list
kubectl --context "$LAB_KUBE_CONTEXT" get namespace "$NS"
```

Cleanup must show an empty state and a namespace NotFound response before starting another incident. An authorization or connection error is not absence evidence. Follow Game 07 teardown at session end; removing these workloads does not stop EKS billing.

Official reference: [Kubernetes documentation](https://kubernetes.io/docs/tasks/configure-pod-container/assign-memory-resource/).
