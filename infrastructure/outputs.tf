output "firebase_dns_verification_records" {
  description = "The target DNS records you must add to your domain registrar to verify ownership and activate SSL."
  # Safely handle the output depending on whether the resource count is 0 or 1
  value = length(google_firebase_hosting_custom_domain.custom_domain) > 0 ? (
    google_firebase_hosting_custom_domain.custom_domain[0].required_dns_updates
  ) : null
}

