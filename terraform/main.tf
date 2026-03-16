terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# 1. Artifact Registry
resource "google_artifact_registry_repository" "repo" {
  repository_id = "explainflow-repo"
  format        = "DOCKER"
  location      = var.region
  description   = "Docker repository for ExplainFlow services"
}

# 2. GCS Bucket for Assets
resource "google_storage_bucket" "assets" {
  name                        = "explainflow-assets-${var.project_id}"
  location                    = var.region
  force_destroy               = true
  uniform_bucket_level_access = true

  cors {
    origin          = ["*"]
    method          = ["GET", "HEAD", "PUT", "POST", "DELETE"]
    response_header = ["*"]
    max_age_seconds = 3600
  }
}

# Make the bucket public for the hackathon demo (convenience for image/audio loading)
resource "google_storage_bucket_iam_member" "public_rule" {
  bucket = google_storage_bucket.assets.name
  role   = "roles/storage.objectViewer"
  member = "allUsers"
}

# 3. Secret Manager (GEMINI_API_KEY)
resource "google_secret_manager_secret" "gemini_api_key" {
  secret_id = "explainflow-gemini-api-key"
  replication {
    auto {}
  }
}

# Allow Cloud Run to access the secret
resource "google_project_iam_member" "secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com"
}

# Allow Cloud Run to write to GCS
resource "google_storage_bucket_iam_member" "storage_admin" {
  bucket = google_storage_bucket.assets.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com"
}

data "google_project" "project" {}

# 4. Cloud Run Service: API
resource "google_cloud_run_v2_service" "api" {
  name     = "explainflow-api"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    scaling {
      min_instance_count = 1
      max_instance_count = 10
    }
    containers {
      image = "us-central1-docker.pkg.dev/${var.project_id}/explainflow-repo/explainflow-api:latest"
      
      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
      }
      env {
        name = "GEMINI_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.gemini_api_key.secret_id
            version = "latest"
          }
        }
      }
      env {
        name  = "EXPLAINFLOW_BUCKET"
        value = google_storage_bucket.assets.name
      }
    }
    timeout = "300s" # Critical for multimodal streaming
  }
}

# Allow unauthenticated access to the API
resource "google_cloud_run_v2_service_iam_member" "api_public" {
  name     = google_cloud_run_v2_service.api.name
  location = google_cloud_run_v2_service.api.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# 4. Cloud Run Service: Web
resource "google_cloud_run_v2_service" "web" {
  name     = "explainflow-web"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    scaling {
      max_instance_count = 10
    }
    containers {
      image = "us-central1-docker.pkg.dev/${var.project_id}/explainflow-repo/explainflow-web:latest"
      
      env {
        name  = "NEXT_PUBLIC_API_URL"
        value = google_cloud_run_v2_service.api.uri
      }
    }
  }
}

# Allow unauthenticated access to the Web app
resource "google_cloud_run_v2_service_iam_member" "web_public" {
  name     = google_cloud_run_v2_service.web.name
  location = google_cloud_run_v2_service.web.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}
