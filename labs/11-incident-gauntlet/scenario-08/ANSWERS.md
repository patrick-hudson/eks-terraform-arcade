# Answer — scenario 08

**The disruption budget permits zero voluntary evictions.** Two replicas with `minAvailable: 2` require both replicas to stay available, leaving zero disruption allowance. The reference keeps two replicas and lowers the minimum to one, allowing the intended one-at-a-time maintenance. A PDB constrains voluntary evictions; it cannot guarantee availability against node failure and does not govern Deployment rolling-update strategy. With both pods on one worker, the lab has no node-failure redundancy.

Run the scenario README first so `NS`, `SCENARIO_DIR`, `LAB_ROOT`, and `LAB_KUBE_CONTEXT` are set.

Apply the corrected PDB, wait until exactly one disruption is allowed, then retry one eviction as the operational acceptance test:

```bash
cd "$LAB_ROOT/run/scenario-08"
cp "$SCENARIO_DIR/solution/fixed.yaml" candidate.yaml
terraform plan -out=repair.tfplan
terraform show repair.tfplan
terraform apply repair.tfplan
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" wait --for=jsonpath='{.status.disruptionsAllowed}'=1 pdb/app --timeout=60s
POD=$(kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" get pods -l app=incident -o jsonpath='{.items[0].metadata.name}')
kubectl --context "$LAB_KUBE_CONTEXT" create --raw "/api/v1/namespaces/$NS/pods/$POD/eviction" -f - <<EOF
{"apiVersion":"policy/v1","kind":"Eviction","metadata":{"name":"$POD","namespace":"$NS"}}
EOF
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" wait --for=delete "pod/$POD" --timeout=90s
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" rollout status deployment/app --timeout=180s
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" get pods,pdb
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" wait --for=condition=Ready pod/arcade-diagnostics --timeout=90s
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" exec arcade-diagnostics -- wget -T 10 -qO- "http://app.$NS.svc.cluster.local:8080/"
```

Pass: the eviction is accepted, the old pod disappears, the replacement becomes Ready, and both replicas return healthy. To demonstrate availability during the experiment, use a second terminal to watch pods before submitting the eviction. Do not request a second eviction while replacement readiness is pending. A network-level availability guarantee needs an actual client/error-budget test, not only pod counts.

Explain what observation would have proved your initial diagnosis wrong. What check would prevent this regression before a production rollout? Diff your candidate against the answer; a correct alternative does not need to be byte-identical.

```bash
diff -u "$SCENARIO_DIR/starter/broken.yaml" "$SCENARIO_DIR/solution/fixed.yaml"
# diff exits 1 when it finds changes; that is expected here.
terraform -chdir="$LAB_ROOT/run/scenario-08" plan -destroy -out=destroy.tfplan
terraform -chdir="$LAB_ROOT/run/scenario-08" show destroy.tfplan
terraform -chdir="$LAB_ROOT/run/scenario-08" apply destroy.tfplan
terraform -chdir="$LAB_ROOT/run/scenario-08" state list
kubectl --context "$LAB_KUBE_CONTEXT" get namespace "$NS"
```

Cleanup must show an empty state and a namespace NotFound response before starting another incident. An authorization or connection error is not absence evidence. Follow Game 07 teardown at session end; removing these workloads does not stop EKS billing.

Official reference: [Kubernetes documentation](https://kubernetes.io/docs/concepts/workloads/pods/disruptions/).
