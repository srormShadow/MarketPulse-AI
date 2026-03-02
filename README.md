# MarketPulse AI

AI-powered retail demand forecasting and inventory optimization for small and medium Indian retailers.

This repository is a hackathon submission focused on one practical question: how can a neighborhood retailer decide what to reorder before festival-driven demand shifts cause stockouts or overstock? MarketPulse AI combines probabilistic demand forecasting, inventory decision logic, and GenAI explanations so store owners can act earlier with less guesswork.

The system is designed for SME retail operators and planners who do not have data science teams. It provides category-level forecasts, reorder guidance, and Bedrock-generated plain-language recommendations in one workflow, with AWS-native deployment and storage patterns for production-ready architecture.

## 1. Why AI Is Required

### Why rule-based systems fail in Indian festival retail
- Simple threshold rules (`if stock < X, reorder`) cannot adapt to changing festival timing and variable demand uplift.
- Fixed seasonal factors break when local behavior changes year to year or by category (e.g., Snacks vs Staples vs Edible Oil).
- Manual spreadsheet planning usually reacts after sales spikes, not before lead-time windows close.

### What BayesianRidge forecasting adds
- Probabilistic forecast output (`mean`, `lower_95`, `upper_95`) instead of single-point guesses.
- Recursive multi-step forecasting with lag features (`lag_1`, `lag_7`, `rolling_mean_7`, `festival_score`).
- Horizon confidence (high/medium/low) and sanity checks (`model_collapse`, `spike_anomaly`, `high_uncertainty`, `runaway_trend`) for safer operations.

### What Amazon Bedrock adds
- Converts model output + risk score + festival context into 3-sentence, actionable guidance for non-technical users.
- Reduces interpretation friction: users get “what to do, why, and by when,” not only charts.
- Enables auditable recommendation logs for operational review.

## 2. How AWS Services Are Used

| Service | Purpose | Why this service |
|---|---|---|
| AWS Amplify | Hosts React frontend and build pipeline | Fast static hosting + simple CI/CD for UI iteration |
| Amazon API Gateway | Public API entry point to backend | Managed routing, CORS, throttling, and budget protection |
| Amazon ECS Fargate | Runs FastAPI backend containers | No EC2 management, scalable API runtime for Python services |
| Amazon DynamoDB | Stores inventory, sales aggregates, forecast cache, recommendation logs | Low-latency, key-based access for dashboard and API workloads |
| Amazon S3 | Stores uploaded CSV files and trained model artifacts | Durable, low-cost object storage for data/model lifecycle |
| AWS Lambda | Event-driven ML retraining trigger on S3 CSV upload | Serverless, zero-cost-at-idle automation for hands-free model refresh |
| Amazon Bedrock | Generates AI insights from forecast + decision context | Managed GenAI integration without hosting foundation models |

## 3. What Value the AI Layer Adds

### Quantified operational value (current implementation)
- Festival-aware planning triggers risk-based action recommendations (`URGENT_ORDER`, `ORDER`, `MONITOR`, `MAINTAIN`) before stockouts.
- With configured lead times in this project (`5`, `7`, `10` days), the system can flag reorder risk up to **5–10 days before festival demand windows**.
- Forecast and decision caching reduce repeated portfolio load latency (batch endpoint + cache hit path).

### Bedrock insight example (sample output)
> “Snacks demand is at high risk of shortage before Diwali because forecasted sales are rising while current stock is below the reorder point. This is likely due to festival buying and a strong short-term demand trend in the next week. Place an urgent order for 1,400 units by October 28 to avoid stockouts during peak days.”

### Before vs after
- **Before (manual ordering):**
  - Spreadsheet checks
  - Static min/max thresholds
  - Late reaction to festival surge
- **After (AI-guided):**
  - Forecast-driven reorder point and safety stock
  - Festival-aware risk scoring and decision actions
  - Bedrock-generated plain-language action summaries

## 4. System Architecture

- Diagram: [docs/architecture.svg](/d:/Projects/MarketPulse_AI/MarketPulse-AI/docs/architecture.svg)
- Architecture details: [docs/ARCHITECTURE.md](/d:/Projects/MarketPulse_AI/MarketPulse-AI/docs/ARCHITECTURE.md)

