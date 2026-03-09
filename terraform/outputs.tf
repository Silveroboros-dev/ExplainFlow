output "api_url" {
  description = "The URL of the deployed API service"
  value       = google_cloud_run_v2_service.api.uri
}

output "web_url" {
  description = "The URL of the deployed Web service"
  value       = google_cloud_run_v2_service.web.uri
}