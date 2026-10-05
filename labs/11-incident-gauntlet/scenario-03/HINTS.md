# Progressive hints

Open the next hint only after testing the previous one.

<details>
<summary>Hint 1 — Inspect termination, not only STATUS</summary>

Use `kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" describe pods -l app=incident` and inspect Last State, Reason, Exit Code, and Restart Count. A backoff is a retry policy, not a root cause.

</details>

<details>
<summary>Hint 2 — Read the process output</summary>

Set `POD=$(kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" get pods -l app=incident -o jsonpath='{.items[0].metadata.name}')`; then run `kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" logs "$POD" -c app --previous`. If no previous instance exists yet, use ordinary logs and wait for a restart.

</details>

<details>
<summary>Hint 3 — Check the launcher</summary>

Inspect the Deployment command. It deliberately exits instead of launching the server. The healthy command must keep the foreground HTTP server on port 8080 running.

</details>


Make the repair in the working `candidate.yaml`, then review and apply a saved Terraform plan. Diagnostic reads, logs, and HTTP requests are evidence; they are not a separate configuration path.
