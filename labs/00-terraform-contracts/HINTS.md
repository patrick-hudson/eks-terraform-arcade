# Hints · open one layer at a time

**Foundation:** A Terraform resource address contains its type, name and, for repeated resources, an instance key. Terraform must decide those keys during planning.

<details><summary>Hint 1 — classify the failure</summary>

There is no AWS provider here. Read whether the error concerns syntax, a value's type, or a remote API. Compare the declared input type to the accepted input types for the failing meta-argument.
</details>

<details><summary>Hint 2 — choose identity</summary>

Neither position in the input list nor the requested memory should identify a service. One existing field is stable enough to serve as its key.
</details>

<details><summary>Hint 3 — transform at the boundary</summary>

Keep the variable as a list of objects. A `for` expression can construct a map with one service name as each key and the complete service object as each value.
</details>

Interview prompts: Why is `count` a poor fit here? Why would a set of objects not be a valid shortcut? What happens if the names come from IDs that only exist after apply? What can a validation rule prove before cloud access?
