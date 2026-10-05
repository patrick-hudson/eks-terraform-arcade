# Practice before using AWS

`arcade check` runs a small set of tests against your work. It currently supports Game00's Terraform service contract and Game05's Python handler. The tests come from this repository, so editing a test inside your practice folder cannot make a broken solution pass.

From any directory, after the tools are on your PATH:

```bash
source "$(arcade root)/scripts/env.sh"
arcade start 00
arcade check 00
```

The starter is broken on purpose. Read the failing check, edit `main.tf` in `$LAB_ROOT/run/00-contracts`, then run `arcade check 00` again. A failing check is feedback for the exercise.

For Game05, create your `handler.py` first or prepare the guided version:

```bash
arcade start 05 --mode guided
arcade check 05
```

If a Game05 workspace already exists in starter mode, keep working in that folder; the launcher refuses to overwrite it with guided code. Write its missing `handler.py`, then check it. To check another folder, pass its path explicitly:

```bash
arcade check 05 --workspace "$HOME/practice/counter"
arcade check 00 --workspace "$LAB_ROOT/run/00-contracts" --json
```

| Check | What it tells you | What it does not prove |
| --- | --- | --- |
| `00` | Eight Terraform **plan** tests check stable service names, both memory allocations, and rejected invalid inputs. “Stable” means reordering your input list does not rename the resources. | Nothing is applied. AWS behavior is not tested. |
| `05` | Three Python tests check invalid counter names, a missing table setting, and converting a fake DynamoDB response into the expected result. | IAM permissions, the Lambda deployment, real table writes, and behavior under concurrent requests still need the lab's AWS checks. |

The runner copies only `main.tf` and `variables.tf` for Game00, or `handler.py` for Game05, into a temporary folder. Other source files are not included. Keep these small exercises in those files. Existing state, saved plans, local tests, and `.terraform` folders stay in your workspace and are not used or changed by the runner.

Game00 disables backend setup, module downloads, and external provider installation; it uses Terraform's built-in `terraform_data` resource. Every trusted test must explicitly request `command = plan`. Game05 uses a fake `boto3` client instead of calling AWS. Both run with a temporary home directory and empty AWS configuration, without inheriting your AWS credentials, `TF_VAR_*` values, or Python import settings. Each command has a 60-second limit and a 64 KiB output limit.

This is a convenience for practicing code you trust, **not a security sandbox**. Your Terraform expressions and Python code still run on your computer. The runner does not block all network access or stop intentionally written code from reading other files.

Exit status `0` means the local tests passed, `1` means a check failed or reached its time/output limit, and `2` means it could not start because a file or prerequisite was missing or unsupported. The JSON report is local feedback; it is not a live AWS verification receipt and does not mark a mission complete in the web app. Follow the lab's live acceptance and cleanup steps afterward.
