#!/bin/bash

# Configuration - Update these or pass as env vars
PROJECT_ID=$(gcloud config get-value project)
REGION="us-central1"
API_SERVICE_NAME="explainflow-api"
WEB_SERVICE_NAME="explainflow-web"

echo "🚀 Starting deployment to Google Cloud Run..."

# 1. Build and Push API
echo "📦 Building API Container..."
gcloud builds submit --tag gcr.io/$PROJECT_ID/$API_SERVICE_NAME api/

# 2. Deploy API
echo "🌍 Deploying API to Cloud Run..."
# CRITICAL: timeout=300s for multimodal "thinking" time
gcloud run deploy $API_SERVICE_NAME 
  --image gcr.io/$PROJECT_ID/$API_SERVICE_NAME 
  --platform managed 
  --region $REGION 
  --allow-unauthenticated 
  --timeout=300 
  --memory=2Gi 
  --cpu=2 
  --set-env-vars="GEMINI_API_KEY=$(cat api/.env | grep GEMINI_API_KEY | cut -d '=' -f2)"

# 3. Build and Push Web
echo "📦 Building Web Container..."
# Note: In production, the Web app needs to know the API URL.
# You might want to redeploy Web after API is live to set the NEXT_PUBLIC_API_URL.
gcloud builds submit --tag gcr.io/$PROJECT_ID/$WEB_SERVICE_NAME --file web/Dockerfile .

# 4. Deploy Web
echo "🌍 Deploying Web to Cloud Run..."
gcloud run deploy $WEB_SERVICE_NAME 
  --image gcr.io/$PROJECT_ID/$WEB_SERVICE_NAME 
  --platform managed 
  --region $REGION 
  --allow-unauthenticated

echo "✅ Deployment complete!"
gcloud run services list
