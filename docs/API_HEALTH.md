# Health Check API

## Overview

The Health Check API provides a simple endpoint to verify that the MarketPulse-AI service is running and responsive.

## Base URL

```
http://localhost:8000
```

## Endpoints

### GET /health

Check the health status of the API service.

#### Request

**Method:** `GET`

**URL:** `/health`

**Headers:** None required

**Query Parameters:** None

**Request Body:** None

#### Response

**Status Code:** `200 OK`

**Content-Type:** `application/json`

**Response Body:**

```json
{
  "status": "ok",
  "timestamp": "2024-03-01T10:30:45.123456+00:00"
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | Health status indicator (always "ok" if service is running) |
| `timestamp` | string | ISO 8601 formatted UTC timestamp of the health check |

#### Example Usage

**cURL:**

```bash
curl -X GET "http://localhost:8000/health"
```

**Python (requests):**

```python
import requests

response = requests.get("http://localhost:8000/health")
data = response.json()

print(f"Status: {data['status']}")
print(f"Timestamp: {data['timestamp']}")
```

**JavaScript (fetch):**

```javascript
fetch('http://localhost:8000/health')
  .then(response => response.json())
  .then(data => {
    console.log('Status:', data.status);
    console.log('Timestamp:', data.timestamp);
  });
```

**HTTPie:**

```bash
http GET http://localhost:8000/health
```

#### Response Examples

**Success Response:**

```json
{
  "status": "ok",
  "timestamp": "2024-03-01T14:25:30.456789+00:00"
}
```

## Use Cases

1. **Service Monitoring**: Automated health checks for monitoring systems
2. **Load Balancer Health Checks**: Verify service availability for load balancers
3. **Deployment Verification**: Confirm successful deployment
4. **Uptime Monitoring**: Track service availability over time
5. **Integration Testing**: Verify API connectivity before running tests

## Error Handling

The health endpoint typically doesn't return errors. If the service is down, you'll receive:

- **Connection Refused**: Service is not running
- **Timeout**: Service is unresponsive
- **502/503/504**: Service is behind a proxy/load balancer that can't reach it

## Best Practices

1. **Polling Interval**: Check health every 30-60 seconds for monitoring
2. **Timeout**: Set a reasonable timeout (e.g., 5 seconds)
3. **Retry Logic**: Implement exponential backoff for retries
4. **Alerting**: Alert on consecutive failures (e.g., 3+ failures)
5. **Logging**: Log health check failures for debugging

## Integration Examples

### Docker Health Check

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1
```

### Kubernetes Liveness Probe

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 30
  timeoutSeconds: 5
  failureThreshold: 3
```

### Python Monitoring Script

```python
import requests
import time
from datetime import datetime

def check_health():
    try:
        response = requests.get(
            "http://localhost:8000/health",
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            print(f"[{datetime.now()}] ✓ Service healthy: {data['status']}")
            return True
        else:
            print(f"[{datetime.now()}] ✗ Unexpected status: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"[{datetime.now()}] ✗ Health check failed: {e}")
        return False

# Monitor every 60 seconds
while True:
    check_health()
    time.sleep(60)
```

## Notes

- The health endpoint is lightweight and designed for frequent polling
- No authentication required
- No rate limiting applied
- Response time should be < 100ms under normal conditions
- The timestamp is always in UTC timezone
