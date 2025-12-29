- Bot Funcional
- DocString
- Security Hardening
- Cloud Run Deployment Configured
- API Gateway Configured

## Cloud Run Deployment

### Service Configuration
- **Service Name**: multi-channel-service
- **Cloud Run URL**: https://multi-channel-service-4k3haexkga-uc.a.run.app (IAM protected)
- **API Gateway URL**: https://multi-channel-gateway-vq1gs9i.uc.gateway.dev (public webhook)
- **Region**: us-central1
- **Service Account**: orchestrator-sa (shared with other services)
- **Authentication**: IAM for Cloud Run, public for Gateway webhook
- **Port**: 8080
- **Status**: DEPLOYED (2025-12-28)

### API Gateway
- **Gateway Name**: multi-channel-gateway
- **API Name**: multi-channel-api
- **Config**: multi-channel-config-v1
- **Webhook URL**: https://multi-channel-gateway-vq1gs9i.uc.gateway.dev/webhook
- **Health URL**: https://multi-channel-gateway-vq1gs9i.uc.gateway.dev/health

### Secret Manager
- `telegram-bot-token`: Telegram Bot API token
- `webhook-secret`: Secret token for webhook validation

### Code Reviews Completed
- ruff (lint + format)
- mypy (types)
- bandit (security)
- pytest (tests)

### Deployment Commands
```bash
# Initial setup (run once)
./deploy/setup-gcp.sh

# Deploy with Cloud Build
gcloud builds submit --config=cloudbuild.yaml

# Manual deploy
./deploy/deploy-manual.sh
```

### Key Files
- `deploy/Dockerfile.cloudrun`: Production Docker image with UV
- `deploy/env.production`: Environment variable documentation
- `deploy/setup-gcp.sh`: GCP infrastructure setup
- `deploy/deploy-manual.sh`: Manual deployment script
- `cloudbuild.yaml`: Cloud Build CI/CD pipeline

### Testing Production
```bash
# Health check via API Gateway (public)
curl https://multi-channel-gateway-vq1gs9i.uc.gateway.dev/health

# Health check via Cloud Run (IAM required)
SERVICE_URL=$(gcloud run services describe multi-channel-service --region=us-central1 --format="value(status.url)")
TOKEN=$(gcloud auth print-identity-token --audiences="$SERVICE_URL")
curl -H "Authorization: Bearer $TOKEN" "$SERVICE_URL/health"

# Check Telegram webhook status
BOT_TOKEN=$(gcloud secrets versions access latest --secret=telegram-bot-token)
curl "https://api.telegram.org/bot$BOT_TOKEN/getWebhookInfo"
```