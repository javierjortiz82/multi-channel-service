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
- **Text** → NLP Service (Gemini 2.0 Flash)
- **Voice/Audio** → ASR Service → NLP Service
- **Photo** → OCR Analyze Service (auto-classification) → NLP Service
  - **Document images**: OCR text extraction → NLP interpretation
  - **Object images**: Object detection → NLP product search (MCP tools)

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

### Status: FULLY OPERATIONAL (2026-01-21)
- Text messages: Processed via NLP (Gemini 2.0 Flash)
- Voice/Audio: ASR transcription + NLP
- Photos: Intelligent routing (document → OCR, object → detection + product search)
- Response time: ~6-7 seconds (with MCP tool calls)

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

## Object Detection in Images (2026-01-20)

El bot detecta automáticamente si una imagen es un documento o un objeto y procesa cada tipo de forma diferente.

### Flujo de Procesamiento de Imágenes
```
Photo → call_analyze_service(mode="auto")
          ↓
   ┌──────┴──────┐
   │             │
document      object
   ↓             ↓
OCR text     Object detection
extraction   + product search
   ↓             ↓
NLP          NLP + MCP tools
interpret    (fuzzy_search_smart)
```

### Archivos Modificados
- `services/internal_client.py`: Agregado `call_analyze_service()` para endpoint `/analyze/upload`
- `services/message_processor.py`:
  - `_process_photo_message()`: Usa analyze endpoint con clasificación automática
  - `_handle_document_image()`: Procesa documentos (OCR + interpretación)
  - `_handle_object_image()`: Procesa objetos (detección + búsqueda de productos)

### Endpoint OCR Analyze
```
POST /analyze/upload
- mode: auto (clasifica automáticamente)
- Retorna: classification.predicted_type (document|object)
- Para objects: detection_result.objects[].name
- Para documents: ocr_result.text
```

### Logs Esperados
```
Calling analyze service: file=photo.jpg, mode=auto
Analyze completed: type=object
Image classified: type=object, confidence=0.92
Objects detected: Laptop, description: "laptop, HP, silver..."
Calling NLP service with 312 characters
```

## Visual Search Confidence Tiers (2026-01-22)

El sistema de búsqueda visual usa un sistema de 4 niveles de confianza para mejorar la experiencia del cliente.

### Problema Resuelto
Antes: búsqueda visual con threshold binario (60%) filtraba silenciosamente productos sin comunicar al cliente.
Ahora: sistema de tiers que comunica honestamente la calidad de los resultados.

### Arquitectura
```
Photo → OCR Service (embedding) → MCP Server (tier classification) → NLP Service (formatting) → Bot Response
                                        ↓
                              confidence_tier + best_match_score
```

### Thresholds de Confianza

| Tier | Similitud | Comportamiento | Mensaje al Cliente |
|------|-----------|----------------|-------------------|
| **high** | ≥75% | Mostrar productos | "Encontré estos productos similares:" |
| **medium** | 60-75% | Mostrar con nota | "Estos productos podrían interesarte:" |
| **low** | 45-60% | Mostrar con `low_confidence: True` | "No encontré exactos, pero quizás te interesen:" |
| **none** | <45% | Filtrar | "No tenemos productos similares. ¿Puedo ayudarte?" |

### Archivos Modificados

**MCP Server** (`/home/javort/mcp-server/tools/sales/embedding_search.py`):
- Constantes: `HIGH_CONFIDENCE_THRESHOLD`, `MEDIUM_CONFIDENCE_THRESHOLD`, `LOW_CONFIDENCE_THRESHOLD`
- Response incluye: `confidence_tier`, `best_match_score`
- Items en tier `low` marcados con `low_confidence: True`

**NLP Service** (`/home/javort/nlp-service/app/services/function_calling.py`):
- `_format_visual_search_results()`: Formatea según tier
- Logging: `visual_search_executed` con `confidence_tier` y `best_match_score`

### Response Format del MCP Server
```json
{
  "items": [...],
  "count": 5,
  "total_count": 15,
  "confidence_tier": "high",
  "best_match_score": 0.956,
  "search_type": "embedding_similarity"
}
```

