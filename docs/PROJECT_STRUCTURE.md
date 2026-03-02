# MarketPulse-AI Project Structure

## Directory Layout

```
MarketPulse-AI/
├── src/marketpulse/              # Backend application (FastAPI)
│   ├── main.py                   # FastAPI app, CORS, lifespan
│   ├── api/                      # Health-check router
│   │   └── v1/health.py
│   ├── core/                     # Settings (pydantic-settings), logging
│   │   ├── config.py
│   │   └── logging.py
│   ├── db/                       # Database layer
│   │   ├── repository.py         # DataRepository protocol + SQLiteRepository
│   │   ├── dynamo_repository.py  # DynamoRepository implementation
│   │   ├── dynamo.py             # boto3 table schemas + ensure_tables_exist
│   │   ├── get_repo.py           # FastAPI dependency factory
│   │   ├── session.py            # SQLAlchemy engine + SessionLocal
│   │   ├── init_db.py            # Startup init (create tables, seed festivals)
│   │   └── base.py               # Declarative base
│   ├── models/                   # SQLAlchemy ORM models
│   │   ├── sku.py
│   │   ├── sales.py
│   │   ├── festival.py
│   │   └── health_ping.py
│   ├── routes/                   # API endpoint handlers
│   │   ├── router.py             # Central router (includes all sub-routers)
│   │   ├── upload.py             # POST /upload_csv
│   │   ├── forecast.py           # POST /forecast/{category}, /forecast/batch
│   │   ├── debug.py              # GET /skus, /sales_count, /festivals
│   │   ├── diagnostics.py        # GET /diagnostics/all, /diagnostics/{cat}
│   │   ├── insights.py           # GET /insights/{category} (Bedrock)
│   │   └── recommendations.py    # GET /recommendations/recent
│   ├── schemas/                  # Pydantic request/response schemas
│   │   ├── forecast.py
│   │   ├── upload.py
│   │   ├── insights.py
│   │   └── debug.py
│   ├── services/                 # Business logic
│   │   ├── forecasting.py        # BayesianRidge train + recursive forecast
│   │   ├── feature_engineering.py # Lag features, festival proximity, time index
│   │   ├── decision_engine.py    # Risk scoring, reorder/safety stock calc
│   │   ├── model_diagnostics.py  # Coefficient extraction, category comparison
│   │   ├── csv_ingestion.py      # CSV parse + upsert (SKU + Sales)
│   │   ├── festival_seed.py      # 2026 Indian festival calendar seed
│   │   ├── ingestion/
│   │   │   └── s3_archive.py     # S3 upload after CSV ingestion
│   │   └── insights/
│   │       └── bedrock_insights.py  # AWS Bedrock GenAI summaries
│   └── infrastructure/
│       └── s3.py                 # S3 client helper
│
├── frontend/                     # React SPA (Vite + Tailwind CSS)
│   └── src/
│       ├── App.jsx               # Router, sidebar, layout
│       ├── api/client.js         # Centralized axios client
│       ├── pages/                # 4 main pages
│       │   ├── PortfolioOverview.jsx
│       │   ├── CategoryIntelligence.jsx
│       │   ├── FestivalIntelligence.jsx
│       │   └── DataManagement.jsx
│       └── components/
│           ├── ui/               # GlassCard, StatCard, RiskDrawer
│           └── festival/         # FestivalCalendar, PredictionSidebar
│
├── tests/                        # pytest suite (122+ tests)
│   ├── conftest.py               # Fixtures (engine, session, repo, client)
│   ├── utils/csv_factory.py      # CSV test data generators
│   └── test_*.py                 # Test modules
│
├── scripts/                      # Utility scripts
│   ├── generate_demo_dataset.py  # Synthetic data generator
│   └── init_local.py             # DynamoDB Local + LocalStack bootstrap
│
├── infra/                        # AWS deployment configs
│   ├── deploy.sh                 # ECR push + ECS deploy script
│   ├── ecs-task-definition.json  # Fargate task definition
│   └── aws-api-gateway-config.json  # API Gateway REST proxy
│
├── docs/                         # Documentation
├── data/                         # Demo CSV datasets + SQLite DB
│
├── Dockerfile                    # Production container
├── docker-compose.yml            # Local full-stack (backend + DynamoDB + S3 + frontend)
├── run_backend.py                # Dev launcher (uvicorn --reload)
├── requirements.txt              # Production Python deps
├── requirements-dev.txt          # Test deps (pytest, httpx)
├── pytest.ini                    # pytest config (pythonpath = src)
├── .coveragerc                   # Coverage config
├── .env.example                  # Environment variable template
├── .gitignore
├── .dockerignore
├── LICENSE                       # MIT
└── README.md
```

## Key Architecture Decisions

### Repository Protocol Pattern
All database I/O goes through `DataRepository` (a Python protocol in `db/repository.py`).
Two implementations exist: `SQLiteRepository` (SQLAlchemy) and `DynamoRepository` (boto3).
The `USE_DYNAMO` env var controls which backend is active via `db/get_repo.py`.

### Service Layer
Services never import SQLAlchemy or boto3 directly — they depend only on `DataRepository`.

### Frontend
Single `apiClient` (axios) in `api/client.js` handles all API calls. Base URL is set via
`VITE_API_BASE_URL` env var. No scattered fetch calls.

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend Framework | FastAPI |
| Database (local) | SQLAlchemy + SQLite |
| Database (cloud) | DynamoDB (boto3) |
| ML | scikit-learn (BayesianRidge) |
| Data Processing | pandas |
| Frontend | React 19 + Vite + Tailwind CSS |
| Charts | Recharts |
| GenAI Insights | AWS Bedrock (Claude) |
| Object Storage | S3 (via LocalStack locally) |
| Container | Docker + ECS Fargate |
