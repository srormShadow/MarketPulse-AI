# Forecast API Documentation

## Overview

The Forecast API provides production-ready endpoints for demand forecasting and inventory optimization decisions. It combines probabilistic forecasting with intelligent inventory management recommendations.

## Endpoint

### POST /forecast/{category}

Generate demand forecast and inventory decision for a product category.

#### Path Parameters

- `category` (string, required): Product category name (e.g., "Snacks", "Beverages")

#### Request Body

```json
{
  "n_days": 30,
  "current_inventory": 500,
  "lead_time_days": 7
}
```

**Parameters:**
- `n_days` (integer, required): Number of days to forecast (1-365)
- `current_inventory` (integer, required): Current inventory level (≥0)
- `lead_time_days` (integer, required): Supplier lead time in days (1-90)

#### Response (200 OK)

```json
{
  "category": "Snacks",
  "forecast": [
    {
      "date": "2024-02-01",
      "predicted_mean": 52.3,
      "lower_95": 42.1,
      "upper_95": 62.5
    },
    {
      "date": "2024-02-02",
      "predicted_mean": 54.7,
      "lower_95": 44.2,
      "upper_95": 65.2
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

**Response Fields:**

- `category`: Product category name
- `forecast`: Array of forecast data points
  - `date`: Forecast date (YYYY-MM-DD format)
  - `predicted_mean`: Mean predicted demand
  - `lower_95`: Lower 95% confidence bound
  - `upper_95`: Upper 95% confidence bound
- `decision`: Inventory optimization summary
  - `recommended_action`: One of:
    - `ORDER`: Place regular order
    - `URGENT_ORDER`: Place urgent order (high risk)
    - `MONITOR`: Monitor inventory levels
    - `MAINTAIN`: Maintain current levels
    - `INSUFFICIENT_DATA`: Not enough data for decision
  - `order_quantity`: Recommended order quantity (0 if no order needed)
  - `reorder_point`: Calculated reorder point
  - `safety_stock`: Calculated safety stock
  - `risk_score`: Risk score (0.0=low risk, 1.0=high risk)

#### Error Responses

**404 Not Found** - Category doesn't exist
```json
{
  "status": "error",
  "message": "Category 'InvalidCategory' not found in database"
}
```

**400 Bad Request** - Validation error
```json
{
  "status": "error",
  "message": "n_days must be a positive integer"
}
```

**422 Unprocessable Entity** - Invalid request parameters
```json
{
  "detail": [
    {
      "loc": ["body", "n_days"],
      "msg": "ensure this value is greater than 0",
      "type": "value_error"
    }
  ]
}
```

**500 Internal Server Error** - Server error
```json
{
  "status": "error",
  "message": "Internal server error during forecast generation"
}
```

## Usage Examples

### cURL

```bash
curl -X POST "http://localhost:8000/forecast/Snacks" \
  -H "Content-Type: application/json" \
  -d '{
    "n_days": 30,
    "current_inventory": 500,
    "lead_time_days": 7
  }'
```

### Python (requests)

```python
import requests

response = requests.post(
    "http://localhost:8000/forecast/Snacks",
    json={
        "n_days": 30,
        "current_inventory": 500,
        "lead_time_days": 7
    }
)

data = response.json()
print(f"Action: {data['decision']['recommended_action']}")
print(f"Order Quantity: {data['decision']['order_quantity']}")
```

### JavaScript (fetch)

```javascript
const response = await fetch('http://localhost:8000/forecast/Snacks', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    n_days: 30,
    current_inventory: 500,
    lead_time_days: 7
  })
});

const data = await response.json();
console.log(`Action: ${data.decision.recommended_action}`);
console.log(`Order Quantity: ${data.decision.order_quantity}`);
```

## Business Logic

### Forecasting

The API uses Bayesian Ridge regression with:
- Time-based features (trend, seasonality)
- Festival proximity scoring
- Probabilistic uncertainty quantification (95% confidence intervals)

### Inventory Decisions

The decision engine calculates:

1. **Safety Stock**: Buffer inventory based on demand uncertainty and service level (95%)
2. **Reorder Point**: Inventory level that triggers reordering (lead time demand + safety stock)
3. **Order Quantity**: Recommended order amount to cover forecast period
4. **Risk Score**: Combined metric of inventory position and forecast uncertainty

### Action Logic

- `URGENT_ORDER`: Order quantity > 0 AND risk score ≥ 0.7
- `ORDER`: Order quantity > 0 AND risk score < 0.7
- `MONITOR`: Order quantity = 0 AND risk score ≥ 0.5
- `MAINTAIN`: Order quantity = 0 AND risk score < 0.5

## Architecture

### Service Layer

- `app/services/forecasting.py`: Probabilistic demand forecasting
- `app/services/decision_engine.py`: Inventory optimization logic
- `app/services/feature_engineering.py`: Feature preparation

### API Layer

- `app/routes/forecast.py`: FastAPI route handlers
- `app/schemas/forecast.py`: Pydantic request/response schemas

### Design Principles

- No business logic in routes (delegated to services)
- Comprehensive error handling with proper HTTP status codes
- Type hints throughout
- Structured logging for observability
- Modular, testable architecture

## Testing

Run the forecast API tests:

```bash
pytest tests/test_forecast_api.py -v
pytest tests/test_decision_engine.py -v
```

All tests include:
- Happy path scenarios
- Error handling validation
- Edge cases (low/high inventory, various horizons)
- Data format validation
- Business logic verification
