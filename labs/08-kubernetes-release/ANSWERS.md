# 08 · Answer

The readiness probe requests `/ready`, but the stock nginx image serves `/` and returns 404 for `/ready`. The container stays `Running`; readiness is false, so endpoint readiness is false and the Service has no usable backend. The liveness probe already points at `/`, so this fault does not cause restart loops.

Edit the readiness path to `/` in your working `candidate.yaml`, which Terraform decodes into tracked Kubernetes resources, keeping the probes and resource limits. The full reference repair is:

```bash
cd "$LAB_ROOT/run/08-kubernetes-release"
cp "$LAB_ROOT/labs/08-kubernetes-release/solution/workload.yaml" candidate.yaml
terraform plan -out=repair.tfplan
terraform show repair.tfplan
terraform apply repair.tfplan
kubectl --context "$LAB_KUBE_CONTEXT" -n arcade-app rollout status deployment/web --timeout=180s
```

Run all the mission assertions, including the in-cluster HTTP check. With `maxUnavailable: 0`, a broken replacement revision can leave the old healthy Pod available; on this first deployment there is no old healthy Pod, so the Service has no ready backend. This is why the same defect can have different customer impact on initial deployment and later rollout.

The observer Role grants only read operations for the stated resources inside one namespace. It cannot read Secrets or modify Deployments. Disabling service-account token automount for the web container avoids injecting a token the application does not need. The impersonated authorization test does not require a real token in the Pod.

A senior answer distinguishes startup, readiness and liveness, asks which health contract the application actually implements, uses Pod events before speculative changes, and proves end-to-end routing after the repair.

After acceptance, `terraform plan -detailed-exitcode` should exit 0. Readiness, successful HTTP and a no-change plan are distinct evidence: none replaces the others. Terraform also removes the diagnostic client and RBAC during the README destroy sequence.
