# Progressive hints

Open the next hint only after testing the previous one.

<details>
<summary>Hint 1 — Read the disruption status</summary>

Run `kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" get pdb app -o yaml`. Compare currentHealthy, desiredHealthy, expectedPods, and disruptionsAllowed.

</details>

<details>
<summary>Hint 2 — Work out the arithmetic</summary>

With two healthy replicas, how many can be disrupted while satisfying the configured minimum? An eviction honors this budget; direct deletion would not demonstrate that it is fixed.

</details>

<details>
<summary>Hint 3 — Allow one safe maintenance action</summary>

Keep two replicas and one minimum available. Wait for the budget status to update, submit the same single-pod eviction again, then verify a replacement becomes Ready. Do not drain the lab node.

</details>


Make the repair in the working `candidate.yaml`, then review and apply a saved Terraform plan. Diagnostic reads, logs, and HTTP requests are evidence; they are not a separate configuration path.
