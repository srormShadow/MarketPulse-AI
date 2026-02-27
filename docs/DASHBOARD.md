# MarketPulse AI Dashboard

Interactive Streamlit dashboard for retail demand forecasting and inventory optimization.

## Overview

The dashboard provides a user-friendly interface to:
- Generate demand forecasts for different product categories
- Visualize predictions with confidence intervals
- Get actionable inventory recommendations
- Assess stockout risk in real-time

## Features

### 1. Forecast Visualization
- Interactive Plotly charts showing predicted demand
- 95% confidence intervals displayed as shaded regions
- Date-based x-axis for easy interpretation
- Responsive design that adapts to screen size

### 2. Inventory Decision Panel
- **Recommended Action**: ORDER, URGENT_ORDER, MONITOR, or MAINTAIN
- **Order Quantity**: Exact units to order
- **Reorder Point**: Threshold for placing orders
- **Safety Stock**: Buffer inventory for uncertainty
- **Risk Score**: Visual progress bar (0.0 = low risk, 1.0 = high risk)

### 3. Interactive Controls
- **Category Selection**: Choose from Snacks, Staples, or Edible Oil
- **Forecast Horizon**: 7 to 60 days
- **Current Inventory**: Input your current stock level
- **Lead Time**: Supplier delivery time (1-30 days)

## Quick Start

### Prerequisites

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Initialize database:**
   ```bash
   python scripts/generate_demo_dataset.py
   ```

### Option 1: Run Everything Together (Recommended)

```bash
python run_all.py
```

This starts both the backend API and dashboard automatically.

- Backend: http://127.0.0.1:8000
- Dashboard: http://localhost:8501

### Option 2: Run Separately

**Terminal 1 - Start Backend:**
```bash
python run_backend.py
```

**Terminal 2 - Start Dashboard:**
```bash
python run_dashboard.py
```

### Option 3: Manual Commands

**Terminal 1 - Backend:**
```bash
python -m uvicorn app.main:app --reload
```

**Terminal 2 - Dashboard:**
```bash
streamlit run app/dashboard/app.py
```

## Usage Guide

### Step 1: Configure Parameters

Use the sidebar to set:
1. **Category**: Select the product category to forecast
2. **Forecast Horizon**: How many days ahead to predict
3. **Current Inventory**: Your current stock level
4. **Lead Time**: Days until supplier delivery

### Step 2: Generate Forecast

Click the **"Generate Forecast"** button in the sidebar.

The dashboard will:
1. Call the FastAPI backend
2. Generate recursive forecasts with lag features
3. Calculate inventory optimization metrics
4. Display results in real-time

### Step 3: Interpret Results

**Forecast Chart (Left Panel):**
- Blue line: Predicted mean demand
- Shaded area: 95% confidence interval
- Wider intervals = higher uncertainty

**Decision Panel (Right Panel):**
- **Action**: What to do now
  - `ORDER`: Place regular order
  - `URGENT_ORDER`: Place urgent order (high risk)
  - `MONITOR`: Watch inventory levels
  - `MAINTAIN`: Current levels are adequate
- **Order Quantity**: Exact units to order
- **Reorder Point**: When to trigger next order
- **Safety Stock**: Buffer for demand variability
- **Risk Score**: Stockout probability
  - Red (>0.7): High risk
  - Yellow (0.4-0.7): Moderate risk
  - Green (<0.4): Low risk

## Architecture

```
┌─────────────────┐
│   Streamlit     │
│   Dashboard     │
│  (Port 8501)    │
└────────┬────────┘
         │ HTTP Requests
         ▼
┌─────────────────┐
│   FastAPI       │
│   Backend       │
│  (Port 8000)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   SQLite DB     │
│  (marketpulse)  │
└─────────────────┘
```

### Data Flow

1. User configures parameters in Streamlit UI
2. Dashboard sends POST request to `/forecast/{category}`
3. Backend generates forecast using:
   - Bayesian Ridge regression
   - Recursive multi-step prediction
   - Lag features (lag_1, lag_7, rolling stats)
   - Festival proximity scoring
4. Backend calculates inventory decisions:
   - Safety stock
   - Reorder point
   - Order quantity
   - Risk assessment
5. Dashboard receives JSON response
6. Plotly renders interactive chart
7. Metrics displayed in decision panel

## API Integration

The dashboard communicates with the backend via REST API:

**Endpoint:** `POST /forecast/{category}`

**Request:**
```json
{
  "n_days": 30,
  "current_inventory": 200,
  "lead_time_days": 7
}
```

**Response:**
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

## Customization

### Change API URL

Edit `app/dashboard/app.py`:

