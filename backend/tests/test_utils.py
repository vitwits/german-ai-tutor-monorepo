"""
Unit tests for utility functions.
"""
import pytest


class TestMathOperations:
    """Simple math operation tests as examples."""

    def test_addition(self):
        """Test basic addition."""
        assert 1 + 1 == 2

    def test_subtraction(self):
        """Test basic subtraction."""
        assert 5 - 3 == 2

    def test_multiplication(self):
        """Test basic multiplication."""
        assert 3 * 4 == 12

    def test_division(self):
        """Test basic division."""
        assert 10 / 2 == 5


class TestStringOperations:
    """Test string utility functions."""

    def test_string_concatenation(self):
        """Test string concatenation."""
        result = "Hello" + " " + "World"
        assert result == "Hello World"

    def test_string_length(self):
        """Test string length calculation."""
        text = "Python"
        assert len(text) == 6

    def test_string_formatting(self):
        """Test string formatting."""
        name = "Developer"
        message = f"Welcome, {name}!"
        assert message == "Welcome, Developer!"
