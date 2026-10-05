mock_provider "kubernetes" {}

run "lab_11_incident_gauntlet_scenario_01_solution_fixed" {
  command = plan
  variables { manifest_path = "../../labs/11-incident-gauntlet/scenario-01/solution/fixed.yaml" }
  assert {
    condition     = startswith(output.namespace, "arcade-") && length(output.resource_keys) > 0
    error_message = "The authored candidate must decode into a dedicated namespace and resources."
  }
}

run "lab_11_incident_gauntlet_scenario_01_starter_broken" {
  command = plan
  variables { manifest_path = "../../labs/11-incident-gauntlet/scenario-01/starter/broken.yaml" }
  assert {
    condition     = startswith(output.namespace, "arcade-") && length(output.resource_keys) > 0
    error_message = "The authored candidate must decode into a dedicated namespace and resources."
  }
}

run "lab_11_incident_gauntlet_scenario_02_solution_fixed" {
  command = plan
  variables { manifest_path = "../../labs/11-incident-gauntlet/scenario-02/solution/fixed.yaml" }
  assert {
    condition     = startswith(output.namespace, "arcade-") && length(output.resource_keys) > 0
    error_message = "The authored candidate must decode into a dedicated namespace and resources."
  }
}

run "lab_11_incident_gauntlet_scenario_02_starter_broken" {
  command = plan
  variables { manifest_path = "../../labs/11-incident-gauntlet/scenario-02/starter/broken.yaml" }
  assert {
    condition     = startswith(output.namespace, "arcade-") && length(output.resource_keys) > 0
    error_message = "The authored candidate must decode into a dedicated namespace and resources."
  }
}

run "lab_11_incident_gauntlet_scenario_03_solution_fixed" {
  command = plan
  variables { manifest_path = "../../labs/11-incident-gauntlet/scenario-03/solution/fixed.yaml" }
  assert {
    condition     = startswith(output.namespace, "arcade-") && length(output.resource_keys) > 0
    error_message = "The authored candidate must decode into a dedicated namespace and resources."
  }
}

run "lab_11_incident_gauntlet_scenario_03_starter_broken" {
  command = plan
  variables { manifest_path = "../../labs/11-incident-gauntlet/scenario-03/starter/broken.yaml" }
  assert {
    condition     = startswith(output.namespace, "arcade-") && length(output.resource_keys) > 0
    error_message = "The authored candidate must decode into a dedicated namespace and resources."
  }
}

run "lab_11_incident_gauntlet_scenario_04_solution_fixed" {
  command = plan
  variables { manifest_path = "../../labs/11-incident-gauntlet/scenario-04/solution/fixed.yaml" }
  assert {
    condition     = startswith(output.namespace, "arcade-") && length(output.resource_keys) > 0
    error_message = "The authored candidate must decode into a dedicated namespace and resources."
  }
}

run "lab_11_incident_gauntlet_scenario_04_starter_broken" {
  command = plan
  variables { manifest_path = "../../labs/11-incident-gauntlet/scenario-04/starter/broken.yaml" }
  assert {
    condition     = startswith(output.namespace, "arcade-") && length(output.resource_keys) > 0
    error_message = "The authored candidate must decode into a dedicated namespace and resources."
  }
}

run "lab_11_incident_gauntlet_scenario_05_solution_fixed" {
  command = plan
  variables { manifest_path = "../../labs/11-incident-gauntlet/scenario-05/solution/fixed.yaml" }
  assert {
    condition     = startswith(output.namespace, "arcade-") && length(output.resource_keys) > 0
    error_message = "The authored candidate must decode into a dedicated namespace and resources."
  }
}

run "lab_11_incident_gauntlet_scenario_05_starter_broken" {
  command = plan
  variables { manifest_path = "../../labs/11-incident-gauntlet/scenario-05/starter/broken.yaml" }
  assert {
    condition     = startswith(output.namespace, "arcade-") && length(output.resource_keys) > 0
    error_message = "The authored candidate must decode into a dedicated namespace and resources."
  }
}

run "lab_11_incident_gauntlet_scenario_06_solution_fixed" {
  command = plan
  variables { manifest_path = "../../labs/11-incident-gauntlet/scenario-06/solution/fixed.yaml" }
  assert {
    condition     = startswith(output.namespace, "arcade-") && length(output.resource_keys) > 0
    error_message = "The authored candidate must decode into a dedicated namespace and resources."
  }
}

run "lab_11_incident_gauntlet_scenario_06_starter_broken" {
  command = plan
  variables { manifest_path = "../../labs/11-incident-gauntlet/scenario-06/starter/broken.yaml" }
  assert {
    condition     = startswith(output.namespace, "arcade-") && length(output.resource_keys) > 0
    error_message = "The authored candidate must decode into a dedicated namespace and resources."
  }
}

run "lab_11_incident_gauntlet_scenario_07_solution_fixed" {
  command = plan
  variables { manifest_path = "../../labs/11-incident-gauntlet/scenario-07/solution/fixed.yaml" }
  assert {
    condition     = startswith(output.namespace, "arcade-") && length(output.resource_keys) > 0
    error_message = "The authored candidate must decode into a dedicated namespace and resources."
  }
}

run "lab_11_incident_gauntlet_scenario_07_starter_broken" {
  command = plan
  variables { manifest_path = "../../labs/11-incident-gauntlet/scenario-07/starter/broken.yaml" }
  assert {
    condition     = startswith(output.namespace, "arcade-") && length(output.resource_keys) > 0
    error_message = "The authored candidate must decode into a dedicated namespace and resources."
  }
}

