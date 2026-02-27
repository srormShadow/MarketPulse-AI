# CSV Upload API

## Overview

The CSV Upload API allows you to ingest SKU (Stock Keeping Unit) master data and sales transaction data into the MarketPulse-AI system. The API automatically detects the file type based on the CSV structure and validates the data before insertion.

## Base URL

```
http://localhost:8000
```

## Endpoints

### POST /upload_csv

Upload and ingest SKU or Sales CSV files.

#### Request

**Method:** `POST`

**URL:** `/upload_csv`

**Headers:**

```
Content-Type: multipart/form-data
```

**Form Data:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | File | Yes | CSV file (must have .csv extension) |

**File Requirements:**

- File extension must be `.csv`
- File must be valid CSV format
- File type (SKU or Sales) is auto-detected from structure

#### SKU CSV Format

**Required Columns:**

| Column | Type | Description | Constraints |
|--------|------|-------------|-------------|
| `sku_id` | string | Unique product identifier | Required, max 64 chars |
| `product_name` | string | Product name | Required, max 255 chars |
| `category` | string | Product category | Required, max 100 chars |
| `mrp` | float | Maximum Retail Price | Required, > 0 |
| `cost` | float | Cost price | Required, > 0 |
| `current_inventory` | integer | Current stock level | Required, >= 0 |

**Example SKU CSV:**

```csv
sku_id,product_name,category,mrp,cost,current_inventory
OIL001,Premium Sunflower Oil 1L,Edible Oil,180.00,130.00,500
OIL002,Refined Soybean Oil 1L,Edible Oil,165.00,120.00,450
SNK001,Potato Chips Classic 100g,Snacks,40.00,25.00,1200
```

#### Sales CSV Format

**Required Columns:**

| Column | Type | Description | Constraints |
|--------|------|-------------|-------------|
| `sku_id` | string | Product identifier (must exist in SKU table) | Required |
| `date` | date | Transaction date | Required, format: YYYY-MM-DD |
| `units_sold` | integer | Number of units sold | Required, >= 0 |

**Example Sales CSV:**

```csv
sku_id,date,units_sold
OIL001,2024-01-01,125
OIL001,2024-01-02,132
OIL002,2024-01-01,98
SNK001,2024-01-01,245
```

#### Response

**Success Response (200 OK):**

```json
{
  "status": "success",
  "records_inserted": 150,
  "file_type": "sales"
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | Always "success" for successful uploads |
| `records_inserted` | integer | Number of records successfully inserted/updated |
| `file_type` | string | Detected file type: "sku" or "sales" |

**Error Response (400 Bad Request):**

```json
{
  "status": "error",
  "message": "Validation failed",
  "errors": [
    {
      "field": "sku_id",
      "issue": "Missing required column"
    },
    {
      "field": "row_5",
      "issue": "Invalid date format"
    }
  ]
}
```

**Error Response (500 Internal Server Error):**

```json
{
  "status": "error",
  "message": "Internal server error"
}
```

## Example Usage

### cURL

**Upload SKU CSV:**

```bash
curl -X POST "http://localhost:8000/upload_csv" \
  -F "file=@sku_master.csv"
```

**Upload Sales CSV:**

```bash
curl -X POST "http://localhost:8000/upload_csv" \
  -F "file=@sales_data.csv"
```

### Python (requests)

```python
import requests

# Upload SKU file
with open('sku_master.csv', 'rb') as f:
    files = {'file': ('sku_master.csv', f, 'text/csv')}
    response = requests.post(
        'http://localhost:8000/upload_csv',
        files=files
    )
    
if response.status_code == 200:
    data = response.json()
    print(f"Success! Inserted {data['records_inserted']} {data['file_type']} records")
else:
    error = response.json()
    print(f"Error: {error['message']}")
    for err in error.get('errors', []):
        print(f"  - {err['field']}: {err['issue']}")
```

### Python (httpx - async)

```python
import httpx
import asyncio

async def upload_csv(file_path: str):
    async with httpx.AsyncClient() as client:
        with open(file_path, 'rb') as f:
            files = {'file': (file_path, f, 'text/csv')}
            response = await client.post(
                'http://localhost:8000/upload_csv',
                files=files
            )
            return response.json()

# Usage
result = asyncio.run(upload_csv('sales_data.csv'))
print(result)
```

### JavaScript (FormData)

```javascript
async function uploadCSV(file) {
  const formData = new FormData();
  formData.append('file', file);

  try {
    const response = await fetch('http://localhost:8000/upload_csv', {
      method: 'POST',
      body: formData
    });

    const data = await response.json();
    
    if (response.ok) {
      console.log(`Success! Inserted ${data.records_inserted} ${data.file_type} records`);
    } else {
      console.error('Upload failed:', data.message);
      data.errors?.forEach(err => {
        console.error(`  - ${err.field}: ${err.issue}`);
      });
    }
  } catch (error) {
    console.error('Network error:', error);
  }
}

