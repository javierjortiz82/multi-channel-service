# REQ-1: Bot de Telegram Empresarial con Webhook en Python

## Resumen

Aplicación empresarial en Python (3.10+) que implementa un bot de
Telegram mediante webhook, con arquitectura modular, pydantic v2,
pruebas E2E, CI, cumplimiento PEP8, Docker, seguridad avanzada,
alta concurrencia y mejores prácticas modernas.

## Objetivo

Construir un bot robusto que reciba mensajes desde Telegram, determine
el tipo de input (texto, imagen, documento, etc.) y lo imprima en
consola, manteniendo estándares empresariales de calidad, empaquetado,
pruebas, documentación, containerización y CI/CD.

## Reglas de Implementación

-   TODO debe estar en idioma inglés.
-   Atender *Minor issues* al cierre de cada iteración.
-   Pruebas E2E completas por cada componente.
-   Documentar todo en `README.md`.
-   Actualizar estado del proyecto en `.Claude`.
-   No usar librerías ni patrones legacy.
-   Solo librerías modernas, estables y compatibles.
-   Pydantic v2 para toda la configuración.
-   Código limpio, PEP8, sin imports muertos, sin antipatrones.
-   Revisar `mypy`, `ruff`, `black`, `isort`.
-   Validar `.env.example` frente a `settings.py`.
-   Arquitectura de paquete Python moderno y distribuible.
-   Aplicar SOLID, KISS, DRY.
-   Archivos \< 280 líneas.
-   Type hints completos.
-   Manejo robusto de errores.
-   Sin hardcoding; configuración dinámica.
-   Chain-of-Thought + Self-Consistency en clasificadores.
-   No usar fallbacks: investigar y justificar siempre 2 alternativas
    antes de decidir.
-   Buenas prácticas SIEMPRE como prioridad.
-   Utiliza https://www.makeareadme.com/ para generar documentación readme.md crear diagramas en mermaid usando un estilo visual atractivo y profesional.Utiliza colores de   formas y letras que sean visibles  en los diagramar de mermaid
-   Google docstrings

## Reglas de Docker

-   Dockerfile con multi-stage build para optimización.
-   Usuario no-root para seguridad.
-   Health checks configurados.
-   docker-compose.yml con mejores prácticas.
-   .dockerignore para builds optimizados.
-   Sin redundancia ni hardcoding en configuración.
-   Variables de entorno desde `.env`.
-   Puerto por defecto: 8002.

## Reglas de Concurrencia

-   Uvicorn con múltiples workers para usuarios concurrentes.
-   Factory pattern para aislamiento de procesos.
-   Configuración dinámica de workers vía `WORKERS` env var.
-   `LIMIT_CONCURRENCY`: máximo de conexiones concurrentes por worker.
-   `LIMIT_MAX_REQUESTS`: reinicio de worker tras N requests (previene memory leaks).
-   `BACKLOG`: cola de conexiones pendientes para picos de tráfico.

## Reglas de Timeouts

-   `TIMEOUT_KEEP_ALIVE`: segundos para mantener conexiones idle.
-   `TIMEOUT_GRACEFUL_SHUTDOWN`: tiempo para shutdown graceful.

## Reglas de Performance

-   `HTTP_IMPLEMENTATION`: auto/h11/httptools (httptools es más rápido).
-   `LOOP_IMPLEMENTATION`: auto/asyncio/uvloop (uvloop es más rápido en Linux).

## Reglas de Seguridad del Webhook

-   **Filtrado de IP**: Solo aceptar requests de rangos oficiales de Telegram:
    -   IPv4: `149.154.160.0/20`, `91.108.4.0/22`
    -   IPv6: `2001:67c:4e8::/48`, `2001:b28:f23d::/48`, `2001:b28:f23f::/48`
