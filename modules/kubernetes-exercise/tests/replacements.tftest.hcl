mock_provider "kubernetes" {}

variables {
  manifest_path         = "tests/fixtures/replacement-before.yaml"
  create_diagnostic_pod = false
}

run "replacement_baseline" {
  command = apply
  assert {
    condition     = kubernetes_manifest.job["Job/check"].manifest.spec.template.spec.containers[0].command[0] == "false"
    error_message = "Baseline must retain the intentionally failing Job."
  }
}

run "immutable_repairs" {
  command = plan
  variables { manifest_path = "tests/fixtures/replacement-after.yaml" }
  assert {
    condition     = kubernetes_manifest.job["Job/check"].manifest.spec.template.spec.containers[0].command[0] == "true"
    error_message = "The repair must flow from candidate YAML into Terraform."
  }
  assert {
    condition     = kubernetes_manifest.storage_class["StorageClass/arcade-gp3"].manifest.provisioner == "ebs.csi.aws.com"
    error_message = "The StorageClass repair must select the standard EKS CSI driver."
  }
}
