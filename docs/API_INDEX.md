# MarketPulse-AI API Documentation

## Overview

MarketPulse-AI provides a RESTful API for retail demand forecasting and inventory optimization. The API enables CSV data ingestion, demand forecasting with uncertainty quantification, and inventory decision recommendations.

## Base URL

```
http://localhost:8000
```

For production deployments, replace with your actual domain.

## API Version

Current Version: **v1.0**

## Authentication

Currently, no authentication is required. For production deployments, implement appropriate authentication mechanisms (API keys, OAuth2, JWT, etc.).

## Content Type

All API endpoints accept and return JSON, except for file uploads which use `multipart/form-data`.

**Request Headers:**
```
Content-Type: application/json
```

**Response Headers:**
```
Content-Type: application/json
```

## API Endpoints

### Health & Monitoring

| Endpoint | Method | Description | Documentation |
|----------|--------|-------------|---------------|
| `/health` | GET | Check service health status | [API_HEALTH.md](API_HEALTH.md) |

### Data Ingestion

| Endpoint | Method | Description | Documentation |
|----------|--------|-------------|---------------|
| `/upload_csv` | POST | Upload SKU or Sales CSV files | [API_UPLOAD.md](API_UPLOAD.md) |

### Forecasting & Decisions

| Endpoint | Method | Description | Documentation |
|----------|--------|-------------|---------------|
| `/forecast/{category}` | POST | Generate demand forecast and inventory decisions | [FORECAST_API.md](FORECAST_API.md) |

### Debug & Inspection

| Endpoint | Method | Description | Documentation |
|----------|--------|-------------|---------------|
| `/skus` | GET | List SKU records (paginated) | [API_DEBUG.md](API_DEBUG.md) |
| `/sales/count` | GET | Get total sales record count | [API_DEBUG.md](API_DEBUG.md) |
| `/festivals` | GET | List festival records | [API_DEBUG.md](API_DEBUG.md) |

## Quick Start

### 1. Check Service Health

```bash
curl http://localhost:8000/health
```

### 2. Upload SKU Data

```bash
curl -X POST http://localhost:8000/upload_csv \
  -F "file=@sku_master.csv"
```

### 3. Upload Sales Data

```bash
curl -X POST http://localhost:8000/upload_csv \
  -F "file=@sales_data.csv"
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

## Response Format

### Success Response

All successful responses follow this structure:

```json
{
  "status": "success",
  // ... endpoint-specific data
}
```

### Error Response

All error responses follow this structure:

```json
{
  "status": "error",
  "message": "Error description",
  "errors": [
    {
      "field": "field_name",
      "issue": "Issue description"
    }
  ]
}
```

## HTTP Status Codes

| Code | Description | Usage |
|------|-------------|-------|
| 200 | OK | Successful request |
| 400 | Bad Request | Invalid input or validation error |
| 404 | Not Found | Resource not found (e.g., category doesn't exist) |
| 422 | Unprocessable Entity | Request validation failed (Pydantic) |
| 500 | Internal Server Error | Server-side error |

## Rate Limiting

Currently, no rate limiting is applied. For production deployments, consider implementing rate limiting based on your requirements.

## Error Handling

### Client-Side Error Handling

```python
import requests

def make_api_request(url, method='GET', **kwargs):
    try:
        response = requests.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 400:
            error_data = e.response.json()
            print(f"Validation Error: {error_data['message']}")
            for err in error_data.get('errors', []):
                print(f"  - {err['field']}: {err['issue']}")
        elif e.response.status_code == 404:
            print("Resource not found")
        elif e.response.status_code == 500:
            print("Server error - please try again later")
        else:
            print(f"HTTP Error: {e}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return None
```

## Data Flow

### Typical Workflow

```
1. Upload SKU Master Data
   POST /upload_csv (sku_master.csv)
   ↓
2. Upload Sales History
   POST /upload_csv (sales_data.csv)
   ↓
3. Verify Data (Optional)
   GET /skus
   GET /sales/count
   ↓
4. Generate Forecast
   POST /forecast/{category}
   ↓
5. Use Forecast Results
   - Inventory decisions
   - Procurement planning
   - Demand analysis
```

## API Clients

### Python Client Example

```python
import requests
from typing import Optional

class MarketPulseClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
    
    def health_check(self) -> dict:
        """Check service health."""
        response = requests.get(f"{self.base_url}/health")
        return response.json()
    
    def upload_csv(self, file_path: str) -> dict:
        """Upload SKU or Sales CSV file."""
        with open(file_path, 'rb') as f:
            files = {'file': f}
            response = requests.post(
                f"{self.base_url}/upload_csv",
                files=files
            )
            response.raise_for_status()
            return response.json()
    
    def forecast(
        self,
        category: str,
        n_days: int,
        current_inventory: int,
        lead_time_days: int
    ) -> dict:
        """Generate forecast for a category."""
        response = requests.post(
            f"{self.base_url}/forecast/{category}",
            json={
                "n_days": n_days,
                "current_inventory": current_inventory,
                "lead_time_days": lead_time_days
            }
        )
        response.raise_for_status()
        return response.json()
    
    def get_skus(self, limit: int = 50, offset: int = 0) -> dict:
        """Get paginated SKU list."""
        response = requests.get(
            f"{self.base_url}/skus",
            params={"limit": limit, "offset": offset}
        )
        return response.json()

# Usage
client = MarketPulseClient()

# Check health
health = client.health_check()
print(f"Service status: {health['status']}")

# Upload data
result = client.upload_csv("sku_master.csv")
print(f"Uploaded {result['records_inserted']} SKU records")

# Generate forecast
forecast = client.forecast(
    category="Snacks",
    n_days=30,
    current_inventory=500,
    lead_time_days=7
)
print(f"Forecast action: {forecast['decision']['recommended_action']}")
```

### JavaScript Client Example

```javascript
class MarketPulseClient {
  constructor(baseUrl = 'http://localhost:8000') {
    this.baseUrl = baseUrl;
  }

  async healthCheck() {
    const response = await fetch(`${this.baseUrl}/health`);
    return await response.json();
  }

  async uploadCSV(file) {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${this.baseUrl}/upload_csv`, {
      method: 'POST',
      body: formData
    });

    if (!response.ok) {
      throw new Error(`Upload failed: ${response.statusText}`);
    }

    return await response.json();
  }

  async forecast(category, nDays, currentInventory, leadTimeDays) {
    const response = await fetch(`${this.baseUrl}/forecast/${category}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        n_days: nDays,
        current_inventory: currentInventory,
        lead_time_days: leadTimeDays
      })
    });

    if (!response.ok) {
      throw new Error(`Forecast failed: ${response.statusText}`);
    }

    return await response.json();
  }

  async getSKUs(limit = 50, offset = 0) {
    const response = await fetch(
      `${this.baseUrl}/skus?limit=${limit}&offset=${offset}`
    );
    return await response.json();
  }
}

