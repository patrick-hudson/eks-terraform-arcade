locals {
  # Split only column-zero document separator lines. Keep surrounding newlines:
  # embedded ConfigMap files and shell scripts may depend on YAML block chomping.
  # A record separator cannot occur literally in valid YAML text.
  decoded_documents = flatten([
    for path in concat([var.manifest_path], var.extra_manifest_paths) : [
      for document in split("\u001e", replace(file(path), "/(?m)^---[\\t ]*(#[^\\r\\n]*)?\\r?$/", "\u001e")) :
      yamldecode(document) if trimspace(document) != ""
    ]
  ])
  documents      = [for document in local.decoded_documents : document if document != null]
  namespaces     = [for document in local.documents : document if document.kind == "Namespace"]
  namespace_name = try(local.namespaces[0].metadata.name, "arcade-invalid")
  namespace_manifest = try(local.namespaces[0], {
    apiVersion = "v1", kind = "Namespace", metadata = { name = "arcade-invalid" }
  })
  objects = {
    for document in local.documents : "${document.kind}/${document.metadata.name}" => document
    if document.kind != "Namespace"
  }
  allowed_kinds = toset([
    "ConfigMap", "Deployment", "Job", "PersistentVolumeClaim", "Pod", "PodDisruptionBudget",
    "Role", "RoleBinding", "Service", "ServiceAccount", "StorageClass"
  ])
}

# Stop a copied exercise from silently managing another namespace or cluster-wide RBAC.
# Secrets are deliberately excluded: Terraform state is a plaintext local artifact.
resource "terraform_data" "contract" {
  input = local.namespace_name
  lifecycle {
    precondition {
      condition     = length(local.namespaces) == 1 && startswith(local.namespace_name, "arcade-")
      error_message = "An exercise needs exactly one dedicated arcade-* Namespace; shared namespaces are not supported."
    }
    precondition {
      condition     = alltrue([for item in values(local.objects) : contains(local.allowed_kinds, item.kind)])
      error_message = "The exercise contains an unsupported resource kind; Secrets and cluster-wide RBAC are excluded."
    }
    precondition {
      condition = alltrue([
        for item in values(local.objects) : item.kind == "StorageClass" ?
        startswith(item.metadata.name, "arcade-") && try(item.metadata.namespace, null) == null :
        try(item.metadata.namespace, "") == local.namespace_name
      ])
      error_message = "Every namespaced object must belong to the exercise Namespace; StorageClasses need an arcade-* name."
    }
    precondition {
      condition     = !var.create_diagnostic_pod || !contains(keys(local.objects), "Pod/arcade-diagnostics")
      error_message = "The name arcade-diagnostics is reserved for the helper; disable create_diagnostic_pod to own it yourself."
    }
  }
}

resource "kubernetes_manifest" "namespace" {
  manifest   = local.namespace_manifest
  depends_on = [terraform_data.contract]
  field_manager {
    name            = "terraform-arcade"
    force_conflicts = false
  }
  timeouts { delete = "5m" }
}

# Provisioners and other StorageClass settings are immutable. Replacing the class
# never deletes its volumes; PVCs must be destroyed and verified separately.
resource "terraform_data" "storage_class_revision" {
  for_each = { for key, item in local.objects : key => item if item.kind == "StorageClass" }
  input    = sha256(jsonencode(each.value))
}
resource "kubernetes_manifest" "storage_class" {
  for_each   = { for key, item in local.objects : key => item if item.kind == "StorageClass" }
  manifest   = each.value
  depends_on = [kubernetes_manifest.namespace]
  lifecycle { replace_triggered_by = [terraform_data.storage_class_revision[each.key]] }
  field_manager {
    name            = "terraform-arcade"
    force_conflicts = false
  }
}

# Do not wait for readiness: a broken workload is the exercise, not an apply timeout.
resource "kubernetes_manifest" "resource" {
  for_each   = { for key, item in local.objects : key => item if !contains(["Job", "Pod", "StorageClass"], item.kind) }
  manifest   = each.value
  depends_on = [kubernetes_manifest.namespace, kubernetes_manifest.storage_class]
  field_manager {
    name            = "terraform-arcade"
    force_conflicts = false
  }
  timeouts { delete = "5m" }
}

# Jobs must be recreated when the Pod template changes, and their service accounts
# and fixture ConfigMaps must exist before their first attempt starts.
resource "terraform_data" "job_revision" {
  for_each = { for key, item in local.objects : key => item if item.kind == "Job" }
  input    = sha256(jsonencode(each.value))
}
resource "kubernetes_manifest" "job" {
  for_each   = { for key, item in local.objects : key => item if item.kind == "Job" }
  manifest   = each.value
  depends_on = [kubernetes_manifest.resource, kubernetes_manifest.namespace]
  lifecycle { replace_triggered_by = [terraform_data.job_revision[each.key]] }
  field_manager {
    name            = "terraform-arcade"
    force_conflicts = false
  }
  timeouts { delete = "5m" }
}

resource "terraform_data" "pod_revision" {
  for_each = { for key, item in local.objects : key => item if item.kind == "Pod" }
  input    = sha256(jsonencode(each.value))
}
resource "kubernetes_manifest" "pod" {
  for_each   = { for key, item in local.objects : key => item if item.kind == "Pod" }
  manifest   = each.value
  depends_on = [kubernetes_manifest.resource, kubernetes_manifest.namespace]
  lifecycle { replace_triggered_by = [terraform_data.pod_revision[each.key]] }
  field_manager {
    name            = "terraform-arcade"
    force_conflicts = false
  }
  timeouts { delete = "5m" }
}

resource "kubernetes_manifest" "diagnostics" {
  count = var.create_diagnostic_pod ? 1 : 0
  manifest = {
    apiVersion = "v1"
    kind       = "Pod"
    metadata = {
      name      = "arcade-diagnostics"
      namespace = local.namespace_name
      labels    = { "app.kubernetes.io/part-of" = "aws-interview-arcade", "app" = "arcade-diagnostics" }
    }
    spec = {
      automountServiceAccountToken = false
      restartPolicy                = "Always"
      nodeSelector                 = { role = "lab" }
      securityContext = {
        runAsNonRoot   = true
        runAsUser      = 1000
        runAsGroup     = 1000
        seccompProfile = { type = "RuntimeDefault" }
      }
      containers = [{
        name    = "diagnostics"
        image   = "public.ecr.aws/docker/library/alpine:3.24.2"
        command = ["/bin/sh", "-ec", "sleep 3600"]
        securityContext = {
          allowPrivilegeEscalation = false
          readOnlyRootFilesystem   = true
          capabilities             = { drop = ["ALL"] }
        }
        resources = {
          requests = { cpu = "5m", memory = "8Mi" }
          limits   = { cpu = "50m", memory = "32Mi" }
        }
      }]
    }
  }
  depends_on = [kubernetes_manifest.namespace]
  field_manager {
    name            = "terraform-arcade"
    force_conflicts = false
  }
}
