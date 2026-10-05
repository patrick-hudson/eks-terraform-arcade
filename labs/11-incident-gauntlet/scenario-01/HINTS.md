# Progressive hints

Open the next hint only after testing the previous one.

<details>
<summary>Hint 1 — Classify the failure</summary>

Has the scheduler assigned a node? Did the application ever start? Events are more useful than application logs here.

</details>

<details>
<summary>Hint 2 — Inspect the resolved image</summary>

Run `kubectl --context "$LAB_KUBE_CONTEXT" -n "$NS" get deployment app -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'`. Compare the registry/tag with a known published image. ImagePullBackOff can also mean authentication, network, or architecture problems; the event narrows it.

</details>

<details>
<summary>Hint 3 — Find the suspicious field</summary>

The image tag in the pod template is deliberately invalid. Keep the repository and use the published Python 3.14.8 Alpine tag used by the other exercise manifests. A new Deployment revision is a cleaner repair than deleting the pod.

</details>


Make the repair in the working `candidate.yaml`, then review and apply a saved Terraform plan. Diagnostic reads, logs, and HTTP requests are evidence; they are not a separate configuration path.
