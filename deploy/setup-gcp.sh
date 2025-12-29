#!/bin/bash
# =============================================================================
# Multi-Channel Service - GCP Infrastructure Setup
# =============================================================================
# This script sets up all required GCP resources for the multi-channel-service.
# Run once per project to configure infrastructure.
#
# Prerequisites:
#   - gcloud CLI installed and authenticated
#   - Sufficient GCP permissions (Project Owner or Editor)
#
# Usage:
#   chmod +x deploy/setup-gcp.sh
#   ./deploy/setup-gcp.sh
# =============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="multi-channel-service"
REPO_NAME="multi-channel-repo"
# Use orchestrator-sa for service-to-service communication
SERVICE_ACCOUNT_NAME="orchestrator-sa"
GITHUB_OWNER="${GITHUB_OWNER:-javierjortiz82}"

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}   Multi-Channel Service - GCP Setup${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo -e "Project ID: ${GREEN}${PROJECT_ID}${NC}"
echo -e "Region: ${GREEN}${REGION}${NC}"
echo -e "Service: ${GREEN}${SERVICE_NAME}${NC}"
echo -e "Service Account: ${GREEN}${SERVICE_ACCOUNT_NAME}${NC}"
echo ""

# Validate project
if [[ -z "$PROJECT_ID" ]]; then
    echo -e "${RED}Error: No project configured. Run 'gcloud config set project PROJECT_ID'${NC}"
    exit 1
fi

# Get project number
PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format="value(projectNumber)" 2>/dev/null || echo "")
if [[ -z "$PROJECT_NUMBER" ]]; then
    echo -e "${RED}Error: Cannot get project number. Check permissions.${NC}"
    exit 1
fi

echo -e "${YELLOW}Step 1/7: Enabling required APIs...${NC}"
gcloud services enable \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com \
    iam.googleapis.com \
    iamcredentials.googleapis.com \
    cloudresourcemanager.googleapis.com \
    secretmanager.googleapis.com \
    --project="${PROJECT_ID}" \
    --quiet

echo -e "${GREEN}APIs enabled successfully${NC}"

echo -e "${YELLOW}Step 2/7: Creating Artifact Registry repository...${NC}"
if ! gcloud artifacts repositories describe "${REPO_NAME}" \
    --location="${REGION}" \
    --project="${PROJECT_ID}" &>/dev/null; then
    gcloud artifacts repositories create "${REPO_NAME}" \
        --repository-format=docker \
        --location="${REGION}" \
        --description="Multi-Channel Service Docker images" \
        --project="${PROJECT_ID}"
    echo -e "${GREEN}Repository created: ${REPO_NAME}${NC}"
else
    echo -e "${GREEN}Repository already exists: ${REPO_NAME}${NC}"
fi

echo -e "${YELLOW}Step 3/7: Verifying orchestrator-sa Service Account...${NC}"
SA_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

if ! gcloud iam service-accounts describe "${SA_EMAIL}" \
    --project="${PROJECT_ID}" &>/dev/null; then
    echo -e "${YELLOW}Creating orchestrator-sa service account...${NC}"
    gcloud iam service-accounts create "${SERVICE_ACCOUNT_NAME}" \
        --display-name="Orchestrator Service Account" \
        --description="Service account for multi-channel-service and service-to-service communication" \
        --project="${PROJECT_ID}"
    echo -e "${GREEN}Service account created: ${SA_EMAIL}${NC}"
else
    echo -e "${GREEN}Service account exists: ${SA_EMAIL}${NC}"
fi

echo -e "${YELLOW}Step 4/7: Configuring IAM permissions...${NC}"
# Roles for Cloud Run service with service-to-service communication
ROLES=(
    "roles/run.invoker"              # Invoke other Cloud Run services
    "roles/logging.logWriter"         # Write logs
    "roles/monitoring.metricWriter"   # Write metrics
    "roles/secretmanager.secretAccessor"  # Access secrets
)

