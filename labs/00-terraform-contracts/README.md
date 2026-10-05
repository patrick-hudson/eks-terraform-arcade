# 00 · Terraform contract clinic

**35–45 minutes · mid-senior · $0 · no AWS credentials needed.** Start here to practice reading a Terraform failure without a cloud bill. The supplied starter is broken before its first apply. Your mission is to make it pass while keeping the public input contract unchanged.

The platform accepts a list of services with `name` and `memory_mib`. Create one `terraform_data.service` instance per service, keyed by service name. Export an `allocations` map. Service order must not control identity. Keep all supplied validation: unique nonempty names, valid identifiers, memory in 64 MiB units, and a 4096 MiB aggregate ceiling. Use the provided default services. Do not replace the input with a different type just to silence the error.

Explain these choices as if reviewing a teammate's PR: why identity matters; which values must be known during planning; where validation belongs; what changes when a service is renamed. Record the first error, your hypothesis and the smallest fix before opening [HINTS.md](HINTS.md) or [ANSWERS.md](ANSWERS.md).

From the extracted package directory:

```bash
export LAB_ROOT="$(pwd)"
test -d "$LAB_ROOT/labs/00-terraform-contracts"
mkdir -p "$LAB_ROOT/run/00-contracts"
cp "$LAB_ROOT/labs/00-terraform-contracts/starter/"*.tf "$LAB_ROOT/run/00-contracts/"
cp -R "$LAB_ROOT/labs/00-terraform-contracts/solution/tests" "$LAB_ROOT/run/00-contracts/"
cd "$LAB_ROOT/run/00-contracts"
terraform init
terraform plan
```

**Expected incident:** the first plan fails. It has not created infrastructure. Investigate the reported expression and variable type, then edit the working copy:

```bash
terraform console
# Inspect: type(var.services)
# Inspect: var.services
# Type exit to leave the console.
${EDITOR:-vi} main.tf
terraform fmt
terraform validate
terraform test
terraform plan -out=lab.tfplan
terraform apply lab.tfplan
terraform output -json allocations | jq -e '. == {"api":256,"worker":512}'
terraform state list
```

Pass requires all eight tests passing and addresses ending in `["api"]` and `["worker"]`. Prove that reordering is harmless:

```bash
cat > reordered.auto.tfvars <<'EOF'
services = [
  { name = "worker", memory_mib = 512 },
  { name = "api", memory_mib = 256 }
]
EOF
terraform plan -detailed-exitcode
# Required exit status: 0 (no changes); 2 means a diff, 1 means an error.
rm reordered.auto.tfvars
```

Bonus, without applying: propose a service rename that retains object identity using a `moved` block. Explain why a renamed map key otherwise appears as a delete/create. Explain why `sensitive = true` would hide display output but not encrypt state.

Always finish with:

```bash
terraform destroy
terraform state list
# Required: no managed objects remain (normally no output).
```

If abandoning the puzzle before its first successful apply, there is nothing to destroy. If you already applied and then broke the configuration, preserve your work elsewhere and copy `solution/main.tf` over the working `main.tf`, run `terraform init`, then destroy. Do not delete state before cleanup. The files in `solution/` are the full reference implementation; only your working directory holds practice state.

References: [Terraform for_each](https://developer.hashicorp.com/terraform/language/meta-arguments/for_each), [input validation](https://developer.hashicorp.com/terraform/language/values/variables#custom-validation-rules), [Terraform tests](https://developer.hashicorp.com/terraform/language/tests).