// Usage with file input
document.getElementById('fileInput').addEventListener('change', (e) => {
  const file = e.target.files[0];
  if (file) {
    uploadCSV(file);
  }
});
```

### HTTPie

```bash
http --form POST http://localhost:8000/upload_csv file@sku_master.csv
```

## Data Validation Rules

### SKU Validation

1. **Required Columns**: All columns must be present
2. **SKU ID**: 
   - Normalized to uppercase
   - Must be unique (duplicates trigger upsert)
   - Max 64 characters
3. **Product Name**: Max 255 characters
4. **Category**: Max 100 characters
5. **MRP & Cost**: Must be positive numbers
6. **Current Inventory**: 
   - Must be non-negative integer
   - Negative values cause row to be dropped

### Sales Validation

1. **Required Columns**: All columns must be present
2. **SKU ID**: Must exist in SKU table (referential integrity)
3. **Date**: 
   - Must be valid date in YYYY-MM-DD format
   - Future dates are accepted
4. **Units Sold**: 
   - Must be non-negative integer
   - Negative values cause row to be dropped
5. **Duplicates**: Same sku_id + date combinations are upserted (latest wins)

## Behavior Details

### Upsert Logic

**SKU Files:**
- If SKU ID already exists, the record is updated
- New SKU IDs are inserted
- No records are deleted

**Sales Files:**
- If sku_id + date combination exists, the record is updated
- New combinations are inserted
- No records are deleted

### Partial Success

If some rows fail validation:
- Valid rows are still inserted
- Invalid rows are reported in the error response
- HTTP status is 400 with details of failed rows

### Case Sensitivity

- SKU IDs are normalized to uppercase
- Column headers are case-insensitive
- Whitespace in headers is trimmed

## Error Codes

| Status Code | Description |
|-------------|-------------|
| 200 | Success - all records inserted/updated |
| 400 | Validation error - check errors array for details |
| 500 | Internal server error - check logs |

## Common Validation Errors

### File Format Errors

```json
{
  "status": "error",
  "message": "Validation failed",
  "errors": [
    {
      "field": "file",
      "issue": "Only .csv files are supported"
    }
  ]
}
```

### Missing Column Errors

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

### Data Type Errors

```json
{
  "status": "error",
  "message": "Validation failed",
  "errors": [
    {
      "field": "row_3.mrp",
      "issue": "Invalid numeric value"
    }
  ]
}
```

### Referential Integrity Errors

```json
{
  "status": "error",
  "message": "Validation failed",
  "errors": [
    {
      "field": "row_5.sku_id",
      "issue": "SKU 'XYZ999' not found in database"
    }
  ]
}
```

## Best Practices

1. **File Size**: Keep files under 10MB for optimal performance
2. **Batch Size**: Upload 1000-5000 rows per file for best results
3. **Order**: Upload SKU files before Sales files (referential integrity)
4. **Validation**: Validate CSV format locally before uploading
5. **Error Handling**: Always check response status and handle errors
6. **Retry Logic**: Implement exponential backoff for transient errors
7. **Idempotency**: Safe to retry uploads (upsert behavior)

## Performance

- **Small files** (<1000 rows): < 1 second
- **Medium files** (1000-5000 rows): 1-3 seconds
- **Large files** (5000+ rows): 3-10 seconds

## Limitations

- Maximum file size: 100MB
- Maximum rows per file: 50,000 (recommended)
- Concurrent uploads: Supported (database handles locking)
- Rate limiting: None currently applied

## Testing

### Sample Test Files

Create test files for validation:

**test_sku.csv:**
```csv
sku_id,product_name,category,mrp,cost,current_inventory
TEST001,Test Product 1,Test Category,100.00,50.00,100
TEST002,Test Product 2,Test Category,150.00,75.00,200
```

**test_sales.csv:**
```csv
sku_id,date,units_sold
TEST001,2024-01-01,50
TEST001,2024-01-02,45
TEST002,2024-01-01,30
```

### Test Script

```python
import requests

def test_upload():
    # Upload SKU file
    with open('test_sku.csv', 'rb') as f:
        response = requests.post(
            'http://localhost:8000/upload_csv',
            files={'file': f}
        )
        assert response.status_code == 200
        data = response.json()
        assert data['file_type'] == 'sku'
        print(f"✓ SKU upload: {data['records_inserted']} records")
    
    # Upload Sales file
    with open('test_sales.csv', 'rb') as f:
        response = requests.post(
            'http://localhost:8000/upload_csv',
            files={'file': f}
        )
        assert response.status_code == 200
        data = response.json()
        assert data['file_type'] == 'sales'
        print(f"✓ Sales upload: {data['records_inserted']} records")

if __name__ == '__main__':
    test_upload()
```

## Related APIs

- [Debug API](API_DEBUG.md) - View uploaded data
- [Forecast API](FORECAST_API.md) - Generate forecasts from uploaded data
