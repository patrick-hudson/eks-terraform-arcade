# Build contract

Write Terraform for an existing log group, including retention and tags. Use the runbook's fixture helper to create it and record ownership; never adopt a group after a name collision. Supply an import block or use CLI import, guarded by the creation receipt check. Then demonstrate drift repair and an address refactor with a moved block. Preserve `state-rescue-fixture.json` so cleanup works before import too. Never edit state JSON by hand.
