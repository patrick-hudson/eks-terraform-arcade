# Answer — scenario 09

**The Service forwards requests to a port where the application is not listening.** The pod serves port 8080 and its readiness probe succeeds there. The starter Service listens on port 8080 but uses `targetPort: 8081`. Its selector can match a Ready pod and populate an EndpointSlice while directing clients to the wrong socket.

The reference changes only `targetPort` to the container's named port, `http`. This binds the Service to the declared container port, although a declared port still must agree with the real process listener. A numeric target of 8080 is also valid. Read the [Kubernetes Service port documentation](https://kubernetes.io/docs/concepts/services-networking/service/#defining-a-service).

After completing the README's setup, apply the reference through Terraform:

```bash
cd "$LAB_ROOT/run/scenario-09"
cp "$SCENARIO_DIR/solution/fixed.yaml" candidate.yaml
terraform plan -out=repair.tfplan
terraform show repair.tfplan
terraform apply repair.tfplan
```

Expect a Service change, not a new node, load balancer, image, or replica. Changing a selector, restarting the pod, or opening a node security group does not fix this port mismatch.

Verify the response bytes from the actual Service path, from an independent client in the cluster:

```bash
(
set -euo pipefail
BODY=$(kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" exec arcade-diagnostics -- \
  wget -T 3 -O - http://app:8080/)
test "$BODY" = arcade-09-ok
printf 'PASS: Service HTTP returned %s\n' "$BODY"
kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" get endpointslices -l kubernetes.io/service-name=app -o yaml
terraform plan -detailed-exitcode
)
```

The subshell stops before printing PASS if the HTTP request or assertion fails. A final Terraform exit code 0 means no drift; 2 means a nonempty plan, and 1 means a plan error. The HTTP assertion is the functional check, while the EndpointSlice and Terraform plan explain the resulting configuration.

For an interview, explain these competing hypotheses:

- If localhost HTTP failed, investigate the process, port binding, and readiness configuration first.
- If localhost worked but the direct Pod IP failed, investigate the pod network path and applicable policy. A listener bound only to loopback is another possibility.
- If both direct requests worked but Service DNS failed, investigate name resolution before a port mapping.
- Here, the Service resolves and has a Ready endpoint, but its endpoint port differs from the working listener. The repair changes that mapping and makes the same client request pass.

Production prevention: keep named ports consistent, validate manifests, and run a release smoke test through the same Service or ingress URL as the caller. An external release additionally needs DNS, TLS, ingress/load-balancer routing, and access policy checks. This ClusterIP result proves none of those; continue with [Game 13](../../13-public-access/README.md) for public access.

Cleanup uses the same state that created the workload:

```bash
cd "$LAB_ROOT/run/scenario-09"
terraform plan -destroy -out=cleanup.tfplan
terraform show cleanup.tfplan
terraform apply cleanup.tfplan
terraform state list
kubectl --context "$LAB_KUBE_CONTEXT" get namespace "$NS"
```

Pass: empty Terraform state and the named namespace returns NotFound. Keep the workspace and state if teardown fails; do not delete objects imperatively to hide the failure. Destroy Game 07 at the end of the session to stop EKS billing.
