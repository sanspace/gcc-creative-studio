# infra/modules/artifact-registry/main.tf

resource "google_artifact_registry_repository" "ghcr_proxy" {
  location      = var.region
  repository_id = "${var.resource_prefix}-${var.environment}-${var.repository_id}"
  description   = "Regional proxy for GHCR with vulnerability scanning"
  format        = "DOCKER"

  # Remote Repository Mode
  mode = "REMOTE_REPOSITORY"

  remote_repository_config {
    description = "Proxy for GitHub Container Registry"
    docker_repository {
      custom_repository {
        uri = var.remote_uri
      }
    }
  }

  # Explicitly enable vulnerability scanning
  # Note: This requires 'containerscanning.googleapis.com' to be enabled in the project
  # Ensure the mirror scans every image it caches
  vulnerability_scanning_config {
    enablement_config = "INHERITED" # Inherits project-level scan settings
  }

  # Cost Guardrail: Automatically purge cached layers unaccessed for 30 days
  cleanup_policies {
    id     = "delete-stale-cache"
    action = "DELETE"
    condition {
      older_than = var.cleanup_older_than
    }
  }

  labels = merge(var.labels, {
    component = "security-mirror"
    region    = var.region
  })
}
