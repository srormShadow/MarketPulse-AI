# Scripts Directory

This directory contains utility and verification scripts for the MarketPulse-AI system.

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

## Verification Scripts

These scripts validate different components of the forecasting system.

### `verify_dataset.py`
Validates the demo dataset integrity and structure.

**Usage:**
```bash
python scripts/verify_dataset.py
```

**Checks:**
- Data completeness
- Date ranges
- Category distribution
- Data quality

### `verify_features.py`
Verifies feature engineering pipeline correctness.

**Usage:**
```bash
python scripts/verify_features.py
```

**Validates:**
- Time index generation
- Weekday features
- Festival proximity scores
- Feature data types

### `verify_forecasting.py`
Tests the basic forecasting functionality.

**Usage:**
```bash
python scripts/verify_forecasting.py
```

**Validates:**
- Model training
- Prediction generation
- Uncertainty estimation
- Output format

### `verify_recursive_forecast.py`
Validates the recursive forecasting implementation with lag features.

**Usage:**
```bash
python scripts/verify_recursive_forecast.py
```

**Validates:**
- Lag feature generation (lag_1, lag_7, rolling_mean_7, rolling_std_7)
- No NaN leakage
- Recursive prediction consistency
- Confidence interval validity
- Uncertainty growth with horizon

**Output:** Comprehensive validation report with ✓/✗ indicators

### `verify_category_behavior.py`
Demonstrates that different categories learn different behavioral patterns.

**Usage:**
```bash
python scripts/verify_category_behavior.py
```

**Analyzes:**
- Category-specific model coefficients
- Festival sensitivity comparison
- Lag feature importance
- Behavioral summaries
- Feature sensitivity leaders

**Output:** Detailed comparison tables and insights

## Running All Verifications

To run all verification scripts in sequence:

```bash
python scripts/verify_dataset.py
python scripts/verify_features.py
python scripts/verify_forecasting.py
python scripts/verify_recursive_forecast.py
python scripts/verify_category_behavior.py
```

## Notes

- All scripts assume the database is initialized and populated
- Scripts should be run from the project root directory
- Some scripts require demo data to be generated first