### Logs de Verificación
```
# MCP Server
visual_search_tier_classification: tier=high, high=5, medium=0, low=0, best_score=0.956, returning=5 items

# NLP Service
visual_search_executed: confidence_tier=high, best_match_score=0.956, results_count=5
```

### Patrón Consistente
Sigue el mismo patrón de 4 tiers que `fuzzy_search.py` (Tier 1, 2, 2.5, 3) para consistencia en toda la aplicación.

---

## Image Recognition Flow (2026-01-22)

Documentación completa del flujo de procesamiento de imágenes para búsqueda visual de productos.

### Flujo Completo de Procesamiento

```
Usuario envía foto → Telegram → Multi-Channel → OCR Service → NLP Service → MCP Server
                                     ↓
                            Clasificación + Embedding
```

### 1. Recepción de Imagen (Multi-Channel Service)

**Archivo:** `src/telegram_bot/services/message_processor.py`

```python
# Línea 485: Obtener foto más grande
photo = message.photo[-1]
file = await bot.get_file(photo.file_id)

# Línea 503: Descargar contenido
image_content = file_bytes.read()

# Línea 511-517: Llamar OCR Service
analyze_result = await self._client.call_analyze_service(
    file_content=image_content,
    filename="photo.jpg",
    mode="auto",  # Clasificación automática
)
```

### 2. Clasificación: Documento vs Objeto (OCR Service)

**Archivo:** `/home/javort/ocr-service/app/services/classifier.py`

#### Paso 1: Análisis PIL (Rápido, Gratis)
Calcula 6 métricas:
- **Entropía**: Información aleatoria (documentos < 5.0)
- **White Ratio**: % píxeles blancos (documentos > 0.3)
- **Color Variance**: Varianza RGB (objetos > 6000)
- **Edge Ratio**: % bordes detectados
- **Aspect Ratio**: Relación ancho/alto
- **Brightness Mean**: Brillo promedio

#### Paso 2: Vision API (Fallback si confianza < 0.8)
- Usa LABEL_DETECTION de Google Cloud Vision
- Cuenta labels de documentos (text, receipt, invoice, etc.)

**Resultado:**
```json
{
  "predicted_type": "object",
  "confidence": 0.92,
  "method": "pil_analysis"
}
```

### 3. Generación del Embedding (Solo para Objetos)

**Archivo:** `/home/javort/ocr-service/app/services/embedding_service.py`

#### Paso 1: Descripción con Gemini Vision
```python
# Línea 72-109: describe_image()
# Modelo: gemini-2.0-flash
# Prompt optimizado para búsqueda de productos

response = await client.aio.models.generate_content(
    model="gemini-2.0-flash",
    contents=[
        types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
        IMAGE_DESCRIPTION_PROMPT,  # "Describe this image with keywords..."
    ],
)
# Resultado: "laptop, HP, silver, aluminum, gaming, 15-inch"
```

#### Paso 2: Vector Embedding
```python
# Línea 111-142: generate_embedding()
# Modelo: gemini-embedding-001
# Output: 1536 dimensiones

response = client.models.embed_content(
    model="gemini-embedding-001",
    contents=description,  # La descripción del paso anterior
    config=types.EmbedContentConfig(
        task_type="SEMANTIC_SIMILARITY",
        output_dimensionality=1536,
    ),
)
# Resultado: [0.123, 0.456, ..., 0.789]  # 1536 floats
```

### 4. Respuesta del OCR Service

```json
{
  "classification": {
    "predicted_type": "object",
    "confidence": 0.92
  },
  "image_embedding": [0.123, ...],
  "image_description": "laptop, HP, silver, aluminum...",
  "detection_result": {
    "objects": [{"name": "Laptop", "confidence": 0.95}]
  }
}
```

### 5. Búsqueda Visual (MCP Server)

**Archivo:** `/home/javort/mcp-server/tools/sales/embedding_search.py`

```sql
-- Búsqueda por similitud coseno (pgvector)
SELECT *, 1 - (image_embedding <=> $1) AS similarity_score
FROM products
WHERE image_embedding IS NOT NULL
ORDER BY image_embedding <=> $1
LIMIT 5
```

### Diagrama Visual Completo

