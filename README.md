# German AI Tutor

An intelligent German learning platform powered by AI, featuring adaptive lessons, vocabulary building, speaking practice, and personalized learning paths.

## Project Structure

```
german_ai_tutor/
├── backend/              # FastAPI backend server
│   ├── app/              # Main application code
│   ├── tests/            # Test suite
│   ├── data/             # SQLite database (created at runtime)
│   ├── static/           # Audio files and assets
│   └── README.md         # Backend documentation
├── frontend/             # Svelte + Vite frontend
│   ├── src/              # Source code
│   ├── tests/            # Test suite
│   └── README.md         # Frontend documentation
├── k8s/                  # Kubernetes configuration (optional)
├── docker-compose.yml    # Production compose config
├── docker-compose.override.yml # Local development config
├── .env.example          # Environment variables template
├── service-account.json  # Google API credentials (keep secure!)
└── README.md             # This file
```

## Quick Start

### Prerequisites

- Docker & Docker Compose
- (Optional) Python 3.11+, Node.js 16+, Poetry for local development

### Option 1: Docker Compose (Recommended)

**Development (with hot reload):**

```bash
docker compose up --build
```

This uses `docker-compose.override.yml` which enables:
- 🔄 Hot reload for backend (code changes apply immediately)
- 🔄 Vite dev server for frontend (fast refresh)
- 📁 Volume mounts for live development

**Access:**
- Frontend: http://localhost:5173 (dev server with hot reload)
- Backend: http://localhost:8000
- API Docs: http://localhost:8000/docs

**Production (optimized, no hot reload):**

```bash
docker compose -f docker-compose.yml up --build
```

This uses only `docker-compose.yml` which provides:
- ✅ Optimized Nginx serving frontend
- ✅ Optimized production build
- ✅ Better performance

**Access:**
- Frontend: http://localhost:80
- Backend: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Option 2: Local Development (Without Docker)

**Backend:**

```bash
cd backend
poetry install --no-root
poetry run uvicorn app.main:app --reload --port 8000
```

Backend runs on: http://localhost:8000

**Frontend:**

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on: http://localhost:5173

## Configuration

### Environment Variables

Create a `.env` file in the project root (copy from `.env.example`):

```bash
cp .env.example .env
```

**Required variables:**

```env
# Google Gemini AI
GEMINI_API_KEY=your_api_key_here

# JWT Authentication
SECRET_KEY=your_secure_random_string_here

# Google Cloud (for service-account.json path)
GOOGLE_APPLICATION_CREDENTIALS=/var/secrets/service-account.json

# Azure Speech (optional, for TTS)
AZURE_SPEECH_KEY=your_key_here
AZURE_SPEECH_REGION=your_region_here
```

### Google Gemini API Setup

1. **Obtain Google Service Account JSON:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create or select a project
   - Enable Google Generative AI API
   - Create a service account and download the JSON key

2. **Place in project root:**
   ```bash
   # Copy your downloaded service-account.json to project root
   cp ~/Downloads/service-account.json ./service-account.json
   ```

3. **Security:**
   - ⚠️ **Never commit** `service-account.json` to git
   - Add to `.gitignore` (already done)
   - Keep file permissions secure on server

## Database

### Location

- **Development:** `./backend/data/app.db` (SQLite)
- **Production:** Same location (SQLite) or PostgreSQL (configure in backend)

### Volume Mounting

Docker volumes ensure database persistence:

```yaml
volumes:
  - ./backend/data:/app/data    # Database
  - ./backend/static:/app/static # Audio files
```

### Server Setup

On a new server, ensure the data directory exists:

```bash
mkdir -p ./backend/data
chmod 755 ./backend/data

# If restoring from backup:
cp backup.db ./backend/data/app.db
```

## Admin Dashboard

### Accessing Admin Interface

1. **URL:** http://localhost:8000/admin (or your backend URL)

2. **Login Credentials:**
   - Default admin user created during initial setup
   - See `backend/ADMIN_INTERFACE.md` for details

