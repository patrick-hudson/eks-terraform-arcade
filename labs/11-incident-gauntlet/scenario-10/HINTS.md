# Progressive hints

Open the next hint only after testing the previous one. Make the repair in your working `candidate.yaml` and apply it through Terraform.

<details>
<summary>Hint 1 — Compare the old and new replicas</summary>

Inspect the Deployment, ReplicaSets, pod events, and the marker returned by the Service. Is the new process crashing, or has the new pod never obtained a node? An old replica can keep serving while its replacement fails to become available.

</details>

<details>
<summary>Hint 2 — Budget requests during the transition</summary>

Read the node's allocatable CPU and requested CPU. Use requests, not observed CPU usage. Compare the number of pods the rollout can create with how many it may make unavailable. One copy fits; can two copies fit simultaneously after kube-system reservations? Increasing a progress deadline cannot create capacity.

</details>

<details>
<summary>Hint 3 — State the availability tradeoff</summary>

This lab has one worker and one replica requesting 1000m CPU. `maxSurge: 1` asks for a second 1000m replica before removing the first, while `maxUnavailable: 0` forbids removing the old one first. Keep the same CPU request and worker count; set `maxSurge: 0` and `maxUnavailable: 1`, then apply through Terraform. This accepts a brief outage. Production alternatives include validated lower requests or budgeted spare capacity, but neither is the exercise's repair.

</details>