for ROLE in "${ROLES[@]}"; do
    echo -e "  Adding ${ROLE}..."
    gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
        --member="serviceAccount:${SA_EMAIL}" \
        --role="${ROLE}" \
        --condition=None \
        --quiet 2>/dev/null || true
done

echo -e "${GREEN}IAM permissions configured${NC}"

echo -e "${YELLOW}Step 5/7: Granting Cloud Build permissions...${NC}"
# Cloud Build service account needs permissions
CLOUDBUILD_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"

CLOUDBUILD_ROLES=(
    "roles/run.developer"
    "roles/iam.serviceAccountUser"
    "roles/artifactregistry.writer"
)

for ROLE in "${CLOUDBUILD_ROLES[@]}"; do
    echo -e "  Adding ${ROLE} to Cloud Build..."
    gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
        --member="serviceAccount:${CLOUDBUILD_SA}" \
        --role="${ROLE}" \
        --condition=None \
        --quiet 2>/dev/null || true
done

echo -e "${GREEN}Cloud Build permissions configured${NC}"

echo -e "${YELLOW}Step 6/7: Creating secrets (if not exist)...${NC}"
# Create placeholder secrets if they don't exist
SECRETS=("telegram-bot-token" "webhook-secret")

for SECRET in "${SECRETS[@]}"; do
    if ! gcloud secrets describe "${SECRET}" --project="${PROJECT_ID}" &>/dev/null; then
        echo -e "  Creating secret: ${SECRET}"
        echo -n "REPLACE_ME" | gcloud secrets create "${SECRET}" \
            --data-file=- \
            --project="${PROJECT_ID}" \
            --replication-policy="automatic"
        echo -e "${YELLOW}  Warning: Update ${SECRET} with actual value${NC}"
    else
        echo -e "${GREEN}  Secret exists: ${SECRET}${NC}"
    fi
done

echo -e "${GREEN}Secrets configured${NC}"

echo -e "${YELLOW}Step 7/7: Configuring Docker authentication...${NC}"
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

echo -e "${GREEN}Docker configured for Artifact Registry${NC}"

# Output summary
echo ""
echo -e "${BLUE}============================================${NC}"
echo -e "${GREEN}   Setup Complete!${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo -e "Configuration:"
echo -e "  Project ID: ${GREEN}${PROJECT_ID}${NC}"
echo -e "  Project Number: ${GREEN}${PROJECT_NUMBER}${NC}"
echo -e "  Region: ${GREEN}${REGION}${NC}"
echo -e "  Service Account: ${GREEN}${SA_EMAIL}${NC}"
echo -e "  Repository: ${GREEN}${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo -e "1. Update secrets in Secret Manager:"
echo -e "   gcloud secrets versions add telegram-bot-token --data-file=<(echo -n 'YOUR_TOKEN')"
echo -e "   gcloud secrets versions add webhook-secret --data-file=<(echo -n 'YOUR_SECRET')"
echo -e ""
echo -e "2. Deploy with Cloud Build:"
echo -e "   gcloud builds submit --config=cloudbuild.yaml"
echo -e ""
echo -e "3. Or deploy manually:"
echo -e "   ./deploy/deploy-manual.sh"

# Save output for reference
OUTPUT_FILE="deploy/.gcp-setup-output.txt"
cat > "${OUTPUT_FILE}" << EOF
# GCP Setup Output - $(date)
GCP_PROJECT_ID=${PROJECT_ID}
GCP_PROJECT_NUMBER=${PROJECT_NUMBER}
GCP_REGION=${REGION}
GCP_SA_EMAIL=${SA_EMAIL}

SERVICE_NAME=${SERVICE_NAME}
REPO_NAME=${REPO_NAME}
IMAGE_URL=${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE_NAME}
EOF

echo -e "${GREEN}Configuration saved to ${OUTPUT_FILE}${NC}"
