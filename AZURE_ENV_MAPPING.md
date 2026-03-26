# Azure env/secret mapping (zenvi-backend)

This document maps the keys in [`zenvi-backend/.env.example`](./.env.example) to **Azure Container Apps** configuration.

## How Container Apps should be configured

- Put **sensitive values** (API keys, tokens) into **Container App Secrets**
- Put **non-sensitive values** into Container App **Environment variables**
- The backend reads values via `pydantic-settings` using environment variable names (see [`config.py`](./config.py))

## Suno key note

- Current `.env.example` uses `SUNO_TOKEN`
- Backend also supports legacy `SUNO_COOKIE` as a backward-compatible alias.

In Azure, prefer setting `SUNO_TOKEN`.

## Mapping table

### Server + runtime

- `ZENVI_HOST` — Env var
- `ZENVI_PORT` — Env var
- `ZENVI_DEBUG` — Env var
- `ZENVI_CORS_ORIGINS` — Env var

### LLM providers (secrets)

- `OPENAI_API_KEY` — Secret
- `ANTHROPIC_API_KEY` — Secret

- `OLLAMA_BASE_URL` — Env var (typically not secret)

- `GOOGLE_API_KEY` — Secret (currently optional)
- `GOOGLE_APPLICATION_CREDENTIALS` — Secret (optional)

- `AWS_ACCESS_KEY_ID` — Secret (optional)
- `AWS_SECRET_ACCESS_KEY` — Secret (optional)
- `AWS_DEFAULT_REGION` — Env var

- `TWELVELABS_API_KEY` — Secret
- `RUNWARE_API_KEY` — Secret
- `PERPLEXITY_API_KEY` — Secret
- `GITHUB_TOKEN` — Secret (optional but recommended)

### Music agent (secrets)

- `SUNO_TOKEN` — Secret
- (legacy) `SUNO_COOKIE` — Secret (optional; do not use unless needed)

### Optional GPU inference

- `NVIDIA_EDGE_URL` — Env var (optional; not a secret)

### Remotion services

- `REMOTION_URL` — Env var
- `REMOTION_PRODUCT_LAUNCH_URL` — Env var

### Agent config

- `ZENVI_DEFAULT_MODEL` — Env var
- `ZENVI_AGENT_MAX_ITERATIONS` — Env var
- `ZENVI_AGENT_TIMEOUT` — Env var

### Supabase

- `SUPABASE_URL` — Env var
- `SUPABASE_ANON_KEY` — Secret (public key, but treat as secretref for consistency)

### Stock video / vector db

- `PEXELS_API_KEY` — Secret
- `PINECONE_API_KEY` — Secret

## Example Azure CLI (pattern)

Assuming you already created:
- a Container Apps environment
- a Container App named `zenvi-backend`

### Set env vars

Use `--set-env-vars` for non-sensitive values, for example:

```bash
az containerapp update \
  --name zenvi-backend \
  --resource-group <rg> \
  --set-env-vars \
  ZENVI_HOST=0.0.0.0 \
  ZENVI_PORT=8500 \
  ZENVI_DEBUG=false \
  ZENVI_CORS_ORIGINS="https://your-frontend-domain"
```

### Set secrets and reference them

Use `az containerapp secret set` to create secrets, then reference them via `secretref`:

```bash
az containerapp secret set \
  --name zenvi-backend \
  --resource-group <rg> \
  --secrets OPENAI_API_KEY="<value>" \

az containerapp update \
  --name zenvi-backend \
  --resource-group <rg> \
  --set-env-vars OPENAI_API_KEY="secretref:OPENAI_API_KEY"
```

## Provider completeness check

Before production traffic, ensure at least one LLM provider key is configured:
- `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` or (if you wire it) other providers.

Also ensure Remotion URLs are set if you use video-rendering endpoints:
- `REMOTION_URL`
- `REMOTION_PRODUCT_LAUNCH_URL`

