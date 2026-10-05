# Progressive hints

Open the next hint only after collecting evidence for the previous one. Keep each proposed repair in your working `candidate.yaml`, then use Terraform plan and apply.

<details>
<summary>Hint 1 — Draw the actual request path</summary>

A Ready pod proves one probe reached one listener. Compare a request to the pod's own listener, a request to its Pod IP, and a request to the Service name. Record the response or error for each. Which hop is the first one that fails?

</details>

<details>
<summary>Hint 2 — Resolve the Service all the way to a socket</summary>

Read the Service and its EndpointSlice ports. Compare them with the container's named port and the port its process actually binds. A populated EndpointSlice is a routing description, not evidence that its destination socket accepts connections. DNS resolution and selector matching can both work while the HTTP request fails.

</details>

<details>
<summary>Hint 3 — Repair the contract between Service and application</summary>

The server listens on 8080. The Service accepts 8080 but forwards to 8081. Set the Service's `targetPort` to the container's named `http` port in `candidate.yaml`; review the Terraform plan and apply it. Repeat the same client requests. A correct selector or a pod restart does not repair a wrong destination port.

</details>
