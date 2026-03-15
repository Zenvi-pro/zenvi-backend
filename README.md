# Zenvi Backend

FastAPI backend for the Zenvi AI video editor. Provides chat (agent-based), media analysis, search, indexing, video generation, and management APIs.

---

## Requirements

- Python 3.11+
- Node.js 18+ (for Remotion rendering services)
- `ffmpeg` on `$PATH` (for Manim scene concatenation)
- `manim` Python package (optional, for Manim agent)

---

## Setup

### 1. Clone and create a virtual environment

```bash
cd zenvi-backend
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment variables

Copy the example and fill in your keys:

```bash
cp .env.example .env   # or create .env manually
```

#### Full `.env` reference

```env
# Server
ZENVI_HOST=0.0.0.0
ZENVI_PORT=8500
ZENVI_DEBUG=false
ZENVI_CORS_ORIGINS=*

# LLM providers (at least one required for chat)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...
OLLAMA_BASE_URL=http://localhost:11434   # if using local Ollama

# Media indexing
TWELVELABS_API_KEY=...

# Video generation (Kling via Runware)
RUNWARE_API_KEY=...

# Research agent
PERPLEXITY_API_KEY=...

# Product launch / Remotion agents
GITHUB_TOKEN=ghp_...            # optional but recommended to avoid rate limits

# Music agent
SUNO_TOKEN=...

# Remotion rendering services (deployed URLs once public)
REMOTION_URL=http://localhost:4500/api/v1
REMOTION_PRODUCT_LAUNCH_URL=http://localhost:3100

# AWS (Rekognition for face detection)
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_DEFAULT_REGION=us-east-1

# Supabase (auth verification + usage tracking)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=...

# Agent tuning
ZENVI_DEFAULT_MODEL=openai/gpt-4o-mini
ZENVI_AGENT_MAX_ITERATIONS=15
ZENVI_AGENT_TIMEOUT=120
```

### 3. Run the backend

```bash
python main.py
# or
uvicorn main:app --host 0.0.0.0 --port 8500 --reload
```

API docs are available at `http://localhost:8500/docs`.

---

## Remotion Rendering Services

Zenvi uses two separate Remotion-based Node.js services for video rendering. Both are deployed independently and their public URLs are set via environment variables (`REMOTION_URL`, `REMOTION_PRODUCT_LAUNCH_URL`).

### Service 1 — Full Rendering Service (`REMOTION_URL`)

Handles full repo-based video rendering with job queuing and polling.

**Expected API contract:**

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/health` | Returns `200` when healthy |
| `POST` | `/api/v1/render` | Submit a render job → `{ job_id: string }` |
| `GET` | `/api/v1/status/:job_id` | Poll status → `{ status: "pending"\|"processing"\|"completed"\|"failed", error?: string }` |
| `GET` | `/api/v1/download/:job_id` | Stream the completed `.mp4` file |

**Render request body:**

```json
{
  "type": "repo",
  "repo_url": "https://github.com/owner/repo",
  "repo_data": { },
  "style": "modern",
  "duration": 30
}
```

or for Sonar/research data:

```json
{
  "type": "sonar",
  "research_data": { },
  "style": "modern",
  "duration": 30,
  "resolution": "1080p"
}
```

**Local development setup:**

```bash
mkdir remotion-service && cd remotion-service
npm init -y
npm install remotion @remotion/bundler @remotion/renderer express
# implement server.js according to the contract above
node server.js   # listens on port 4500
```

Set in `.env`:
```env
REMOTION_URL=http://localhost:4500/api/v1
```

---

### Service 2 — Product Launch Service (`REMOTION_PRODUCT_LAUNCH_URL`)

Simpler, synchronous rendering for product-launch promotional videos.

**Expected API contract:**

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Returns `200` when healthy |
| `POST` | `/api/render` | Render and return result synchronously |

**Render request body:**

```json
{
  "repo_data": { },
  "style": "modern",
  "duration": 30
}
```

**Render response:**

```json
{
  "status": "completed",
  "video_url": "/videos/output.mp4"
}
```

The backend will then `GET {base_url}{video_url}` to download the file.

**Local development setup:**

```bash
mkdir remotion-product-launch && cd remotion-product-launch
npm init -y
npm install remotion @remotion/bundler @remotion/renderer express
# implement server.js according to the contract above
node server.js   # listens on port 3100
```

Set in `.env`:
```env
REMOTION_PRODUCT_LAUNCH_URL=http://localhost:3100
```

---

### Deploying Remotion Services

When deploying publicly, update `.env` with the deployed service URLs:

```env
REMOTION_URL=https://remotion.your-domain.com/api/v1
REMOTION_PRODUCT_LAUNCH_URL=https://remotion-pl.your-domain.com
```

No other code changes are needed — the backend reads these at startup from `config.py`.

---

## Project Structure

```
zenvi-backend/
├── api/
│   ├── routes/          # FastAPI routers (chat, media, search, generation, …)
│   └── schemas.py       # Pydantic request/response models
├── core/
│   ├── agents/          # Root agent + sub-agents (video, manim, remotion, …)
│   ├── chat/            # Agent runner, session management, prompts
│   ├── directors/       # Director analysis agents
│   ├── generation/      # Runware/Kling video generation
│   ├── llm/             # LLM provider abstraction + usage tracker
│   ├── managers/        # Media / session managers
│   ├── media/           # Media processing utilities
│   ├── providers/       # External service clients (GitHub, Remotion, Suno, …)
│   └── tools/           # LangChain tool definitions per domain
├── config.py            # Pydantic settings (loaded from .env)
├── logger.py            # Logging setup
├── main.py              # FastAPI app factory + entry point
└── requirements.txt
```

---

## Key API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Backend health check |
| `POST` | `/api/v1/chat` | Synchronous chat (no tool delegation) |
| `WS` | `/api/v1/chat/ws` | Streaming chat with bidirectional tool execution |
| `GET` | `/api/v1/chat/history/{session_id}` | Conversation history |
| `POST` | `/api/v1/generation/video` | Direct video generation (Runware/Kling) |
| `POST` | `/api/v1/indexing/index` | Index a media file with TwelveLabs |
| `GET` | `/api/v1/models` | List available LLM models |

Full interactive docs: `http://localhost:8500/docs`
