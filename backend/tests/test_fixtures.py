"""
Sample fixtures and data tests.
"""
import pytest


class TestSampleData:
    """Test sample data fixtures."""

    def test_user_data_structure(self, sample_user_data):
        """Verify user data fixture has required fields."""
        assert "email" in sample_user_data
        assert "password" in sample_user_data
        assert "username" in sample_user_data

    def test_user_email_valid(self, sample_user_data):
        """Verify sample user email is valid."""
        assert "@" in sample_user_data["email"]
        assert "." in sample_user_data["email"]

    def test_lesson_data_structure(self, sample_lesson_data):
        """Verify lesson data fixture has required fields."""
        assert "title" in sample_lesson_data
        assert "description" in sample_lesson_data
        assert "level" in sample_lesson_data

    def test_lesson_level_valid(self, sample_lesson_data):
        """Verify sample lesson level is one of valid CEFR levels."""
        valid_levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
        assert sample_lesson_data["level"] in valid_levels
