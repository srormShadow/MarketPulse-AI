# Debug API

## Overview

The Debug API provides read-only endpoints for inspecting data stored in the MarketPulse-AI system. These endpoints are designed for internal debugging, data verification, and system monitoring.

## Base URL

```
http://localhost:8000
```

## Endpoints

### GET /skus

Retrieve paginated list of SKU (Stock Keeping Unit) records.

#### Request

**Method:** `GET`

**URL:** `/skus`

**Headers:** None required

**Query Parameters:**

| Parameter | Type | Required | Default | Constraints | Description |
|-----------|------|----------|---------|-------------|-------------|
| `limit` | integer | No | 50 | 1-500 | Number of records per page |
| `offset` | integer | No | 0 | >= 0 | Number of records to skip |

#### Response

**Status Code:** `200 OK`

**Content-Type:** `application/json`

**Response Body:**

```json
{
  "status": "success",
  "total": 1250,
  "limit": 50,
  "offset": 0,
  "items": [
    {
      "sku_id": "OIL001",
      "product_name": "Premium Sunflower Oil 1L",
      "category": "Edible Oil",
      "mrp": 180.0,
      "cost": 130.0,
      "current_inventory": 500
    },
    {
      "sku_id": "OIL002",
      "product_name": "Refined Soybean Oil 1L",
      "category": "Edible Oil",
      "mrp": 165.0,
      "cost": 120.0,
      "current_inventory": 450
    }
  ]
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | Always "success" |
| `total` | integer | Total number of SKU records in database |
| `limit` | integer | Number of records per page (from request) |
| `offset` | integer | Number of records skipped (from request) |
| `items` | array | Array of SKU records |

**SKU Item Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `sku_id` | string | Unique product identifier |
| `product_name` | string | Product name |
| `category` | string | Product category |
| `mrp` | float | Maximum Retail Price |
| `cost` | float | Cost price |
| `current_inventory` | integer | Current stock level |

#### Example Usage

**cURL:**

```bash
# Get first 50 SKUs
curl -X GET "http://localhost:8000/skus"

# Get next 50 SKUs
curl -X GET "http://localhost:8000/skus?limit=50&offset=50"

# Get 100 SKUs starting from record 200
curl -X GET "http://localhost:8000/skus?limit=100&offset=200"
```

**Python:**

```python
import requests

# Get first page
response = requests.get('http://localhost:8000/skus')
data = response.json()

print(f"Total SKUs: {data['total']}")
print(f"Showing {len(data['items'])} records")

for sku in data['items']:
    print(f"{sku['sku_id']}: {sku['product_name']} - {sku['category']}")

# Pagination example
def get_all_skus():
    all_skus = []
    offset = 0
    limit = 100
    
    while True:
        response = requests.get(
            'http://localhost:8000/skus',
            params={'limit': limit, 'offset': offset}
        )
        data = response.json()
        all_skus.extend(data['items'])
        
        if offset + limit >= data['total']:
            break
        offset += limit
    
    return all_skus

skus = get_all_skus()
print(f"Retrieved {len(skus)} total SKUs")
```

**JavaScript:**

```javascript
async function getSKUs(limit = 50, offset = 0) {
  const response = await fetch(
    `http://localhost:8000/skus?limit=${limit}&offset=${offset}`
  );
  return await response.json();
}

