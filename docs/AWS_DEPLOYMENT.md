# MarketPulse AI — AWS Deployment Strategy (Hackathon Edition)

> **Budget**: $100 AWS Credits | **Goal**: Clean, impressive demo | **Priority**: Cost control + reliability

---

## TL;DR — Recommended Architecture

| Component         | AWS Service              | Est. Cost (3-day hackathon) |
| ----------------- | ------------------------ | --------------------------- |
| Backend (FastAPI) | EC2 `t3.small`           | ~$1.50                      |
| Frontend (React)  | S3 + CloudFront          | ~$0.10                      |
| Database          | SQLite on EC2 (keep it)  | $0.00                       |
| Domain/SSL        | CloudFront default + ACM | $0.00                       |
| **Total**         |                          | **~$1.60 – $3.00**          |

You'll use **less than 5%** of your $100 credits. The rest is safety margin.

---

## Why This Architecture?

### What I Analyzed

| Aspect              | Finding                                                     |
| ------------------- | ----------------------------------------------------------- |
| ML Model            | BayesianRidge (scikit-learn) — CPU-only, trains in ~50ms    |
| Database            | SQLite, ~53KB demo data — no need for RDS                   |
| External APIs       | **None** — fully self-contained                             |
| Frontend            | React SPA — static files, perfect for S3/CloudFront         |
| Backend             | FastAPI, stateless — single instance handles hackathon load |
| GPU Needed?         | **No** — standard CPU is more than enough                   |

### What I Rejected (and Why)

| Option                | Why Not                                                              |
| --------------------- | -------------------------------------------------------------------- |
| ECS/Fargate           | Overkill. NAT Gateway alone costs $1/day. Container orchestration adds complexity for no demo benefit |
| RDS PostgreSQL        | $0.50+/day minimum. Your SQLite DB is 53KB — RDS is burning money    |
| Elastic Beanstalk     | Spins up ALB ($0.60/day) + EC2. Hidden costs, less control           |
| Lambda + API Gateway  | FastAPI on Lambda needs Mangum adapter, cold starts hurt demo UX     |
| Lightsail             | Fixed $3.50/month is fine, but less flexibility than EC2             |
| EKS (Kubernetes)      | $2.40/day just for the control plane. Absolutely not for a hackathon |

---

## Step-by-Step Deployment

### Phase 1: Pre-Deployment Prep (Local Machine)

#### 1.1 — Build the Frontend for Production

```bash
cd frontend

# Create production environment file
echo "VITE_API_URL=http://YOUR_EC2_IP:8000" > .env.production

# Build static files
npm run build
```

This produces `frontend/dist/` — your entire frontend as static files.

#### 1.2 — Prepare the Backend

Create a `Dockerfile` in the project root:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY data/ ./data/
COPY run_backend.py .
COPY .env .

# Expose port
EXPOSE 8000

