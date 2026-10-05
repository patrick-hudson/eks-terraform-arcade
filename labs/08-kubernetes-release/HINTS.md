# 08 · Layered hints

<details><summary>Hint 1 — Separate lifecycle from traffic</summary>

Check `READY`, `STATUS`, restart count and Pod events separately. Is the process exiting, failing image pulls, failing to start, or alive but excluded from traffic?
</details>

<details><summary>Hint 2 — Compare the observed response with the configured contract</summary>

Inspect the probe events and the application access log. Which HTTP request is failing? Does this image serve that path? Is the Service selecting the same label as the Deployment?
</details>

<details><summary>Hint 3 — Fix the smallest durable mismatch</summary>

The liveness probe and readiness probe do not hit the same path. Verify which path nginx serves. Keep both probes but make the readiness contract valid. Edit the working `candidate.yaml`, review the saved Terraform plan, then apply it. Keep the module as the only writer of workload configuration.
</details>
