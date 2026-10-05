# 09 · Layered hints

<details><summary>Hint 1 — Identify the failing layer</summary>

A missing-credentials message happens earlier than an S3 AccessDenied. First ask whether the Pod received a workload identity. Do not widen S3 permissions before you know which identity made the request.
</details>

<details><summary>Hint 2 — Compare three exact strings</summary>

Pod Identity binds a cluster, namespace and service-account name. Read `spec.serviceAccountName` from the live Job Pod, then compare it with `aws eks list-pod-identity-associations`. Kubernetes service accounts may exist without any IAM association.
</details>

<details><summary>Hint 3 — Admission happened when the Pod was created</summary>

The reference association names `reader`. The failing Job chooses an older identity. Repair `serviceAccountName` in the workload `candidate.yaml`, then inspect Terraform's planned Job replacement and apply it. Existing Pods are not retroactively mutated when you change an association.
</details>
