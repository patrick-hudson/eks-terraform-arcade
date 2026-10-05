# Answer · stable Terraform identities

The supplied `for_each = var.services` passes a list of objects. `for_each` accepts a map or a set of strings, and its keys must be known during planning. The minimal repair is:

```hcl
resource "terraform_data" "service" {
  for_each = { for service in var.services : service.name => service }
  input    = each.value
}
```

`toset(var.services)` still produces a set of objects. Index-based keys accept the input but fail the identity requirement when list order changes. The existing uniqueness rule prevents two services claiming one key. Each object's memory stays a value, so changing memory updates the existing instance.

To install the complete answer in the same working directory:

```bash
: "${LAB_ROOT:?Set LAB_ROOT to the extracted package directory}"
cd "$LAB_ROOT/run/00-contracts"
cp "$LAB_ROOT/labs/00-terraform-contracts/solution/main.tf" main.tf
terraform fmt
terraform validate
terraform test
terraform plan -out=lab.tfplan
terraform apply lab.tfplan
```

Changing `api` to `gateway` without a state move destroys one `terraform_data` instance and creates another. For an intended rename, change the name in the input and add:

```hcl
moved {
  from = terraform_data.service["api"]
  to   = terraform_data.service["gateway"]
}
```

Then inspect the plan before applying. Leave the baseline names unchanged for the supplied tests. In a real service, `moved` describes identity continuity; it does not make an incompatible provider-level argument change non-destructive.

A senior answer distinguishes input validation, preconditions and provider validation; understands that local state is still state; and preserves evidence before using force-unlock, state removal or replacement. Cleanup is the `terraform destroy` sequence in the mission.
