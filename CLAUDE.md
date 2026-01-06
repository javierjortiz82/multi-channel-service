- Bot Funcional
- DocString
- Security Hardening
- Cloud Run Deployment Configured
- API Gateway Configured
- Intelligent Message Processing (NLP, ASR, OCR)
- Webhook via API Gateway (IMPORTANT)

## Cloud Run Deployment

### Service Configuration
- **Service Name**: multi-channel-service
- **Cloud Run URL**: https://multi-channel-service-4k3haexkga-uc.a.run.app (IAM protected)
- **API Gateway URL**: https://multi-channel-gateway-vq1gs9i.uc.gateway.dev (public webhook)
- **Region**: us-central1
- **Service Account**: orchestrator-sa (shared with other services)
- **Authentication**: IAM for Cloud Run, public for Gateway webhook
- **Port**: 8080
- **Status**: DEPLOYED & OPERATIONAL (2025-12-31)

### IMPORTANT: Webhook Configuration
> **El webhook de Telegram DEBE apuntar al API Gateway, NO a Cloud Run directamente.**
> Cloud Run está protegido por IAM y rechazará las solicitudes de Telegram con 403.

```bash
# Configurar webhook correctamente (apuntar al API Gateway)
WEBHOOK_SECRET=$(gcloud secrets versions access latest --secret=webhook-secret)
BOT_TOKEN=$(gcloud secrets versions access latest --secret=telegram-bot-token)
curl "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook" \
    -d "url=https://multi-channel-gateway-vq1gs9i.uc.gateway.dev/webhook" \
    -d "secret_token=${WEBHOOK_SECRET}"
```

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

## Intelligent Message Processing

### Message Type Routing
- **Text** → NLP Service (Gemini 2.0)
- **Voice/Audio** → ASR Service → NLP Service
- **Photo** → OCR Service → NLP Service

### Backend Services
| Service | URL |
|---------|-----|
| NLP | `nlp-service-4k3haexkga-uc.a.run.app` |
| ASR | `asr-service-4k3haexkga-uc.a.run.app` |
| OCR | `ocr-service-4k3haexkga-uc.a.run.app` |

### Key Components
- `services/message_processor.py`: Routing logic
- `services/internal_client.py`: IAM-authenticated service calls
- `bot/handlers/message_handler.py`: Updated handlers

### Environment Variables for Services
| Variable | Default |
|----------|---------|
| `NLP_SERVICE_URL` | `https://nlp-service-4k3haexkga-uc.a.run.app` |
| `ASR_SERVICE_URL` | `https://asr-service-4k3haexkga-uc.a.run.app` |
| `OCR_SERVICE_URL` | `https://ocr-service-4k3haexkga-uc.a.run.app` |

### Status: FULLY OPERATIONAL (2025-12-31)
- Text messages: Processed via NLP (Gemini 2.0)
- Voice/Audio: ASR transcription + NLP
- Photos: OCR extraction + NLP
- Response time: ~3 seconds

## Conversation Memory (2026-01-06)

El bot mantiene contexto de conversación entre mensajes usando el `chat_id` de Telegram.

### Arquitectura
```
Telegram Message → message_processor.py → internal_client.py → NLP Service
                   (extracts chat_id)     (sends as conversation_id)    (stores in PostgreSQL)
```

### Cambios Realizados
- `services/internal_client.py`: Método `call_nlp_service()` acepta parámetro `conversation_id`
- `services/message_processor.py`: Pasa `chat_id` como `conversation_id` en:
  - `_process_text_message()` (línea 149)
  - `_process_audio_message()` (línea 256)
  - `_process_photo_message()` (línea 346)

### Request Format al NLP Service
```json
{
  "text": "mensaje del usuario",
  "conversation_id": "5850719087"  // Telegram chat_id
}
```

### Flujo de Conversación
1. Usuario envía mensaje a Telegram
2. `message_processor.py` extrae `message.chat.id`
3. `internal_client.py` envía al NLP con `conversation_id`
4. NLP recupera historial de PostgreSQL (últimos 10 mensajes)
5. NLP incluye historial en el prompt para Gemini
6. NLP almacena nuevo mensaje y respuesta
7. Bot responde manteniendo contexto

### Logs de Verificación
```
conversation_history_loaded: messages_count=6, conversation_id=5850719087
unified_template_rendered: has_history=True
```