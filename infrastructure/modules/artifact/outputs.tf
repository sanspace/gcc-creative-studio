output "repository_id" {
  description = "The ID of the Artifact Registry repository."
  value       = google_artifact_registry_repository.ghcr_proxy.repository_id
}

output "repository_name" {
  description = "The fully qualified name of the repository."
  value       = google_artifact_registry_repository.ghcr_proxy.name
}

output "repository_url" {
  description = "The URL of the repository (without image name)."
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.ghcr_proxy.repository_id}"
}
