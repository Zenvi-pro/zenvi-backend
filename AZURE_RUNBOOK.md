# Azure Container Apps runbook (zenvi-backend)

This runbook focuses on the operational steps to deploy `zenvi-backend` to Azure using **Azure Container Apps**.

## Assumptions

- You have an Azure subscription and permissions to create/update resources.
- You will deploy from GitHub `main` using the workflow in `.github/workflows/azure-container-apps-deploy.yml`.
- Environment variables are loaded by the backend using [`zenvi-backend/config.py`](./config.py).
- Health endpoint is `GET /health` (see [`zenvi-backend/main.py`](./main.py)).

## 0) Required Azure prerequisites

You will need:

- Resource Group name
- Container Apps Environment name
- Container App name (example: `zenvi-backend`)
- Azure Container Registry (ACR) login server (example: `myacr.azurecr.io`)
- A GitHub secret for Azure auth (example `AZURE_CREDENTIALS` containing a service principal JSON)

## 1) Container image

Build and push the image:

- The GitHub Actions workflow builds a Docker image from this folder using `Dockerfile`.
- The image is pushed to your ACR with a tag derived from the Git commit SHA.

## 2) Create secrets + environment variables in Container Apps

Follow [`AZURE_ENV_MAPPING.md`](./AZURE_ENV_MAPPING.md) for the exact key mapping.

Typical approach:

1. Create secrets for API keys/tokens:
   - Use `az containerapp secret set`
2. Reference secrets from env vars:
   - Use `az containerapp update --set-env-vars KEY=secretref:KEY`
3. Set non-sensitive config as plain env vars:
   - Use `az containerapp update --set-env-vars ZENVI_HOST=0.0.0.0 ZENVI_PORT=8500 ...`

## 3) Create or update the Container App

Recommended flags:

- Ingress: `external` (public API) if your frontend needs direct access
- Target port: `8500`
- Health probes: HTTP `GET /health`

### Health probes (HTTP)

Container Apps supports HTTP probes with success status codes in `[200, 399]`.

Example update pattern (adjust probe timings if your model startup takes longer):

```bash
az containerapp update \
  --name <containerAppName> \
  --resource-group <resourceGroup> \
  --set \
  properties.template.containers[0].probes[0].type="Readiness" \
  properties.template.containers[0].probes[0].httpGet.path="/health" \
  properties.template.containers[0].probes[0].httpGet.port=8500 \
  properties.template.containers[0].probes[1].type="Liveness" \
  properties.template.containers[0].probes[1].httpGet.path="/health" \
  properties.template.containers[0].probes[1].httpGet.port=8500
```

Note:
- Probe array indices depend on the existing revision configuration. If you’re creating the app fresh, it’s simpler to set probes at creation time.

## 4) Deployment verification

After deployment:

1. Confirm app is reachable:
   - Query the container app health endpoint (based on your ingress URL)
2. Confirm backend logs:
   - Container Apps “Logs” in the portal
3. Confirm expected startup:
   - Your endpoints should respond:
     - `GET /health`
     - `/api/v1/*` routes

### Quick health check (CLI)

```bash
FQDN=$(az containerapp show \
  --name <containerAppName> \
  --resource-group <resourceGroup> \
  --query "properties.configuration.ingress.fqdn" -o tsv)

curl -f "http://${FQDN}/health"
```

## 5) Rollback strategy

Container Apps keeps revisions. To rollback:

1. List revisions:

```bash
az containerapp revision list --name <containerAppName> --resource-group <resourceGroup> -o table
```

2. Enable multi-revision mode if you intend to traffic-split:

```bash
az containerapp revision set-mode --name <containerAppName> --resource-group <resourceGroup> --mode multiple
```

3. Activate an older revision:

```bash
az containerapp revision activate --revision <REVISION_NAME> --resource-group <resourceGroup> --name <containerAppName>
```

If you only need quick rollback without traffic-splitting, you can also re-deploy an older image tag.

### Canary / progressive delivery (optional)

If you want gradual traffic shifting:

1. Switch to multi-revision mode:

```bash
az containerapp revision set-mode \
  --name <containerAppName> \
  --resource-group <resourceGroup> \
  --mode multiple
```

2. Route a small % of traffic to the new revision label/name (see the Azure Container Apps traffic splitting docs):

```bash
az containerapp ingress traffic set \
  --name <containerAppName> \
  --resource-group <resourceGroup> \
  --revision-weight <REVISION_OLD>=90 <REVISION_NEW>=10
```

## 6) Operational checks

Common “it’s deployed but not working” checks:

- Env vars loaded:
  - Ensure `OPENAI_API_KEY` (or another provider key) is present in secrets.
- CORS:
  - Ensure `ZENVI_CORS_ORIGINS` includes your frontend origin.
- Remotion URLs:
  - Ensure `REMOTION_URL` and `REMOTION_PRODUCT_LAUNCH_URL` are reachable from the internet (if invoked).

