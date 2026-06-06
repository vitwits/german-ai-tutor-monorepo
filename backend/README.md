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

This installs all dependencies from `pyproject.toml` and `poetry.lock` files.

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

## Managing Dependencies

### Adding a New Dependency

```bash
poetry add package_name
```

This automatically updates `pyproject.toml` and `poetry.lock`.

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

**Where are dependencies stored?**

- **`pyproject.toml`** - Lists all project dependencies with version constraints (human-readable)
- **`poetry.lock`** - Locks specific versions for reproducibility (auto-generated, don't edit manually)

**How does it work?**

1. When you run `poetry add pytest`, Poetry:
   - Adds `pytest` to `pyproject.toml`
   - Resolves the exact version and adds it to `poetry.lock`
   - Installs it in the virtual environment

2. When you run `poetry install`, it:
   - Reads both files
   - Uses exact versions from `poetry.lock`
   - Ensures everyone has the same environment

**For new machines:**

Just run:
```bash
poetry install --no-root
```

Poetry reads `poetry.lock` and installs the exact same versions. No manual installation needed!