# Answer — scenario 03

**The configured command exits with code 23.** The launcher prints a fatal message and exits instead of running a server. Restart policy retries, then backs off. The reference uses the Python foreground HTTP server, preserving the intended port and probes. Changing probes, adding capacity, or repeatedly deleting the pod does not repair an explicit application exit. Capture the previous log and exit code before the replacement loses that evidence.

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
cd "$LAB_ROOT/run/scenario-03"
cp "$SCENARIO_DIR/solution/fixed.yaml" candidate.yaml
terraform plan -out=repair.tfplan
terraform show repair.tfplan
terraform apply repair.tfplan
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" rollout status deployment/app --timeout=180s
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" get pods -o wide
```

Check both the application process and a request through Service DNS from the separately managed diagnostic Pod:

```bash
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" exec deployment/app -- python -c 'import urllib.request; print(urllib.request.urlopen("http://127.0.0.1:8080/").status)'
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" get endpointslices -l kubernetes.io/service-name=app -o yaml
# Expect HTTP 200 and an endpoint condition ready: true.
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" wait --for=condition=Ready pod/arcade-diagnostics --timeout=90s
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" exec arcade-diagnostics -- wget -T 10 -qO- "http://app.$NS.svc.cluster.local:8080/"
# Expect the Python directory listing through the Service, not just localhost.
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" port-forward service/app 8080:8080
```

In a second local terminal, run `curl --fail http://127.0.0.1:8080/`. Expect a directory listing, then stop port-forward with Ctrl-C. Port-forward confirms reachability through the API tunnel; the diagnostic Pod request separately proves Service routing. Neither check claims internet access. Game 13 covers the public endpoint boundary.

Explain what observation would have proved your initial diagnosis wrong. What check would prevent this regression before a production rollout? Diff your candidate against the answer; a correct alternative does not need to be byte-identical.

```bash
diff -u "$SCENARIO_DIR/starter/broken.yaml" "$SCENARIO_DIR/solution/fixed.yaml"
# diff exits 1 when it finds changes; that is expected here.
terraform -chdir="$LAB_ROOT/run/scenario-03" plan -destroy -out=destroy.tfplan
terraform -chdir="$LAB_ROOT/run/scenario-03" show destroy.tfplan
terraform -chdir="$LAB_ROOT/run/scenario-03" apply destroy.tfplan
terraform -chdir="$LAB_ROOT/run/scenario-03" state list
kubectl --context "$LAB_KUBE_CONTEXT" get namespace "$NS"
```

Cleanup must show an empty state and a namespace NotFound response before starting another incident. An authorization or connection error is not absence evidence. Follow Game 07 teardown at session end; removing these workloads does not stop EKS billing.

Official reference: [Kubernetes documentation](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/).