-   **Secret Token**: Validación del header `X-Telegram-Bot-Api-Secret-Token` con comparación timing-safe (`hmac.compare_digest`).
-   **Rate Limiting**: Algoritmo sliding window para limitar requests por IP.
-   **Security Headers**: X-Content-Type-Options, X-Frame-Options, CSP, HSTS, etc.
-   **Procesamiento en Background**: Respuesta inmediata HTTP 200 a Telegram,
    procesamiento asíncrono con `asyncio.create_task`.
-   **Configuración flexible**: IP filter desactivable para proxies.
-   **PII Protection**: Truncado de contenido en logs para proteger datos sensibles.

## Comparación de Alternativas

### Opción A: aiogram (asíncrono)

-   Moderno, rápido, orientado a arquitectura async.
-   Integración óptima con FastAPI.

### Opción B: python-telegram-bot

-   Maduro, fácil de usar, pero menos eficiente para integraciones async
    grandes.

**Elección:** aiogram + FastAPI por rendimiento, compatibilidad y
escalabilidad.

## Estructura del Proyecto

    multi-channel-service/
    ├─ Dockerfile
    ├─ docker-compose.yml
    ├─ .dockerignore
    ├─ pyproject.toml
    ├─ README.md
    ├─ .env.example
    ├─ .github/workflows/ci.yml
    ├─ REQ/REQ-1.md
    ├─ scripts/validate_env.py
    ├─ logs/
    │  ├─ telegram_bot.log
    │  └─ telegram_bot.error.log
    └─ src/telegram_bot/
       ├─ __init__.py
       ├─ main.py
       ├─ app.py
       ├─ logging_config.py
       ├─ config/
       │  ├─ __init__.py
       │  └─ settings.py          # 28 variables configurables
       ├─ bot/
       │  ├─ __init__.py
       │  └─ handlers/
       │     ├─ __init__.py
       │     └─ message_handler.py
       ├─ services/
       │  ├─ __init__.py
       │  ├─ input_classifier.py
       │  └─ webhook_service.py   # IP filtering & security
       └─ tests/
          ├─ __init__.py
          ├─ conftest.py
          ├─ test_settings.py
          ├─ test_input_classifier.py
          ├─ test_webhook_e2e.py
          └─ test_webhook_service.py

## API Endpoints

| Endpoint | Method | Description | Auth |
|----------|--------|-------------|------|
| `/webhook` | POST | Telegram webhook endpoint | IP Filter + Secret Token + Rate Limit |
| `/health` | GET | Health check endpoint | None |

### Webhook Endpoint Response Codes

| Code | Description |
|------|-------------|
| `200 OK` | Request accepted and queued for processing |
| `400 Bad Request` | Invalid JSON or malformed Telegram update |
| `401 Unauthorized` | Invalid or missing secret token |
| `403 Forbidden` | Request from non-Telegram IP |
| `429 Too Many Requests` | Rate limit exceeded |

### Health Check Response

```json
{
  "status": "healthy"
}
```

## Variables de Configuración (28 total)

### Telegram Bot
| Variable | Descripción | Default | Validación |
|----------|-------------|---------|------------|
| `TELEGRAM_BOT_TOKEN` | Token del bot desde @BotFather | Requerido | SecretStr |

### Webhook
| Variable | Descripción | Default | Validación |
|----------|-------------|---------|------------|
| `WEBHOOK_HOST` | URL pública HTTPS | Requerido | Debe iniciar con http:// o https:// |
| `WEBHOOK_PATH` | Path del endpoint | `/webhook` | Debe iniciar con `/`, alfanumérico |
| `WEBHOOK_SECRET` | Token secreto para verificación | Requerido | SecretStr |
| `WEBHOOK_MAX_CONNECTIONS` | Conexiones HTTPS simultáneas | `100` | 1-100 |
| `WEBHOOK_IP_FILTER_ENABLED` | Filtrar IPs de Telegram | `true` | boolean |
| `WEBHOOK_DROP_PENDING_UPDATES` | Descartar updates pendientes | `true` | boolean |
| `WEBHOOK_MAX_RETRIES` | Reintentos por flood control | `3` | 1-10 |
| `WEBHOOK_RETRY_BUFFER_SECONDS` | Buffer adicional en retry | `0.5` | 0.0-5.0 |

