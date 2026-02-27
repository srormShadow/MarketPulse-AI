# MarketPulse-AI Project Structure

## Directory Organization

```
MarketPulse-AI/
├── app/                          # Application source code
│   ├── api/                      # API versioning and routing
│   ├── core/                     # Configuration and logging
│   ├── db/                       # Database setup and sessions
│   ├── models/                   # SQLAlchemy ORM models
│   ├── routes/                   # API endpoint handlers
│   ├── schemas/                  # Pydantic request/response schemas
│   ├── services/                 # Business logic and algorithms
│   └── main.py                   # FastAPI application entry point
│
├── data/                         # Demo datasets and sample files
│   ├── demo_sales_365.csv        # Sample sales data
│   ├── demo_sku_master.csv       # Sample SKU master data
│   └── *.png                     # Visualization outputs
│
├── docs/                         # Documentation and guides
│   ├── API_*.md                  # API endpoint documentation
│   ├── FORECAST_*.md             # Forecasting documentation
│   ├── MODEL_*.md                # Model diagnostics documentation
│   ├── RECURSIVE_*.md            # Recursive forecasting docs
│   ├── DIAGNOSTICS_*.md/txt      # Diagnostics documentation
│   ├── IMPLEMENTATION_*.md       # Implementation summaries
│   ├── QUICK_REFERENCE.md        # Quick reference guide
│   └── README.md                 # Documentation index
│
├── scripts/                      # Utility and verification scripts
│   ├── generate_demo_dataset.py  # Generate demo data
│   ├── verify_dataset.py         # Validate dataset
│   ├── verify_features.py        # Verify feature engineering
│   ├── verify_forecasting.py     # Test forecasting
│   ├── verify_recursive_forecast.py  # Validate recursive forecasting
│   ├── verify_category_behavior.py   # Analyze category models
│   └── README.md                 # Scripts documentation
│
├── tests/                        # Comprehensive test suite (117 tests)
│   ├── data/                     # Test fixtures and sample CSVs
│   ├── utils/                    # Test utilities
│   ├── test_*.py                 # Test modules
│   └── conftest.py               # Pytest configuration
│
├── .env.example                  # Environment template
├── .gitignore                    # Git ignore rules
├── LICENSE                       # Project license
├── README.md                     # Project overview
├── requirements.txt              # Production dependencies
├── requirements-dev.txt          # Development dependencies
└── marketpulse.db                # SQLite database (generated)
```

## Key Directories

### `/app` - Application Code
Contains all production application code organized by function:
- **api/**: API versioning and route registration
- **core/**: Configuration, logging, and core utilities
- **db/**: Database connection and session management
- **models/**: SQLAlchemy ORM models (SKU, Sales, Festival, etc.)
- **routes/**: FastAPI route handlers (upload, forecast, debug, health)
- **schemas/**: Pydantic schemas for request/response validation
- **services/**: Business logic (forecasting, feature engineering, decision engine, diagnostics)

### `/data` - Demo Data
Sample datasets for testing and demonstration:
- Sales history (365 days)
- SKU master data
- Visualization outputs

### `/docs` - Documentation
Comprehensive documentation organized by topic:
- **API Documentation**: Complete API reference with examples
- **Technical Guides**: Deep dives into forecasting and diagnostics
- **Implementation Summaries**: Feature overviews and upgrade notes
- **Quick References**: Common tasks and commands

### `/scripts` - Utilities
Standalone scripts for data generation and verification:
- Data generation tools
- Verification and validation scripts
- Category behavior analysis
- Each script is self-contained and documented

### `/tests` - Test Suite
117 comprehensive tests covering:
- API endpoints (health, upload, forecast, debug)
- CSV ingestion and validation
- Feature engineering and lag features
- Forecasting algorithms
- Decision engine logic
- Model diagnostics
- Error handling and edge cases
- Performance benchmarks

## File Organization Principles

1. **Root Directory**: Only essential files (README, LICENSE, requirements, config)
2. **Documentation**: All `.md` and `.txt` docs in `/docs`
3. **Scripts**: All utility scripts in `/scripts`
4. **Source Code**: All application code in `/app`
5. **Tests**: All test code in `/tests`
6. **Data**: All sample data in `/data`

## Quick Navigation

- **Getting Started**: See [README.md](README.md)
- **API Reference**: See [docs/API_INDEX.md](docs/API_INDEX.md)
- **Documentation Index**: See [docs/README.md](docs/README.md)
- **Scripts Guide**: See [scripts/README.md](scripts/README.md)
- **Run Tests**: `pytest tests/`
- **Generate Data**: `python scripts/generate_demo_dataset.py`
- **Start Server**: `uvicorn app.main:app --reload`

## Development Workflow

1. **Setup**: Install dependencies from `requirements.txt` and `requirements-dev.txt`
2. **Generate Data**: Run `scripts/generate_demo_dataset.py`
3. **Start Server**: Run `uvicorn app.main:app --reload`
4. **Run Tests**: Run `pytest tests/`
5. **Verify**: Run scripts in `/scripts` to validate functionality
6. **Document**: Update relevant docs in `/docs`

## Production Deployment

For production, only these directories are needed:
- `/app` - Application code
- `requirements.txt` - Dependencies
- `.env` - Environment configuration (create from `.env.example`)

Optional for production:
- `/data` - If using demo data
- `marketpulse.db` - SQLite database (or use external DB)

Not needed in production:
- `/docs` - Documentation (keep for reference)
- `/scripts` - Utility scripts (keep for maintenance)
- `/tests` - Test suite (keep for CI/CD)
- `requirements-dev.txt` - Development tools

## File Counts

- **Application Code**: ~3,500 lines
- **Test Code**: ~2,000 lines
- **Documentation**: ~5,000 lines
- **Scripts**: ~1,500 lines
- **Total**: ~12,000 lines

## Technology Stack

- **Framework**: FastAPI
- **Database**: SQLAlchemy + SQLite
- **ML**: scikit-learn (BayesianRidge)
- **Data**: pandas, numpy
- **Testing**: pytest
- **Validation**: Pydantic

## Status

✅ Production Ready
- 117 tests passing
- Comprehensive documentation
- Clean architecture
- Type hints throughout
- Full error handling
