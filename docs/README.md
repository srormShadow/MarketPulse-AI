# MarketPulse-AI Documentation

Welcome to the MarketPulse-AI documentation! This directory contains comprehensive documentation for the retail demand forecasting and inventory optimization API.

## 📚 Documentation Index

### API Documentation

Complete API reference with examples and use cases:

- **[API Index](API_INDEX.md)** - Complete API overview and quick start guide
- **[Health API](API_HEALTH.md)** - Service health monitoring endpoint
- **[Upload API](API_UPLOAD.md)** - CSV data ingestion (SKU and Sales)
- **[Forecast API](FORECAST_API.md)** - Demand forecasting and inventory decisions
- **[Debug API](API_DEBUG.md)** - Data inspection and debugging endpoints

### Technical Documentation

Deep dives into the forecasting system:

- **[Recursive Forecasting](RECURSIVE_FORECASTING.md)** - Technical details on lag features and recursive multi-step forecasting
- **[Before/After Comparison](BEFORE_AFTER_COMPARISON.md)** - Comparison of forecasting approaches (batch vs recursive)

## 🚀 Quick Start

### 1. Start the Service

```bash
cd MarketPulse-AI
uvicorn app.main:app --reload
```

### 2. Check Health

```bash
curl http://localhost:8000/health
```

### 3. Upload Data

```bash
# Upload SKU master data
curl -X POST http://localhost:8000/upload_csv \
  -F "file=@data/demo_sku_master.csv"

# Upload sales history
curl -X POST http://localhost:8000/upload_csv \
  -F "file=@data/demo_sales_365.csv"
```

### 4. Generate Forecast

```bash
curl -X POST http://localhost:8000/forecast/Snacks \
  -H "Content-Type: application/json" \
  -d '{
    "n_days": 30,
    "current_inventory": 500,
    "lead_time_days": 7
  }'
```

## 📖 Documentation Structure

```
docs/
├── README.md                      # This file
├── API_INDEX.md                   # Complete API overview
├── API_HEALTH.md                  # Health check endpoint
├── API_UPLOAD.md                  # CSV upload endpoint
├── API_DEBUG.md                   # Debug endpoints
├── FORECAST_API.md                # Forecasting endpoint
├── RECURSIVE_FORECASTING.md       # Technical deep dive
└── BEFORE_AFTER_COMPARISON.md     # Forecasting comparison
```

## 🎯 Use Cases

### Retail Demand Forecasting

Generate probabilistic demand forecasts with uncertainty quantification:

```python
import requests

response = requests.post(
    'http://localhost:8000/forecast/Snacks',
    json={
        'n_days': 30,
        'current_inventory': 500,
        'lead_time_days': 7
    }
)

forecast = response.json()
print(f"Action: {forecast['decision']['recommended_action']}")
print(f"Order Quantity: {forecast['decision']['order_quantity']}")
```

### Inventory Optimization

Get actionable inventory recommendations:

- **ORDER**: Place regular order
- **URGENT_ORDER**: Place urgent order (high risk)
- **MONITOR**: Monitor inventory levels
- **MAINTAIN**: Maintain current levels

### Data Analysis

Inspect and analyze your data:

```python
import requests

# Get all SKUs
response = requests.get('http://localhost:8000/skus?limit=100')
skus = response.json()['items']

# Analyze by category
from collections import Counter
categories = Counter(sku['category'] for sku in skus)
print(categories)
```

## 🔧 API Features

### Forecasting Engine

- **Recursive Multi-Step Prediction**: Proper temporal dependency handling
- **Lag Features**: Captures short-term momentum and weekly seasonality
- **Uncertainty Quantification**: 95% confidence intervals
- **Festival Impact**: Accounts for festival-driven demand spikes

### Inventory Decisions

- **Safety Stock**: Calculated based on demand uncertainty
- **Reorder Point**: Optimized for lead time and service level
- **Order Quantity**: Recommended order amount
- **Risk Score**: Inventory risk assessment (0.0-1.0)

### Data Ingestion

- **Auto-Detection**: Automatically detects SKU vs Sales files
- **Validation**: Comprehensive data validation
- **Upsert Logic**: Updates existing records, inserts new ones
- **Error Reporting**: Detailed validation error messages

## 📊 Response Formats

### Forecast Response

```json
{
  "category": "Snacks",
  "forecast": [
    {
      "date": "2024-03-01",
      "predicted_mean": 52.3,
      "lower_95": 42.1,
      "upper_95": 62.5
    }
  ],
  "decision": {
    "recommended_action": "ORDER",
    "order_quantity": 450,
    "reorder_point": 385.5,
    "safety_stock": 125.3,
    "risk_score": 0.65
  }
}
```

### Upload Response

```json
{
  "status": "success",
  "records_inserted": 150,
  "file_type": "sales"
}
```