### Server
| Variable | Descripción | Default | Validación |
|----------|-------------|---------|------------|
| `SERVER_HOST` | Host del servidor | `0.0.0.0` | IP válida o hostname |
| `SERVER_PORT` | Puerto del servidor | `8002` | 1-65535 |
| `ENVIRONMENT` | Ambiente de ejecución | `development` | development/staging/production |
| `LOG_LEVEL` | Nivel de log | `INFO` | DEBUG/INFO/WARNING/ERROR/CRITICAL |
| `DEBUG` | Modo debug | `false` | boolean |

### Concurrencia
| Variable | Descripción | Default | Validación |
|----------|-------------|---------|------------|
| `WORKERS` | Workers de uvicorn | `4` | 1-32 |
| `LIMIT_CONCURRENCY` | Conexiones por worker | `100` | 1-10000 |
| `LIMIT_MAX_REQUESTS` | Requests antes de reinicio | `10000` | 0=unlimited |
| `BACKLOG` | Cola de conexiones | `2048` | 1-65535 |

### Timeouts
| Variable | Descripción | Default | Validación |
|----------|-------------|---------|------------|
| `TIMEOUT_KEEP_ALIVE` | Keep-alive (segundos) | `5` | 1-300 |
| `TIMEOUT_GRACEFUL_SHUTDOWN` | Shutdown graceful (segundos) | `30` | 1-300 |

### Performance
| Variable | Descripción | Default | Validación |
|----------|-------------|---------|------------|
| `HTTP_IMPLEMENTATION` | Implementación HTTP | `auto` | auto/h11/httptools |
| `LOOP_IMPLEMENTATION` | Event loop | `auto` | auto/asyncio/uvloop |

### Logging
| Variable | Descripción | Default | Validación |
|----------|-------------|---------|------------|
| `LOG_TO_FILE` | Escribir logs a archivo | `true` | boolean |
| `LOG_DIR` | Directorio de logs | `./logs` | Path válido |
| `LOG_MAX_SIZE_MB` | Tamaño máximo de archivo | `10` | 1-100 MB |
| `LOG_BACKUP_COUNT` | Archivos de backup | `5` | 1-20 |

### Rate Limiting
| Variable | Descripción | Default | Validación |
|----------|-------------|---------|------------|
| `RATE_LIMIT_REQUESTS` | Requests máximos por ventana | `100` | 10-10000 |
| `RATE_LIMIT_WINDOW_SECONDS` | Ventana de tiempo | `60` | 10-3600 segundos |

## Bot Commands

| Comando | Descripción | Respuesta |
|---------|-------------|-----------|
| `/start` | Iniciar el bot | Mensaje de bienvenida con capacidades |
| `/help` | Mostrar ayuda | Lista de comandos y tipos soportados |

### Respuesta de /start

```html
<b>¡Bienvenido!</b> 👋

Soy un bot de Telegram con soporte para webhook.

Puedo procesar diferentes tipos de mensajes:
• Texto
• Fotos
• Documentos
• Videos
• Audio
• Ubicaciones
• Y más...

Usa /help para ver los comandos disponibles.
```

### Respuesta de /help

```html
<b>Comandos disponibles:</b>

/start - Iniciar el bot
/help - Mostrar esta ayuda

<b>Tipos de contenido soportados:</b>
• Mensajes de texto
• Fotos e imágenes
• Documentos y archivos
• Videos y animaciones
• Mensajes de voz y audio
• Ubicaciones y lugares
• Contactos
• Encuestas
• Stickers
```

## Input Classification (InputType Enum)