# Run with production settings
CMD ["uvicorn", "marketpulse.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

Create a `.dockerignore`:

```
__pycache__
*.pyc
.git
node_modules
frontend
tests
docs
venv
.venv
*.egg-info
```

---

### Phase 2: AWS Infrastructure Setup

#### 2.1 — Launch EC2 Instance

**Console Path**: EC2 → Launch Instance

| Setting           | Value                                           |
| ----------------- | ----------------------------------------------- |
| **Name**          | `marketpulse-backend`                           |
| **AMI**           | Amazon Linux 2023 (free tier eligible)           |
| **Instance type** | `t3.small` (2 vCPU, 2GB RAM) — $0.0208/hr      |
| **Key pair**      | Create new → `marketpulse-key` (download .pem)  |
| **Storage**       | 20 GB gp3 (default is fine)                     |
| **Security Group**| Create new: see below                           |

> **Why t3.small?** Your scikit-learn model + FastAPI + data processing fits comfortably in 2GB RAM. A `t3.micro` (1GB) might choke when training + serving simultaneously. The cost difference is ~$0.01/hr — not worth the risk during a live demo.

**Security Group Rules:**

| Type        | Port  | Source        | Purpose                |
| ----------- | ----- | ------------- | ---------------------- |
| SSH         | 22    | Your IP only  | Admin access           |
| HTTP        | 80    | 0.0.0.0/0     | (Optional) Redirect    |
| Custom TCP  | 8000  | 0.0.0.0/0     | FastAPI backend        |

#### 2.2 — Allocate an Elastic IP (Free While Attached)

```bash
# AWS CLI (or do this in the console)
aws ec2 allocate-address --domain vpc
aws ec2 associate-address --instance-id i-YOUR_INSTANCE --allocation-id eipalloc-XXXXX
```

> This gives you a stable public IP that survives instance restarts. **Free** as long as it's attached to a running instance.

#### 2.3 — SSH Into the Instance and Set Up

```bash
ssh -i marketpulse-key.pem ec2-user@YOUR_ELASTIC_IP
```

**Install Docker:**

```bash
sudo yum update -y
sudo yum install -y docker git
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker ec2-user

# Log out and back in for group change
exit
ssh -i marketpulse-key.pem ec2-user@YOUR_ELASTIC_IP
```

#### 2.4 — Deploy the Backend

**Option A — Docker (Recommended for Clean Demo)**

```bash
# Clone your repo
git clone https://github.com/YOUR_USERNAME/MarketPulse-AI.git
cd MarketPulse-AI

# Build and run
docker build -t marketpulse-backend .
docker run -d \
  --name marketpulse \
  -p 8000:8000 \
  -v $(pwd)/data/db:/app/data/db \
  --restart unless-stopped \
  marketpulse-backend
```

**Option B — Direct Python (Simpler, No Docker Overhead)**

```bash
# Install Python
sudo yum install -y python3.12 python3.12-pip

# Clone and setup
git clone https://github.com/YOUR_USERNAME/MarketPulse-AI.git
cd MarketPulse-AI
pip3.12 install -r requirements.txt

# Run with nohup (survives SSH disconnect)
nohup uvicorn marketpulse.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 2 \
  > /tmp/marketpulse.log 2>&1 &
```

**Verify Backend:**

```bash
curl http://localhost:8000/health
# Expected: {"status":"ok","timestamp":"..."}
```

#### 2.5 — Seed Demo Data

```bash
# Upload demo CSVs via the API
curl -X POST http://localhost:8000/upload_csv \
  -F "file=@data/demo_sku_master.csv"

curl -X POST http://localhost:8000/upload_csv \
  -F "file=@data/demo_sales_365.csv"

# Verify
curl http://localhost:8000/skus
curl http://localhost:8000/sales/count
```

---

### Phase 3: Frontend Deployment (S3 + CloudFront)

#### 3.1 — Create S3 Bucket

```bash
aws s3 mb s3://marketpulse-frontend-demo --region us-east-1
```

#### 3.2 — Upload Built Frontend

First, rebuild with the real backend URL:

```bash
# Local machine
cd frontend
echo "VITE_API_URL=http://YOUR_ELASTIC_IP:8000" > .env.production
npm run build

# Upload to S3
aws s3 sync dist/ s3://marketpulse-frontend-demo/ --delete
```

#### 3.3 — Create CloudFront Distribution

**Console Path**: CloudFront → Create Distribution

| Setting                 | Value                                     |
| ----------------------- | ----------------------------------------- |
| **Origin domain**       | `marketpulse-frontend-demo.s3.amazonaws.com` |
| **Origin access**       | Origin Access Control (OAC) — create new  |
| **Viewer protocol**     | Redirect HTTP to HTTPS                    |
| **Default root object** | `index.html`                              |
| **Price class**         | Use only North America and Europe (cheapest) |

**Important — SPA Routing Fix:**
Create a custom error response:
- Error code: `403` → Response page: `/index.html` → Response code: `200`
- Error code: `404` → Response page: `/index.html` → Response code: `200`

This ensures React Router works properly.

#### 3.4 — Update S3 Bucket Policy

After CloudFront creates the OAC, update the bucket policy (CloudFront will prompt you):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowCloudFrontServicePrincipal",
      "Effect": "Allow",
      "Principal": {
        "Service": "cloudfront.amazonaws.com"
      },
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::marketpulse-frontend-demo/*",
      "Condition": {
        "StringEquals": {
          "AWS:SourceArn": "arn:aws:cloudfront::YOUR_ACCOUNT_ID:distribution/YOUR_DIST_ID"
        }
      }
    }
  ]
}
```

Your frontend will be live at: `https://XXXXXX.cloudfront.net`

---

### Phase 4: Wire Everything Together

#### 4.1 — Update Backend CORS

Edit `src/marketpulse/main.py` — add your CloudFront URL to the CORS origins:

```python
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://XXXXXX.cloudfront.net",  # Your CloudFront URL
]
```

Rebuild/restart the backend after this change.

#### 4.2 — Final Verification Checklist

```bash
# Backend health
curl http://YOUR_ELASTIC_IP:8000/health

# API docs accessible
# Open: http://YOUR_ELASTIC_IP:8000/docs

# Frontend loads
# Open: https://XXXXXX.cloudfront.net

# Forecast works end-to-end
curl -X POST http://YOUR_ELASTIC_IP:8000/forecast/Snacks
```

---

## Cost Breakdown — Detailed

### For a 3-Day Hackathon

| Service            | Unit Cost          | Usage         | Total    |
| ------------------ | ------------------ | ------------- | -------- |
| EC2 t3.small       | $0.0208/hr         | 72 hrs        | $1.50    |
| EBS (20GB gp3)     | $0.08/GB/mo        | 20GB × 3 days | $0.16    |
| Elastic IP         | $0.00 (attached)   | —             | $0.00    |
| S3 Storage         | $0.023/GB/mo       | ~1MB          | $0.00    |
| S3 Requests        | $0.0004/1K PUT     | ~100 requests | $0.00    |
| CloudFront         | $0.085/GB transfer | ~100MB        | $0.01    |
| Data Transfer Out  | $0.09/GB           | ~1GB          | $0.09    |
| **TOTAL**          |                    |               | **~$1.76** |

### For a 7-Day Sprint (With Buffer)

| Scenario             | Estimated Cost |
| -------------------- | -------------- |
| Normal hackathon use | $3 – $5        |
| Left instance running 30 days by accident | ~$15 |
| Worst case (forgot to shut down everything for a month) | ~$25 |

> **You won't even come close to $100.** The biggest risk is forgetting to shut down resources after the hackathon.

---

## Cost Protection — Set Up IMMEDIATELY

### Budget Alert (Do This First!)

```bash
# AWS CLI — create a $10 budget alarm
aws budgets create-budget \
  --account-id YOUR_ACCOUNT_ID \
  --budget '{
    "BudgetName": "hackathon-guard",
    "BudgetLimit": {"Amount": "10", "Unit": "USD"},
    "TimeUnit": "MONTHLY",
    "BudgetType": "COST"
  }' \
  --notifications-with-subscribers '[{
    "Notification": {
      "NotificationType": "ACTUAL",
      "ComparisonOperator": "GREATER_THAN",
      "Threshold": 50,
      "ThresholdType": "PERCENTAGE"
    },
    "Subscribers": [{
      "SubscriptionType": "EMAIL",
      "Address": "your-email@example.com"
    }]
  }]'
```

Or in the console: **Billing → Budgets → Create Budget → $10 threshold → email alert at 50%, 80%, 100%**

### Post-Hackathon Cleanup Script

Save this and **run it after the event**:

```bash
#!/bin/bash
echo "=== MarketPulse Cleanup ==="

# Terminate EC2 instance
aws ec2 terminate-instances --instance-ids i-YOUR_INSTANCE_ID

# Release Elastic IP
aws ec2 release-address --allocation-id eipalloc-YOUR_ID

# Empty and delete S3 bucket
aws s3 rm s3://marketpulse-frontend-demo --recursive
aws s3 rb s3://marketpulse-frontend-demo

# Disable CloudFront distribution (then delete after it's disabled)
aws cloudfront get-distribution-config --id YOUR_DIST_ID > cf-config.json
# Edit cf-config.json: set "Enabled": false, then update
# Wait for status "Deployed", then delete

echo "=== Cleanup Complete ==="
```

---

## Demo Day Tips

### Before the Demo

1. **SSH in 30 minutes before** — verify everything is running
2. **Pre-warm the API** — hit `/forecast/Snacks` once so the model is cached
3. **Have demo data pre-loaded** — don't waste demo time on CSV uploads
4. **Open these tabs:**
   - Your frontend: `https://XXXXXX.cloudfront.net`
   - Swagger docs: `http://YOUR_IP:8000/docs` (backup if frontend has issues)
   - Architecture diagram (from this doc)

### If Something Breaks During Demo

| Problem                  | Quick Fix                                              |
| ------------------------ | ------------------------------------------------------ |
| Backend unreachable      | SSH in, `docker restart marketpulse` or restart uvicorn |
| Frontend shows blank     | Fall back to Swagger UI at `:8000/docs`                |
| Forecast returns error   | Check if demo data is loaded: `curl :8000/sales/count` |
| CORS error in browser    | Use Swagger UI as backup, fix CORS config after        |

### Impressive Demo Flow

1. **Show the live CloudFront URL** — "This is deployed on AWS right now"
2. **Upload a CSV live** — shows real-time data ingestion
3. **Run a forecast** — show the confidence intervals + inventory decision
4. **Switch categories** — show model adapts per category
5. **Show Swagger docs** — demonstrates API-first design
6. **Mention the architecture** — "React SPA on CloudFront, FastAPI on EC2, Bayesian Ridge ML — all under $2"

---

## Architecture Diagram

```
                    ┌──────────────────────────────────────────────────┐
                    │                   AWS Cloud                      │
                    │                                                  │
  Users ──HTTPS──▶  │  ┌─────────────┐     ┌──────────────────────┐   │
                    │  │ CloudFront   │     │  EC2 (t3.small)      │   │
                    │  │ (CDN)        │     │                      │   │
                    │  │   ┌───────┐  │     │  ┌────────────────┐  │   │
                    │  │   │ React │  │     │  │ FastAPI        │  │   │
                    │  │   │ SPA   │──┼─────┼─▶│ (uvicorn)      │  │   │
                    │  │   └───────┘  │ API │  │                │  │   │
                    │  │       ▲      │     │  │ ┌────────────┐ │  │   │
                    │  │       │      │     │  │ │ BayesianRidge│ │  │   │
                    │  └───────┼──────┘     │  │ │ ML Model   │ │  │   │
                    │          │            │  │ └────────────┘ │  │   │
                    │     ┌────┴────┐       │  │                │  │   │
                    │     │   S3    │       │  │ ┌────────────┐ │  │   │
                    │     │ Bucket  │       │  │ │  SQLite DB │ │  │   │
                    │     └─────────┘       │  │ └────────────┘ │  │   │
                    │                       │  └────────────────┘  │   │
                    │                       └──────────────────────┘   │
                    └──────────────────────────────────────────────────┘
```

---

## Alternative: Even Cheaper (If Credits Are Tight)

If you want to go **absolute minimum**, here's a single-instance approach:

### Everything on One EC2 t3.micro ($0.0104/hr = ~$0.75/3 days)

```bash
# Install Nginx on EC2 to serve frontend + proxy backend
sudo yum install -y nginx

# Nginx config: /etc/nginx/conf.d/marketpulse.conf
server {
    listen 80;

    # Serve React frontend
    location / {
        root /home/ec2-user/MarketPulse-AI/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # Proxy API requests to FastAPI
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Proxy non-prefixed API endpoints
    location ~ ^/(health|upload_csv|forecast|skus|sales|festivals|docs|openapi.json) {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

**Total cost: Under $1.** No S3, no CloudFront, just one box doing everything.

> **Trade-off**: No HTTPS (unless you add Let's Encrypt), no CDN caching. But for a hackathon demo where judges are in the same room? Perfectly fine.

---

## Summary

| Question                                    | Answer                           |
| ------------------------------------------- | -------------------------------- |
| Will I overspend $100?                      | **No.** Expect $2-5 total.       |
| Do I need RDS?                              | **No.** SQLite is fine for demo. |
| Do I need a GPU?                            | **No.** BayesianRidge is CPU.    |
| How long to deploy?                         | ~30-45 minutes first time.       |
| What if I forget to shut down?              | Budget alarm will catch it.      |
| Can this handle hackathon judge traffic?    | **Yes.** Easily.                 |
| Does this look professional for a demo?     | **Yes.** CloudFront HTTPS + clean API. |

**Set the budget alarm first. Deploy confidently. Crush the demo.**