// Usage
const data = await getSKUs();
console.log(`Total SKUs: ${data.total}`);
data.items.forEach(sku => {
  console.log(`${sku.sku_id}: ${sku.product_name}`);
});
```

---

### GET /sales/count

Get total count of sales records in the database.

#### Request

**Method:** `GET`

**URL:** `/sales/count`

**Headers:** None required

**Query Parameters:** None

#### Response

**Status Code:** `200 OK`

**Content-Type:** `application/json`

**Response Body:**

```json
{
  "status": "success",
  "total_sales_rows": 45678
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | Always "success" |
| `total_sales_rows` | integer | Total number of sales records |

#### Example Usage

**cURL:**

```bash
curl -X GET "http://localhost:8000/sales/count"
```

**Python:**

```python
import requests

response = requests.get('http://localhost:8000/sales/count')
data = response.json()

print(f"Total sales records: {data['total_sales_rows']:,}")
```

**JavaScript:**

```javascript
async function getSalesCount() {
  const response = await fetch('http://localhost:8000/sales/count');
  const data = await response.json();
  return data.total_sales_rows;
}

const count = await getSalesCount();
console.log(`Total sales records: ${count.toLocaleString()}`);
```

---

### GET /festivals

Retrieve list of all festival records.

#### Request

**Method:** `GET`

**URL:** `/festivals`

**Headers:** None required

**Query Parameters:** None

#### Response

**Status Code:** `200 OK`

**Content-Type:** `application/json`

**Response Body:**

```json
{
  "status": "success",
  "total": 8,
  "items": [
    {
      "festival_name": "Pongal",
      "date": "2024-01-15",
      "category": "general",
      "historical_uplift": 0.2
    },
    {
      "festival_name": "Holi",
      "date": "2024-03-25",
      "category": "general",
      "historical_uplift": 0.15
    },
    {
      "festival_name": "Diwali",
      "date": "2024-11-01",
      "category": "general",
      "historical_uplift": 0.3
    }
  ]
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | Always "success" |
| `total` | integer | Total number of festival records |
| `items` | array | Array of festival records |

**Festival Item Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `festival_name` | string | Name of the festival |
| `date` | string | Festival date (YYYY-MM-DD format) |
| `category` | string | Festival category (e.g., "general") |
| `historical_uplift` | float | Historical sales uplift factor (0.0-1.0) |

#### Example Usage

**cURL:**

```bash
curl -X GET "http://localhost:8000/festivals"
```

**Python:**

```python
import requests
from datetime import datetime

response = requests.get('http://localhost:8000/festivals')
data = response.json()

print(f"Total festivals: {data['total']}")
print("\nUpcoming festivals:")

for festival in data['items']:
    date = datetime.strptime(festival['date'], '%Y-%m-%d')
    uplift_pct = festival['historical_uplift'] * 100
    print(f"  {festival['festival_name']}: {date.strftime('%B %d, %Y')} "
          f"(+{uplift_pct:.0f}% uplift)")
```

**JavaScript:**

```javascript
async function getFestivals() {
  const response = await fetch('http://localhost:8000/festivals');
  return await response.json();
}

const data = await getFestivals();
console.log(`Total festivals: ${data.total}`);

data.items.forEach(festival => {
  const date = new Date(festival.date);
  const uplift = (festival.historical_uplift * 100).toFixed(0);
  console.log(`${festival.festival_name}: ${date.toLocaleDateString()} (+${uplift}% uplift)`);
});
```

## Use Cases

### 1. Data Verification

Verify that uploaded data was correctly ingested:

```python
import requests

# Upload SKU file
with open('sku_master.csv', 'rb') as f:
    upload_response = requests.post(
        'http://localhost:8000/upload_csv',
        files={'file': f}
    )
    records_inserted = upload_response.json()['records_inserted']

# Verify count
skus_response = requests.get('http://localhost:8000/skus')
total_skus = skus_response.json()['total']

print(f"Inserted: {records_inserted}, Total in DB: {total_skus}")
```

### 2. Data Export

Export all SKUs to a different format:

```python
import requests
import csv

def export_skus_to_csv(output_file):
    all_skus = []
    offset = 0
    limit = 500
    
    while True:
        response = requests.get(
            'http://localhost:8000/skus',
            params={'limit': limit, 'offset': offset}
        )
        data = response.json()
        all_skus.extend(data['items'])
        
        if offset + limit >= data['total']:
            break
        offset += limit
    
    # Write to CSV
    with open(output_file, 'w', newline='') as f:
        if all_skus:
            writer = csv.DictWriter(f, fieldnames=all_skus[0].keys())
            writer.writeheader()
            writer.writerows(all_skus)
    
    print(f"Exported {len(all_skus)} SKUs to {output_file}")

export_skus_to_csv('exported_skus.csv')
```

### 3. Category Analysis

Analyze SKUs by category:

```python
import requests
from collections import defaultdict

def analyze_categories():
    all_skus = []
    offset = 0
    
    while True:
        response = requests.get(
            'http://localhost:8000/skus',
            params={'limit': 500, 'offset': offset}
        )
        data = response.json()
        all_skus.extend(data['items'])
        
        if offset + 500 >= data['total']:
            break
        offset += 500
    
    # Group by category
    categories = defaultdict(list)
    for sku in all_skus:
        categories[sku['category']].append(sku)
    
    # Print summary
    print("Category Analysis:")
    for category, skus in sorted(categories.items()):
        total_inventory = sum(s['current_inventory'] for s in skus)
        avg_mrp = sum(s['mrp'] for s in skus) / len(skus)
        print(f"  {category}:")
        print(f"    SKUs: {len(skus)}")
        print(f"    Total Inventory: {total_inventory:,}")
        print(f"    Avg MRP: ₹{avg_mrp:.2f}")

analyze_categories()
```

### 4. Festival Calendar

Display upcoming festivals:

```python
import requests
from datetime import datetime, timedelta

def show_upcoming_festivals(days=90):
    response = requests.get('http://localhost:8000/festivals')
    festivals = response.json()['items']
    
    today = datetime.now().date()
    cutoff = today + timedelta(days=days)
    
    upcoming = [
        f for f in festivals
        if today <= datetime.strptime(f['date'], '%Y-%m-%d').date() <= cutoff
    ]
    
    print(f"Upcoming festivals (next {days} days):")
    for festival in sorted(upcoming, key=lambda x: x['date']):
        date = datetime.strptime(festival['date'], '%Y-%m-%d')
        days_away = (date.date() - today).days
        uplift = festival['historical_uplift'] * 100
        print(f"  {festival['festival_name']}: {date.strftime('%B %d')} "
              f"({days_away} days away, +{uplift:.0f}% uplift)")

show_upcoming_festivals()
```

## Pagination Best Practices

### Efficient Pagination

```python
def paginate_efficiently(endpoint, limit=100):
    """Generator for efficient pagination."""
    offset = 0
    
    while True:
        response = requests.get(
            f'http://localhost:8000/{endpoint}',
            params={'limit': limit, 'offset': offset}
        )
        data = response.json()
        
        yield from data['items']
        
        if offset + limit >= data['total']:
            break
        offset += limit

# Usage
for sku in paginate_efficiently('skus', limit=500):
    print(sku['sku_id'])
```

### Progress Tracking

```python
def get_all_with_progress(endpoint, limit=100):
    """Fetch all records with progress indicator."""
    all_items = []
    offset = 0
    
    # Get total first
    response = requests.get(
        f'http://localhost:8000/{endpoint}',
        params={'limit': 1, 'offset': 0}
    )
    total = response.json()['total']
    
    print(f"Fetching {total} records...")
    
    while offset < total:
        response = requests.get(
            f'http://localhost:8000/{endpoint}',
            params={'limit': limit, 'offset': offset}
        )
        data = response.json()
        all_items.extend(data['items'])
        
        progress = min(100, (offset + limit) / total * 100)
        print(f"Progress: {progress:.1f}% ({len(all_items)}/{total})")
        
        offset += limit
    
    return all_items
```

## Performance Considerations

- **Limit Size**: Use 100-500 for optimal performance
- **Caching**: Results are not cached; each request hits the database
- **Concurrent Requests**: Safe to make concurrent requests
- **Response Time**: 
  - Small limits (< 100): < 100ms
  - Medium limits (100-500): 100-300ms
  - Large limits (> 500): 300ms-1s

## Error Handling

These endpoints typically don't return errors, but handle edge cases:

```python
import requests

def safe_get_skus(limit=50, offset=0):
    try:
        response = requests.get(
            'http://localhost:8000/skus',
            params={'limit': limit, 'offset': offset},
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        print("Request timed out")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return None
```

## Related APIs

- [Upload API](API_UPLOAD.md) - Upload data to inspect
- [Forecast API](FORECAST_API.md) - Generate forecasts from data
- [Health API](API_HEALTH.md) - Check service health
