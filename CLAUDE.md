## Project Expertise

**Lee `expertise/project.yaml` para conocimiento acumulado del proyecto.**

Contiene:
- Lecciones aprendidas y errores comunes
- Patrones y convenciones del proyecto
- Troubleshooting quick reference
- Preferencias del usuario

---

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

### CRITICAL: Webhook Configuration
> **El webhook de Telegram DEBE apuntar al API Gateway, NO a Cloud Run directamente.**
> Cloud Run está protegido por IAM (política de organización impide acceso público).

**Arquitectura obligatoria:**
```
Telegram → API Gateway (público) → Cloud Run (privado/IAM)
              ↓
         X-Telegram-Bot-Api-Secret-Token validado por el servicio
```

**Configurar webhook (con secret_token):**
```bash
# Obtener credenciales desde Secret Manager (NUNCA hardcodear tokens)
WEBHOOK_SECRET=$(gcloud secrets versions access latest --secret=webhook-secret)
BOT_TOKEN=$(gcloud secrets versions access latest --secret=telegram-bot-token)

# Configurar webhook - INCLUIR secret_token ES OBLIGATORIO
curl "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook?url=https://multi-channel-gateway-vq1gs9i.uc.gateway.dev/webhook&secret_token=${WEBHOOK_SECRET}"
```

**Verificar webhook:**
```bash
curl "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo"
# Debe mostrar: url=gateway, pending_update_count=0, NO last_error_message
```

### Troubleshooting Webhook

| Error | Causa | Solución |
|-------|-------|----------|
| 404 Not Found | URL apunta a ngrok expirado | Reconfigurar con API Gateway URL |
| 401 Unauthorized | Falta `secret_token` en setWebhook | Agregar `&secret_token=...` al setWebhook |
| 403 Forbidden | URL apunta a Cloud Run directo | Cambiar a API Gateway URL |
| "Invalid secret token" | Token no coincide | Verificar secret en Secret Manager |
| pending_update_count > 0 | Mensajes no procesados | Verificar que el servicio responda |

**Script de diagnóstico rápido:**
```bash
# 1. Verificar gateway responde
curl -s https://multi-channel-gateway-vq1gs9i.uc.gateway.dev/health
# Debe retornar: {"status":"healthy"}

# 2. Verificar webhook config
curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo" | python3 -m json.tool

# 3. Si hay errores, reconfigurar:
WEBHOOK_SECRET=$(gcloud secrets versions access latest --secret=webhook-secret)
curl "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook?url=https://multi-channel-gateway-vq1gs9i.uc.gateway.dev/webhook&secret_token=${WEBHOOK_SECRET}"
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

## Image Similarity Search (2026-01-17)

Búsqueda de productos por similitud de imagen estilo Google Lens.

### Arquitectura
```
Telegram Photo → OCR Service (classify + embed) → Multi-Channel Service
                         ↓
                 image_embedding (if object/mixed)
                         ↓
                 MCP Server → pgvector search → Similar products
                         ↓
                 NLP Service → Format response → User
```

### Prioridades de Procesamiento
1. **Prioridad 1**: Documentos con texto → OCR + NLP
2. **Prioridad 2**: Imágenes con embedding → Buscar productos similares
3. **Prioridad 3**: Objetos detectados → Descripción genérica

### Componentes Modificados

| Servicio | Archivo | Cambio |
|----------|---------|--------|
| OCR | `app/services/embedding_service.py` | NUEVO - Genera embeddings de imagen |
| OCR | `app/services/analyzer.py` | Incluye embedding en respuesta |
| OCR | `app/models/response.py` | Campos `image_embedding`, `image_description` |
| MCP | `tools/sales/image_search.py` | NUEVO - Búsqueda por vector |
| MCP | `server.py` | Endpoint `/api/v1/image-search` |
| MCP | `sql/004_add_image_url.sql` | Migración para `image_url` |
| Multi-Channel | `services/internal_client.py` | Método `search_products_by_embedding()` |
| Multi-Channel | `services/message_processor.py` | Lógica de 3 prioridades |

### Environment Variables
| Variable | Default |
|----------|---------|
| `MCP_SERVICE_URL` | `https://mcp-server-4k3haexkga-uc.a.run.app` |

### Respuesta del OCR Service
```json
{
  "result": "keyboard",
  "classification": {"predicted_type": "object", "confidence": 0.92},
  "image_embedding": [0.123, -0.456, ...],
  "image_description": "Black mechanical keyboard with RGB lighting"
}
```

### Request al MCP Server
```bash
curl -X POST https://mcp-server/api/v1/image-search \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"embedding": [...], "limit": 5, "max_distance": 0.5}'
```

### Logs de Verificación
```
Image analyzed: type=object, confidence=0.92, has_embedding=True
Priority 2: Searching products by image similarity
Image search found 3 products (best similarity: 0.85)
```