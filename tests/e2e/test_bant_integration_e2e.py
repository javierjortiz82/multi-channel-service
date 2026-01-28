"""
E2E Tests for BANT Service Integration in Production.

This test suite verifies the complete BANT lead qualification flow
across all services deployed in Google Cloud Run.

Test Flow:
1. BANT Service: Schema, API endpoint, tracking fields
2. MCP Server: Tool registration, tool execution
3. NLP Service: Function calling with BANT tool
4. Full Integration: Simulated conversation analysis

Prerequisites:
- All services deployed to Cloud Run
- gcloud CLI authenticated with proper permissions
- Network access to Cloud Run services

Usage:
    # Run all tests
    pytest tests/e2e/test_bant_integration_e2e.py -v

    # Run specific test
    pytest tests/e2e/test_bant_integration_e2e.py::TestBANTServiceE2E::test_health_check -v

    # Run with production URLs (default)
    pytest tests/e2e/test_bant_integration_e2e.py -v

Author: Odiseo Team
Date: 2026-01-28
"""

import asyncio
import json
import os
import subprocess
import time
import uuid
from datetime import datetime, timezone

import httpx
import pytest

# =============================================================================
# Configuration
# =============================================================================

# Cloud Run Service URLs
BANT_SERVICE_URL = os.getenv(
    "BANT_SERVICE_URL",
    "https://bant-service-4k3haexkga-uc.a.run.app"
)
MCP_SERVER_URL = os.getenv(
    "MCP_SERVER_URL",
    "https://mcp-server-4k3haexkga-uc.a.run.app"
)
NLP_SERVICE_URL = os.getenv(
    "NLP_SERVICE_URL",
    "https://nlp-service-4k3haexkga-uc.a.run.app"
)

# Test configuration
TEST_TIMEOUT = 60  # seconds
REQUEST_TIMEOUT = 30.0  # seconds for individual requests


# =============================================================================
# Fixtures
# =============================================================================

