# Getting Started with MarketPulse AI

Quick start guide to get MarketPulse AI up and running locally.

## Prerequisites

- Python 3.11+
- Node.js 18+ (for React frontend)
- pip (Python package manager)

## Installation

### 1. Clone and Enter the Project

```bash
cd MarketPulse-AI
```

### 2. Create Virtual Environment

**Windows:**
```bash
python -m venv .venv
.venv\Scripts\activate
```

**macOS/Linux:**
```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install Backend Dependencies

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt   # for tests
```

### 4. Install Frontend Dependencies

```bash
cd frontend
npm install
cd ..
```

### 5. Generate Demo Data

```bash
python scripts/generate_demo_dataset.py
```

Creates `data/demo_sales_365.csv` and `data/demo_sku_master.csv`.

## Running Locally (SQLite Mode)

### Terminal 1 — Backend

```bash
python run_backend.py
```

- API: http://127.0.0.1:8000
- Docs: http://127.0.0.1:8000/docs

### Terminal 2 — Frontend

```bash
cd frontend
npm run dev
```

- React app: http://localhost:5173

### Alternative — Docker Compose (Full Stack)

```bash
docker-compose up --build
```

Starts backend + DynamoDB Local + LocalStack S3 + React frontend.

## Using the API

### Interactive Documentation

Visit http://127.0.0.1:8000/docs for Swagger UI.

### Example Calls

```bash
# Health check
curl http://127.0.0.1:8000/health

# Upload CSV
curl -X POST http://127.0.0.1:8000/upload_csv \
  -F "file=@data/demo_sales_365.csv"

# Batch forecast
curl -X POST http://127.0.0.1:8000/forecast/batch \
  -H "Content-Type: application/json" \
  -d '{"categories":["Snacks","Staples","Edible Oil"],"n_days":30,"inventory":{"Snacks":2800,"Staples":5100,"Edible Oil":1900},"lead_times":{"Snacks":5,"Staples":7,"Edible Oil":10}}'

# Festival calendar
curl http://127.0.0.1:8000/festivals?month=3&year=2026
```

## Verification

### Run Tests

```bash
pytest tests/ -v
```

Expected: 122+ tests passing.

## Project Structure

```
MarketPulse-AI/
├── src/marketpulse/        # Backend (FastAPI + ML services)
│   ├── main.py             # App entry point
│   ├── routes/             # API endpoints
│   ├── services/           # Forecasting, ingestion, diagnostics
│   ├── models/             # SQLAlchemy ORM models
│   ├── schemas/            # Pydantic request/response schemas
│   ├── db/                 # Database layer (SQLite + DynamoDB)
│   └── core/               # Config, logging
├── frontend/               # React SPA (Vite + Tailwind)
│   └── src/
│       ├── pages/          # Portfolio, Category, Festival, Data pages
│       └── components/     # Reusable UI components
├── tests/                  # pytest test suite
├── scripts/                # Data generation, local infra setup
├── infra/                  # AWS deployment configs (ECS, API Gateway)
├── docs/                   # Documentation
├── Dockerfile              # Production container
├── docker-compose.yml      # Local full-stack dev
├── run_backend.py          # Dev launcher (backend only)
└── requirements.txt        # Python dependencies
```

## Common Issues

### "Module not found"

```bash
pip install -r requirements.txt
```

### "Port already in use"

```bash
# Windows:
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# macOS/Linux:
lsof -ti:8000 | xargs kill -9
```

### "Database not found"

The SQLite database is created automatically on first startup. If needed:

```bash
python scripts/generate_demo_dataset.py
```

## Development

### Run Tests with Coverage

```bash
pytest tests/ --cov=src/marketpulse --cov-report=html
```

### DynamoDB Mode (Local)

```bash
docker-compose up dynamodb-local localstack -d
python scripts/init_local.py
USE_DYNAMO=true python run_backend.py
```

## Next Steps

- [API Reference](API_INDEX.md)
- [Architecture Overview](ARCHITECTURE.md)
- [Forecasting Details](RECURSIVE_FORECASTING.md)
- [Model Diagnostics](MODEL_DIAGNOSTICS.md)
