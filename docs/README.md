# Documentation Index

All project documentation lives in this directory.

## Getting Started

- **[Getting Started](GETTING_STARTED.md)** — Installation, setup, and first run
- **[Project Structure](PROJECT_STRUCTURE.md)** — Directory layout and organization

## API Reference

- **[API Index](API_INDEX.md)** — All endpoints overview, client examples, Postman collection
- **[Health API](API_HEALTH.md)** — `GET /health` endpoint
- **[Upload API](API_UPLOAD.md)** — `POST /upload_csv` with CSV format specs
- **[Forecast API](FORECAST_API.md)** — `POST /forecast/{category}` with decision engine
- **[Debug API](API_DEBUG.md)** — `/skus`, `/sales/count`, `/festivals` inspection endpoints

## Technical Deep Dives

- **[Recursive Forecasting](RECURSIVE_FORECASTING.md)** — Lag features, recursive multi-step algorithm, data flow, performance
- **[Before/After Comparison](BEFORE_AFTER_COMPARISON.md)** — Batch vs recursive forecasting side-by-side
- **[Model Diagnostics](MODEL_DIAGNOSTICS.md)** — Category coefficient analysis, feature importance, behavioral classification

## Deployment

- **[AWS Deployment](AWS_DEPLOYMENT.md)** — EC2 + S3 + CloudFront deployment strategy, cost breakdown, architecture

## Quick API Test

```bash
# Start backend
uvicorn src.marketpulse.api.main:app --reload

# Health check
curl http://localhost:8000/health

# Upload demo data
curl -X POST http://localhost:8000/upload_csv -F "file=@data/demo_sku_master.csv"
curl -X POST http://localhost:8000/upload_csv -F "file=@data/demo_sales_365.csv"

# Generate forecast
curl -X POST http://localhost:8000/forecast/Snacks \
  -H "Content-Type: application/json" \
  -d '{"n_days": 30, "current_inventory": 500, "lead_time_days": 7}'
```
