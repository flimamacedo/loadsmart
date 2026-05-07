#!/bin/bash
set -euxo pipefail
dnf update -y
dnf install -y docker awscli
systemctl enable --now docker

REGION="${region}"
REGISTRY="${ecr_registry}"
REPO_URI="${repository_uri}"
TAG="${image_tag}"

cat >/etc/sre-api.env <<EOF
AWS_DEFAULT_REGION=$REGION
%{ if aws_access_key_id != "" ~}
AWS_ACCESS_KEY_ID=${aws_access_key_id}
AWS_SECRET_ACCESS_KEY=${aws_secret_key}
%{ endif ~}
ECR_REGISTRY=$REGISTRY
ECR_REPOSITORY_URI=$REPO_URI
IMAGE_TAG=$TAG
API_BASIC_USER_B64=${basic_user_b64}
API_BASIC_PASSWORD_B64=${basic_pass_b64}
EOF
chmod 600 /etc/sre-api.env

cat >/usr/local/bin/redeploy-sre-api.sh <<'EOS'
#!/bin/bash
set -euo pipefail
set -a
# shellcheck source=/dev/null
source /etc/sre-api.env
set +a
API_BASIC_USER="$(printf '%s' "$API_BASIC_USER_B64" | base64 -d)"
API_BASIC_PASSWORD="$(printf '%s' "$API_BASIC_PASSWORD_B64" | base64 -d)"
if [[ -n "$${DEPLOY_IMAGE_TAG:-}" ]]; then
  IMAGE_TAG="$DEPLOY_IMAGE_TAG"
fi
IMAGE="$${ECR_REPOSITORY_URI}:$${IMAGE_TAG}"
aws ecr get-login-password --region "$AWS_DEFAULT_REGION" | docker login --username AWS --password-stdin "$ECR_REGISTRY"
docker pull "$IMAGE"
docker rm -f sre-api 2>/dev/null || true
docker run -d --name sre-api --restart unless-stopped -p 80:8080 \
  -e AWS_DEFAULT_REGION="$AWS_DEFAULT_REGION" \
  -e AWS_ACCESS_KEY_ID="$${AWS_ACCESS_KEY_ID:-}" \
  -e AWS_SECRET_ACCESS_KEY="$${AWS_SECRET_ACCESS_KEY:-}" \
  -e API_BASIC_USER="$API_BASIC_USER" \
  -e API_BASIC_PASSWORD="$API_BASIC_PASSWORD" \
  "$IMAGE"
EOS
chmod 755 /usr/local/bin/redeploy-sre-api.sh

/usr/local/bin/redeploy-sre-api.sh
