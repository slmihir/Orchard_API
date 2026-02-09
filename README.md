# Autoflow

AI-powered browser test automation.

- **API Testing:** See [docs/API_TESTING.md](docs/API_TESTING.md) for architecture, data model, execution flows (Python and Karate), and code references.

## Setup

```bash
cp .env.example .env
# Add your API keys to .env
```

### Docker (Recommended)

```bash
docker-compose up
```

Tables are created automatically on startup.

### Manual Setup

**Backend:**
```bash
cd backend
pip install -r requirements.txt
playwright install chromium
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

**Services:**
- PostgreSQL on port 5432
- Redis on port 6379

## Ports

- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- Demo Site: http://localhost:8080
# Orchard_API
