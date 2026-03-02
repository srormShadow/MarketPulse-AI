# Scripts Directory

Utility scripts for the MarketPulse-AI system.

## Data Generation

### `generate_demo_dataset.py`
Generates synthetic demo datasets for testing and demonstration purposes.

**Usage:**
```bash
python scripts/generate_demo_dataset.py
```

**Output:**
- `data/demo_sales_365.csv` - 365 days of sales data
- `data/demo_sku_master.csv` - SKU master data

## Local Infrastructure

### `init_local.py`
Initializes local AWS-compatible services (DynamoDB Local, LocalStack S3)
and seeds baseline data.

**Usage:**
```bash
python scripts/init_local.py
```

**Prerequisites:** Docker containers for DynamoDB Local and LocalStack
must be running (see `docker-compose.yml`).

## Notes

- All scripts should be run from the project root directory
- Some scripts require demo data to be generated first
