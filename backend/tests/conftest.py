"""
Pytest configuration and fixtures for testing.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    """Provide a test client for API testing."""
    return TestClient(app)


@pytest.fixture
def sample_user_data():
    """Provide sample user data for testing."""
    return {
        "email": "test@example.com",
        "password": "test_password_123",
        "username": "testuser",
    }


@pytest.fixture
def sample_lesson_data():
    """Provide sample lesson data for testing."""
    return {
        "title": "Test Lesson",
        "description": "A test lesson for German learning",
        "level": "A1",
        "language": "de",
    }