### Data flow (brief)
1. User interacts with React UI hosted on Amplify.
2. UI calls backend APIs through API Gateway.
3. FastAPI on ECS runs forecasting, decision logic, and Bedrock insight generation.
4. DynamoDB stores operational records, caches, and logs.
5. S3 stores CSV uploads and model objects; models are loaded from S3 during forecasting.
6. S3 PUT events trigger a Lambda function that automatically retrains the relevant category model via API Gateway (event-driven ML retraining pipeline).
7. Bedrock returns natural-language recommendations shown in the dashboard.

## 5. Features List

| Feature | Description | AWS service(s) powering it |
|---|---|---|
| Portfolio Overview | Batch forecast for multiple categories, action summary, risk/gap analytics | ECS Fargate, API Gateway, DynamoDB |
| Category Intelligence | Per-category forecast, confidence tiers, Bedrock insight, decision breakdown | ECS Fargate, Bedrock, DynamoDB |
| Data Management | CSV upload flow, freshness indicators, model/recommendation operational views | S3, ECS Fargate, DynamoDB |
| Festival Intelligence | 90-day festival calendar, readiness table, impact cards | DynamoDB, ECS Fargate |
| Forecast API + Cache | `/forecast/{category}`, `/forecast/batch` with warning and staleness checks | ECS Fargate, DynamoDB |
| GenAI Insights API | `/insights/{category}`, `/insights/batch` with cache-aware logging | Bedrock, DynamoDB, ECS Fargate |
| Model Persistence | Save/load trained models per category | S3, ECS Fargate |
| Event-Driven ML Retraining | S3 upload auto-triggers model retrain per category via Lambda | S3, Lambda, API Gateway |

## 6. Local Setup Instructions

### Prerequisites
- Python 3.11+
- Node.js 18+
- Docker + Docker Compose (for containerized run)
- AWS credentials (for S3/Bedrock/Dynamo paths)

### Clone and environment setup
```bash
git clone <your-repo-url>
cd MarketPulse-AI
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate
pip install -r requirements.txt
```

### Backend (local)
```bash
set PYTHONPATH=src
uvicorn marketpulse.main:app --reload --port 8000
```

### Frontend (local)
```bash
cd frontend
npm install
npm run dev
```

### Docker Compose (recommended for quick full-stack run)
```bash
docker-compose up --build
```

## 7. Demo Script (for judges)

1. Open the app and confirm backend health banner is green.
2. Go to **Data Management** and upload a sales CSV.
3. Show upload summary: accepted/rejected rows, date range, categories, retrain impact.
4. Open **Portfolio Overview** and show batch forecast actions across categories.
5. Open **Category Intelligence** for `Snacks`:
   - forecast confidence segments,
   - decision detail,
   - Bedrock insight card.
6. Open **Festival Intelligence**:
   - 90-day festival view,
   - per-festival impact card,
   - readiness table (`READY / AT RISK / CRITICAL`).
7. Show recommendation history/audit trail view in **Data Management**.
8. Close with architecture slide using [docs/architecture.svg](/d:/Projects/MarketPulse_AI/MarketPulse-AI/docs/architecture.svg).

## What This System Does and Does Not Do

### Does
- Provides category-level demand forecasting and inventory recommendations.
- Uses festival context to adjust risk and safety-related decisions.
- Produces plain-language AI insights for operational action.
- Supports AWS-native deployment components for production-like architecture.

### Does not (current scope)
- Does not optimize pricing or promotions.
- Does not yet model store-level geography or hyperlocal events.
- Does not guarantee business outcomes without proper data quality and lead-time configuration.
- Some advanced operational endpoints may require environment-specific backend wiring depending on deployment mode.

## Additional Documentation

- [docs/API_INDEX.md](/d:/Projects/MarketPulse_AI/MarketPulse-AI/docs/API_INDEX.md)
- [docs/FORECAST_API.md](/d:/Projects/MarketPulse_AI/MarketPulse-AI/docs/FORECAST_API.md)
- [docs/MODEL_DIAGNOSTICS.md](/d:/Projects/MarketPulse_AI/MarketPulse-AI/docs/MODEL_DIAGNOSTICS.md)
- [docs/AWS_DEPLOYMENT.md](/d:/Projects/MarketPulse_AI/MarketPulse-AI/docs/AWS_DEPLOYMENT.md)
- [docs/ARCHITECTURE.md](/d:/Projects/MarketPulse_AI/MarketPulse-AI/docs/ARCHITECTURE.md)
