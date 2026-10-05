# AWS Interview Arcade · Terraform + EKS

Practice diagnosing failures, judging Terraform changes and explaining your decisions before spending money on AWS. Then build small systems, prove the repair works and tear them down.

**31 exercises for mid–senior DevOps, platform and SRE interviews:** 24 existing hands-on missions (14 labs and 10 pod incidents) plus **7 simulated drills**. The drills use authored evidence; finishing one does not verify a live environment or complete a hands-on mission.

## Try one exercise — no AWS setup

You need **Python 3.10+**, Bash and Git. No AWS credentials, downloaded lab tools, pip packages or Node installation are needed for the Practice desk.

```bash
git clone https://github.com/patrick-hudson/eks-terraform-arcade.git
cd eks-terraform-arcade
./arcade serve
```

Open **[the Practice desk](http://127.0.0.1:8765/#/practice)**. Choose an investigation, reveal an observation, make a decision, then select **Finish attempt** to save its summary. The desk has four investigations and three Terraform plan-reading drills. Keep this terminal running while using the browser; Ctrl-C stops the local server.

![Actual browser capture of the purple Practice desk and its simulated exercises](docs/images/practice-desk.png)

Already have a checkout or extracted ZIP? Open its directory and run `./arcade serve`. The root entry works before PATH activation. From elsewhere, use the entry's absolute path, such as `"/path with spaces/eks-terraform-arcade/arcade" help`.

## Use the full terminal workspace

In another terminal, from the checkout:

```bash
./arcade tui
```

Browse missions and simulated drills, inspect prerequisites, prepare practice files and manage supported Terraform environments in a full-screen interface. Use arrows and Enter to navigate; the screen shows help, back and quit controls. Python's standard-library `curses` and an interactive terminal are required. See the [terminal guide](docs/tui.md) for controls and recovery.

![Actual terminal recording of the arcade TUI](docs/images/tui.gif)

This is an actual terminal recording. Terminal lifecycle actions support Games **00, 01, 03, 04, 05, 07, 08 and incidents 11-01 through 11-10**. Games **02, 06, 09, 10, 12 and 13** hand off to their runbooks for environment operations; Game 11 is the incident directory. Paid operations need an explicitly selected account/profile/region, a reviewed saved plan and typed approval. The interface shows prerequisite setup order; preparing files alone does not establish live readiness.

For a short command-line practice session:

```bash
./arcade drill list
./arcade drill show ID
./arcade drill evidence ID EVIDENCE_ID
./arcade drill answer ID OPTION_ID
```

Use IDs printed by the preceding command. CLI drills are stateless; browser attempts are saved separately. `./arcade review-plan PATH` reads local Terraform show JSON and reports actions and uncertainty without displaying plan values or approving an apply. [The workspace guide](docs/web-ui.md) explains history and backups.

## Optional: install tools for hands-on labs

The installer and workspace preparation support **Linux and WSL2**. The installer needs Bash, Python 3.10+, curl, unzip, tar, GPG and sha256sum already installed. Other platforms can use the browser and the [manual setup guide](docs/setup.md).

```bash
./arcade setup
source scripts/env.sh
./arcade doctor
```

Verified downloads go under this project's `.tools/`. Setup needs no sudo, does not edit shell startup files and does not sign you into AWS. Source `scripts/env.sh` in each lab terminal. Follow [account preflight](docs/setup.md) to choose a named profile, intended account and **us-west-2** before cloud work.

Start with a local-only Terraform exercise:

```bash
./arcade start 00
./arcade check 00
./arcade next 00
./arcade status
```

Game 00 starts broken, so its first check should fail. Edit `run/00-contracts/` and rerun the check. `./arcade start 05 --mode guided` prepares reference code for a walkthrough. Repeating `start` preserves registered edits and state; preparation never applies resources. Follow each printed working directory and prerequisite runbook before continuing. The [launcher guide](docs/lab-launcher.md) covers preparation modes.

## Choose your game

| Game | Mission | Time box | Practice mode |
|---|---|---:|---|
| [00](labs/00-terraform-contracts/README.md) | Terraform types, stable resource names and input checks | 30–45m | Local broken start; $0 AWS |
| [01](labs/01-private-s3/README.md) | Private versioned S3 and complete cleanup | 35m | Build |
| [02](labs/02-remote-state/README.md) | Shared state, locking and recovery | 45m | Build + competing runs |
| [03](labs/03-vpc-routing/README.md) | Public/private subnet routes without a NAT gateway | 45m | Build + explain traffic paths |
| [04](labs/04-iam-boundaries/README.md) | Find why an IAM permission still denies access | 45m | Broken start |
| [05](labs/05-serverless-counter/README.md) | Lambda, DynamoDB, narrow permissions and logs | 45–60m | Broken start |
| [06](labs/06-state-rescue/README.md) | Import, unexpected changes and safe refactoring | 45m | Three recovery drills |
| [07](labs/07-eks-foundation/README.md) | Build one short-lived EKS cluster with Terraform | 45–60m | Shared cluster |
| [08](labs/08-kubernetes-release/README.md) | App rollout, health checks, traffic and access | 40m | Broken start |
| [09](labs/09-pod-identity/README.md) | Let a pod access exactly the S3 data it needs | 40m | Broken start |
| [10](labs/10-ebs-storage/README.md) | Attach storage, preserve data and remove its AWS disk | 40m | Broken start |
| [11](labs/11-incident-gauntlet/README.md) | Ten isolated incidents on the same cluster | 10–25m each | Debugging gauntlet |
| [12](labs/12-capstone/README.md) | Timed delivery, incident, change and cleanup interview | 90m | Integrate and explain |
| [13](labs/13-public-access/README.md) | Healthy pods, broken internet access | 25–35m | Trace and repair the public path |

The gauntlet covers image pull failures, missing configuration, crashes, scheduling, health checks, traffic selection, permissions, safe maintenance, Service ports and a stalled update. Incident titles do not give away the answer. Each has three progressive hints and a reference repair.

Times are practice time boxes; provisioning and deletion take additional billable time. Stretch questions ask you to explain production choices unless they explicitly say to deploy something.

## Repair, verify and clean up

The browser follows **Brief → Build → Investigate → Verify → Cleanup**, with progressive hints and an evidence notebook. Save the symptom, decisive observation, Terraform repair, recovery proof and deletion evidence. Back up progress before clearing browser data. The [glossary](docs/glossary.md) explains terms in plain English.

Every durable repair goes through Terraform. AWS repairs change `.tf` files or inputs. Kubernetes repairs change `candidate.yaml`, which the shared Terraform module manages; use `kubectl` for diagnosis. After following the mission's setup and moving into its **own run directory**, review the saved plan:

```bash
terraform init
terraform validate
terraform plan -out=repair.tfplan
terraform show repair.tfplan
terraform apply repair.tfplan
```

Use the mission's exact flags and inputs, then run its behavioral checks. A clean plan or healthy pod does not prove users can reach the app. Game 13 requires an actual internet `curl` to the node's public address, restricted to your current IPv4 `/32`, followed by proof that access closes after teardown. It reuses the worker without a load balancer or NAT gateway. See [Terraform-managed workloads](docs/terraform-workloads.md).

## Keep the whole course within $20

The planning allowance is **$20 total**, with an estimated spend below $5 for the suggested short sessions in **us-west-2**. This is an estimate, not an enforced cap. Prices, retries and forgotten resources affect the bill; use the [cost guide and session ledger](docs/cost-and-cleanup.md).

1. Work through Games 00–06 first, tearing down each cloud fixture when finished.
2. Build Game 07 once per EKS session and reuse it for the workloads and incidents. Aim for about eight total cluster-hours across short sessions.
3. Keep the default one worker, with no NAT gateway or load balancer. Reserve time for deletion.

In a shared account, use distinct lab names, confirm the intended account and inspect every plan. Only manage resources owned by the lab's state. Never import, modify or delete unfamiliar resources to make an exercise pass.

Follow the mission's cleanup order, then review a saved destroy plan from that same state directory:

```bash
terraform plan -destroy -out=destroy.tfplan
terraform show destroy.tfplan
terraform apply destroy.tfplan
terraform state list
```

For EKS, remove public access and workloads while the cluster is reachable; verify storage disks are gone before removing their driver, then remove identities/add-ons and the foundation. Follow the [complete cleanup sequence](docs/cost-and-cleanup.md) for nested states and the remote backend. Keep state and inputs until AWS deletion checks succeed. **Closing the app or terminal, stopping a timer or deleting local files does not stop AWS charges.**

## Evidence and further reading

Simulated feedback, local Terraform observations and live cloud evidence are different. This release adds no AWS resources, and offline checks do not prove live IAM permissions, EKS behavior, managed Lambda execution, internet reachability or deletion. The [validation record](docs/VALIDATION.md) states what was executed and what still needs a real account; the [AWS smoke-test guide](docs/aws-testing.md) describes scoped live checks. Tool versions and support limits are in the [toolchain record](docs/toolchain.md).

[Development and CI](docs/development.md) · [Interview scorecard](docs/interview-scorecard.md) · [Learning design](docs/learning-design.md) · [Third-party notices](web/THIRD_PARTY_NOTICES.md)

Keep state, plans, credentials and personal `.tfvars` out of Git and shared progress backups. Keep provider lockfiles. Your practice files and state belong under `run/`; authored missions are under `labs/`, and simulated drills under `practice/`.
