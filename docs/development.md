# Develop and verify the arcade

The app is plain HTML, CSS and JavaScript served by Python's standard library. There is no build step or package installation. Use Python 3.10+ for the app and Node 18+ for JavaScript tests. The bootstrap installs the pinned Terraform binary; Node is a separate development dependency.

From the project root, start the app with `python3 web/server.py`. Reload the page after editing existing source documents or frontend files. Restart the server after changing playbooks or adding inventory paths, then reload the page. The server reads its allowed source paths from `MANIFEST.sha256`, so add new deliverables to the packaging inventory and rebuild it before checking new missions in the browser.

## Run the local checks

```bash
source scripts/env.sh
export PYTHONDONTWRITEBYTECODE=1
python3 -m unittest discover -s web/tests -p 'test_*.py' -v
python3 -m unittest discover -s scripts/tests -p 'test_*.py' -v
python3 -m unittest discover -s labs/05-serverless-counter/solution -p 'test_*.py' -v
python3 -m unittest discover -s labs/10-ebs-storage/tests -p 'test_*.py' -v
python3 -m unittest discover -s labs/13-public-access/tests -p 'test_*.py' -v
node --test web/tests/*.test.cjs
python3 scripts/lab_manager.py labs --json
```

The tests create temporary fixtures and use fake AWS/Kubernetes responses. HTTP server tests bind an available loopback port. The local rehearsal tests run a real Terraform binary when available and check both the broken and repaired Game 00 code. No test needs AWS credentials. A skipped Terraform test is a coverage gap; install the pinned binary to run it.

To inspect the Terraform fixtures themselves:

```bash
terraform fmt -check -recursive labs
terraform fmt -check -recursive modules
terraform -chdir=labs/00-terraform-contracts/solution init -backend=false -input=false
terraform -chdir=labs/00-terraform-contracts/solution test
terraform -chdir=modules/kubernetes-exercise init -backend=false -input=false -lockfile=readonly
terraform -chdir=modules/kubernetes-exercise validate
ARCADE_TEST_LOG=$(mktemp)
terraform -chdir=modules/kubernetes-exercise test -json -verbose > "$ARCADE_TEST_LOG"
python3 modules/kubernetes-exercise/tests/assert-replacements.py "$ARCADE_TEST_LOG"
rm -- "$ARCADE_TEST_LOG"
```

Provider initialization downloads dependencies but does not provision infrastructure. The workload tests use Terraform's mocked Kubernetes provider, including a simulated apply followed by a repair plan. The replacement check verifies that immutable Job and StorageClass changes create replacement objects without replacing their namespace. It does not contact an EKS API server.

`bash scripts/check-local.sh` additionally initializes and validates the complete AWS solution roots. It downloads providers; it does not plan or apply AWS infrastructure. Deliberately broken starter configurations are not all expected to validate.

## Add or change a mission

1. Write the mission, acceptance checks, cleanup steps, hints and reference repair under `labs/`. Keep the starting failure intentional and explain the observed symptom before introducing terminology.
2. Add the mission to the four-column table in the root README. The catalog reads its duration and practice mode from that table.
3. Add an explicit recipe in `lab-recipes.json`. List only authored files to copy, identify separate Terraform state directories and show the commands. The launcher must never execute those command strings or overwrite existing state.
4. Add the five stages, three progressive hints and reasoning check to `web/playbooks.json`. Keep answers out of the public lesson response until the learner requests feedback.
5. Use the shared workload module for Kubernetes exercises. Repairs edit `candidate.yaml` and use Terraform. `kubectl` supplies diagnostics and the runbook's explicit operational tests.
6. Add meaningful coverage for the changed behavior, then check the actual browser at desktop and narrow widths. Test a failed state as well as the repair, and preserve existing learner progress during browser checks.

A private in-cluster response, a port-forward and a public internet response prove different traffic paths. State which one the exercise requires. A cleanup check must distinguish “deleted” from “could not inspect because access was denied.” Shared-account inventory is evidence to investigate, never a list to delete indiscriminately.

## Package only authored files

The packaging script combines the existing manifest with its explicit `ADDED_FILES` list. Add new public files there; do not use a broad recursive archive command.

```bash
python3 scripts/package-kit.py
sha256sum --check --quiet MANIFEST.sha256
git status --short
```

Review the inventory and archive before publishing. Keep `run/`, `work/`, `.tools/`, credentials, state, plans and personal variable files out of both Git and the ZIP. Include provider lockfiles and third-party notices. Screenshots belong in `docs/images/` and should show the teaching interface without account IDs or private terminal output.

## Continuous integration and its limits

[The CI workflow](../.github/workflows/ci.yml) runs on pull requests, pushes to `main` and manual dispatch. It checks the manifest, local Python/JavaScript suites, recipe structure and referenced files, shell syntax, Terraform formatting and mocked workload plans. It uses Python 3.14, Node 24 and Terraform 1.16.5. No AWS credentials, cloud-login action or deployment step is configured.

The action releases were verified on October 4, 2026 and pinned to complete commit IDs: [checkout v7.0.1](https://github.com/actions/checkout/releases/tag/v7.0.1), [setup-python v7.0.0](https://github.com/actions/setup-python/releases/tag/v7.0.0), [setup-node v7.0.0](https://github.com/actions/setup-node/releases/tag/v7.0.0) and [setup-terraform v4.0.1](https://github.com/hashicorp/setup-terraform/releases/tag/v4.0.1). Review their upstream release notes before updating those pins.

Passing CI proves the tested local behavior. It cannot prove live IAM permissions, Kubernetes admission, available node capacity, image pulls, public internet reachability or AWS deletion. Record those results separately using the [AWS smoke-test guide](aws-testing.md) and [validation record](VALIDATION.md). Do not describe a mocked plan as a deployed cluster.
