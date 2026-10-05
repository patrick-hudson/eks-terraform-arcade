# Progressive hints

Open the next hint only after testing the previous one.

<details>
<summary>Hint 1 — Scheduling uses a reservation model</summary>

Compare the requested resources to node allocatable capacity. Low observed CPU usage is not evidence that a new request fits.

</details>

<details>
<summary>Hint 2 — Compare quantities</summary>

Run `kubectl --context "$LAB_KUBE_CONTEXT" describe nodes` and `kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" get deployment app -o yaml`. Pay attention to CPU units: `8` is eight CPU cores; `8m` is eight millicores.

</details>

<details>
<summary>Hint 3 — Fit one node</summary>

One pod must fit on one node; its resources cannot be split across two nodes. Restore realistic requests and limits for this tiny HTTP process. No node scaling is needed.

</details>


Make the repair in the working `candidate.yaml`, then review and apply a saved Terraform plan. Diagnostic reads, logs, and HTTP requests are evidence; they are not a separate configuration path.
