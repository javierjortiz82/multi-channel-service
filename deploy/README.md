# Multi-Channel Service - Deployment Guide

## Overview

This guide covers deploying the Multi-Channel Service (Telegram Bot) to Google Cloud Run with IAM authentication and service-to-service communication support.

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                       Google Cloud Platform                           │
├──────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  ┌──────────────┐    ┌────────────────────┐    ┌──────────────────┐  │
│  │   Telegram   │───▶│   API Gateway      │───▶│ multi-channel    │  │
│  │   Servers    │    │   (Public)         │    │ (Cloud Run)      │  │
│  └──────────────┘    │                    │    │                  │  │
│                      │ /webhook (public)  │    │ Port: 8080       │  │
│                      │ /health  (public)  │    │ SA: orchestrator │  │
│                      └────────────────────┘    └──────────────────┘  │
│                                                        │              │
│                                                        ▼ (IAM Auth)   │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │                 Other Cloud Run Services                      │    │
│  │   • nlp-service    • bant-service    • sentiment-service     │    │
│  │   • intent-service • mcp-server      • email-service         │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                        │
└──────────────────────────────────────────────────────────────────────┘
```

## URLs

| Component | URL | Access |
|-----------|-----|--------|
| API Gateway | https://multi-channel-gateway-vq1gs9i.uc.gateway.dev | Public |
| Webhook | https://multi-channel-gateway-vq1gs9i.uc.gateway.dev/webhook | Public |
| Cloud Run | https://multi-channel-service-4k3haexkga-uc.a.run.app | IAM |

## Prerequisites

1. **GCP Project** with billing enabled
2. **gcloud CLI** installed and authenticated
3. **Docker** installed (for local builds)
4. **Telegram Bot Token** from [@BotFather](https://t.me/BotFather)

## Quick Start

### 1. Initial Setup (Run Once)

```bash
# Set your project
export GCP_PROJECT_ID="gen-lang-client-0329024102"
gcloud config set project $GCP_PROJECT_ID

# Run setup script
chmod +x deploy/setup-gcp.sh
./deploy/setup-gcp.sh
```

### 2. Configure Secrets

```bash
# Set Telegram Bot Token
echo -n "YOUR_BOT_TOKEN" | gcloud secrets versions add telegram-bot-token --data-file=-

# Set Webhook Secret (generate a random string)
echo -n "$(openssl rand -hex 32)" | gcloud secrets versions add webhook-secret --data-file=-
```

### 3. Deploy

**Option A: Cloud Build (Recommended)**
```bash
gcloud builds submit --config=cloudbuild.yaml
```

**Option B: Manual Deploy**
```bash
chmod +x deploy/deploy-manual.sh
./deploy/deploy-manual.sh
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TELEGRAM_BOT_TOKEN` | Bot API token (Secret) | Required |
| `WEBHOOK_SECRET` | Webhook validation token (Secret) | Required |
| `WEBHOOK_HOST` | Service URL (auto-set) | Service URL |
| `WEBHOOK_PATH` | Webhook endpoint | `/webhook` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `RATE_LIMIT_REQUESTS` | Max requests/minute/IP | `100` |

### Secret Manager

| Secret Name | Description |
|-------------|-------------|
| `telegram-bot-token` | Telegram Bot API token |
| `webhook-secret` | Secret for webhook validation |

## Security

### IAM Authentication

The service uses `--no-allow-unauthenticated`, requiring IAM authentication:

```bash
# Test with identity token
TOKEN=$(gcloud auth print-identity-token)
curl -H "Authorization: Bearer $TOKEN" \
     https://multi-channel-service-xxx.run.app/health
```

### Service Account: orchestrator-sa

Used for:
- Running the Cloud Run service
- Service-to-service communication
- Accessing Secret Manager

Roles assigned:
- `roles/run.invoker` - Call other Cloud Run services
- `roles/logging.logWriter` - Write logs
- `roles/secretmanager.secretAccessor` - Access secrets

## Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/webhook` | POST | Telegram Secret | Telegram webhook |
| `/health` | GET | IAM | Health check |

## Monitoring

### View Logs
```bash
gcloud run logs read multi-channel-service --region=us-central1 --limit=100
```

### Stream Logs
```bash
gcloud run logs tail multi-channel-service --region=us-central1
```

### Service Details
```bash
gcloud run services describe multi-channel-service --region=us-central1
```

## Troubleshooting

### Service Not Starting
1. Check logs: `gcloud run logs read multi-channel-service`
2. Verify secrets exist: `gcloud secrets list`
3. Check IAM: `gcloud run services get-iam-policy multi-channel-service`

### Webhook Not Working
1. Verify WEBHOOK_HOST is set correctly
2. Check Telegram can reach the service (Cloud Run URL must be public)
3. Verify WEBHOOK_SECRET matches in both Telegram and Secret Manager

### Permission Denied
```bash
# Grant invoker permission
gcloud run services add-iam-policy-binding multi-channel-service \
    --region=us-central1 \
    --member="serviceAccount:orchestrator-sa@PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/run.invoker"
```

## Production Testing

### 1. Health Check
```bash
SERVICE_URL=$(gcloud run services describe multi-channel-service \
    --region=us-central1 --format="value(status.url)")
TOKEN=$(gcloud auth print-identity-token --audiences="$SERVICE_URL")
curl -H "Authorization: Bearer $TOKEN" "$SERVICE_URL/health"
```

### 2. Webhook Simulation
```bash
# This requires the actual Telegram secret token
curl -X POST "$SERVICE_URL/webhook" \
    -H "X-Telegram-Bot-Api-Secret-Token: YOUR_SECRET" \
    -H "Content-Type: application/json" \
    -d '{"update_id": 1, "message": {"message_id": 1, "date": 1234567890, "chat": {"id": 123, "type": "private"}, "text": "/start"}}'
```

### 3. Integration with Orchestrator
```python
from internal_service_client import InternalServiceClient

client = InternalServiceClient()
result = await client.call_multi_channel_service(message_data)
```

## File Structure

```
deploy/
├── Dockerfile.cloudrun    # Production Docker image with UV
├── api-gateway-spec.yaml  # API Gateway OpenAPI specification
├── env.production         # Environment variable documentation
├── setup-gcp.sh           # Initial GCP setup script
├── deploy-manual.sh       # Manual deployment script
└── README.md              # This file

cloudbuild.yaml            # Cloud Build CI/CD pipeline
```

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.1.0 | 2025-12 | Added API Gateway for public webhook access |
| 1.0.0 | 2025-12 | Initial Cloud Run deployment |
