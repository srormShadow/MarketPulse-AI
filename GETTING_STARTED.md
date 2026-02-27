# Getting Started with MarketPulse AI

Quick start guide to get MarketPulse AI up and running in minutes.

## Prerequisites

- Python 3.10 or higher
- pip (Python package manager)
- 500MB free disk space

## Installation

### 1. Clone or Download the Project

```bash
cd MarketPulse-AI
```

### 2. Create Virtual Environment (Recommended)

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

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- FastAPI (backend framework)
- Streamlit (dashboard)
- SQLAlchemy (database)
- scikit-learn (ML models)
- pandas, numpy (data processing)
- plotly (visualizations)

### 4. Generate Demo Data

```bash
python scripts/generate_demo_dataset.py
```

This creates:
- `data/demo_sales_365.csv` - 365 days of sales data
- `data/demo_sku_master.csv` - SKU master data
- `marketpulse.db` - SQLite database with sample data

## Running the Application

### Option 1: Run Everything (Easiest)

```bash
python run_all.py
```

This starts both backend and dashboard automatically.

**Access:**
- Dashboard: http://localhost:8501 (opens automatically)
- Backend API: http://127.0.0.1:8000
- API Docs: http://127.0.0.1:8000/docs

### Option 2: Run Separately

**Terminal 1 - Backend:**
```bash
python run_backend.py
```

**Terminal 2 - Dashboard:**
```bash
python run_dashboard.py
```

### Option 3: Manual Commands

**Terminal 1:**
```bash
python -m uvicorn app.main:app --reload
```

**Terminal 2:**
```bash
streamlit run app/dashboard/app.py
```

## Using the Dashboard

### 1. Open Dashboard

Navigate to http://localhost:8501 in your browser.

### 2. Configure Forecast

In the sidebar, set:
- **Category**: Snacks, Staples, or Edible Oil
- **Forecast Horizon**: 7-60 days
- **Current Inventory**: Your stock level
- **Lead Time**: Supplier delivery time

### 3. Generate Forecast

Click **"Generate Forecast"** button.

### 4. View Results

- **Left Panel**: Interactive forecast chart with confidence intervals
- **Right Panel**: Inventory recommendations and risk assessment

## Using the API

### Interactive Documentation

Visit http://127.0.0.1:8000/docs for interactive API documentation.

### Example API Calls

**Health Check:**
```bash
curl http://127.0.0.1:8000/health
```

**Generate Forecast:**
```bash
curl -X POST http://127.0.0.1:8000/forecast/Snacks \
  -H "Content-Type: application/json" \
  -d '{
    "n_days": 30,
    "current_inventory": 500,
    "lead_time_days": 7
  }'
```

**Upload Sales Data:**
```bash
curl -X POST http://127.0.0.1:8000/upload/sales \
  -F "file=@data/demo_sales_365.csv"
```

## Verification

### Run Tests

```bash
pytest tests/ -v
```

Expected: 117 tests passing

### Run Verification Scripts

```bash
# Verify dataset
python scripts/verify_dataset.py

# Verify features
python scripts/verify_features.py

# Verify forecasting
python scripts/verify_forecasting.py

# Verify recursive forecast
python scripts/verify_recursive_forecast.py

# Analyze category behavior
python scripts/verify_category_behavior.py
```

## Project Structure

```
MarketPulse-AI/
├── app/                    # Application code
│   ├── dashboard/          # Streamlit dashboard
│   ├── routes/             # API endpoints
│   ├── services/           # Business logic
│   └── main.py             # FastAPI app
├── data/                   # Demo datasets
├── docs/                   # Documentation
├── scripts/                # Utility scripts
├── tests/                  # Test suite
├── run_all.py              # Launch everything
├── run_backend.py          # Launch backend only
├── run_dashboard.py        # Launch dashboard only
└── requirements.txt        # Dependencies
```

## Common Issues

### Issue: "Module not found"

**Solution:**
```bash
pip install -r requirements.txt
```

### Issue: "Port already in use"

**Solution:**
```bash
# Kill process on port 8000 (backend)
# Windows:
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# macOS/Linux:
lsof -ti:8000 | xargs kill -9
```

### Issue: "Database not found"

**Solution:**
```bash
python scripts/generate_demo_dataset.py
```

### Issue: "Connection refused" in dashboard

**Solution:** Make sure backend is running first:
```bash
python run_backend.py
```

## Next Steps

### 1. Explore the Dashboard
- Try different categories
- Adjust forecast horizons
- Experiment with inventory levels

### 2. Review Documentation
- [API Documentation](docs/API_INDEX.md)
- [Dashboard Guide](docs/DASHBOARD.md)
- [Forecasting Details](docs/RECURSIVE_FORECASTING.md)
- [Model Diagnostics](docs/MODEL_DIAGNOSTICS.md)

### 3. Customize for Your Data
- Replace demo data with your actual sales data
- Add your product categories
- Configure festival calendar for your region

### 4. Run Diagnostics
```bash
python scripts/verify_category_behavior.py
```

This shows how different categories learn different patterns.

## Development

### Install Dev Dependencies

```bash
pip install -r requirements-dev.txt
```

### Run Tests with Coverage

```bash
pytest tests/ --cov=app --cov-report=html
```

View coverage report: `htmlcov/index.html`

### Code Quality

```bash
# Type checking
mypy app/

# Linting
ruff check app/

# Formatting
black app/
```

## Production Deployment

For production deployment:

1. **Use Production Database:**
   - Replace SQLite with PostgreSQL/MySQL
   - Update connection string in `.env`

2. **Enable Security:**
   - Add authentication (API keys, OAuth2)
   - Enable HTTPS
   - Configure CORS properly

3. **Scale Services:**
   - Use Gunicorn/uWSGI for backend
   - Deploy dashboard separately
   - Add load balancer

4. **Monitor:**
   - Add logging
   - Set up error tracking
   - Monitor performance

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for detailed instructions (coming soon).

## Getting Help

- **Documentation**: See [docs/](docs/) directory
- **API Reference**: http://127.0.0.1:8000/docs (when running)
- **Examples**: See [scripts/](scripts/) directory
- **Tests**: See [tests/](tests/) directory for usage examples

## Quick Reference

**Start Everything:**
```bash
python run_all.py
```

**Backend Only:**
```bash
python run_backend.py
```

**Dashboard Only:**
```bash
python run_dashboard.py
```

**Run Tests:**
```bash
pytest tests/
```

**Generate Data:**
```bash
python scripts/generate_demo_dataset.py
```

**Verify System:**
```bash
python scripts/verify_recursive_forecast.py
```

## Success Checklist

- [ ] Virtual environment created and activated
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] Demo data generated (`python scripts/generate_demo_dataset.py`)
- [ ] Backend starts successfully (`python run_backend.py`)
- [ ] Dashboard opens in browser (`python run_dashboard.py`)
- [ ] Forecast generates without errors
- [ ] Tests pass (`pytest tests/`)

## What's Next?

You're ready to use MarketPulse AI! 🎉

- Explore the dashboard at http://localhost:8501
- Try the API at http://127.0.0.1:8000/docs
- Read the documentation in [docs/](docs/)
- Customize for your business needs

Happy forecasting! 📊
