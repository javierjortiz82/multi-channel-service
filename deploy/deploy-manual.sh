#!/bin/bash
# =============================================================================
# Multi-Channel Service - Manual Deployment Script
# =============================================================================
# Deploy the service to Google Cloud Run manually.
#
# Usage:
#   ./deploy/deploy-manual.sh              # Uses git SHA as tag
#   ./deploy/deploy-manual.sh v1.0.0       # Uses custom tag
#
# Prerequisites:
#   - gcloud CLI authenticated
#   - Docker configured for Artifact Registry
#   - run ./deploy/setup-gcp.sh first
# =============================================================================

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="multi-channel-service"
REPO_NAME="multi-channel-repo"
SERVICE_ACCOUNT="orchestrator-sa@${PROJECT_ID}.iam.gserviceaccount.com"

# Tag: use argument or git SHA
TAG="${1:-$(git rev-parse --short HEAD 2>/dev/null || echo 'latest')}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE_NAME}"

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}   Multi-Channel Service - Manual Deploy${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo -e "Project: ${GREEN}${PROJECT_ID}${NC}"
echo -e "Region: ${GREEN}${REGION}${NC}"
echo -e "Service: ${GREEN}${SERVICE_NAME}${NC}"
echo -e "Image: ${GREEN}${IMAGE}:${TAG}${NC}"
echo -e "Service Account: ${GREEN}${SERVICE_ACCOUNT}${NC}"
echo ""

# Pre-flight checks
echo -e "${YELLOW}Pre-flight checks...${NC}"

# Check gcloud auth
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -1 > /dev/null; then
    echo -e "${RED}Error: Not authenticated. Run 'gcloud auth login'${NC}"
    exit 1
fi

# Check project
if [[ -z "$PROJECT_ID" ]]; then
    echo -e "${RED}Error: No project set. Run 'gcloud config set project PROJECT_ID'${NC}"
    exit 1
fi

# Check Dockerfile
if [[ ! -f "deploy/Dockerfile.cloudrun" ]]; then
    echo -e "${RED}Error: deploy/Dockerfile.cloudrun not found${NC}"
    exit 1
fi

echo -e "${GREEN}Pre-flight checks passed${NC}"
echo ""

# Step 1: Build Docker image
echo -e "${YELLOW}Step 1/4: Building Docker image...${NC}"
docker build \
    -f deploy/Dockerfile.cloudrun \
    -t "${IMAGE}:${TAG}" \
    -t "${IMAGE}:latest" \
    .

echo -e "${GREEN}Image built successfully${NC}"

# Step 2: Push to Artifact Registry
echo -e "${YELLOW}Step 2/4: Pushing to Artifact Registry...${NC}"
docker push "${IMAGE}:${TAG}"
docker push "${IMAGE}:latest"

echo -e "${GREEN}Image pushed successfully${NC}"

# Step 3: Deploy to Cloud Run
echo -e "${YELLOW}Step 3/4: Deploying to Cloud Run...${NC}"

# Get secrets from environment or use defaults for webhook host
WEBHOOK_HOST="${WEBHOOK_HOST:-https://${SERVICE_NAME}-$(gcloud projects describe ${PROJECT_ID} --format='value(projectNumber)' | cut -c1-10).${REGION}.run.app}"

gcloud run deploy "${SERVICE_NAME}" \
    --image="${IMAGE}:${TAG}" \
    --region="${REGION}" \
    --platform=managed \
    --service-account="${SERVICE_ACCOUNT}" \
    --no-allow-unauthenticated \
    --port=8080 \
    --memory=512Mi \
    --cpu=1 \
    --min-instances=0 \
    --max-instances=10 \
    --timeout=300 \
    --concurrency=80 \
    --set-env-vars="\
GCP_PROJECT_ID=${PROJECT_ID},\
GCP_LOCATION=${REGION},\
ENVIRONMENT=production,\
DEBUG=false,\
LOG_LEVEL=INFO,\
LOG_FORMAT=json,\
LOG_TO_FILE=false,\
USE_ADC=true,\
SERVER_HOST=0.0.0.0,\
SERVER_PORT=8080,\
WEBHOOK_PATH=/webhook,\
WEBHOOK_MAX_CONNECTIONS=100,\
WEBHOOK_IP_FILTER_ENABLED=false,\
WEBHOOK_DROP_PENDING_UPDATES=true,\
RATE_LIMIT_REQUESTS=100,\
RATE_LIMIT_WINDOW_SECONDS=60,\
WORKERS=1" \
    --set-secrets="\
TELEGRAM_BOT_TOKEN=telegram-bot-token:latest,\
WEBHOOK_SECRET=webhook-secret:latest" \
    --project="${PROJECT_ID}"

echo -e "${GREEN}Deployment initiated${NC}"

# Step 4: Verify deployment
echo -e "${YELLOW}Step 4/4: Verifying deployment...${NC}"

# Get service URL
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" \
    --region="${REGION}" \
    --platform=managed \
    --project="${PROJECT_ID}" \
    --format="value(status.url)")

echo -e "Service URL: ${GREEN}${SERVICE_URL}${NC}"

# Update webhook host if needed
echo -e "${YELLOW}Updating WEBHOOK_HOST...${NC}"
gcloud run services update "${SERVICE_NAME}" \
    --region="${REGION}" \
    --platform=managed \
    --project="${PROJECT_ID}" \
    --update-env-vars="WEBHOOK_HOST=${SERVICE_URL}" \
    --quiet

# Health check with retry
MAX_RETRIES=10
RETRY_DELAY=5

for i in $(seq 1 $MAX_RETRIES); do
    echo -e "Health check attempt ${i}/${MAX_RETRIES}..."

    # Get identity token for authenticated request
    TOKEN=$(gcloud auth print-identity-token --audiences="${SERVICE_URL}")

    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Authorization: Bearer ${TOKEN}" \
        "${SERVICE_URL}/health" 2>/dev/null || echo "000")

    if [[ "$HTTP_CODE" == "200" ]]; then
        echo -e "${GREEN}Health check passed!${NC}"
        break
    fi

    if [[ $i -eq $MAX_RETRIES ]]; then
        echo -e "${YELLOW}Warning: Health check did not pass after ${MAX_RETRIES} attempts${NC}"
        echo -e "${YELLOW}Service may still be starting. Check logs with:${NC}"
        echo -e "gcloud run logs read ${SERVICE_NAME} --region=${REGION} --limit=50"
    else
        sleep $RETRY_DELAY
    fi
done

# Summary
echo ""
echo -e "${BLUE}============================================${NC}"
echo -e "${GREEN}   Deployment Complete!${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo -e "Service: ${GREEN}${SERVICE_NAME}${NC}"
echo -e "URL: ${GREEN}${SERVICE_URL}${NC}"
echo -e "Image: ${GREEN}${IMAGE}:${TAG}${NC}"
echo ""
echo -e "${YELLOW}Commands:${NC}"
echo -e "  View logs: gcloud run logs read ${SERVICE_NAME} --region=${REGION} --limit=50"
echo -e "  Describe: gcloud run services describe ${SERVICE_NAME} --region=${REGION}"
echo -e "  Health: curl -H \"Authorization: Bearer \$(gcloud auth print-identity-token)\" ${SERVICE_URL}/health"
