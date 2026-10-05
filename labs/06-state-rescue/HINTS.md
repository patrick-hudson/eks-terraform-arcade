# Hints — 06

1. The configuration describes desired objects. State maps their addresses to remote identities. Existence in AWS does not create that binding.
2. Refresh-only accepts observed remote attributes into state; it does not rewrite your HCL.
3. An address rename is different from changing the remote resource's name. How can you tell Terraform these two addresses describe the same object?