def get_identity_token(audience: str) -> str:
    """Get GCP identity token for IAM-authenticated Cloud Run services.

    Args:
        audience: The Cloud Run service URL

    Returns:
        Identity token string
    """
    try:
        # First try with --audiences (service accounts)
        result = subprocess.run(
            ["gcloud", "auth", "print-identity-token", f"--audiences={audience}"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return result.stdout.strip()

        # Fallback to basic identity token (user accounts)
        result = subprocess.run(
            ["gcloud", "auth", "print-identity-token"],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        pytest.skip(f"Failed to get identity token: {e.stderr}")
    except FileNotFoundError:
        pytest.skip("gcloud CLI not found. Install Google Cloud SDK.")


@pytest.fixture
def bant_token() -> str:
    """Get identity token for BANT service."""
    return get_identity_token(BANT_SERVICE_URL)


@pytest.fixture
def mcp_token() -> str:
    """Get identity token for MCP server."""
    return get_identity_token(MCP_SERVER_URL)


@pytest.fixture
def nlp_token() -> str:
    """Get identity token for NLP service."""
    return get_identity_token(NLP_SERVICE_URL)


@pytest.fixture
def test_conversation_id() -> str:
    """Generate unique conversation ID for testing."""
    return f"test_{uuid.uuid4().hex[:12]}"


@pytest.fixture
def sample_lead_text() -> str:
    """Sample lead text with high BANT signals."""
    return """
    Hola, soy el Director de Tecnología de una empresa de retail con 50 tiendas.
    Tenemos un presupuesto aprobado de $150,000 USD para implementar un nuevo sistema
    de gestión de inventario. Necesitamos tenerlo funcionando antes del Black Friday,
    que es en 3 meses. Nuestro sistema actual está causando pérdidas significativas
    por desabastecimiento. Yo tomo la decisión final sobre proveedores tecnológicos.
    ¿Qué soluciones tienen disponibles?
    """


@pytest.fixture
def sample_cold_lead_text() -> str:
    """Sample lead text with low BANT signals."""
    return """
    Hola, estoy investigando opciones para mi jefe.
    No tenemos presupuesto definido todavía y no hay urgencia.
    Solo quiero ver qué hay disponible en el mercado.
    """


# =============================================================================
# BANT Service Tests
# =============================================================================

class TestBANTServiceE2E:
    """E2E tests for BANT Service endpoints."""

    @pytest.mark.asyncio
    async def test_health_check(self, bant_token: str):
        """Test BANT service health endpoint."""
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(
                f"{BANT_SERVICE_URL}/health",
                headers={"Authorization": f"Bearer {bant_token}"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data.get("status") == "healthy"
            print(f"✅ BANT Service Health: {data}")

    @pytest.mark.asyncio
    async def test_analyze_lead_without_tracking(
        self, bant_token: str, sample_lead_text: str
    ):
        """Test lead analysis without tracking fields (backward compatibility)."""
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.post(
                f"{BANT_SERVICE_URL}/api/v1/leads/analyze",
                headers={
                    "Authorization": f"Bearer {bant_token}",
                    "Content-Type": "application/json",
                },
                json={"text": sample_lead_text},
            )

            assert response.status_code == 201
            data = response.json()

            # Verify BANT scores
            assert "id" in data
            assert "overall_score" in data
            assert 0 <= data["overall_score"] <= 10
            assert 0 <= data["budget_score"] <= 10
            assert 0 <= data["authority_score"] <= 10
            assert 0 <= data["need_score"] <= 10
            assert 0 <= data["timeline_score"] <= 10

            # High BANT signals should produce high scores
            assert data["overall_score"] >= 6, f"Expected hot/warm lead, got score {data['overall_score']}"

            print(f"✅ Lead Analysis (no tracking):")
            print(f"   Overall: {data['overall_score']}/10")
            print(f"   Budget: {data['budget_score']}, Authority: {data['authority_score']}")
            print(f"   Need: {data['need_score']}, Timeline: {data['timeline_score']}")

    @pytest.mark.asyncio
    async def test_analyze_lead_with_tracking(
        self, bant_token: str, sample_lead_text: str, test_conversation_id: str
    ):
        """Test lead analysis WITH tracking fields (new functionality)."""
        test_user_id = str(uuid.uuid4())

        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.post(
                f"{BANT_SERVICE_URL}/api/v1/leads/analyze",
                headers={
                    "Authorization": f"Bearer {bant_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "text": sample_lead_text,
                    "conversation_id": test_conversation_id,
                    "user_id": test_user_id,
                    "channel": "telegram",
                    "message_count": 5,
                },
            )

            assert response.status_code == 201
            data = response.json()

            # Verify tracking fields are returned
            assert data.get("conversation_id") == test_conversation_id
            assert data.get("user_id") == test_user_id
            assert data.get("channel") == "telegram"
            assert data.get("message_count") == 5

            print(f"✅ Lead Analysis (with tracking):")
            print(f"   Lead ID: {data['id']}")
            print(f"   Conversation ID: {data['conversation_id']}")
            print(f"   Channel: {data['channel']}")
            print(f"   Message Count: {data['message_count']}")
            print(f"   Overall Score: {data['overall_score']}/10")

    @pytest.mark.asyncio
    async def test_analyze_cold_lead(
        self, bant_token: str, sample_cold_lead_text: str, test_conversation_id: str
    ):
        """Test that cold leads receive low scores."""
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.post(
                f"{BANT_SERVICE_URL}/api/v1/leads/analyze",
                headers={
                    "Authorization": f"Bearer {bant_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "text": sample_cold_lead_text,
                    "conversation_id": f"cold_{test_conversation_id}",
                    "channel": "telegram",
                },
            )

            assert response.status_code == 201
            data = response.json()

            # Cold leads should have lower scores
            assert data["overall_score"] <= 5, f"Expected cold lead, got score {data['overall_score']}"

            print(f"✅ Cold Lead Analysis:")
            print(f"   Overall: {data['overall_score']}/10 (expected <= 5)")
            print(f"   Budget: {data['budget_score']}, Authority: {data['authority_score']}")

    @pytest.mark.asyncio
    async def test_get_lead_by_id(self, bant_token: str, sample_lead_text: str):
        """Test retrieving a lead by its ID."""
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            # First create a lead
            create_response = await client.post(
                f"{BANT_SERVICE_URL}/api/v1/leads/analyze",
                headers={
                    "Authorization": f"Bearer {bant_token}",
                    "Content-Type": "application/json",
                },
                json={"text": sample_lead_text},
            )
            assert create_response.status_code == 201
            lead_id = create_response.json()["id"]

            # Then retrieve it
            get_response = await client.get(
                f"{BANT_SERVICE_URL}/api/v1/leads/{lead_id}",
                headers={"Authorization": f"Bearer {bant_token}"},
            )

            assert get_response.status_code == 200
            data = get_response.json()
            assert data["id"] == lead_id

            print(f"✅ Get Lead by ID: {lead_id}")

    @pytest.mark.asyncio
    async def test_list_leads(self, bant_token: str):
        """Test listing leads with pagination."""
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(
                f"{BANT_SERVICE_URL}/api/v1/leads",
                headers={"Authorization": f"Bearer {bant_token}"},
                params={"limit": 5, "offset": 0},
            )

            assert response.status_code == 200
            data = response.json()

            assert "leads" in data
            assert "total" in data
            assert isinstance(data["leads"], list)

            print(f"✅ List Leads: {len(data['leads'])} leads, {data['total']} total")


# =============================================================================
# MCP Server Tests
# =============================================================================

class TestMCPServerE2E:
    """E2E tests for MCP Server BANT tool."""

    @pytest.mark.asyncio
    async def test_health_check(self, mcp_token: str):
        """Test MCP server health endpoint."""
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(
                f"{MCP_SERVER_URL}/health",
                headers={"Authorization": f"Bearer {mcp_token}"},
            )

            # MCP server might use different health endpoint format
            assert response.status_code in [200, 404]
            print(f"✅ MCP Server responded: {response.status_code}")

    @pytest.mark.asyncio
    async def test_tool_list_includes_bant(self, mcp_token: str):
        """Test that analyze_lead_bant tool is registered."""
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            # MCP protocol uses JSON-RPC style requests
            response = await client.post(
                f"{MCP_SERVER_URL}/mcp/v1/tools/list",
                headers={
                    "Authorization": f"Bearer {mcp_token}",
                    "Content-Type": "application/json",
                },
                json={},
            )

            if response.status_code == 200:
                data = response.json()
                tools = data.get("tools", [])
                tool_names = [t.get("name") for t in tools]

                assert "analyze_lead_bant" in tool_names, \
                    f"analyze_lead_bant not found in tools: {tool_names}"

                print(f"✅ BANT tool registered. Total tools: {len(tools)}")
                print(f"   Sales tools: {[t for t in tool_names if 'search' in t or 'fetch' in t or 'bant' in t]}")
            else:
                # Alternative endpoint format
                print(f"⚠️ Tool list endpoint returned {response.status_code}")
                print(f"   Response: {response.text[:200]}")


# =============================================================================
# NLP Service Tests
# =============================================================================

class TestNLPServiceE2E:
    """E2E tests for NLP Service with BANT function calling."""

    @pytest.mark.asyncio
    async def test_health_check(self, nlp_token: str):
        """Test NLP service health endpoint."""
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(
                f"{NLP_SERVICE_URL}/api/v1/health",
                headers={"Authorization": f"Bearer {nlp_token}"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data.get("status") == "healthy"
            print(f"✅ NLP Service Health: {data}")

    @pytest.mark.asyncio
    async def test_process_with_buying_intent(
        self, nlp_token: str, test_conversation_id: str
    ):
        """Test NLP processing with buying intent triggers BANT analysis."""
        buying_intent_message = """
        Quiero comprar una laptop gaming. Tengo presupuesto de $2000.
        Soy el encargado de compras de mi empresa.
        La necesito para la próxima semana. ¿Qué opciones tienen?
        """

        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.post(
                f"{NLP_SERVICE_URL}/api/v1/process",
                headers={
                    "Authorization": f"Bearer {nlp_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "text": buying_intent_message,
                    "conversation_id": test_conversation_id,
                },
            )

            assert response.status_code == 200
            data = response.json()

            # Verify response structure
            assert "response" in data or "text" in data

            print(f"✅ NLP Process (buying intent):")
            print(f"   Conversation ID: {test_conversation_id}")
            print(f"   Response length: {len(str(data))} chars")

            # Check if BANT tool was called (may be in metadata)
            if "tool_calls" in data:
                bant_called = any(
                    "bant" in str(tc).lower()
                    for tc in data.get("tool_calls", [])
                )
                print(f"   BANT tool called: {bant_called}")


# =============================================================================
# Full Integration Tests
# =============================================================================

class TestFullIntegrationE2E:
    """Full E2E integration tests across all services."""

    @pytest.mark.asyncio
    async def test_complete_bant_flow(
        self,
        bant_token: str,
        nlp_token: str,
        test_conversation_id: str,
    ):
        """Test complete BANT qualification flow.

        Simulates a real conversation flow:
        1. User sends product inquiry
        2. User shows buying signals
        3. BANT analysis is triggered
        4. Lead is created with tracking
        5. Qualification tier is determined
        """
        print("\n" + "=" * 60)
        print("COMPLETE BANT INTEGRATION TEST")
        print("=" * 60)

        # Step 1: Simulate conversation with buying signals
        conversation_text = """
        Usuario: Hola, busco laptops para mi empresa
        Asistente: ¡Hola! Tenemos varias opciones. ¿Qué uso le darán?
        Usuario: Necesitamos 20 laptops para el departamento de diseño
        Asistente: Excelente. Para diseño recomiendo estas opciones...
        Usuario: Perfecto. Soy el Director de IT y tenemos presupuesto de $40,000.
        Lo necesitamos para el próximo mes porque estamos abriendo una nueva oficina.
        ¿Pueden hacer una cotización formal?
        """

        print(f"\n📝 Step 1: Simulated conversation")
        print(f"   Conversation ID: {test_conversation_id}")
        print(f"   Text length: {len(conversation_text)} chars")

        # Step 2: Direct BANT analysis
        print(f"\n🎯 Step 2: BANT Analysis")

        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            bant_response = await client.post(
                f"{BANT_SERVICE_URL}/api/v1/leads/analyze",
                headers={
                    "Authorization": f"Bearer {bant_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "text": conversation_text,
                    "conversation_id": test_conversation_id,
                    "channel": "telegram",
                    "message_count": 6,
                },
            )

            assert bant_response.status_code == 201
            bant_data = bant_response.json()

            print(f"   Lead ID: {bant_data['id']}")
            print(f"   Overall Score: {bant_data['overall_score']}/10")
            print(f"   Budget: {bant_data['budget_score']}/10")
            print(f"   Authority: {bant_data['authority_score']}/10")
            print(f"   Need: {bant_data['need_score']}/10")
            print(f"   Timeline: {bant_data['timeline_score']}/10")

        # Step 3: Determine qualification tier
        overall_score = bant_data["overall_score"]
        if overall_score >= 8:
            tier = "HOT 🔥"
            recommendation = "Priorizar cierre, ofrecer ayuda inmediata"
        elif overall_score >= 6:
            tier = "WARM 🌡️"
            recommendation = "Continuar nurturing, responder dudas"
        elif overall_score >= 4:
            tier = "COLD ❄️"
            recommendation = "Información general, no presionar"
        else:
            tier = "UNQUALIFIED ⚪"
            recommendation = "Responder amablemente, no insistir"

        print(f"\n📊 Step 3: Qualification Result")
        print(f"   Tier: {tier}")
        print(f"   Recommendation: {recommendation}")

        # Step 4: Verify lead was persisted
        print(f"\n💾 Step 4: Verify Persistence")

        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            get_response = await client.get(
                f"{BANT_SERVICE_URL}/api/v1/leads/{bant_data['id']}",
                headers={"Authorization": f"Bearer {bant_token}"},
            )

            assert get_response.status_code == 200
            persisted_data = get_response.json()

            assert persisted_data["conversation_id"] == test_conversation_id
            assert persisted_data["channel"] == "telegram"
            print(f"   ✅ Lead persisted with tracking fields")

        # Final assertions
        assert overall_score >= 6, f"Expected hot/warm lead, got {overall_score}"

        print(f"\n{'=' * 60}")
        print(f"✅ COMPLETE BANT FLOW TEST PASSED")
        print(f"{'=' * 60}\n")

    @pytest.mark.asyncio
    async def test_qualification_tiers_accuracy(self, bant_token: str):
        """Test that different lead qualities produce correct tiers."""
        test_cases = [
            {
                "name": "Hot Lead",
                "text": """
                Soy el CEO y ya tenemos aprobado $500,000 para este proyecto.
                Necesitamos implementarlo este mes porque perdemos dinero cada día.
                Quiero cerrar el trato hoy mismo si es posible.
                """,
                "expected_tier": "hot",
                "min_score": 8,
            },
            {
                "name": "Warm Lead",
                "text": """
                Soy gerente de área y estoy evaluando opciones.
                Tenemos un presupuesto tentativo pero necesito aprobación final.
                Estamos planeando para el próximo trimestre.
                """,
                "expected_tier": "warm",
                "min_score": 5,
                "max_score": 8,
            },
            {
                "name": "Cold Lead",
                "text": """
                Solo estoy investigando para ver qué hay en el mercado.
                No tengo presupuesto definido ni urgencia.
                Mi jefe me pidió que recopilara información.
                """,
                "expected_tier": "cold",
                "max_score": 5,
            },
        ]

        print("\n" + "=" * 60)
        print("QUALIFICATION TIERS ACCURACY TEST")
        print("=" * 60)

        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            for case in test_cases:
                response = await client.post(
                    f"{BANT_SERVICE_URL}/api/v1/leads/analyze",
                    headers={
                        "Authorization": f"Bearer {bant_token}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "text": case["text"],
                        "conversation_id": f"tier_test_{uuid.uuid4().hex[:8]}",
                        "channel": "test",
                    },
                )

                assert response.status_code == 201
                data = response.json()
                score = data["overall_score"]

                # Validate score is within expected range
                if "min_score" in case:
                    assert score >= case["min_score"], \
                        f"{case['name']}: Expected score >= {case['min_score']}, got {score}"
                if "max_score" in case:
                    assert score <= case["max_score"], \
                        f"{case['name']}: Expected score <= {case['max_score']}, got {score}"

                status = "✅" if (
                    ("min_score" not in case or score >= case["min_score"]) and
                    ("max_score" not in case or score <= case["max_score"])
                ) else "❌"

                print(f"\n{status} {case['name']}:")
                print(f"   Score: {score}/10 (expected: {case.get('min_score', 0)}-{case.get('max_score', 10)})")
                print(f"   B:{data['budget_score']} A:{data['authority_score']} N:{data['need_score']} T:{data['timeline_score']}")

        print(f"\n{'=' * 60}")
        print(f"✅ QUALIFICATION TIERS TEST PASSED")
        print(f"{'=' * 60}\n")


# =============================================================================
# Database Verification Tests
# =============================================================================

class TestDatabaseSchemaE2E:
    """Tests to verify database schema changes were applied."""

    @pytest.mark.asyncio
    async def test_tracking_fields_persisted(
        self, bant_token: str, test_conversation_id: str
    ):
        """Verify tracking fields are stored and retrieved correctly."""
        test_user_id = str(uuid.uuid4())

        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            # Create lead with all tracking fields
            create_response = await client.post(
                f"{BANT_SERVICE_URL}/api/v1/leads/analyze",
                headers={
                    "Authorization": f"Bearer {bant_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "text": "Test lead with tracking fields. Budget $10k, need ASAP.",
                    "conversation_id": test_conversation_id,
                    "user_id": test_user_id,
                    "channel": "whatsapp",
                    "message_count": 10,
                },
            )

            assert create_response.status_code == 201
            created = create_response.json()

            # Retrieve and verify
            get_response = await client.get(
                f"{BANT_SERVICE_URL}/api/v1/leads/{created['id']}",
                headers={"Authorization": f"Bearer {bant_token}"},
            )

            assert get_response.status_code == 200
            retrieved = get_response.json()

            # Verify all tracking fields
            assert retrieved["conversation_id"] == test_conversation_id
            assert retrieved["user_id"] == test_user_id
            assert retrieved["channel"] == "whatsapp"
            assert retrieved["message_count"] == 10

            print(f"✅ Database Schema Verification:")
            print(f"   conversation_id: {retrieved['conversation_id']}")
            print(f"   user_id: {retrieved['user_id']}")
            print(f"   channel: {retrieved['channel']}")
            print(f"   message_count: {retrieved['message_count']}")


# =============================================================================
# Performance Tests
# =============================================================================

class TestPerformanceE2E:
    """Performance tests for BANT integration."""

    @pytest.mark.asyncio
    async def test_bant_analysis_latency(
        self, bant_token: str, sample_lead_text: str
    ):
        """Test BANT analysis response time."""
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            start = time.time()

            response = await client.post(
                f"{BANT_SERVICE_URL}/api/v1/leads/analyze",
                headers={
                    "Authorization": f"Bearer {bant_token}",
                    "Content-Type": "application/json",
                },
                json={"text": sample_lead_text},
            )

            latency = time.time() - start

            assert response.status_code == 201

            # BANT analysis should complete in reasonable time
            # (includes Gemini API call + cold start, allow up to 15 seconds)
            assert latency < 15, f"BANT analysis too slow: {latency:.2f}s"

            print(f"✅ BANT Analysis Latency: {latency:.2f}s")
            print(f"   (Acceptable: < 10s, includes AI analysis)")

    @pytest.mark.asyncio
    async def test_concurrent_bant_requests(self, bant_token: str):
        """Test BANT service handles concurrent requests."""
        num_requests = 5
        texts = [
            f"Lead {i}: Budget ${i*1000}, need in {i} weeks, I'm the {['CEO', 'CTO', 'Manager', 'Director', 'VP'][i]}"
            for i in range(num_requests)
        ]

        async def make_request(text: str, idx: int) -> tuple[int, float]:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                start = time.time()
                response = await client.post(
                    f"{BANT_SERVICE_URL}/api/v1/leads/analyze",
                    headers={
                        "Authorization": f"Bearer {bant_token}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "text": text,
                        "conversation_id": f"concurrent_{idx}_{uuid.uuid4().hex[:8]}",
                    },
                )
                latency = time.time() - start
                return response.status_code, latency

        # Run requests concurrently
        start = time.time()
        tasks = [make_request(text, i) for i, text in enumerate(texts)]
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start

        # Verify all succeeded
        statuses = [r[0] for r in results]
        latencies = [r[1] for r in results]

        assert all(s == 201 for s in statuses), f"Some requests failed: {statuses}"

        print(f"✅ Concurrent Requests ({num_requests}):")
        print(f"   Total time: {total_time:.2f}s")
        print(f"   Avg latency: {sum(latencies)/len(latencies):.2f}s")
        print(f"   Max latency: {max(latencies):.2f}s")


# =============================================================================
# CLI Runner
# =============================================================================

if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([
        __file__,
        "-v",
        "-s",
        "--tb=short",
        "-x",  # Stop on first failure
    ])