### Error Response

```json
{
  "status": "error",
  "message": "Validation failed",
  "errors": [
    {
      "field": "sku_id",
      "issue": "Missing required column"
    }
  ]
}
```

## 🛠️ Development

### Running Tests

```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/test_forecast_api.py -v

# With coverage
pytest tests/ --cov=app --cov-report=html
```

### API Documentation

Interactive API docs available at:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Code Quality

```bash
# Type checking
mypy app/

# Linting
ruff check app/

# Formatting
black app/
```

## 📝 Examples

### Python Client

```python
from marketpulse_client import MarketPulseClient

client = MarketPulseClient('http://localhost:8000')

# Upload data
client.upload_csv('sku_master.csv')
client.upload_csv('sales_data.csv')

# Generate forecast
forecast = client.forecast(
    category='Snacks',
    n_days=30,
    current_inventory=500,
    lead_time_days=7
)

print(f"Recommended action: {forecast['decision']['recommended_action']}")
```

### JavaScript Client

```javascript
const client = new MarketPulseClient('http://localhost:8000');

// Generate forecast
const forecast = await client.forecast('Snacks', 30, 500, 7);
console.log(`Action: ${forecast.decision.recommended_action}`);
```

## 🔍 Troubleshooting

### Common Issues

**Issue: "Category not found"**
- Ensure SKU data is uploaded first
- Check category name spelling (case-sensitive)

**Issue: "Insufficient historical data"**
- Need at least 7 days of sales history
- Upload more sales data

**Issue: "Validation failed"**
- Check CSV format matches requirements
- Verify all required columns are present
- Check data types (dates, numbers)

### Debug Endpoints

Use debug endpoints to inspect data:

```bash
# Check SKU count
curl http://localhost:8000/skus

# Check sales count
curl http://localhost:8000/sales/count

# View festivals
curl http://localhost:8000/festivals
```

## 📚 Additional Resources

### Project Files

- **[QUICK_REFERENCE.md](../QUICK_REFERENCE.md)** - Quick reference guide
- **[RECURSIVE_FORECAST_UPGRADE.md](../RECURSIVE_FORECAST_UPGRADE.md)** - Implementation details
- **[UPGRADE_SUMMARY.txt](../UPGRADE_SUMMARY.txt)** - Visual upgrade summary

### Test Files

- `tests/test_forecast_api.py` - Forecast API tests
- `tests/test_lag_features.py` - Lag feature tests
- `tests/test_forecasting.py` - Forecasting algorithm tests

### Verification

- `verify_recursive_forecast.py` - Verification script for forecasting

## 🤝 Contributing

When adding new API endpoints:

1. Implement the endpoint in `app/routes/`
2. Add Pydantic schemas in `app/schemas/`
3. Write comprehensive tests in `tests/`
4. Document the endpoint in `docs/API_*.md`
5. Update `docs/API_INDEX.md`

## 📄 License

See [LICENSE](../LICENSE) file for details.

## 🆘 Support

For issues, questions, or contributions:

- Open an issue on GitHub
- Check existing documentation
- Review test files for examples
- Run verification scripts

## 🎓 Learning Path

**Beginner:**
1. Read [API_INDEX.md](API_INDEX.md)
2. Try [Quick Start](#-quick-start)
3. Explore [API_UPLOAD.md](API_UPLOAD.md)

**Intermediate:**
1. Read [FORECAST_API.md](FORECAST_API.md)
2. Understand [API_DEBUG.md](API_DEBUG.md)
3. Experiment with different parameters

**Advanced:**
1. Study [RECURSIVE_FORECASTING.md](RECURSIVE_FORECASTING.md)
2. Review [BEFORE_AFTER_COMPARISON.md](BEFORE_AFTER_COMPARISON.md)
3. Explore source code in `app/services/`

## 📈 Performance

- **Health Check**: < 10ms
- **CSV Upload**: 1-3 seconds (1000-5000 rows)
- **Forecast Generation**: 15-50ms (7-90 days)
- **Debug Queries**: 50-300ms (100-500 records)

## 🔐 Security

For production deployments:

- Implement authentication (API keys, OAuth2, JWT)
- Add rate limiting
- Enable HTTPS
- Validate file uploads thoroughly
- Sanitize user inputs
- Monitor for abuse

## 🌟 Features

- ✅ Recursive multi-step forecasting
- ✅ Lag-based autoregressive features
- ✅ Uncertainty quantification (95% CI)
- ✅ Festival impact modeling
- ✅ Inventory optimization
- ✅ CSV data ingestion
- ✅ Comprehensive validation
- ✅ Debug endpoints
- ✅ Full test coverage (92 tests)
- ✅ Production-ready

---

**Last Updated**: March 2024  
**Version**: 1.0  
**Status**: Production Ready ✅
