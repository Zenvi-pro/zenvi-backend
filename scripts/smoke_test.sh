#!/usr/bin/env bash
set -euo pipefail

CONTAINERAPP_NAME="${1:-}"
RESOURCE_GROUP="${2:-}"

if [[ -z "${CONTAINERAPP_NAME}" || -z "${RESOURCE_GROUP}" ]]; then
  echo "Usage: $0 <containerAppName> <resourceGroup>" >&2
  exit 2
fi

FQDN="$(az containerapp show \
  --name "${CONTAINERAPP_NAME}" \
  --resource-group "${RESOURCE_GROUP}" \
  --query 'properties.configuration.ingress.fqdn' -o tsv)"

if [[ -z "${FQDN}" ]]; then
  echo "Could not determine Container Apps ingress FQDN from az output." >&2
  exit 1
fi

echo "Health check: http://${FQDN}/health"
curl -fsS "http://${FQDN}/health" >/dev/null

echo "Docs check: http://${FQDN}/docs"
curl -fsS "http://${FQDN}/docs" >/dev/null

echo "Smoke test OK."

