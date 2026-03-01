#!/usr/bin/env bash
set -euo pipefail

# Required env vars:
# AWS_REGION, AWS_ACCOUNT_ID, ECR_REPO_NAME, ECS_CLUSTER, ECS_SERVICE
# Optional:
# IMAGE_TAG (default: git SHA)

AWS_REGION="${AWS_REGION:?AWS_REGION is required}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:?AWS_ACCOUNT_ID is required}"
ECR_REPO_NAME="${ECR_REPO_NAME:?ECR_REPO_NAME is required}"
ECS_CLUSTER="${ECS_CLUSTER:?ECS_CLUSTER is required}"
ECS_SERVICE="${ECS_SERVICE:?ECS_SERVICE is required}"

IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD)}"
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
IMAGE_URI="${ECR_URI}/${ECR_REPO_NAME}:${IMAGE_TAG}"

echo "Ensuring ECR repository exists: ${ECR_REPO_NAME}"
if ! aws ecr describe-repositories --repository-names "${ECR_REPO_NAME}" --region "${AWS_REGION}" >/dev/null 2>&1; then
  aws ecr create-repository --repository-name "${ECR_REPO_NAME}" --region "${AWS_REGION}" >/dev/null
fi

echo "Logging into Amazon ECR"
aws ecr get-login-password --region "${AWS_REGION}" | docker login --username AWS --password-stdin "${ECR_URI}"

echo "Building Docker image"
docker build -t "${ECR_REPO_NAME}:${IMAGE_TAG}" .
docker tag "${ECR_REPO_NAME}:${IMAGE_TAG}" "${IMAGE_URI}"

echo "Pushing image to ECR: ${IMAGE_URI}"
docker push "${IMAGE_URI}"

TMP_TASK_DEF="$(mktemp)"
python - <<'PY' "${IMAGE_URI}" "${TMP_TASK_DEF}"
import json
import sys

image_uri = sys.argv[1]
output_path = sys.argv[2]

with open("ecs-task-definition.json", "r", encoding="utf-8") as f:
    task_def = json.load(f)

task_def["executionRoleArn"] = task_def["executionRoleArn"].replace("<AWS_ACCOUNT_ID>", image_uri.split(".")[0])
task_def["taskRoleArn"] = task_def["taskRoleArn"].replace("<AWS_ACCOUNT_ID>", image_uri.split(".")[0])
task_def["containerDefinitions"][0]["image"] = image_uri

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(task_def, f)
PY

echo "Registering new ECS task definition revision"
TASK_DEF_ARN="$(
  aws ecs register-task-definition \
    --cli-input-json "file://${TMP_TASK_DEF}" \
    --region "${AWS_REGION}" \
    --query 'taskDefinition.taskDefinitionArn' \
    --output text
)"

echo "Updating ECS service: ${ECS_SERVICE}"
aws ecs update-service \
  --cluster "${ECS_CLUSTER}" \
  --service "${ECS_SERVICE}" \
  --task-definition "${TASK_DEF_ARN}" \
  --force-new-deployment \
  --region "${AWS_REGION}" >/dev/null

rm -f "${TMP_TASK_DEF}"

echo "Deployment complete"
echo "Image: ${IMAGE_URI}"
echo "Task definition: ${TASK_DEF_ARN}"

