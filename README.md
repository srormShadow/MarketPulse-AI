# MarketPulse AI Backend

Production-ready FastAPI backend for retail demand forecasting and inventory optimization with recursive multi-step forecasting, lag-based autoregressive features, and comprehensive model diagnostics.

> **Quick Links**: [Project Structure](PROJECT_STRUCTURE.md) | [Documentation](docs/README.md) | [API Reference](docs/API_INDEX.md) | [Scripts](scripts/README.md)

## Project Structure

```text
MarketPulse-AI/
├── app/                      # Application code
│   ├── api/                  # API routes and endpoints
│   ├── core/                 # Core configuration and logging
│   ├── db/                   # Database setup and session management
│   ├── models/               # SQLAlchemy models
│   ├── routes/               # API route handlers
│   ├── schemas/              # Pydantic schemas
│   ├── services/             # Business logic and services
│   └── main.py               # FastAPI application entrypoint
├── data/                     # Demo datasets and sample data
├── docs/                     # Documentation and summaries
├── scripts/                  # Utility and verification scripts
├── tests/                    # Test suite
├── .env.example              # Environment template
├── requirements.txt          # Production dependencies
└── requirements-dev.txt      # Development dependencies
```

## Features

### Core Infrastructure
- FastAPI application with modular architecture
- SQLite + SQLAlchemy ORM with session management
- Environment-based configuration via `pydantic-settings`
- Centralized logging with configurable levels
- Health check endpoint at `GET /health`

### Data Management
- CSV ingestion for sales and SKU data
- Festival calendar management
- Category-level sales aggregation
- Data validation and error handling

### Forecasting Engine
- Bayesian Ridge regression with uncertainty quantification
- Recursive multi-step forecasting (up to 90 days)
- Autoregressive lag features (lag_1, lag_7, rolling stats)
- Festival proximity scoring with multi-event accumulation
- Category-specific model training

### Inventory Optimization
- Safety stock calculation based on forecast uncertainty
- Reorder point determination with lead time consideration
- Order quantity recommendations
- Risk assessment and action recommendations

### Model Diagnostics
- Category-specific coefficient analysis
- Cross-category behavioral comparison
- Feature importance ranking
- Sensitivity analysis

### API Endpoints
- `GET /health` - Health check
- `POST /upload/sales` - Upload sales CSV
- `POST /upload/sku` - Upload SKU master CSV
- `POST /forecast/{category}` - Generate forecast with inventory decisions
- `GET /debug/sales` - View sales data
- `GET /debug/sku` - View SKU data
- `GET /debug/festivals` - View festival calendar

## Quick Start

1. **Create and activate a virtual environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt  # For development
   ```

3. **Set up environment:**
   ```bash
   cp .env.example .env
   ```

4. **Initialize database and load demo data:**
   ```bash
   python scripts/generate_demo_dataset.py
   ```

5. **Run the API:**
   ```bash
   uvicorn app.main:app --reload
   ```

6. **Access the application:**
   - API: `http://127.0.0.1:8000`
   - Interactive docs: `http://127.0.0.1:8000/docs`
   - Health check: `http://127.0.0.1:8000/health`

## Testing

Run the full test suite:
```bash
pytest
```

Run with coverage:
```bash
pytest --cov=app --cov-report=html
```

Run verification scripts:
```bash
python scripts/verify_dataset.py
python scripts/verify_features.py
python scripts/verify_forecasting.py
python scripts/verify_recursive_forecast.py
python scripts/verify_category_behavior.py
```

## Documentation

Comprehensive documentation is available in the `docs/` directory:

- **[API Index](docs/API_INDEX.md)** - Overview of all API endpoints
- **[Forecast API](docs/FORECAST_API.md)** - Forecasting endpoint details
- **[Recursive Forecasting](docs/RECURSIVE_FORECASTING.md)** - Technical implementation
- **[Model Diagnostics](docs/MODEL_DIAGNOSTICS.md)** - Category analysis tools
- **[Quick Reference](docs/QUICK_REFERENCE.md)** - Common tasks and examples

## Project Organization

- **`app/`** - Application source code
- **`data/`** - Demo datasets and sample files
- **`docs/`** - Documentation, summaries, and guides
- **`scripts/`** - Utility scripts for data generation and verification
- **`tests/`** - Comprehensive test suite (117 tests)

## Technology Stack

- **FastAPI** - Modern web framework
- **SQLAlchemy** - ORM and database toolkit
- **Pydantic** - Data validation
- **scikit-learn** - Machine learning (BayesianRidge)
- **pandas** - Data manipulation
- **numpy** - Numerical computing
- **pytest** - Testing framework


## File Organization

All files are now properly organized:

- **Root**: Only essential files (README, LICENSE, requirements, config)
- **`/app`**: All application source code
- **`/data`**: Demo datasets and sample files
- **`/docs`**: All documentation, summaries, and guides
- **`/scripts`**: All utility and verification scripts
- **`/tests`**: Comprehensive test suite (117 tests)

See [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) for detailed directory structure and organization principles.

## Contributing

When adding new features:
1. Add code to appropriate `/app` subdirectory
2. Add tests to `/tests`
3. Add documentation to `/docs`
4. Add verification scripts to `/scripts` if needed
5. Update relevant README files

## License

See [LICENSE](LICENSE) file for details.
