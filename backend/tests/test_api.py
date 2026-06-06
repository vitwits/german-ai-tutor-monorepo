"""
Basic API health check tests.
"""
import pytest


def test_api_health(client):
    """Test that the API is running and responds."""
    # Test the root endpoint - it may return 200, 404, or 405 depending on implementation
    response = client.get("/")
    assert response.status_code in [200, 404, 405]


def test_api_docs_available(client):
    """Test that API documentation is available."""
    response = client.get("/docs")
    assert response.status_code == 200
    assert "swagger" in response.text.lower()


def test_openapi_schema(client):
    """Test that OpenAPI schema is available."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert "info" in data
    assert "title" in data["info"]


class TestHealthEndpoint:
    """Test suite for health check endpoints."""

    def test_docs_endpoint_exists(self, client):
        """Verify that docs endpoint is accessible."""
        response = client.get("/docs")
        assert response.status_code == 200
        
    def test_openapi_schema_valid(self, client):
        """Verify OpenAPI schema is valid and has proper structure."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        
        # Check for essential OpenAPI fields
        assert "openapi" in schema or "swagger" in schema
        assert "paths" in schema