```
┌──────────────────┐
│ Usuario envía    │
│ foto de reloj    │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Multi-Channel    │
│ Descarga imagen  │
│ Llama OCR        │
└────────┬─────────┘
         │
         ▼
┌──────────────────────────────────────────┐
│ OCR Service: /analyze/upload             │
│                                          │
│ 1. Clasificar (PIL → Vision API)         │
│    → "object" (confidence: 0.92)         │
│                                          │
│ 2. Generar Embedding (si es objeto):     │
│    a) Gemini Vision: "watch, BULOVA..."  │
│    b) Gemini Embed: [0.12, 0.45, ...]    │
│                                          │
│ Response:                                │
│   image_embedding: [1536 floats]         │
│   image_description: "watch, BULOVA..."  │
└────────┬─────────────────────────────────┘
         │
         ▼
┌──────────────────┐
│ NLP Service      │
│ Recibe embedding │
│ Llama MCP        │
└────────┬─────────┘
         │
         ▼
┌──────────────────────────────────────────┐
│ MCP Server: search_products_by_embedding │
│                                          │
│ Búsqueda pgvector (similitud coseno)     │
│ → Productos con similarity_score         │
│ → Sistema de 4 tiers de confianza        │
└──────────────────────────────────────────┘
```

### Archivos Clave

| Función | Archivo | Líneas |
|---------|---------|--------|
| Recibir foto | `message_processor.py` | 457-568 |
| Clasificar imagen | `classifier.py` | 468-542 |
| Describir imagen | `embedding_service.py` | 72-109 |
| Generar embedding | `embedding_service.py` | 111-142 |
| Búsqueda visual | `embedding_search.py` | 25-191 |

### Modelos de IA Usados

| Modelo | Propósito | Output |
|--------|-----------|--------|
| `gemini-2.0-flash` | Describir imagen | Texto: "laptop, HP, silver..." |
| `gemini-embedding-001` | Generar vector | 1536 dimensiones |
| Vision API (LABEL_DETECTION) | Clasificar documento/objeto | Labels + confidence |
| Vision API (OBJECT_LOCALIZATION) | Detectar objetos | Nombre + bounding box |

---

## NLP Service Model Change (2026-01-21)

### Cambio de Modelo
- **Anterior**: `gemini-2.5-flash` (preview, quotas restrictivas, causaba 429)
- **Intentados**: `gemini-1.5-flash`, `gemini-1.5-pro` (error 404 NOT_FOUND en Vertex AI)
- **Intentado**: `gemini-2.0-flash-exp` (resuelve a `gemini-experimental`, también quota issues)
- **Actual**: `gemini-2.0-flash` ✅ (funciona correctamente)

### Razón del Cambio
El modelo `gemini-2.5-flash` causaba errores `429 RESOURCE_EXHAUSTED` frecuentes debido a:
- Rate limits internos no visibles en GCP Console
- Quotas de modelos preview más restrictivas
- Límites que no se pueden aumentar vía Console

### Comando de Actualización
```bash
gcloud run services update nlp-service \
  --region=us-central1 \
  --update-env-vars="GEMINI_MODEL=gemini-2.0-flash"
```

### Verificar Modelo Actual
```bash
gcloud run services describe nlp-service \
  --region=us-central1 \
  --format="value(spec.template.spec.containers[0].env)" | grep GEMINI_MODEL
```

### Troubleshooting 429 Errors
| Síntoma | Causa | Solución |
|---------|-------|----------|
| 429 RESOURCE_EXHAUSTED | Quota agotada | Esperar 1-5 min o cambiar modelo |
| Quota muestra "ilimitado" | Rate limit interno | Usar `gemini-2.0-flash` (modelo estable) |
| 404 NOT_FOUND | Modelo no disponible | Verificar nombre exacto del modelo |
| Errores intermitentes | Picos de uso | Implementar retry con backoff |

### Modelos Probados (Vertex AI via Google GenAI SDK)
| Modelo | Estado | Notas |
|--------|--------|-------|
| `gemini-2.5-flash` | ❌ 429 | Preview, quotas restrictivas |
| `gemini-1.5-flash` | ❌ 404 | No disponible en proyecto |
| `gemini-1.5-pro` | ❌ 404 | No disponible en proyecto |
| `gemini-2.0-flash-exp` | ❌ 429 | Resuelve a gemini-experimental |
| `gemini-2.0-flash` | ✅ OK | **Modelo actual recomendado** |