// Usage
const client = new MarketPulseClient();

// Check health
const health = await client.healthCheck();
console.log(`Service status: ${health.status}`);

// Generate forecast
const forecast = await client.forecast('Snacks', 30, 500, 7);
console.log(`Action: ${forecast.decision.recommended_action}`);
```

## Testing

### Postman Collection

Import the following collection to test all endpoints:

```json
{
  "info": {
    "name": "MarketPulse-AI API",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "item": [
    {
      "name": "Health Check",
      "request": {
        "method": "GET",
        "header": [],
        "url": {
          "raw": "{{base_url}}/health",
          "host": ["{{base_url}}"],
          "path": ["health"]
        }
      }
    },
    {
      "name": "Upload CSV",
      "request": {
        "method": "POST",
        "header": [],
        "body": {
          "mode": "formdata",
          "formdata": [
            {
              "key": "file",
              "type": "file",
              "src": "/path/to/file.csv"
            }
          ]
        },
        "url": {
          "raw": "{{base_url}}/upload_csv",
          "host": ["{{base_url}}"],
          "path": ["upload_csv"]
        }
      }
    },
    {
      "name": "Generate Forecast",
      "request": {
        "method": "POST",
        "header": [
          {
            "key": "Content-Type",
            "value": "application/json"
          }
        ],
        "body": {
          "mode": "raw",
          "raw": "{\n  \"n_days\": 30,\n  \"current_inventory\": 500,\n  \"lead_time_days\": 7\n}"
        },
        "url": {
          "raw": "{{base_url}}/forecast/Snacks",
          "host": ["{{base_url}}"],
          "path": ["forecast", "Snacks"]
        }
      }
    }
  ],
  "variable": [
    {
      "key": "base_url",
      "value": "http://localhost:8000"
    }
  ]
}
```

### Integration Tests

```python
import pytest
import requests

BASE_URL = "http://localhost:8000"

def test_health_check():
    response = requests.get(f"{BASE_URL}/health")
    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'ok'
    assert 'timestamp' in data

def test_upload_and_forecast_workflow():
    # Upload SKU data
    with open('test_sku.csv', 'rb') as f:
        response = requests.post(
            f"{BASE_URL}/upload_csv",
            files={'file': f}
        )
        assert response.status_code == 200
        assert response.json()['file_type'] == 'sku'
    
    # Upload sales data
    with open('test_sales.csv', 'rb') as f:
        response = requests.post(
            f"{BASE_URL}/upload_csv",
            files={'file': f}
        )
        assert response.status_code == 200
        assert response.json()['file_type'] == 'sales'
    
    # Generate forecast
    response = requests.post(
        f"{BASE_URL}/forecast/TestCategory",
        json={
            "n_days": 7,
            "current_inventory": 100,
            "lead_time_days": 5
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert 'forecast' in data
    assert 'decision' in data
    assert len(data['forecast']) == 7
```

## OpenAPI/Swagger Documentation

Access interactive API documentation at:

```
http://localhost:8000/docs
```

This provides:
- Interactive API testing
- Request/response schemas
- Example requests
- Try-it-out functionality

Alternative ReDoc documentation:

```
http://localhost:8000/redoc
```

## Versioning

Current API version is embedded in the base URL. Future versions will use:

```
http://localhost:8000/api/v2/...
```

## Support & Resources

- **GitHub Repository**: [Link to repo]
- **Issue Tracker**: [Link to issues]
- **Documentation**: This directory
- **Examples**: See `examples/` directory

## Changelog

### v1.0 (Current)
- Initial API release
- Health check endpoint
- CSV upload (SKU and Sales)
- Demand forecasting with recursive multi-step prediction
- Inventory decision engine
- Debug endpoints for data inspection

## Related Documentation

- [Health API](API_HEALTH.md) - Service health monitoring
- [Upload API](API_UPLOAD.md) - CSV data ingestion
- [Forecast API](FORECAST_API.md) - Demand forecasting and inventory decisions
- [Debug API](API_DEBUG.md) - Data inspection and debugging
- [Recursive Forecasting](RECURSIVE_FORECASTING.md) - Technical details on forecasting algorithm
- [Before/After Comparison](BEFORE_AFTER_COMPARISON.md) - Forecasting upgrade details