| Type | Value | Descripción | Ejemplo |
|------|-------|-------------|---------|
| `TEXT` | `text` | Mensajes de texto plano | "Hola, bot!" |
| `COMMAND` | `command` | Comandos del bot | `/start`, `/help` |
| `PHOTO` | `photo` | Fotos e imágenes | Archivos de imagen |
| `DOCUMENT` | `document` | Documentos y archivos | PDF, ZIP, DOCX |
| `VIDEO` | `video` | Videos | MP4, MOV |
| `AUDIO` | `audio` | Archivos de audio | MP3, OGG |
| `VOICE` | `voice` | Mensajes de voz | Grabaciones de voz |
| `VIDEO_NOTE` | `video_note` | Videos redondos | Círculos de video |
| `STICKER` | `sticker` | Stickers | Animados/estáticos |
| `ANIMATION` | `animation` | GIFs | Animaciones |
| `LOCATION` | `location` | Ubicaciones | Coordenadas GPS |
| `VENUE` | `venue` | Lugares | Ubicaciones con nombre |
| `CONTACT` | `contact` | Contactos | Contactos telefónicos |
| `POLL` | `poll` | Encuestas | Preguntas con opciones |
| `DICE` | `dice` | Dados aleatorios | 🎲 🎯 🏀 ⚽ 🎰 🎳 |
| `UNKNOWN` | `unknown` | Tipo no reconocido | Fallback |

## Comportamiento del Webhook

1.  Recibe request de Telegram via POST.
2.  **Rate Limiting**: Verifica límite de requests por IP.
3.  **IP Filter**: Valida IP del cliente (filtro de IPs de Telegram).
4.  **Secret Token**: Valida `X-Telegram-Bot-Api-Secret-Token` con timing-safe comparison.
5.  **JSON Validation**: Parsea y valida JSON payload.
6.  **Update Validation**: Valida estructura del Update con Pydantic.
7.  Crea task en background para procesar.
8.  Responde 200 OK inmediatamente a Telegram.
9.  Clasifica tipo de input usando Chain-of-Thought.
10. Log del tipo detectado con PII protection.

## Security Features

### 1. Rate Limiting

```python
class RateLimiter:
    """Sliding window rate limiting algorithm."""

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._requests: dict[str, list[float]] = {}
        self._lock = asyncio.Lock()
```

- **Algoritmo**: Sliding window con cleanup periódico
- **Thread-safe**: Usa `asyncio.Lock()` para concurrencia
- **Memory-safe**: Limpieza automática de IPs inactivas

### 2. IP Filtering (IPv4 + IPv6)

```python
TELEGRAM_IP_RANGES_V4 = (
    IPv4Network("149.154.160.0/20"),
    IPv4Network("91.108.4.0/22"),
)

TELEGRAM_IP_RANGES_V6 = (
    IPv6Network("2001:67c:4e8::/48"),
    IPv6Network("2001:b28:f23d::/48"),
    IPv6Network("2001:b28:f23f::/48"),
)
```

### 3. Security Headers Middleware

| Header | Value | Propósito |
|--------|-------|-----------|
| `X-Content-Type-Options` | `nosniff` | Previene MIME sniffing |
| `X-Frame-Options` | `DENY` | Previene clickjacking |
| `X-XSS-Protection` | `1; mode=block` | Filtro XSS |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Control de referrer |
| `Cache-Control` | `no-store` | Previene caching de respuestas |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains; preload` | HSTS |
| `Content-Security-Policy` | `default-src 'none'; frame-ancestors 'none'` | CSP |
| `X-Permitted-Cross-Domain-Policies` | `none` | Bloquea políticas cross-domain |
| `Permissions-Policy` | `geolocation=(), microphone=(), camera=()` | Deshabilita APIs sensibles |

### 4. PII Protection

- Contenido de mensajes truncado a 30 caracteres en logs
- Información de usuario limitada a ID y username

### 5. Timing-Safe Authentication

```python
# Comparación segura (constante en tiempo)
hmac.compare_digest(received_token, expected_secret)

