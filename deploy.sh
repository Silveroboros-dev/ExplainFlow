#!/bin/bash

# ExplainFlow Automated Deployment Script
# This script uses Terraform and Cloud Build for a fully automated CI/CD pipeline.

echo "🚀 Starting ExplainFlow Automated Deployment..."

# Ensure we have the project ID
PROJECT_ID=$(gcloud config get-value project)
if [ -z "$PROJECT_ID" ]; then
    echo "❌ Error: Google Cloud Project ID is not set. Please run 'gcloud config set project <YOUR_PROJECT_ID>'."
    exit 1
fi

echo "🔹 Project ID: $PROJECT_ID"

# 1. Infrastructure as Code (Terraform)
echo "🛠️  Applying Terraform Infrastructure..."
cd terraform
terraform init
# We pass the project_id to Terraform. Assuming 'us-central1' is the default region.
terraform apply -var="project_id=$PROJECT_ID" -auto-approve
cd ..

echo "✅ Infrastructure applied successfully."

# 2. Secret Management Check
# The Terraform script creates the secret, but the value needs to be set if it hasn't been already.
SECRET_CHECK=$(gcloud secrets versions list explainflow-gemini-api-key --limit=1 --format="value(name)" 2>/dev/null)
if [ -z "$SECRET_CHECK" ]; then
    echo "⚠️  API Key Secret is empty. Fetching from api/.env and adding to Secret Manager..."
    if [ -f "api/.env" ]; then
        API_KEY=$(grep GEMINI_API_KEY api/.env | cut -d '=' -f2)
        if [ -n "$API_KEY" ]; then
             echo -n "$API_KEY" | gcloud secrets versions add explainflow-gemini-api-key --data-file=-
             echo "✅ Secret updated."
        else
             echo "❌ Error: GEMINI_API_KEY not found in api/.env. Deployment will fail."
             exit 1
        fi
    else
        echo "❌ Error: api/.env file not found. Cannot set the API Key secret. Deployment will fail."
        exit 1
    fi
fi

# 3. Global CI/CD (Cloud Build)
echo "📦 Triggering Cloud Build Pipeline..."
# This will build both API and Web containers, push them to Artifact Registry, and deploy them to Cloud Run.
gcloud builds submit --config cloudbuild.yaml .

echo "🎉 Deployment Pipeline Complete!"
echo "Check the Cloud Run console for the active service URLs."
gcloud run services list --region us-central1