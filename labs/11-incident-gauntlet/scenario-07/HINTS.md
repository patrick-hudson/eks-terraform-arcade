# Progressive hints

Open the next hint only after testing the previous one.

<details>
<summary>Hint 1 — Capture the previous termination</summary>

Inspect Last State before a rollout replaces the pod. An exit code of 137 can mean several signals; a recorded termination reason is stronger evidence.

</details>

<details>
<summary>Hint 2 — Compare workload size and memory limit</summary>

Run `kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" get deployment app -o yaml`. Read the Python allocation and the memory limit together. These units are binary: 64Mi means 64 × 1024 × 1024 bytes.

</details>

<details>
<summary>Hint 3 — Bound the input</summary>

Keep the existing 64Mi container limit; make the allocation fit. Merely increasing the limit can transfer the failure to the node. The answer uses an 8MiB allocation and preserves it while the process sleeps.

</details>


Make the repair in the working `candidate.yaml`, then review and apply a saved Terraform plan. Diagnostic reads, logs, and HTTP requests are evidence; they are not a separate configuration path.