run "lab_11_incident_gauntlet_scenario_08_solution_fixed" {
  command = plan
  variables { manifest_path = "../../labs/11-incident-gauntlet/scenario-08/solution/fixed.yaml" }
  assert {
    condition     = startswith(output.namespace, "arcade-") && length(output.resource_keys) > 0
    error_message = "The authored candidate must decode into a dedicated namespace and resources."
  }
}

run "lab_11_incident_gauntlet_scenario_08_starter_broken" {
  command = plan
  variables { manifest_path = "../../labs/11-incident-gauntlet/scenario-08/starter/broken.yaml" }
  assert {
    condition     = startswith(output.namespace, "arcade-") && length(output.resource_keys) > 0
    error_message = "The authored candidate must decode into a dedicated namespace and resources."
  }
}

run "lab_11_incident_gauntlet_scenario_09_solution_fixed" {
  command = plan
  variables { manifest_path = "../../labs/11-incident-gauntlet/scenario-09/solution/fixed.yaml" }
  assert {
    condition     = startswith(output.namespace, "arcade-") && length(output.resource_keys) > 0
    error_message = "The authored candidate must decode into a dedicated namespace and resources."
  }
}

run "lab_11_incident_gauntlet_scenario_09_starter_broken" {
  command = plan
  variables { manifest_path = "../../labs/11-incident-gauntlet/scenario-09/starter/broken.yaml" }
  assert {
    condition     = startswith(output.namespace, "arcade-") && length(output.resource_keys) > 0
    error_message = "The authored candidate must decode into a dedicated namespace and resources."
  }
}

run "lab_11_incident_gauntlet_scenario_10_baseline_healthy" {
  command = plan
  variables { manifest_path = "../../labs/11-incident-gauntlet/scenario-10/baseline/healthy.yaml" }
  assert {
    condition     = startswith(output.namespace, "arcade-") && length(output.resource_keys) > 0
    error_message = "The authored candidate must decode into a dedicated namespace and resources."
  }
}

run "lab_11_incident_gauntlet_scenario_10_solution_fixed" {
  command = plan
  variables { manifest_path = "../../labs/11-incident-gauntlet/scenario-10/solution/fixed.yaml" }
  assert {
    condition     = startswith(output.namespace, "arcade-") && length(output.resource_keys) > 0
    error_message = "The authored candidate must decode into a dedicated namespace and resources."
  }
}

run "lab_11_incident_gauntlet_scenario_10_starter_broken" {
  command = plan
  variables { manifest_path = "../../labs/11-incident-gauntlet/scenario-10/starter/broken.yaml" }
  assert {
    condition     = startswith(output.namespace, "arcade-") && length(output.resource_keys) > 0
    error_message = "The authored candidate must decode into a dedicated namespace and resources."
  }
}

run "lab_08_kubernetes_release_broken_workload" {
  command = plan
  variables { manifest_path = "../../labs/08-kubernetes-release/broken/workload.yaml" }
  assert {
    condition     = startswith(output.namespace, "arcade-") && length(output.resource_keys) > 0
    error_message = "The authored candidate must decode into a dedicated namespace and resources."
  }
}

run "lab_08_kubernetes_release_solution_workload" {
  command = plan
  variables { manifest_path = "../../labs/08-kubernetes-release/solution/workload.yaml" }
  assert {
    condition     = startswith(output.namespace, "arcade-") && length(output.resource_keys) > 0
    error_message = "The authored candidate must decode into a dedicated namespace and resources."
  }
}

run "lab_09_pod_identity_broken_workload" {
  command = plan
  variables { manifest_path = "../../labs/09-pod-identity/broken/workload.yaml" }
  assert {
    condition     = startswith(output.namespace, "arcade-") && length(output.resource_keys) > 0
    error_message = "The authored candidate must decode into a dedicated namespace and resources."
  }
}

run "lab_09_pod_identity_solution_workload" {
  command = plan
  variables { manifest_path = "../../labs/09-pod-identity/solution/workload.yaml" }
  assert {
    condition     = startswith(output.namespace, "arcade-") && length(output.resource_keys) > 0
    error_message = "The authored candidate must decode into a dedicated namespace and resources."
  }
}

run "lab_10_ebs_storage_broken_workload" {
  command = plan
  variables { manifest_path = "../../labs/10-ebs-storage/broken/workload.yaml" }
  assert {
    condition     = startswith(output.namespace, "arcade-") && length(output.resource_keys) > 0
    error_message = "The authored candidate must decode into a dedicated namespace and resources."
  }
}

run "lab_10_ebs_storage_solution_workload" {
  command = plan
  variables { manifest_path = "../../labs/10-ebs-storage/solution/workload.yaml" }
  assert {
    condition     = startswith(output.namespace, "arcade-") && length(output.resource_keys) > 0
    error_message = "The authored candidate must decode into a dedicated namespace and resources."
  }
}

run "lab_12_capstone_solution_workload_v2" {
  command = plan
  variables { manifest_path = "../../labs/12-capstone/solution/workload-v2.yaml" }
  assert {
    condition     = startswith(output.namespace, "arcade-") && length(output.resource_keys) > 0
    error_message = "The authored candidate must decode into a dedicated namespace and resources."
  }
}


run "lab_13_public_access_starter" {
  command = plan
  variables { manifest_path = "../../labs/13-public-access/starter/workload.yaml" }
  assert {
    condition     = output.namespace == "arcade-public" && contains(output.resource_keys, "Service/public-demo")
    error_message = "The public demo workload must remain in its own namespace."
  }
}

run "lab_13_public_access_solution" {
  command = plan
  variables { manifest_path = "../../labs/13-public-access/solution/workload.yaml" }
  assert {
    condition     = output.namespace == "arcade-public" && contains(output.resource_keys, "Service/public-demo")
    error_message = "The public demo workload must remain in its own namespace."
  }
}
