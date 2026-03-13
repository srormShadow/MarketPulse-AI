# MarketPulse AI Production SaaS Architecture

## 1. Target architecture

- Frontend: React SPA behind CloudFront.
- API: FastAPI app behind ALB, deployed on ECS Fargate.
- Database: Amazon RDS PostgreSQL for transactional multi-tenant data.
- Object storage: Amazon S3 for CSV uploads, model artifacts, and raw ingestion archives.
- Background jobs: Celery or Dramatiq workers on ECS, backed by SQS.
- Forecasting jobs: asynchronous worker tier with model training and sync orchestration.
- Secrets: AWS Secrets Manager and KMS.
- Monitoring: CloudWatch Logs, CloudWatch Metrics, X-Ray, alarms to SNS/PagerDuty.

## 2. Tenant isolation model

- Primary tenant boundary: `organization_id`.
- Every customer-facing record must carry `organization_id`.
- Store-specific records also carry `store_id`.
- UI and API queries must always scope by authenticated user organization unless role is admin.
- Demo data must never be shared with retailer tenants.

## 3. Recommended auth approach

- Primary login: email/password.
- Add Google OAuth as a secondary convenience option after core RBAC/session model is stable.
- Do not use mobile OTP as the primary login for this SaaS; it adds delivery complexity and weaker account recovery for B2B users.

### Auth implementation

- Password hashing: bcrypt/Argon2id.
- Session: short-lived JWT in `HttpOnly`, `SameSite=Strict`, `Secure` cookie.
- CSRF: double-submit token or custom CSRF header for mutating requests.
- Account protections:
  - rate limiting on login and registration
  - strong password policy
  - optional MFA for admin accounts
  - audit logging for login, logout, store connect, sync, and CSV upload

## 4. Shopify security

- Only authenticated users can initiate Shopify OAuth.
- OAuth `state` must be signed, time-bound, and include the target tenant context.
- HMAC verification is mandatory on callback and webhook endpoints.
- Access tokens must be encrypted at rest using KMS or application-level envelope encryption.
- Stores must be bound to the authenticated organization on install.
- Webhooks must be idempotent using Shopify webhook IDs.

## 5. Database design

Core tables:

- `organizations`
- `users`
- `stores`
- `data_sources`
- `products`
- `inventory_snapshots`
- `orders`
- `order_items`
- `sales_daily`
- `forecast_runs`
- `recommendations`
- `upload_events`

Key rules:

- Unique constraints should be tenant-scoped, for example `(organization_id, sku_id)`.
- Queries for retailer users must filter on `organization_id`.
- Admin-only views can be cross-tenant.

## 6. Shopify sync data flow

1. User authenticates.
2. User initiates Shopify OAuth.
3. Shopify callback stores encrypted access token and binds store to `organization_id`.
4. User triggers sync or webhook arrives.
5. Integration layer fetches products/orders from Shopify.
6. Raw payloads are archived to S3 for traceability.
7. Normalized records are upserted into tenant-scoped database tables.
8. Dashboard bootstrap endpoint returns live categories, inventory, and onboarding state.
9. Forecasting and recommendation endpoints read tenant-scoped normalized data.
10. UI refreshes from the database, not from static arrays or demo constants.

## 7. Empty-dashboard strategy

- Show onboarding cards, not fake analytics.
- Detect:
  - no connected stores
  - no catalog rows
  - no sales rows
- Present next actions:
  - connect Shopify
  - upload SKU catalog CSV
  - upload sales history CSV

## 8. AWS deployment blueprint

- CloudFront + WAF
- S3 static hosting origin or containerized frontend origin
- ALB -> ECS Fargate API service
- ECS Fargate worker service for Shopify sync, CSV processing, training, forecasting jobs
- RDS PostgreSQL Multi-AZ
- ElastiCache Redis for queues, caching, and rate limiting
- SQS for async job dispatch
- S3 for uploads and artifacts
- Secrets Manager for API secrets and Shopify credentials
- CloudWatch + X-Ray for observability

## 9. Security best practices

- Enforce HTTPS everywhere.
- Encrypt at rest for RDS, S3, backups, and secrets.
- Rotate JWT secrets and Shopify secrets.
- Add per-tenant query scoping tests.
- Add dependency and container image scanning in CI/CD.
- Add audit trails for privileged actions.
- Use least-privilege IAM roles for ECS tasks and workers.

## 10. Migration guidance

- Move from SQLite to PostgreSQL before production.
- Add Alembic migrations for tenant-scoped unique constraints and new `organization_id` columns.
- Remove or disable demo-seeding endpoints from retailer flows in production.