3. **Admin Privileges:**

   To grant admin access to a user, update the database:

   ```bash
   # Via SQLite CLI
   sqlite3 backend/data/app.db
   UPDATE users SET is_admin = 1 WHERE email = 'user@example.com';
   ```

   Or through API:
   ```bash
   poetry run python -c "
   from app.database import SessionLocal
   from app.models import User
   db = SessionLocal()
   user = db.query(User).filter(User.email == 'user@example.com').first()
   if user:
       user.is_admin = True
       db.commit()
   "
   ```

## Ports

| Service | Dev Port | Prod Port | Notes |
|---------|----------|-----------|-------|
| **Frontend** | 5173 | 80 | Vite dev / Nginx prod |
| **Backend** | 8000 | 8000 | FastAPI server |
| **API Docs** | 8000/docs | 8000/docs | Swagger UI |

## Docker Compose Override Explained

### What is `docker-compose.override.yml`?

Docker Compose automatically merges `docker-compose.override.yml` with `docker-compose.yml` if both exist.

**Development Mode (`override.yml`):**
```yaml
backend:
  command: uvicorn ... --reload        # Hot reload enabled
  volumes:
    - ./backend:/app                    # Mount entire folder

frontend:
  command: npm run dev -- --host 0.0.0.0  # Vite dev server
  ports:
    - "5173:5173"                       # Dev port
  volumes:
    - ./frontend:/app                   # Mount entire folder
```

**Production Mode (no override):**
```yaml
backend:
  # Default: just runs the app
  volumes:
    - ./backend/data:/app/data          # Only data persists

frontend:
  # Default: runs Nginx
  ports:
    - "80:80"                           # Standard HTTP port
```

### How to Use

**For local development:**
```bash
# Uses both docker-compose.yml + override.yml (automatic)
docker compose up --build
```

**For production build:**
```bash
# Ignores override.yml, uses only compose.yml
docker compose -f docker-compose.yml up --build
```

## Testing

### Backend Tests

```bash
cd backend
poetry install --no-root
poetry run pytest -v
```

See `backend/README.md` for test details.

### Frontend Tests

```bash
cd frontend
npm install
npm run test:run
```

See `frontend/README.md` for test details.

## Deployment

### Docker Image Build

```bash
# Build for production
docker build -t german-ai-tutor-backend:latest ./backend
docker build -t german-ai-tutor-frontend:latest ./frontend

# Push to registry
docker push your-registry/german-ai-tutor-backend:latest
docker push your-registry/german-ai-tutor-frontend:latest
```

### Environment on Server

Ensure `.env` file exists on production server with:
- Real `GEMINI_API_KEY`
- Strong `SECRET_KEY` (min 32 characters)
- Real API keys for Azure Speech (if using)

```bash
# On production server
cp .env.production .env
docker compose -f docker-compose.yml up -d
```

## Troubleshooting

### Database Issues

```bash
# Verify database exists
ls -la backend/data/

# Check database integrity
sqlite3 backend/data/app.db ".tables"

# Backup database
cp backend/data/app.db backend/data/app.db.backup
```

### Port Already in Use

```bash
# Find what's using port 8000
lsof -i :8000
lsof -i :5173

# Kill process (macOS/Linux)
kill -9 <PID>
```

### Google API Issues

```bash
# Verify service-account.json is readable
cat service-account.json | head -5

# Check environment variable in container
docker compose exec backend env | grep GOOGLE
```

## Documentation

- **Backend:** See [backend/README.md](backend/README.md)
- **Frontend:** See [frontend/README.md](frontend/README.md)
- **Admin Interface:** See [backend/ADMIN_INTERFACE.md](backend/ADMIN_INTERFACE.md)
- **AI Models:** See [backend/AI_MODELS_GUIDE.md](backend/AI_MODELS_GUIDE.md)

## License

[Add your license]

## Support

For issues or questions, please check the documentation above or create an issue in the repository.