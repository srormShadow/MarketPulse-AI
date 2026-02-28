# MarketPulse AI

Retail demand forecasting and inventory optimization platform powered by Bayesian Ridge regression with recursive multi-step prediction, lag-based autoregressive features, and a React dashboard.

> **Docs**: [Getting Started](docs/GETTING_STARTED.md) | [API Reference](docs/API_INDEX.md) | [Project Structure](docs/PROJECT_STRUCTURE.md) | [All Documentation](docs/README.md)

## Quick Start

```bash
# 1. Clone and set up Python environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Generate demo data and start backend
python scripts/generate_demo_dataset.py
uvicorn src.marketpulse.api.main:app --reload

# 3. Start frontend (separate terminal)
cd frontend
npm install
npm run dev
```

**Access:**
- Frontend Dashboard: http://localhost:5173
- Backend API: http://127.0.0.1:8000
- Swagger Docs: http://127.0.0.1:8000/docs

## Architecture

```
MarketPulse-AI/
├── src/marketpulse/          # Backend (FastAPI + Python)
│   ├── api/                  # Routes and REST endpoints
│   ├── core/                 # Config, logging
│   ├── db/                   # SQLAlchemy session and init
│   ├── domain/               # Models and Pydantic schemas
│   └── infrastructure/       # Database layer
├── frontend/                 # Frontend (React + Vite + Tailwind)
│   └── src/
│       ├── components/       # Reusable UI components
│       └── pages/            # Dashboard pages
├── scripts/                  # Data generation and verification
├── tests/                    # pytest test suite (117 tests)
├── data/                     # Demo datasets and DB
└── docs/                     # All documentation
```

## Features

### Backend
- **Forecasting Engine** — BayesianRidge with recursive multi-step prediction (up to 90 days), 95% confidence intervals, autoregressive lag features (lag_1, lag_7, rolling stats), festival proximity scoring
- **Inventory Optimization** — Safety stock calculation, reorder point determination, order quantity recommendations, risk assessment with action classification
- **Model Diagnostics** — Per-category coefficient analysis, cross-category comparison, feature importance ranking, behavioral classification
- **REST API** — FastAPI with health check, CSV upload (sales/SKU), forecast generation, debug endpoints

### Frontend
- **Portfolio Overview** — KPI cards, inventory health table with risk indicators, interactive risk drawer for high-risk categories, risk distribution and inventory gap charts
- **Category Intelligence** — Per-category demand forecast visualization with historical/predicted lines, confidence bands, decision summary with AI-recommended actions
- **Data Management** — CSV upload with drag-and-drop, inventory configuration, demo dataset loader
- Dark glass-morphism UI with Recharts visualizations and Tailwind CSS

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/upload/sales` | Upload sales CSV |
| `POST` | `/upload/sku` | Upload SKU master CSV |
| `POST` | `/forecast/{category}` | Generate forecast with inventory decisions |
| `GET` | `/debug/sales` | View sales data |
| `GET` | `/debug/sku` | View SKU data |
| `GET` | `/debug/festivals` | View festival calendar |

## Testing

```bash
pytest                                    # Run all tests
pytest --cov=src --cov-report=html        # With coverage
pytest tests/test_lag_features.py -v      # Specific test file
```

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | FastAPI, SQLAlchemy 2.0, Pydantic |
| ML | scikit-learn (BayesianRidge), pandas, numpy |
| Frontend | React 19, Vite 7, Tailwind CSS v4, Recharts |
| Testing | pytest |
| Database | SQLite (dev) |

## Documentation

See [docs/README.md](docs/README.md) for the full documentation index, including:
- [API Reference](docs/API_INDEX.md) — All endpoints with examples
- [Forecast API](docs/FORECAST_API.md) — Forecasting endpoint details
- [Recursive Forecasting](docs/RECURSIVE_FORECASTING.md) — Algorithm deep-dive
- [Model Diagnostics](docs/MODEL_DIAGNOSTICS.md) — Category analysis tools
- [AWS Deployment](docs/AWS_DEPLOYMENT.md) — Deployment strategy

## License

See [LICENSE](LICENSE) for details.
