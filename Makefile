# =============================================================================
# Makefile for Multi-Channel Service (Telegram Bot)
# =============================================================================
# Fast deployment with UV package manager and Cloud Build
#
# Quick Start:
#   make deploy     - Deploy to Cloud Run (~2-3 min)
#   make logs       - View recent logs
#   make health     - Check service health
#
# Best Practices Applied:
#   - Pre-deployment validation (lint + format check)
#   - Semantic color coding (cyan=info, green=success, yellow=warning, red=error)
#   - Secret Manager integration (no hardcoded secrets)
#   - IAM-aware health checks
# =============================================================================

# All targets that don't produce files
.PHONY: help dev test lint format deploy deploy-quick logs logs-live logs-asr \
        url health webhook webhook-reset docker-build docker-run clean install \
        info validate check-gcp setup-secrets

# -----------------------------------------------------------------------------
# Colors (ANSI escape codes)
# -----------------------------------------------------------------------------
CYAN := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
RESET := \033[0m
BOLD := \033[1m

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
PROJECT_ID := gen-lang-client-0329024102
REGION := us-central1
SERVICE_NAME := multi-channel-service
GATEWAY_URL := https://multi-channel-gateway-vq1gs9i.uc.gateway.dev

# Related services
ASR_SERVICE := asr-service
NLP_SERVICE := nlp-service
OCR_SERVICE := ocr-service

# =============================================================================
# Default: Show help
# =============================================================================
.DEFAULT_GOAL := help

help:
	@echo ""
	@echo "$(BOLD)Multi-Channel Service$(RESET) (Telegram Bot)"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@echo "$(CYAN)Development:$(RESET)"
	@echo "  make dev           Run local bot (requires TELEGRAM_BOT_TOKEN)"
	@echo "  make test          Run pytest"
	@echo "  make lint          Run ruff lint + format check"
	@echo "  make format        Auto-format code with ruff"
	@echo "  make install       Create venv and install dependencies"
	@echo ""
	@echo "$(GREEN)Deployment:$(RESET)"
	@echo "  make deploy        Deploy with validation (lint + format)"
	@echo "  make deploy-quick  Deploy without validation (faster)"
	@echo "  make validate      Run lint + format check only"
	@echo ""
	@echo "$(YELLOW)Monitoring:$(RESET)"
	@echo "  make logs          View recent logs (last 50)"
	@echo "  make logs-live     Stream logs real-time"
	@echo "  make logs-asr      View ASR service logs"
	@echo ""
	@echo "$(CYAN)Health & Status:$(RESET)"
	@echo "  make health        Check service health via Gateway"
	@echo "  make webhook       Check Telegram webhook status"
	@echo "  make webhook-reset Reset webhook to Gateway URL"
	@echo "  make info          Show service info and status"
	@echo "  make url           Show service URLs"
	@echo ""
	@echo "$(CYAN)Docker (Local):$(RESET)"
	@echo "  make docker-build  Build Docker image locally"
	@echo "  make docker-run    Run container locally"
	@echo ""
	@echo "$(CYAN)Setup:$(RESET)"
	@echo "  make check-gcp     Verify GCP configuration"
	@echo "  make setup-secrets Show required secrets"
	@echo "  make clean         Remove cache files"
	@echo ""

# =============================================================================
# Development
# =============================================================================
dev:
	@echo "$(CYAN)Starting local bot...$(RESET)"
	@echo "$(YELLOW)Requires: TELEGRAM_BOT_TOKEN env var$(RESET)"
	@if [ -f .venv/bin/activate ]; then \
		. .venv/bin/activate && python -m src.telegram_bot.main; \
	else \
		echo "$(RED)Error: .venv not found. Run 'make install' first$(RESET)"; \
		exit 1; \
	fi

test:
	@echo "$(CYAN)Running tests...$(RESET)"
	@if [ -f .venv/bin/activate ]; then \
		. .venv/bin/activate && pytest src/ -v --tb=short && \
		echo "$(GREEN)Tests passed!$(RESET)"; \
	else \
		echo "$(RED)Error: .venv not found. Run 'make install' first$(RESET)"; \
		exit 1; \
	fi

lint:
	@echo "$(CYAN)Running linters...$(RESET)"
	@ruff check src/
	@ruff format --check src/
	@echo "$(GREEN)Lint passed!$(RESET)"

format:
	@echo "$(CYAN)Formatting code...$(RESET)"
	@ruff format src/
	@ruff check --fix src/
	@echo "$(GREEN)Format complete!$(RESET)"

# =============================================================================
# Validation (Pre-deployment checks)
# =============================================================================
validate:
	@echo "$(CYAN)Validating code...$(RESET)"
	@ruff check src/ || (echo "$(RED)Lint failed!$(RESET)" && exit 1)
	@ruff format --check src/ || (echo "$(RED)Format check failed! Run 'make format'$(RESET)" && exit 1)
	@echo "$(GREEN)Validation passed!$(RESET)"

check-gcp:
	@echo "$(CYAN)Verifying GCP configuration...$(RESET)"
	@echo "Project: $$(gcloud config get-value project)"
	@echo "Account: $$(gcloud config get-value account)"
	@echo ""
	@echo "$(CYAN)Checking required APIs...$(RESET)"
	@gcloud services list --enabled --filter="name:run.googleapis.com OR name:cloudbuild.googleapis.com OR name:speech.googleapis.com" \
		--format="table(config.name)" --project=$(PROJECT_ID) 2>/dev/null || echo "$(YELLOW)Could not verify APIs$(RESET)"

# =============================================================================
# Deployment
# =============================================================================
deploy: validate
	@echo ""
	@echo "$(BOLD)Deploying $(SERVICE_NAME)...$(RESET)"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "$(CYAN)Config: min-instances=1 (always warm)$(RESET)"
	@echo ""
	@gcloud builds submit \
		--config=cloudbuild.yaml \
		--project=$(PROJECT_ID) \
		--quiet
	@echo ""
	@echo "$(GREEN)$(BOLD)Deploy complete!$(RESET)"
	@echo ""
	@make -s url

deploy-quick:
	@echo ""
	@echo "$(BOLD)Deploying $(SERVICE_NAME) (quick mode)...$(RESET)"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "$(YELLOW)Skipping validation (use 'make deploy' for full checks)$(RESET)"
	@echo ""
	@gcloud builds submit \
		--config=cloudbuild.yaml \
		--project=$(PROJECT_ID) \
		--quiet
	@echo ""
	@echo "$(GREEN)$(BOLD)Deploy complete!$(RESET)"
	@echo ""
	@make -s url

# =============================================================================
# Logs
# =============================================================================
logs:
	@gcloud run services logs read $(SERVICE_NAME) \
		--region=$(REGION) \
		--project=$(PROJECT_ID) \
		--limit=50

logs-live:
	@echo "$(CYAN)Streaming logs (Ctrl+C to stop)...$(RESET)"
	@gcloud run services logs tail $(SERVICE_NAME) \
		--region=$(REGION) \
		--project=$(PROJECT_ID)

logs-asr:
	@echo "$(CYAN)ASR Service logs (last 30)...$(RESET)"
	@gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="$(ASR_SERVICE)"' \
		--limit=30 \
		--format="table(timestamp,textPayload)" \
		--project=$(PROJECT_ID)

logs-error:
	@echo "$(CYAN)Recent errors (all services)...$(RESET)"
	@gcloud logging read 'resource.type="cloud_run_revision" AND severity>=ERROR' \
		--limit=20 \
		--format="table(timestamp,resource.labels.service_name,textPayload)" \
		--project=$(PROJECT_ID)

# =============================================================================
# Health & Status
# =============================================================================
url:
	@echo "$(BOLD)Service URLs:$(RESET)"
	@echo "  Gateway:  $(GATEWAY_URL)"
	@echo "  Cloud Run: $$(gcloud run services describe $(SERVICE_NAME) --region=$(REGION) --project=$(PROJECT_ID) --format='value(status.url)' 2>/dev/null || echo 'N/A')"

health:
	@echo "$(CYAN)Checking health via Gateway...$(RESET)"
	@curl -s "$(GATEWAY_URL)/health" | python3 -m json.tool || echo "$(RED)Health check failed$(RESET)"

health-direct:
	@echo "$(CYAN)Checking health via Cloud Run (IAM)...$(RESET)"
	@TOKEN=$$(gcloud auth print-identity-token) && \
	URL=$$(gcloud run services describe $(SERVICE_NAME) --region=$(REGION) --project=$(PROJECT_ID) --format='value(status.url)') && \
	curl -s -H "Authorization: Bearer $$TOKEN" "$$URL/health" | python3 -m json.tool

webhook:
	@echo "$(CYAN)Checking Telegram webhook...$(RESET)"
	@BOT_TOKEN=$$(gcloud secrets versions access latest --secret=telegram-bot-token --project=$(PROJECT_ID)) && \
	curl -s "https://api.telegram.org/bot$$BOT_TOKEN/getWebhookInfo" | python3 -m json.tool

webhook-reset:
	@echo "$(YELLOW)Resetting webhook to Gateway...$(RESET)"
	@BOT_TOKEN=$$(gcloud secrets versions access latest --secret=telegram-bot-token --project=$(PROJECT_ID)) && \
	WEBHOOK_SECRET=$$(gcloud secrets versions access latest --secret=webhook-secret --project=$(PROJECT_ID)) && \
	curl -s "https://api.telegram.org/bot$$BOT_TOKEN/setWebhook?url=$(GATEWAY_URL)/webhook&secret_token=$$WEBHOOK_SECRET&drop_pending_updates=true" | python3 -m json.tool
	@echo "$(GREEN)Webhook configured!$(RESET)"

# =============================================================================
# Docker (Local Development)
# =============================================================================
docker-build:
	@echo "$(CYAN)Building Docker image...$(RESET)"
	@docker build -f deploy/Dockerfile.cloudrun -t $(SERVICE_NAME):local .
	@echo "$(GREEN)Build complete: $(SERVICE_NAME):local$(RESET)"

docker-run:
	@echo "$(CYAN)Running container locally...$(RESET)"
	@echo "$(YELLOW)Fetching secrets from Secret Manager...$(RESET)"
	@docker run -p 8080:8080 \
		-e PORT=8080 \
		-e TELEGRAM_BOT_TOKEN=$$(gcloud secrets versions access latest --secret=telegram-bot-token --project=$(PROJECT_ID)) \
		-e WEBHOOK_SECRET=$$(gcloud secrets versions access latest --secret=webhook-secret --project=$(PROJECT_ID)) \
		$(SERVICE_NAME):local

# =============================================================================
# Setup & Utilities
# =============================================================================
install:
	@echo "$(CYAN)Creating virtual environment...$(RESET)"
	@python3 -m venv .venv
	@echo "$(CYAN)Installing UV and dependencies...$(RESET)"
	@. .venv/bin/activate && pip install --quiet uv && uv pip install -r requirements.txt
	@echo ""
	@echo "$(GREEN)$(BOLD)Installation complete!$(RESET)"
	@echo "Activate with: $(CYAN)source .venv/bin/activate$(RESET)"

setup-secrets:
	@echo "$(BOLD)Required Secrets in Secret Manager:$(RESET)"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "  telegram-bot-token  - Telegram Bot API token"
	@echo "  webhook-secret      - Secret for webhook validation"
	@echo ""
	@echo "$(CYAN)Current secrets in project:$(RESET)"
	@gcloud secrets list --project=$(PROJECT_ID) --format="table(name)" 2>/dev/null || echo "$(YELLOW)Could not list secrets$(RESET)"

clean:
	@echo "$(CYAN)Cleaning cache files...$(RESET)"
	@rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "$(GREEN)Clean!$(RESET)"

# =============================================================================
# Service Info
# =============================================================================
info:
	@echo ""
	@echo "$(BOLD)Service Information$(RESET)"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@echo "$(CYAN)Cloud Run Service:$(RESET)"
	@gcloud run services describe $(SERVICE_NAME) \
		--region=$(REGION) \
		--project=$(PROJECT_ID) \
		--format="table(status.url,spec.template.metadata.annotations.'autoscaling.knative.dev/minScale',spec.template.spec.containers[0].resources.limits.memory)" 2>/dev/null || echo "Service not found"
	@echo ""
	@echo "$(CYAN)Related Services:$(RESET)"
	@echo "  ASR: https://$(ASR_SERVICE)-4k3haexkga-uc.a.run.app"
	@echo "  NLP: https://$(NLP_SERVICE)-4k3haexkga-uc.a.run.app"
	@echo "  OCR: https://$(OCR_SERVICE)-4k3haexkga-uc.a.run.app"
	@echo ""
	@make -s webhook
