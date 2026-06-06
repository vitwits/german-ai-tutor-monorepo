# Backend Setup

## Prerequisites

- Python 3.8+
- Poetry (Python dependency manager)

## Installation

### 1. Activate Virtual Environment

First, activate the virtual environment created by Poetry:

```bash
poetry shell
```

Or if you prefer not to activate it, you can prefix commands with `poetry run`.

### 2. Install Poetry

If you don't have Poetry installed yet:

```bash
pip install poetry
```

### 3. Install Dependencies

```bash
poetry install --no-root
```

This installs all dependencies from `pyproject.toml` and `poetry.lock` files, including development dependencies like pytest.

## Running the Application

### Option 1: With Poetry (Recommended)

```bash
poetry run uvicorn app.main:app --reload --port 8000
```

### Option 2: After Activating Virtual Environment

```bash
poetry shell
uvicorn app.main:app --reload --port 8000
```

The `--reload` flag enables hot reloading during development.

## API Documentation

Swagger UI documentation is available at:
```
http://localhost:8000/docs
```

## Testing

### Running Tests

Run all tests:

```bash
poetry run pytest
```

Or after activating virtual environment:

```bash
pytest
```

### Running Tests in Watch Mode

For continuous testing during development:

```bash
poetry run pytest -v --tb=short
```

### Running Specific Test File

```bash
poetry run pytest tests/test_api.py -v
```

### Running Specific Test Class or Function

```bash
poetry run pytest tests/test_api.py::TestHealthEndpoint -v
poetry run pytest tests/test_utils.py::test_addition -v
```

### Test Coverage Report

Generate a coverage report:

```bash
poetry run pytest --cov=app tests/
```

## Test Structure

```
tests/
├── __init__.py           # Tests package marker
├── conftest.py           # Shared fixtures and configuration
├── test_api.py           # API endpoint tests
├── test_utils.py         # Utility function tests
└── test_fixtures.py      # Fixture validation tests
```

## Managing Dependencies

### Adding a New Dependency

```bash
poetry add package_name
```

### Adding a Development Dependency (Testing, Linting, etc.)

```bash
poetry add --group dev package_name
```

For example:

```bash
poetry add --group dev black  # Code formatter
poetry add --group dev pytest-cov  # Coverage reporting
```

### Updating Dependencies

Update the lock file:

```bash
poetry lock
```

Then reinstall:

```bash
poetry install --no-root
```

### Checking Poetry Version

```bash
poetry --version
```

## Dependency Storage Explanation

### Where are dependencies stored?

- **`pyproject.toml`** - Lists all project dependencies with version constraints (human-readable)
- **`poetry.lock`** - Locks specific versions for reproducibility (auto-generated, don't edit manually)

### How does it work?

1. When you run `poetry add pytest`, Poetry:
   - Adds `pytest` to `pyproject.toml` (under dev dependencies)
   - Resolves the exact version and adds it to `poetry.lock`
   - Installs it in the virtual environment

2. When you run `poetry install`, it:
   - Reads both files
   - Uses exact versions from `poetry.lock`
   - Ensures everyone has the same environment

### For new machines:

Just run:

```bash
poetry install --no-root
```

Poetry reads `poetry.lock` and installs the exact same versions. No manual installation needed!

### Development vs. Production Dependencies

Development dependencies (testing tools, formatters, etc.) are installed separately:

```toml
[tool.poetry.group.dev.dependencies]
pytest = "^7.4.0"
pytest-asyncio = "^0.21.0"
```

These are not included when deploying to production.