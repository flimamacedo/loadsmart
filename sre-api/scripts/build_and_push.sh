#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

REGION="${AWS_REGION:-us-east-1}"
if [[ -z "${1:-}" ]]; then
  echo "Usage: $0 <tag>  (e.g. $0 v1.0.1  or  $0 \$(git rev-parse --short HEAD))" >&2
  exit 1
fi
TAG="$1"

if ! command -v terraform >/dev/null 2>&1; then
  echo "terraform is required" >&2
  exit 1
fi

TF_DIR="$ROOT/terraform"
REPO_URL="$(cd "$TF_DIR" && terraform output -raw ecr_repository_url)"
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"

aws ecr get-login-password --region "$REGION" \
  | docker login --username AWS --password-stdin "${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com"

docker buildx build --platform linux/amd64 -t "$REPO_URL:$TAG" --push .

echo "Pushed $REPO_URL:$TAG"
echo "Deploying via terraform apply..."

cd "$TF_DIR"
terraform apply -auto-approve -var="container_tag=$TAG"
