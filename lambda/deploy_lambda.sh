#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# deploy_lambda.sh — Package and deploy the auto_retrain_trigger Lambda
#
# Prerequisites:
#   - AWS CLI v2 configured with credentials
#   - Python 3.11 available locally (for pip install)
#
# Usage:
#   chmod +x deploy_lambda.sh
#   ./deploy_lambda.sh
# ---------------------------------------------------------------------------

set -euo pipefail

# ── Configuration ──────────────────────────────────────────────────────────
FUNCTION_NAME="auto_retrain_trigger"
RUNTIME="python3.11"
HANDLER="auto_retrain_trigger.handler"
MEMORY=128
TIMEOUT=30
REGION="ap-south-1"
S3_BUCKET="marketpulse-data-uploads"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${FUNCTION_NAME}-role"

# Replace with your actual API Gateway endpoint
API_BASE_URL="${API_BASE_URL:-https://your-api-gateway-id.execute-api.ap-south-1.amazonaws.com}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="${SCRIPT_DIR}/.build"
ZIP_FILE="${SCRIPT_DIR}/function.zip"

echo "══════════════════════════════════════════════════"
echo "  MarketPulse AI — Lambda Deployment"
echo "══════════════════════════════════════════════════"

# ── Step 1: Create IAM Role (if it doesn't exist) ─────────────────────────
echo ""
echo "▸ Step 1/6: Creating IAM execution role..."

TRUST_POLICY='{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "Service": "lambda.amazonaws.com" },
    "Action": "sts:AssumeRole"
  }]
}'

if ! aws iam get-role --role-name "${FUNCTION_NAME}-role" --region "$REGION" > /dev/null 2>&1; then
    aws iam create-role \
        --role-name "${FUNCTION_NAME}-role" \
        --assume-role-policy-document "$TRUST_POLICY" \
        --region "$REGION"

    # Attach basic Lambda execution policy (CloudWatch Logs)
    aws iam attach-role-policy \
        --role-name "${FUNCTION_NAME}-role" \
        --policy-arn "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole" \
        --region "$REGION"

    # Attach S3 read-only for the trigger bucket
    aws iam attach-role-policy \
        --role-name "${FUNCTION_NAME}-role" \
        --policy-arn "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess" \
        --region "$REGION"

    echo "  ✓ Role created. Waiting 10s for IAM propagation..."
    sleep 10
else
    echo "  ✓ Role already exists."
fi

# ── Step 2: Install dependencies ──────────────────────────────────────────
echo ""
echo "▸ Step 2/6: Installing dependencies..."

rm -rf "$BUILD_DIR" "$ZIP_FILE"
mkdir -p "$BUILD_DIR"

pip install \
    --target "$BUILD_DIR" \
    --requirement "${SCRIPT_DIR}/requirements.txt" \
    --quiet

# ── Step 3: Package the function ──────────────────────────────────────────
echo ""
echo "▸ Step 3/6: Packaging Lambda function..."

cp "${SCRIPT_DIR}/auto_retrain_trigger.py" "$BUILD_DIR/"

cd "$BUILD_DIR"
zip -r "$ZIP_FILE" . -x '*.pyc' '__pycache__/*' > /dev/null
cd "$SCRIPT_DIR"

SIZE_KB=$(( $(wc -c < "$ZIP_FILE") / 1024 ))
echo "  ✓ Package created: function.zip (${SIZE_KB} KB)"

# ── Step 4: Create or update the Lambda function ──────────────────────────
echo ""
echo "▸ Step 4/6: Deploying Lambda function..."

if aws lambda get-function --function-name "$FUNCTION_NAME" --region "$REGION" > /dev/null 2>&1; then
    # Update existing function
    aws lambda update-function-code \
        --function-name "$FUNCTION_NAME" \
        --zip-file "fileb://${ZIP_FILE}" \
        --region "$REGION" \
        --output text > /dev/null

    aws lambda update-function-configuration \
        --function-name "$FUNCTION_NAME" \
        --runtime "$RUNTIME" \
        --handler "$HANDLER" \
        --memory-size "$MEMORY" \
        --timeout "$TIMEOUT" \
        --environment "Variables={API_BASE_URL=${API_BASE_URL}}" \
        --region "$REGION" \
        --output text > /dev/null

    echo "  ✓ Function updated."
else
    # Create new function
    aws lambda create-function \
        --function-name "$FUNCTION_NAME" \
        --runtime "$RUNTIME" \
        --role "$ROLE_ARN" \
        --handler "$HANDLER" \
        --memory-size "$MEMORY" \
        --timeout "$TIMEOUT" \
        --zip-file "fileb://${ZIP_FILE}" \
        --environment "Variables={API_BASE_URL=${API_BASE_URL}}" \
        --region "$REGION" \
        --output text > /dev/null

    echo "  ✓ Function created."
fi

# ── Step 5: Grant S3 permission to invoke Lambda ─────────────────────────
echo ""
echo "▸ Step 5/6: Adding S3 trigger permission..."

aws lambda add-permission \
    --function-name "$FUNCTION_NAME" \
    --statement-id "s3-invoke-${FUNCTION_NAME}" \
    --action "lambda:InvokeFunction" \
    --principal "s3.amazonaws.com" \
    --source-arn "arn:aws:s3:::${S3_BUCKET}" \
    --source-account "$ACCOUNT_ID" \
    --region "$REGION" \
    2>/dev/null || echo "  (permission already exists — skipping)"

echo "  ✓ S3 invoke permission configured."

# ── Step 6: Configure S3 event notification ───────────────────────────────
echo ""
echo "▸ Step 6/6: Setting up S3 event notification..."

LAMBDA_ARN="arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:${FUNCTION_NAME}"

NOTIFICATION_CONFIG=$(cat <<EOF
{
  "LambdaFunctionConfigurations": [
    {
      "Id": "auto-retrain-on-csv-upload",
      "LambdaFunctionArn": "${LAMBDA_ARN}",
      "Events": ["s3:ObjectCreated:Put", "s3:ObjectCreated:CompleteMultipartUpload"],
      "Filter": {
        "Key": {
          "FilterRules": [
            { "Name": "suffix", "Value": ".csv" }
          ]
        }
      }
    }
  ]
}
EOF
)

aws s3api put-bucket-notification-configuration \
    --bucket "$S3_BUCKET" \
    --notification-configuration "$NOTIFICATION_CONFIG" \
    --region "$REGION"

echo "  ✓ S3 event notification configured."

# ── Cleanup build artifacts ───────────────────────────────────────────────
rm -rf "$BUILD_DIR"

# ── Summary ───────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════"
echo "  Deployment Complete"
echo "══════════════════════════════════════════════════"
echo ""
echo "  Function : ${FUNCTION_NAME}"
echo "  Runtime  : ${RUNTIME}"
echo "  Memory   : ${MEMORY} MB"
echo "  Timeout  : ${TIMEOUT}s"
echo "  Region   : ${REGION}"
echo "  Trigger  : s3://${S3_BUCKET}/*.csv"
echo "  API URL  : ${API_BASE_URL}"
echo ""
echo "  Test it:"
echo "    aws s3 cp test_snacks_sales.csv s3://${S3_BUCKET}/"
echo "    aws logs tail /aws/lambda/${FUNCTION_NAME} --follow"
echo ""