# NO USAR (vulnerable a timing attacks)
received_token == expected_secret
```

## Diagramas (Mermaid)

### Arquitectura General

```mermaid
flowchart TD
    subgraph Internet
        A((Telegram\nServers))
    end

    subgraph Security["Security Layer"]
        RL{Rate\nLimiter}
        B{IP Filter\n149.154.160.0/20\n91.108.4.0/22}
        C{Secret Token\nValidation}
    end

    subgraph Application["Application Layer"]
        D[FastAPI\nWebhook Endpoint]
        E[Background Task\nasyncio.create_task]
        F[aiogram\nDispatcher]
        G[Input\nClassifier]
    end

    subgraph Output
        H[(Console\nLogging)]
        I[HTTP 200 OK]
        FL[(File Logs\nRotating)]
    end

    A -->|HTTPS POST| RL
    RL -->|Rate Limited| Z[HTTP 429]
    RL -->|Allowed| B
    B -->|Valid IP| C
    B -->|Invalid IP| X[HTTP 403]
    C -->|Valid Token| D
    C -->|Invalid Token| Y[HTTP 401]
    D --> E
    D -->|Immediate| I
    E --> F
    F --> G
    G -->|print type| H
    G -->|write| FL

    style A fill:#0088cc,color:#fff
    style RL fill:#ff9800,color:#fff
    style B fill:#ff6b6b,color:#fff
    style C fill:#ff6b6b,color:#fff
    style D fill:#4ecdc4,color:#fff
    style E fill:#45b7d1,color:#fff
    style F fill:#96ceb4,color:#fff
    style G fill:#ffeaa7,color:#333
    style H fill:#dfe6e9,color:#333
    style I fill:#00b894,color:#fff
    style FL fill:#795548,color:#fff
    style X fill:#d63031,color:#fff
    style Y fill:#d63031,color:#fff
    style Z fill:#d63031,color:#fff
```

### Arquitectura Docker

```mermaid
flowchart TD
    subgraph Orchestration["Container Orchestration"]
        A[docker-compose.yml]
    end

    subgraph Build["Build Process"]
        B[Dockerfile]
        C[Multi-stage Build]
        D[Builder Stage\nPython 3.12-slim]
        E[Production Stage\nPython 3.12-slim]
    end

    subgraph Security["Security Features"]
        F[Non-root User\nappuser:appgroup\nUID 1000]
        G[Read-only FS]
        H[no-new-privileges]
        I[tmpfs /tmp]
    end

    subgraph Runtime["Runtime Configuration"]
        J[Health Check\n/health endpoint]
        K[Uvicorn Workers\nWORKERS env]
        L[28 ENV Variables]
        M[Resource Limits\nCPU & Memory]
    end

    subgraph Volumes["Volume Mounts"]
        N[./logs:/app/logs:rw]
    end

    A --> B
    B --> C
    C --> D
    C --> E
    E --> F
    E --> G
    E --> H
    E --> I
    E --> J
    E --> K
    E --> L
    A --> M
    A --> N

    style A fill:#3498db,color:#fff
    style B fill:#9b59b6,color:#fff
    style C fill:#9b59b6,color:#fff
    style D fill:#e74c3c,color:#fff
    style E fill:#27ae60,color:#fff
    style F fill:#f39c12,color:#fff
    style G fill:#f39c12,color:#fff
    style H fill:#f39c12,color:#fff
    style I fill:#f39c12,color:#fff
    style J fill:#1abc9c,color:#fff
    style K fill:#1abc9c,color:#fff
    style L fill:#1abc9c,color:#fff
    style M fill:#3498db,color:#fff
    style N fill:#8bc34a,color:#fff
