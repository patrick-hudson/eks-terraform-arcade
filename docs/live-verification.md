# Check real lab results

The experimental verifier connects your terminal's observations to the guided workspace. It supports Game 07, Game 08, and the eight individual Game 11 incidents. It runs fixed, read-only AWS and Kubernetes commands; it never applies a manifest, repairs a workload, evicts a pod, or deletes a resource.

## The practice loop

1. Complete the mission's authenticated setup in your terminal.
2. Open **Verify** in the workspace and expand **Generate a verification receipt**. Run the displayed command while the fixture is broken to capture a baseline.
3. Import its JSON file. Failed checks show expected and observed values. An **error** means the check could not establish a result, such as an authorization failure; it is not evidence of absence.
4. Repair your working copy, run the same verifier again, and import the new report. The workspace compares changed check statuses for the same account, region, cluster, context and phase.
5. Complete the runbook's remaining acceptance checks. The verifier does not inspect every property or replace the interview reasoning tasks.
6. Run the runbook's teardown. Generate and import a **Cleanup** receipt afterward. Read the scope statement: namespace absence proves less than deletion of an entire AWS environment.

The latest three verification reports and three cleanup reports are retained per mission in browser storage. Reports appear in progress backups and interview debrief exports. Starting a new attempt retains this evidence history; always inspect its observation time. Importing a receipt never ticks your checkboxes or marks a mission complete. An older import selects that report if retained; if three newer reports already exist for that phase, the import is rejected with an explanation. Timestamped command outputs keep terminal files from overwriting your baseline.

## Terminal identity

The verifier requires an explicit profile, expected 12-digit account ID, region, cluster name, and kubeconfig context. It checks the caller's account and compares the kubeconfig server with the named EKS cluster's endpoint before inspecting workloads. The CLI does not read application Secrets or collect application logs into the report.

Use the command generated in the mission. To inspect the available arguments without calling AWS:

```bash
arcade verify --help
```

For a first cloud test, follow [Connect AWS for testing](aws-testing.md). That guide prepares a small Lambda/DynamoDB test before creating an EKS cluster.

## Meaning and limits

A report is a **point-in-time observation** from a local command. A green deployment does not establish that real users can reach a Service, that an eviction was successfully performed, that Terraform has no drift, or that every cloud resource was deleted. Each report states its coverage; full acceptance remains in the runbook.

Reports are editable JSON, not signed attestations. The importer validates their shape, mission, timestamps, result counts and supported version. It cannot authenticate who created a file or determine whether its observations are truthful. Nothing is uploaded: the browser reads the selected file locally, and the web server still cannot execute terminal commands.

The verifier's runner and observation logic are covered by mocked command-response tests. Until a live session is recorded in the validation document, these checks have not been exercised against a real EKS cluster.
