# =============================================================================
# Makefile for Multi-Channel Service (Telegram Bot)
# =============================================================================
# Fast deployment with UV package manager
#
# Quick Start:
#   make deploy     - Deploy to Cloud Run (~2-3 min)
#   make logs       - View recent logs
#   make test-bot   - Test bot health
# =============================================================================

.PHONY: help dev test lint deploy logs health clean

# Colors
CYAN := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
RESET := \033[0m
BOLD := \033[1m

# Configuration
PROJECT_ID := gen-lang-client-0329024102
REGION := us-central1
SERVICE_NAME := multi-channel-service

# =============================================================================
# Default: Show help
# =============================================================================
.DEFAULT_GOAL := help

help:
	@echo ""
	@echo "$(BOLD)Multi-Channel Service$(RESET) (Telegram Bot)"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@echo "$(CYAN)Development:$(RESET)"
	@echo "  make dev         Run local bot (requires TELEGRAM_BOT_TOKEN)"
	@echo "  make test        Run pytest"
	@echo "  make lint        Run ruff + mypy"
	@echo ""
	@echo "$(GREEN)Deployment:$(RESET)"
	@echo "  make deploy      Deploy to Cloud Run (~2-3min)"
	@echo "  make logs        View recent logs"
	@echo "  make logs-live   Stream logs real-time"
	@echo ""
	@echo "$(YELLOW)Testing:$(RESET)"
	@echo "  make health      Check service health"
	@echo "  make webhook     Check Telegram webhook status"
	@echo ""

# =============================================================================
# Development
# =============================================================================
dev:
	@echo "$(CYAN)Starting local bot...$(RESET)"
	@echo "$(YELLOW)Requires: TELEGRAM_BOT_TOKEN env var$(RESET)"
	@source .venv/bin/activate && python -m src.telegram_bot.main

test:
	@echo "$(CYAN)Running tests...$(RESET)"
	@source .venv/bin/activate && pytest src/ -v --tb=short
	@echo "$(GREEN)Tests passed!$(RESET)"

lint:
	@echo "$(CYAN)Running linters...$(RESET)"
	@source .venv/bin/activate && ruff check src/
	@source .venv/bin/activate && ruff format --check src/
	@echo "$(GREEN)Lint passed!$(RESET)"

format:
	@echo "$(CYAN)Formatting...$(RESET)"
	@source .venv/bin/activate && ruff format src/
	@source .venv/bin/activate && ruff check --fix src/

# =============================================================================
# Deployment (UV-optimized)
# =============================================================================
deploy:
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

# =============================================================================
# Health & Webhook
# =============================================================================
url:
	@echo "$(BOLD)Service URL:$(RESET)"
	@gcloud run services describe $(SERVICE_NAME) \
		--region=$(REGION) \
		--project=$(PROJECT_ID) \
		--format='value(status.url)'

health:
	@echo "$(CYAN)Checking health...$(RESET)"
	@TOKEN=$$(gcloud auth print-identity-token) && \
	URL=$$(gcloud run services describe $(SERVICE_NAME) --region=$(REGION) --project=$(PROJECT_ID) --format='value(status.url)') && \
	curl -s -H "Authorization: Bearer $$TOKEN" "$$URL/health" | python3 -m json.tool

webhook:
	@echo "$(CYAN)Checking Telegram webhook...$(RESET)"
	@BOT_TOKEN=$$(gcloud secrets versions access latest --secret=telegram-bot-token --project=$(PROJECT_ID)) && \
	curl -s "https://api.telegram.org/bot$$BOT_TOKEN/getWebhookInfo" | python3 -m json.tool

webhook-reset:
	@echo "$(YELLOW)Resetting webhook...$(RESET)"
	@BOT_TOKEN=$$(gcloud secrets versions access latest --secret=telegram-bot-token --project=$(PROJECT_ID)) && \
	WEBHOOK_URL="https://multi-channel-gateway-vq1gs9i.uc.gateway.dev/webhook" && \
	curl -s "https://api.telegram.org/bot$$BOT_TOKEN/setWebhook?url=$$WEBHOOK_URL&drop_pending_updates=true" | python3 -m json.tool

# =============================================================================
# Docker (Local)
# =============================================================================
docker-build:
	@echo "$(CYAN)Building with UV...$(RESET)"
	@docker build -f deploy/Dockerfile.cloudrun -t $(SERVICE_NAME):local .

docker-run:
	@echo "$(CYAN)Running container...$(RESET)"
	@docker run -p 8080:8080 \
		-e PORT=8080 \
		-e TELEGRAM_BOT_TOKEN=$$(gcloud secrets versions access latest --secret=telegram-bot-token --project=$(PROJECT_ID)) \
		$(SERVICE_NAME):local

# =============================================================================
# Utilities
# =============================================================================
clean:
	@echo "$(CYAN)Cleaning...$(RESET)"
	@rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)Clean!$(RESET)"

install:
	@echo "$(CYAN)Installing with UV...$(RESET)"
	@python3 -m venv .venv
	@source .venv/bin/activate && pip install uv && uv pip install -r requirements.txt
	@echo "$(GREEN)Done! Activate: source .venv/bin/activate$(RESET)"

# =============================================================================
# Service Info
# =============================================================================
info:
	@echo ""
	@echo "$(BOLD)Service Info$(RESET)"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@gcloud run services describe $(SERVICE_NAME) \
		--region=$(REGION) \
		--project=$(PROJECT_ID) \
		--format="table(status.url,spec.template.metadata.annotations.'autoscaling.knative.dev/minScale',spec.template.spec.containers[0].resources.limits.memory)"
	@echo ""
	@make -s webhook
