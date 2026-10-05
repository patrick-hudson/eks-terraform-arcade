# Plain-English field guide

Use this when a lab uses an unfamiliar term. The goal is to explain what you observed and why your change works. You do not need to recite these definitions in an interview.

## Terraform and AWS

| Term | What it means in these labs |
|---|---|
| **Terraform root / workspace directory** | The directory where you run Terraform. It contains the source and has its own state. Here, “workspace” usually means a directory under `run/`, not Terraform's named-workspaces feature. |
| **State** | Terraform's record connecting resource addresses in your code to real objects. Keep it until cleanup is verified. Deleting state does not delete AWS resources. |
| **Resource address** | Terraform's name for one managed object, such as `aws_lambda_function.counter`. A `for_each` key becomes part of that address. |
| **Plan** | The proposed changes between the source, recorded state and observed resources. Review `terraform show lab.tfplan` before applying that saved plan. |
| **Provider** | Terraform's adapter for an API, such as AWS or Kubernetes. A provider knows how to read, create, update and delete that API's objects. |
| **Module** | A reusable group of Terraform resources. The Kubernetes exercise module reads your `candidate.yaml`; the root around it supplies the account and cluster connection. |
| **Backend** | Where Terraform stores state and, when supported, coordinates its lock. A backend can be local storage or an S3 bucket. |
| **Drift** | A real resource differs from the source because something changed outside the normal Terraform apply. A normal plan helps you see and repair that difference. |
| **Import** | Tell Terraform that an existing object belongs to a particular resource address. Import only the explicitly created lab fixture, never an unrelated shared-account resource. |
| **IAM role / permissions boundary** | A role is an AWS identity that can be assumed. Its policies grant actions; a permissions boundary limits what those policies may grant. Trust controls who may assume it. |
| **Security group / CIDR / `/32`** | A security group filters traffic for attached AWS network interfaces. A CIDR describes an address range; IPv4 `/32` names exactly one address, such as your laptop's current public IP. |
| **VPC / subnet / route** | A VPC is an isolated AWS network. A subnet is an address range inside it. A route says where traffic for a destination should go; it does not itself grant permission or create a public IP. |
| **Atomic / duplicate-safe request** | An atomic increment does not lose simultaneous updates. It can still count a retry twice. Recognizing a request ID already processed is a separate behavior, often called idempotency. |

## Kubernetes and EKS

| Term | What it means in these labs |
|---|---|
| **EKS control plane / worker node** | The control plane runs Kubernetes management APIs and controllers. A worker is the EC2 machine that runs your app's pods. Removing pods does not stop either one's billing. |
| **Context / namespace** | A context selects a cluster and identity for `kubectl`. A namespace groups resources within that cluster. The exercises use distinct namespaces, but namespace separation alone is not a security boundary. |
| **Pod / container image** | A pod is Kubernetes's unit of scheduling, with one or more containers. An image is the packaged application. The worker must download the image before it can start the process. |
| **Deployment / replica / rollout** | A Deployment maintains the requested number of app copies, called replicas. A rollout replaces those copies when their settings change. An accepted update can still get stuck. |
| **Service / selector / EndpointSlice** | A Service supplies a stable app address. Its selector matches pod labels. EndpointSlices list the selected destination addresses, ports and readiness; inspect all three when requests fail. |
| **ClusterIP / NodePort** | ClusterIP exposes a Service inside the cluster. NodePort also listens on a worker port and forwards to that Service. AWS routing and ingress rules must still permit external clients. |
| **`port` / `targetPort` / `nodePort`** | `port` is the Service's port; `targetPort` is the destination port on the app; `nodePort` is the worker port used for NodePort access. Game 13 follows `30080 → 80 → 8080`. |
| **Readiness / liveness probe** | Readiness asks whether this pod should receive traffic. Liveness asks whether its container should restart. Removing a failing check hides the symptom instead of proving the app is healthy. |
| **Request / limit / allocatable capacity** | A request reserves capacity when Kubernetes picks a worker. A limit caps consumption. Allocatable is the worker capacity available to pods after system reservations. Low current use does not erase requests. |
| **ConfigMap / ServiceAccount / RBAC** | A ConfigMap stores ordinary configuration. A ServiceAccount is a pod's Kubernetes identity. RBAC rules define which API actions that identity can perform. Do not put secrets in a ConfigMap. |
| **Job / replacement** | A Job runs a task to completion. A failed Job does not automatically rerun after an outside permission changes. These labs use Terraform to replace it when another execution is required. |
| **Pod Identity** | EKS connects a namespace and ServiceAccount to an AWS role so the workload can obtain temporary AWS credentials. Its Kubernetes permissions remain a separate concern. |
| **PVC / PV / StorageClass / CSI** | A PVC is the app's disk request. A PV represents its backing storage. A StorageClass describes how to provision it. The CSI driver performs the disk operations in AWS. A disk may exist outside the foundation's Terraform state. |
| **PDB / eviction** | A PodDisruptionBudget limits voluntary pod removals, such as planned maintenance evictions. It does not prevent worker failures or control a Deployment's rollout strategy. The PDB repair uses Terraform; the test eviction is the maintenance operation being demonstrated. |
| **Port-forward** | A temporary tunnel through the Kubernetes API to an app. It is useful for inspection, but bypasses parts of the normal Service or public path. It cannot prove internet reachability. |

If a command succeeds, ask what it actually proved. A schema check proves shape, an apply proves API acceptance, and a real HTTP request proves a particular client could reach a particular response at that time. Keep those claims separate in your debrief.