```

### Flujo de Seguridad Completo

```mermaid
flowchart LR
    subgraph Input
        A[Incoming\nRequest]
    end

    subgraph RateLimiting["Rate Limiting"]
        RL{Requests\n< 100/min?}
    end

    subgraph IPValidation["IP Validation"]
        B{IP in\n149.154.160.0/20?}
        C{IP in\n91.108.4.0/22?}
        D{IP in\nIPv6 ranges?}
    end

    subgraph TokenValidation["Token Validation"]
        E{Secret Token\nValid?\nhmac.compare_digest}
    end

    subgraph JSONValidation["JSON Validation"]
        F{Valid\nJSON?}
        G{Valid\nUpdate?}
    end

    subgraph Result
        H[Process\nUpdate]
        I[429\nToo Many]
        J[403\nForbidden]
        K[401\nUnauthorized]
        L[400\nBad Request]
    end

    A --> RL
    RL -->|No| I
    RL -->|Yes| B
    B -->|Yes| E
    B -->|No| C
    C -->|Yes| E
    C -->|No| D
    D -->|Yes| E
    D -->|No| J
    E -->|Yes| F
    E -->|No| K
    F -->|Yes| G
    F -->|No| L
    G -->|Yes| H
    G -->|No| L

    style A fill:#3498db,color:#fff
    style RL fill:#ff9800,color:#fff
    style B fill:#e74c3c,color:#fff
    style C fill:#e74c3c,color:#fff
    style D fill:#2196f3,color:#fff
    style E fill:#f39c12,color:#fff
    style F fill:#9c27b0,color:#fff
    style G fill:#9c27b0,color:#fff
    style H fill:#27ae60,color:#fff
    style I fill:#c0392b,color:#fff
    style J fill:#c0392b,color:#fff
    style K fill:#c0392b,color:#fff
    style L fill:#c0392b,color:#fff
```

### Flujo de Clasificación (Chain-of-Thought)

```mermaid
flowchart LR
    subgraph Input
        A[Telegram\nUpdate]
    end

    subgraph Classification["Chain-of-Thought Classification"]
        B{Check Media\nAttributes}
        C{Check Special\nContent}
        D{Check Text\nContent}
    end

    subgraph MediaTypes["Media Types"]
        M1[photo]
        M2[document]
        M3[video]
        M4[audio]
        M5[voice]
        M6[video_note]
        M7[sticker]
        M8[animation]
    end

    subgraph SpecialTypes["Special Content"]
        S1[location]
        S2[venue]
        S3[contact]
        S4[poll]
        S5[dice]
    end

    subgraph TextTypes["Text Content"]
        T1[command /]
        T2[text]
    end

    subgraph Fallback
        U[unknown]
    end

    subgraph Output
        O[(Log\nPII Protected)]
    end

    A --> B
    B -->|Has Media| M1
    B -->|Has Media| M2
    B -->|Has Media| M3
    B -->|Has Media| M4
    B -->|Has Media| M5
    B -->|Has Media| M6
    B -->|Has Media| M7
    B -->|Has Media| M8
    B -->|No Media| C
    C -->|Has Special| S1
    C -->|Has Special| S2
    C -->|Has Special| S3
    C -->|Has Special| S4
    C -->|Has Special| S5
    C -->|No Special| D
    D -->|Starts /| T1
    D -->|Plain| T2
    D -->|Empty| U

    M1 --> O
    M2 --> O
    T1 --> O
    T2 --> O
    S1 --> O
    U --> O

    style A fill:#0088cc,color:#fff
    style B fill:#9b59b6,color:#fff
    style C fill:#9b59b6,color:#fff
    style D fill:#9b59b6,color:#fff
    style M1 fill:#e74c3c,color:#fff
    style M2 fill:#f39c12,color:#fff
    style M3 fill:#e91e63,color:#fff
    style M4 fill:#ff5722,color:#fff
    style M5 fill:#795548,color:#fff
    style M6 fill:#607d8b,color:#fff
    style M7 fill:#9e9e9e,color:#fff
    style M8 fill:#00bcd4,color:#fff
    style S1 fill:#27ae60,color:#fff
    style S2 fill:#1abc9c,color:#fff
    style S3 fill:#3f51b5,color:#fff
    style S4 fill:#673ab7,color:#fff
    style S5 fill:#ff9800,color:#fff
    style T1 fill:#2196f3,color:#fff
    style T2 fill:#3498db,color:#fff
    style U fill:#95a5a6,color:#fff
    style O fill:#2c3e50,color:#fff
