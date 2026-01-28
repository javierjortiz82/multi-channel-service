#!/bin/bash
# =============================================================================
# BANT Integration E2E Test Runner
# =============================================================================
#
# Executes E2E tests for BANT lead qualification integration across all
# Cloud Run services in production.
#
# Prerequisites:
#   - gcloud CLI installed and authenticated
#   - pytest installed (pip install pytest pytest-asyncio httpx)
#   - Network access to Cloud Run services
#
# Usage:
#   ./run_bant_e2e_tests.sh           # Run all tests
#   ./run_bant_e2e_tests.sh --quick   # Run quick smoke tests only
#   ./run_bant_e2e_tests.sh --verbose # Run with extra verbosity
#
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Service URLs (Cloud Run production)
export BANT_SERVICE_URL="${BANT_SERVICE_URL:-https://bant-service-4k3haexkga-uc.a.run.app}"
export MCP_SERVER_URL="${MCP_SERVER_URL:-https://mcp-server-4k3haexkga-uc.a.run.app}"
export NLP_SERVICE_URL="${NLP_SERVICE_URL:-https://nlp-service-4k3haexkga-uc.a.run.app}"

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}   BANT Integration E2E Test Suite${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# =============================================================================
# Pre-flight checks
# =============================================================================

echo -e "${YELLOW}[1/4] Pre-flight checks...${NC}"

# Check gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}Error: gcloud CLI not found. Install Google Cloud SDK.${NC}"
    exit 1
fi
echo "  ✓ gcloud CLI found"

# Check gcloud is authenticated
if ! gcloud auth print-identity-token --audiences="$BANT_SERVICE_URL" &> /dev/null; then
    echo -e "${RED}Error: gcloud not authenticated. Run 'gcloud auth login'.${NC}"
    exit 1
fi
echo "  ✓ gcloud authenticated"

# Check pytest is installed
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}Error: pytest not found. Install with 'pip install pytest pytest-asyncio httpx'.${NC}"
    exit 1
fi
echo "  ✓ pytest found"

echo ""

# =============================================================================
# Service health checks
# =============================================================================

echo -e "${YELLOW}[2/4] Checking service health...${NC}"

check_service_health() {
    local name=$1
    local url=$2
    local token=$(gcloud auth print-identity-token --audiences="$url" 2>/dev/null)

    local status=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Authorization: Bearer $token" \
        "$url/health" 2>/dev/null)

    if [ "$status" == "200" ]; then
        echo -e "  ✓ $name: ${GREEN}healthy${NC}"
        return 0
    else
        echo -e "  ✗ $name: ${RED}status $status${NC}"
        return 1
    fi
}

SERVICES_OK=true

check_service_health "BANT Service" "$BANT_SERVICE_URL" || SERVICES_OK=false
check_service_health "NLP Service" "$NLP_SERVICE_URL" || SERVICES_OK=false

# MCP Server might not have /health endpoint, check differently
MCP_TOKEN=$(gcloud auth print-identity-token --audiences="$MCP_SERVER_URL" 2>/dev/null)
MCP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer $MCP_TOKEN" \
    "$MCP_SERVER_URL/" 2>/dev/null)
if [ "$MCP_STATUS" != "000" ]; then
    echo -e "  ✓ MCP Server: ${GREEN}responding${NC}"
else
    echo -e "  ✗ MCP Server: ${RED}not responding${NC}"
    SERVICES_OK=false
fi

if [ "$SERVICES_OK" == "false" ]; then
    echo ""
    echo -e "${RED}Some services are not healthy. Fix before running tests.${NC}"
    exit 1
fi

echo ""

# =============================================================================
# Parse arguments
# =============================================================================

PYTEST_ARGS="-v -s --tb=short"
TEST_MARKERS=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --quick)
            echo -e "${YELLOW}Running quick smoke tests only...${NC}"
            TEST_MARKERS="-k 'health or test_analyze_lead_without_tracking'"
            shift
            ;;
        --verbose)
            PYTEST_ARGS="-v -s --tb=long"
            shift
            ;;
        --full)
            echo -e "${YELLOW}Running full test suite including performance tests...${NC}"
            shift
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Usage: $0 [--quick|--verbose|--full]"
            exit 1
            ;;
    esac
done

# =============================================================================
# Run tests
# =============================================================================

echo -e "${YELLOW}[3/4] Running E2E tests...${NC}"
echo ""

cd "$PROJECT_ROOT"

# Run pytest with markers if specified
if [ -n "$TEST_MARKERS" ]; then
    pytest tests/e2e/test_bant_integration_e2e.py $PYTEST_ARGS $TEST_MARKERS
else
    pytest tests/e2e/test_bant_integration_e2e.py $PYTEST_ARGS
fi

TEST_EXIT_CODE=$?

echo ""

# =============================================================================
# Summary
# =============================================================================

echo -e "${YELLOW}[4/4] Test Summary${NC}"
echo ""

if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}============================================${NC}"
    echo -e "${GREEN}   ALL TESTS PASSED ✓${NC}"
    echo -e "${GREEN}============================================${NC}"
    echo ""
    echo "Services tested:"
    echo "  - BANT Service: $BANT_SERVICE_URL"
    echo "  - MCP Server: $MCP_SERVER_URL"
    echo "  - NLP Service: $NLP_SERVICE_URL"
else
    echo -e "${RED}============================================${NC}"
    echo -e "${RED}   SOME TESTS FAILED ✗${NC}"
    echo -e "${RED}============================================${NC}"
    echo ""
    echo "Check the output above for details."
    echo ""
    echo "Common issues:"
    echo "  - Service not deployed: gcloud run services list --region=us-central1"
    echo "  - IAM permissions: Ensure your account has roles/run.invoker"
    echo "  - Database schema: Run BANT service deployment to apply migrations"
fi

exit $TEST_EXIT_CODE