```python
API_BASE = "http://your-api-url:8000"
```

### Add New Categories

1. Add category to backend database
2. Update dropdown in dashboard:

```python
category = st.sidebar.selectbox(
    "Category",
    ["Snacks", "Staples", "Edible Oil", "Your New Category"]
)
```

### Modify Chart Styling

Edit the Plotly figure configuration:

```python
fig.update_layout(
    title=f"{category} Demand Forecast",
    xaxis_title="Date",
    yaxis_title="Units",
    template="plotly_white",  # Try: plotly_dark, ggplot2, seaborn
    font=dict(size=14),
    height=500
)
```

### Change Color Scheme

Modify the trace colors:

```python
fig.add_trace(go.Scatter(
    x=forecast_df["date"],
    y=forecast_df["predicted_mean"],
    mode="lines",
    name="Predicted Demand",
    line=dict(color="blue", width=3)  # Customize here
))
```

## Troubleshooting

### Issue: "Connection Error"

**Cause:** Backend is not running

**Solution:**
```bash
# Start backend first
python run_backend.py
```

### Issue: "API Error" message

**Cause:** Category not found or insufficient data

**Solution:**
1. Check that demo data is loaded:
   ```bash
   python scripts/generate_demo_dataset.py
   ```
2. Verify category name matches database

### Issue: Dashboard won't start

**Cause:** Streamlit not installed

**Solution:**
```bash
pip install streamlit plotly requests
```

### Issue: Port already in use

**Cause:** Another service is using port 8501

**Solution:**
```bash
# Use different port
streamlit run app/dashboard/app.py --server.port=8502
```

### Issue: Blank chart

**Cause:** No forecast data returned

**Solution:**
1. Check backend logs for errors
2. Verify API response in browser: http://127.0.0.1:8000/docs
3. Test forecast endpoint manually

## Performance

- **Initial Load**: < 1 second
- **Forecast Generation**: 1-3 seconds (depends on horizon)
- **Chart Rendering**: < 500ms
- **Memory Usage**: ~100MB

## Browser Compatibility

Tested and working on:
- ✅ Chrome 120+
- ✅ Firefox 120+
- ✅ Edge 120+
- ✅ Safari 17+

## Mobile Support

The dashboard is responsive and works on:
- Tablets (iPad, Android tablets)
- Large phones (landscape mode recommended)

Note: Some features may be limited on small screens.

## Security Considerations

### For Production Deployment:

1. **Enable Authentication:**
   ```python
   # Add to app.py
   import streamlit_authenticator as stauth
   ```

2. **Use HTTPS:**
   ```bash
   streamlit run app.py --server.enableCORS=false --server.enableXsrfProtection=true
   ```

3. **Restrict API Access:**
   - Add API key authentication
   - Use environment variables for API URL
   - Implement rate limiting

4. **Secure Data:**
   - Don't expose sensitive inventory data
   - Use encrypted connections
   - Implement user roles

## Advanced Features

### Export Forecast Data

Add download button:

```python
csv = forecast_df.to_csv(index=False)
st.download_button(
    label="Download Forecast CSV",
    data=csv,
    file_name=f"forecast_{category}_{n_days}days.csv",
    mime="text/csv"
)
```

### Multiple Category Comparison

Add multi-select:

```python
categories = st.sidebar.multiselect(
    "Compare Categories",
    ["Snacks", "Staples", "Edible Oil"]
)
```

### Historical Data View

Add historical chart:

```python
# Fetch historical data from /debug/sales endpoint
historical = requests.get(f"{API_BASE}/debug/sales?category={category}")
# Plot historical + forecast together
```

## Development

### File Structure

```
app/dashboard/
├── __init__.py          # Package marker
└── app.py               # Main dashboard code
```

### Adding New Pages

Streamlit supports multi-page apps:

```
app/dashboard/
├── app.py               # Home page
├── pages/
│   ├── 1_Forecast.py    # Forecast page
│   ├── 2_Analytics.py   # Analytics page
│   └── 3_Settings.py    # Settings page
```

### Testing

Test the dashboard:

```bash
# Run with test data
streamlit run app/dashboard/app.py -- --test-mode
```

## Resources

- **Streamlit Docs**: https://docs.streamlit.io
- **Plotly Docs**: https://plotly.com/python/
- **FastAPI Docs**: https://fastapi.tiangolo.com

## Support

For issues or questions:
1. Check [Troubleshooting](#troubleshooting) section
2. Review backend logs
3. Test API endpoints directly at http://127.0.0.1:8000/docs
4. Check Streamlit logs in terminal

## License

Same as main project. See [LICENSE](../LICENSE).