```

### Multi-Worker Architecture

```mermaid
flowchart LR
    subgraph Uvicorn["Uvicorn Server"]
        M["Master Process\nPID 7"]
        W1["Worker 1\nPID 9"]
        W2["Worker 2\nPID 10"]
        W3["Worker 3\nPID 11"]
        W4["Worker 4\nPID 12"]
    end

    subgraph Shared["Shared Resources"]
        BOT["Bot Instance\naiogram"]
        LOG["Log Files\ntelegram_bot.log\ntelegram_bot.error.log"]
        TMP["Banner Lock\n/tmp/.telegram_bot_banner_printed"]
        RL["Rate Limiter\nPer Worker"]
    end

    M --> W1
    M --> W2
    M --> W3
    M --> W4

    W1 --> BOT
    W2 --> BOT
    W3 --> BOT
    W4 --> BOT

    W1 --> LOG
    W2 --> LOG
    W3 --> LOG
    W4 --> LOG

    W1 -.->|First Only| TMP

    W1 --> RL
    W2 --> RL
    W3 --> RL
    W4 --> RL

    style M fill:#e91e63,color:#fff
    style W1 fill:#2196f3,color:#fff
    style W2 fill:#2196f3,color:#fff
    style W3 fill:#2196f3,color:#fff
    style W4 fill:#2196f3,color:#fff
    style BOT fill:#0088cc,color:#fff
    style LOG fill:#795548,color:#fff
    style TMP fill:#607d8b,color:#fff
    style RL fill:#ff9800,color:#fff
```

## Logging Configuration

### Log Files

| Archivo | Descripción | Rotación |
|---------|-------------|----------|
| `telegram_bot.log` | Log principal (todos los niveles) | 10 MB x 5 backups |
| `telegram_bot.error.log` | Solo errores (ERROR+) | 5 MB x 5 backups |

### Log Formats

**Console (Simple)**:
```
2025-12-05 12:30:22 | INFO     | Message here
```

**File (Detailed)**:
```
2025-12-05 12:30:22 | INFO     | telegram_bot.app:function_name:42 - Message here
```

### Startup Banner

```
 ████████╗  ██████╗  ██████╗   ██████╗  ████████╗
 ╚══██╔══╝ ██╔════╝  ██╔══██╗ ██╔═══██╗ ╚══██╔══╝
    ██║    ██║  ███╗ ██████╔╝ ██║   ██║    ██║
    ██║    ██║   ██║ ██╔══██╗ ██║   ██║    ██║
    ██║    ╚██████╔╝ ██████╔╝ ╚██████╔╝    ██║
    ╚═╝     ╚═════╝  ╚═════╝   ╚═════╝     ╚═╝
────────────────────────────────────────────────────────────────────────
  Telegram Bot Webhook Service
────────────────────────────────────────────────────────────────────────
```

### Multi-Worker Banner Lock

- Solo el primer worker imprime el banner
- Usa file lock atómico en `/tmp/.telegram_bot_banner_printed`
- Evita duplicación de output en logs

## Pruebas

### Test Files

| Archivo | Descripción |
|---------|-------------|
| `test_settings.py` | Validación de configuración Pydantic |
| `test_input_classifier.py` | Clasificación de tipos de mensaje |
| `test_webhook_e2e.py` | Tests E2E del webhook |
| `test_webhook_service.py` | IP filtering y seguridad |

### Test Coverage

-   Unit: cobertura de handlers, classifier y webhook_service.
-   Integration: simulación de POST al webhook con payloads reales.
-   E2E: validar impresión correcta y HTTP 200.
-   Security: validar filtrado de IPs, tokens y rate limiting.

### Running Tests

```bash
# All tests with coverage
pytest

