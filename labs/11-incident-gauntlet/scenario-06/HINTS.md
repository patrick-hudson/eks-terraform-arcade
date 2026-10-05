# Progressive hints

Open the next hint only after testing the previous one.

<details>
<summary>Hint 1 — Capture the actual API response</summary>

Run `kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" logs job/inspect`. An HTTP 403 from Kubernetes is different from an AWS AccessDenied error or a network timeout.

</details>

<details>
<summary>Hint 2 — Trace identity and authorization</summary>

Inspect the Job serviceAccountName, RoleBinding subject, Role, namespace, resource name, and verb with `kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" get job,serviceaccount,role,rolebinding -o yaml`. A request for one named object uses a different verb from a collection request.

</details>

<details>
<summary>Hint 3 — Repair only the required permission</summary>

The Role grants a collection verb while the Job requests a named ConfigMap. Scope the correction to that ConfigMap. A failed Job with backoffLimit 0 needs an explicit Terraform replacement to rerun after an RBAC-only repair. A changed Job manifest triggers replacement automatically; changing only its Role does not.

</details>


Make the repair in the working `candidate.yaml`, then review and apply a saved Terraform plan. Diagnostic reads, logs, and HTTP requests are evidence; they are not a separate configuration path.
