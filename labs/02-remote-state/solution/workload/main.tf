resource "terraform_data" "checkpoint" {
  input = "remote-state-locking-exercise"
  # This intentional local delay lets another Terraform process observe the lock.
  # There is no remote compute. Do not use this pattern for production deployments.
  provisioner "local-exec" {
    command = "sleep 45"
  }
}

output "checkpoint_id" {
  value = terraform_data.checkpoint.id
}
