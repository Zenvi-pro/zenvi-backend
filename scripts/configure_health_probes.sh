#!/usr/bin/env bash
set -euo pipefail

CONTAINERAPP_NAME="${1:-}"
RESOURCE_GROUP="${2:-}"
PORT="${3:-8500}"
HEALTH_PATH="${4:-/health}"

if [[ -z "${CONTAINERAPP_NAME}" || -z "${RESOURCE_GROUP}" ]]; then
  echo "Usage: $0 <containerAppName> <resourceGroup> [port] [healthPath]" >&2
  exit 2
fi

echo "Configuring Container Apps health probes on ${CONTAINERAPP_NAME} (${RESOURCE_GROUP})"
echo "HTTP ${HEALTH_PATH} port=${PORT}"

# Note: Container Apps uses a probes array in template properties.
# If the container app already has probes configured, probe indices may differ.
# In that case, run the same command after resetting probes in portal or adjust indices.

az containerapp update \
  --name "${CONTAINERAPP_NAME}" \
  --resource-group "${RESOURCE_GROUP}" \
  --set \
    properties.template.containers[0].probes[0].type="Startup" \
    properties.template.containers[0].probes[0].httpGet.path="${HEALTH_PATH}" \
    properties.template.containers[0].probes[0].httpGet.port=${PORT} \
    properties.template.containers[0].probes[0].initialDelaySeconds=3 \
    properties.template.containers[0].probes[0].periodSeconds=5 \
    properties.template.containers[0].probes[1].type="Readiness" \
    properties.template.containers[0].probes[1].httpGet.path="${HEALTH_PATH}" \
    properties.template.containers[0].probes[1].httpGet.port=${PORT} \
    properties.template.containers[0].probes[1].initialDelaySeconds=5 \
    properties.template.containers[0].probes[1].periodSeconds=5 \
    properties.template.containers[0].probes[2].type="Liveness" \
    properties.template.containers[0].probes[2].httpGet.path="${HEALTH_PATH}" \
    properties.template.containers[0].probes[2].httpGet.port=${PORT} \
    properties.template.containers[0].probes[2].initialDelaySeconds=10 \
    properties.template.containers[0].probes[2].periodSeconds=10

echo "Health probe configuration update submitted."

