mock_provider "kubernetes" {}

variables {
  manifest_path = "tests/fixtures/valid.yaml"
}

run "names_and_order_are_stable" {
  command = plan
  assert {
    condition     = output.namespace == "arcade-contract"
    error_message = "Use the dedicated Namespace from the candidate file."
  }
  assert {
    condition     = output.resource_keys == tolist(["ConfigMap/settings", "Deployment/app", "Job/check", "Service/app"])
    error_message = "Every authored resource must retain Kind/name identity."
  }
  assert {
    condition     = kubernetes_manifest.resource["ConfigMap/settings"].manifest.data.script == "echo --- is data\n---\necho end\n"
    error_message = "The YAML decoder must preserve document-like text within block scalars."
  }
  assert {
    condition     = kubernetes_manifest.diagnostics[0].manifest.spec.automountServiceAccountToken == false && kubernetes_manifest.diagnostics[0].manifest.spec.securityContext.runAsNonRoot
    error_message = "Diagnostics must not inherit API access or run as root."
  }
  assert {
    condition     = length(kubernetes_manifest.job) == 1 && length(kubernetes_manifest.resource) == 3
    error_message = "Jobs require separate dependency and replacement handling."
  }
}

run "diagnostics_are_optional" {
  command = plan
  variables { create_diagnostic_pod = false }
  assert {
    condition     = length(kubernetes_manifest.diagnostics) == 0
    error_message = "Disabling the diagnostic helper must remove its planned Pod."
  }
}

run "reject_cross_namespace_objects" {
  command = plan
  variables { manifest_path = "tests/fixtures/wrong-namespace.yaml" }
  expect_failures = [terraform_data.contract]
}

run "reject_shared_namespace" {
  command = plan
  variables { manifest_path = "tests/fixtures/shared-namespace.yaml" }
  expect_failures = [terraform_data.contract]
}

run "extra_files_are_managed_together" {
  command = plan
  variables { extra_manifest_paths = ["tests/fixtures/extra-config.yaml"] }
  assert {
    condition     = kubernetes_manifest.resource["ConfigMap/fixture"].manifest.data.bucket == "example-lab-bucket"
    error_message = "A generated non-secret AWS fixture must join the same workload state."
  }
}

run "reject_missing_namespace" {
  command = plan
  variables { manifest_path = "tests/fixtures/extra-config.yaml" }
  expect_failures = [terraform_data.contract]
}

run "reject_secret_state" {
  command = plan
  variables { extra_manifest_paths = ["tests/fixtures/secret.yaml"] }
  expect_failures = [terraform_data.contract]
}
