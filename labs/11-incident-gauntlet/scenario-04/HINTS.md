# Progressive hints

Open the next hint only after testing the previous one.

<details>
<summary>Hint 1 — Separate lifecycle from traffic eligibility</summary>

A running process does not imply a ready Service backend. Inspect pod readiness, probe events, and EndpointSlices.

</details>

<details>
<summary>Hint 2 — Compare the actual HTTP endpoints</summary>

Run `kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" exec deployment/app -- python -c 'import urllib.request; print(urllib.request.urlopen("http://127.0.0.1:8080/").status)'`. Compare that URL to the configured readiness path. This checks the process directly without requiring Service readiness.

</details>

<details>
<summary>Hint 3 — Keep a useful probe</summary>

The simple HTTP server provides a successful root path but no custom health endpoint. Correct readiness to a real endpoint; do not remove readiness or change the Service to publish unready addresses.

</details>


Make the repair in the working `candidate.yaml`, then review and apply a saved Terraform plan. Diagnostic reads, logs, and HTTP requests are evidence; they are not a separate configuration path.
