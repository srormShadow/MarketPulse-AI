# MarketPulse AI Architecture

## Overview
MarketPulse AI is deployed as an AWS-native, API-first retail intelligence platform:

- `AWS Amplify` hosts the React frontend.
- `Amazon API Gateway` provides a single secure API entry point.
- `Amazon ECS Fargate` runs the FastAPI backend.
- `Amazon DynamoDB` stores operational and decision data.
- `Amazon S3` stores CSV uploads and model artifacts.
- `Amazon Bedrock` generates plain-language AI insights.

Architecture diagram: [architecture.svg](/d:/Projects/MarketPulse_AI/MarketPulse-AI/docs/architecture.svg)

## Why Each AWS Service Was Chosen

### AWS Amplify
- Fast, managed frontend hosting with CI/CD support.
- Built for modern React/Vite workflows.
- Easy environment management for API base URLs.

### Amazon API Gateway
- Central ingress for all backend routes.
- CORS, throttling, and usage control for hackathon cost protection.
- Decouples frontend from internal ECS networking details.

### Amazon ECS Fargate (FastAPI backend)
- Serverless container runtime: no EC2 management overhead.
- Good fit for Python FastAPI APIs and bursty request patterns.
- Scales service replicas independently from frontend traffic.

### Amazon DynamoDB
- Low-latency key-value/document storage for:
  - sales
  - forecast cache
  - inventory
  - recommendation logs
- Predictable performance for read-heavy dashboards and write-heavy logs.
- Natural fit for category/time keyed access patterns.

### Amazon S3
- Durable object storage for:
  - uploaded CSV datasets
  - serialized model artifacts
- Cheap and simple persistence for training and inference lifecycle.
- Decouples model/data files from container filesystem state.

### Amazon Bedrock (Claude Sonnet)
- Managed foundation model access without custom model hosting.
- Generates actionable natural-language explanations on top of numeric forecasts.
- Adds a business-consumable decision layer for non-technical users.

## How Bedrock Adds Value (Hackathon Criteria)

Bedrock is not decorative; it addresses a core business gap:

- Forecast numbers alone do not tell store owners what to do.
- Bedrock converts forecast + risk + festival context into concise action steps.
- Insights are logged and cacheable for consistency and auditability.

Judging criteria alignment:
- **Why AI is required**: The GenAI layer translates technical demand signals into human action guidance with timing and risk framing.
- **How AWS GenAI is used**: FastAPI invokes `bedrock-runtime` to generate category and batch insights using Claude Sonnet.
- **What value AI adds**: Faster, clearer decisions for small retailers, especially during festival volatility windows.

## Data Flow Narrative (Plain English)

1. A user opens the dashboard in the browser.
2. The frontend is served by Amplify and calls API Gateway.
3. API Gateway routes requests to the FastAPI service running on ECS Fargate.
4. Backend services read/write inventory, sales, forecast cache, and logs in DynamoDB.
5. CSV uploads and trained model artifacts are stored in S3.
6. During forecasting, backend loads models from S3 (or retrains and re-saves).
7. For recommendations, backend sends forecast/decision context to Bedrock.
8. Bedrock returns a concise AI insight; backend returns this to the UI and logs it.
9. The user sees both numeric forecasts and natural-language actions in one workflow.
