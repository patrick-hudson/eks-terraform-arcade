# Practice before provisioning

The Practice desk contains seven authored simulations: four investigations and three Terraform plan reviews. Python is enough to use them. No AWS credentials, cluster, Terraform installation or paid resources are required. The displayed commands and outputs are teaching material; opening an observation never runs a command.

Start the browser with `./arcade web`, then choose **Practice desk**, or use the same content from the terminal:

```bash
./arcade drill list
./arcade drill show service-request-a
./arcade drill evidence service-request-a service
./arcade drill evidence service-request-a pods
./arcade drill answer service-request-a selector
```

The final line submits a choice. Try choosing your own answer after reading the brief and observations. Use `python3 scripts/drill.py` in place of `./arcade drill` to call the Python entry point directly. Both entry points find the catalog relative to this checkout, so an absolute path to either entry point works from another directory.

## Investigate before changing

Each investigation starts with a symptom, offers several observations and asks for the best supported diagnosis and Terraform repair. The two Service cases share a symptom; the two Pending-pod cases do too. Their titles and briefs do not reveal the causes. Comparing each pair trains you to distinguish plausible explanations rather than memorize one fix per symptom.

| Drill | Decision to practice | Related live missions |
| --- | --- | --- |
| `service-request-a`, `service-request-b` | Trace a failed Service request from client to backend | [Game 08](../labs/08-kubernetes-release/README.md), [Incident 04](../labs/11-incident-gauntlet/scenario-04/README.md), [Game 13](../labs/13-public-access/README.md) |
| `pending-pod-a`, `pending-pod-b` | Separate scheduling constraints from storage and startup failures | [Incident 05](../labs/11-incident-gauntlet/scenario-05/README.md), [Game 10](../labs/10-ebs-storage/README.md) |
| `plan-replacement-order` | Explain replacement and its order | [Game 00](../labs/00-terraform-contracts/README.md) |
| `plan-address-change` | Distinguish an address change from a move | [Game 06](../labs/06-state-rescue/README.md) |
| `plan-incomplete-evidence` | Identify what an incomplete plan does not establish | [Game 06](../labs/06-state-rescue/README.md) |

An observation reveals only the item you selected. There is no penalty for inspecting more evidence. A valid answer returns the decisive observation IDs, an explanation, the source repair, recovery evidence, cleanup considerations and a changed-constraint interview prompt. An incorrect choice receives the same useful debrief. The authored files are available in the checkout; hiding answers until submission is a teaching boundary, not examination security.

Repairs stay in Terraform source. In the Kubernetes missions, `candidate.yaml` is an input to the Terraform module, so editing it and reviewing a saved Terraform plan keeps changes reproducible. The simulations do not authorize applying that plan or changing your account. Use the matching live mission's setup and verification instructions; the invented case names and addresses are not a script to run against your cluster.

## Keep evidence claims precise

**Authored simulation:** Choosing an answer shows that your conclusion fits these invented observations. It does not check a real cluster, prove mastery or complete any of the 24 live missions.

**Local Terraform observation:** A real local plan can establish proposed actions and known metadata. It cannot prove application recovery, resource ownership, current price or safe cleanup. The separate local plan reader accepts a file or standard input:

```bash
./arcade review-plan /path/to/plan.json --json
# With an existing Terraform workspace and saved plan:
terraform show -json /path/to/saved.tfplan | ./arcade review-plan -
```

Plan JSON may contain sensitive values. The reader reports allowed action metadata and uncertainty without displaying resource values; it does not upload plans, store them in practice history or offer a browser upload route. The command above that invokes Terraform is an explicit action you run yourself. See [the plan review guide](plan-review.md) for the reader's limits.

**Live cloud evidence:** The live mission's observations establish the particular behavior tested. A ready Pod alone does not prove Service traffic. A successful in-cluster HTTP request does not prove public internet access; [Game 13](../labs/13-public-access/README.md) requires an actual external HTTP request from your workstation. A bound claim does not prove persistence through replacement, and an empty Terraform state does not prove CSI-created EBS volumes were deleted.

When you choose live practice, retain the **$20 total allowance**, prefer **us-west-2**, and verify the intended account, profile, region, workspace and ownership before any paid action. The account may contain unrelated resources. Destroy only the resources owned by the mission, preserve controllers until their dependent resources have been cleaned up, and verify deletion rather than treating a closed terminal as cleanup. Start with [setup](setup.md) and the mission's prerequisites.

## Repetition and saved attempts

The CLI is stateless: list, show, evidence and answer never save an attempt or modify the authored catalogs. You can repeat any request in any order.

The browser owns practice history in its local progress storage. **Finish attempt** saves one summary; refreshing, revisiting or requesting feedback does not finish it. **New attempt** starts a separate attempt and clears the current evidence and feedback. Up to 20 completed summaries are kept, and the existing progress export/restore includes practice history alongside the separate live mission records. Browser storage is editable and may be unavailable; exporting a backup is useful, but it does not certify work.

The suggested repeat has a visible reason: first an incorrectly answered completed drill, then a drill never attempted, then the least recently completed drill. You can choose any drill instead. Answer correctness, time and number of observations are practice context, never a cloud-health or mastery score.

## CLI and integration contract

Every operation supports `--json`:

```bash
./arcade drill list --json
./arcade drill show pending-pod-a --json
./arcade drill evidence pending-pod-a nodes --json
./arcade drill answer pending-pod-a cpu-request --json
```

Invalid drill, observation or option IDs and malformed authored catalogs return a concise error and nonzero exit. JSON errors use `{"status":"error","message":"..."}`. Commands are display text even if locally edited to resemble executable code.

Both authored catalogs, `practice/cases.json` and `practice/plan-drills.json`, use schema version 1. The shared Python module exports `list_drills(root=ROOT)`, `public_drill(drill_id, root=ROOT)`, `evidence(drill_id, evidence_id, root=ROOT)` and `answer(drill_id, option_id, root=ROOT)`. The browser's read-only routes call these same operations:

| Operation | HTTP route | Returned teaching content |
| --- | --- | --- |
| List | `/api/drills` | `{schemaVersion: 1, drills: [...]}` with card metadata |
| Brief | `/api/drill?id=ID` | Brief, observation choices and answer options; no outputs or answer key |
| Evidence | `/api/drill-evidence?id=ID&evidence=EVIDENCE_ID` | One requested observation, its drill ID and simulation provenance |
| Answer | `/api/drill-answer?id=ID&answer=OPTION_ID` | Correctness, selected and correct option IDs, decisive evidence IDs and debrief |

Each required query parameter appears exactly once; unknown or repeated parameters fail. The engine reads only the two fixed authored catalogs and their referenced mission README files using regular-file checks that reject symlinks. It validates IDs and references before serving the catalog. It does not execute commands, contact AWS, evaluate free-form prose or read learner Terraform plans.
