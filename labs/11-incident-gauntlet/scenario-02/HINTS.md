# Progressive hints

Open the next hint only after testing the previous one.

<details>
<summary>Hint 1 — Find what prevented process creation</summary>

Compare the pod events with the container specification. A failure before startup will not be explained by previous application logs.

</details>

<details>
<summary>Hint 2 — Enumerate dependencies</summary>

Run `kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" get configmaps` and `kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" get deployment app -o yaml`. Check the exact ConfigMap name and key referenced by the environment variable; both are namespace scoped.

</details>

<details>
<summary>Hint 3 — Preserve the intended config</summary>

The file creates one ConfigMap but references a different name. Correct the reference; do not make it optional or delete the environment variable to silence the error.

</details>


Make the repair in the working `candidate.yaml`, then review and apply a saved Terraform plan. Diagnostic reads, logs, and HTTP requests are evidence; they are not a separate configuration path.