# Specific test file
pytest src/telegram_bot/tests/test_input_classifier.py

# With HTML coverage report
pytest --cov-report=html
```

## CI/CD

-   ruff → black → isort → mypy → pytest → build wheel.
-   GitHub Actions integrado.

```bash
# Format
black src/
isort src/

# Lint
ruff check src/

# Type check
mypy src/telegram_bot/
```

## Docker Commands

```bash
# Build and start
docker compose up -d --build

# View logs
docker compose logs -f telegram-bot

# View file logs
tail -f logs/telegram_bot.log

# Restart
docker compose restart

# Stop
docker compose down
```

## Checklist de Calidad

### Código
-   [x] Código PEP8
-   [x] 0 imports muertos
-   [x] mypy sin errores
-   [x] ruff sin warnings
-   [x] black/isort limpios
-   [x] Type hints completos
-   [x] Google docstrings

### Documentación
-   [x] README.md actualizado
-   [x] REQ-1.md actualizado
-   [x] .env.example validado (28 variables)

### Testing
-   [x] Pruebas E2E funcionando
-   [x] Tests de clasificador
-   [x] Tests de webhook
-   [x] Tests de settings
-   [x] Tests de webhook_service

### Docker
-   [x] Dockerfile multi-stage
-   [x] docker-compose.yml con mejores prácticas
-   [x] .dockerignore configurado
-   [x] Usuario no-root en container (UID 1000)
-   [x] Health checks configurados
-   [x] Puerto 8002 por defecto
-   [x] Read-only filesystem
-   [x] tmpfs para /tmp
-   [x] no-new-privileges
-   [x] Resource limits configurados

### Concurrencia
-   [x] Uvicorn workers para concurrencia
-   [x] LIMIT_CONCURRENCY configurado
-   [x] LIMIT_MAX_REQUESTS configurado
-   [x] BACKLOG configurado

### Timeouts
-   [x] TIMEOUT_KEEP_ALIVE configurado
-   [x] TIMEOUT_GRACEFUL_SHUTDOWN configurado

### Performance
-   [x] HTTP_IMPLEMENTATION configurable
-   [x] LOOP_IMPLEMENTATION configurable

### Seguridad
-   [x] Filtrado de IPs de Telegram (IPv4 + IPv6)
-   [x] Validación de secret token (timing-safe)
-   [x] Rate limiting (sliding window)
-   [x] Security headers middleware
-   [x] Procesamiento en background
-   [x] Sin hardcoding en Docker
-   [x] PII protection en logs
-   [x] HSTS habilitado
-   [x] CSP configurado

### Logging
-   [x] Rotating file logs
-   [x] Separate error log
-   [x] Colored console banner
-   [x] Multi-worker safe (banner lock)
-   [x] Graceful permission error handling

## Conclusión

Este documento define el blueprint profesional para una aplicación
empresarial basada en Telegram Webhooks usando Python, aiogram, FastAPI,
Docker y las mejores prácticas modernas de ingeniería, con énfasis en
seguridad avanzada, alta concurrencia, logging robusto y configuración flexible.

**Versión**: 1.1.0
**Última actualización**: 2025-12-05
**Variables de configuración**: 28
**Endpoints**: 2 (`/webhook`, `/health`)
**Bot Commands**: 2 (`/start`, `/help`)
**Input Types**: 16
**Security Layers**: 5 (Rate Limit, IP Filter, Token, JSON, Update)