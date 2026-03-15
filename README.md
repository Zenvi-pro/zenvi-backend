# Zenvi Backend

FastAPI backend for the Zenvi AI video editor. Provides chat (agent-based), media analysis, search, indexing, video generation, and management APIs.

---

## Requirements

- Python 3.11+
- Node.js 18+ (for Remotion rendering services)
- `ffmpeg` on `$PATH` (for Manim scene concatenation and video processing)

---

## Setup

### 1. Clone and create a virtual environment

```bash
cd zenvi-backend
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
```

### 2. Install Python dependencies

```bash
# Core backend dependencies (required)
pip install -r requirements.txt

# Manim agent — educational/math animation videos (optional)
# Ubuntu/Debian: install system libs first
sudo apt-get install -y libcairo2-dev libpango1.0-dev pkg-config ffmpeg
pip install -r requirements-manim.txt
```

> To install everything at once:
> ```bash
> pip install $(ls requirements*.txt | sed 's/^/-r /' | tr '\n' ' ')
> ```

### 3. Configure environment variables

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

### 4. Run the backend

```bash
python main.py
# or
uvicorn main:app --host 0.0.0.0 --port 8500 --reload
```

API docs are available at `http://localhost:8500/docs`.

---

## Remotion Rendering Services

Zenvi uses two separate Remotion-based Node.js services for video rendering. Both are deployed independently and their public URLs are set via environment variables (`REMOTION_URL`, `REMOTION_PRODUCT_LAUNCH_URL`).

Both servers live in `remotion-servers/` inside this repo. Each is a self-contained Node.js project.

```
zenvi-backend/
└── remotion-servers/
    ├── full-service/          # Port 4500 — async job queue
    │   ├── server.js
    │   ├── package.json
    │   ├── remotion.config.js
    │   └── src/
    │       ├── index.ts
    │       ├── Root.tsx
    │       ├── RepoVideo.tsx   ← renders GitHub repo data
    │       └── SonarVideo.tsx  ← renders Perplexity research data
    └── product-launch/        # Port 3100 — synchronous render
        ├── server.js
        ├── package.json
        ├── remotion.config.js
        └── src/
            ├── index.ts
            ├── Root.tsx
            └── ProductLaunchVideo.tsx
```

### Service 1 — Full Rendering Service (`REMOTION_URL`, port 4500)

Handles repo and Sonar renders with async job queuing and polling. Renders are done in the background; clients poll `/status/:job_id` until `"completed"`, then download via `/download/:job_id`.

**Setup:**

```bash
cd remotion-servers/full-service
npm install
npm start          # http://localhost:4500
```

**API:**

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/health` | Health check |
| `POST` | `/api/v1/render` | Submit render job → `{ job_id }` |
| `GET` | `/api/v1/status/:job_id` | Poll → `{ status, progress, error? }` |
| `GET` | `/api/v1/download/:job_id` | Stream completed MP4 |

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

```json
{
  "type": "sonar",
  "research_data": { "topic": "...", "summary": "...", "keyPoints": [] },
  "style": "bold",
  "duration": 45
}
```

Styles: `"modern"` (default) · `"minimal"` · `"bold"`

Set in `.env`:
```env
REMOTION_URL=http://localhost:4500/api/v1
```

---

### Service 2 — Product Launch Service (`REMOTION_PRODUCT_LAUNCH_URL`, port 3100)

Synchronous render — the POST call blocks until the video is ready and returns a `video_url` immediately.

**Setup:**

```bash
cd remotion-servers/product-launch
npm install
npm start          # http://localhost:3100
```

**API:**

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Health check |
| `POST` | `/api/render` | Render synchronously → `{ status, video_url }` |
| `GET` | `/videos/:filename` | Download rendered MP4 |

**Render request body:**

```json
{
  "repo_data": {
    "owner": "acme",
    "repo": "my-project",
    "name": "My Project",
    "description": "...",
    "stars": 1200,
    "forks": 340,
    "language": "TypeScript",
    "topics": ["open-source"],
    "homepage": "https://example.com",
    "readme": "..."
  },
  "style": "modern",
  "duration": 30
}
```

The backend fetches GitHub data automatically before calling this endpoint, so `repo_data` is already populated.

Set in `.env`:
```env
REMOTION_PRODUCT_LAUNCH_URL=http://localhost:3100
```

---

### Compositions

| Composition | Service | Scenes |
|---|---|---|
| `RepoVideo` | full-service | Intro → Stats → Topics → CTA |
| `SonarVideo` | full-service | Title → Summary → Key Insights → Outro |
| `ProductLaunchVideo` | product-launch | Hero → Stats → Features → CTA |

Preview any composition locally with the Remotion Studio:

```bash
cd remotion-servers/full-service   # or product-launch
npx remotion studio src/index.ts
```

---

### Deploying Remotion Services

When deploying publicly, update `.env` with the live URLs:

```env
REMOTION_URL=https://remotion.your-domain.com/api/v1
REMOTION_PRODUCT_LAUNCH_URL=https://remotion-pl.your-domain.com
```

No other code changes are needed — the Python backend reads these at startup from `config.py`.

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
├── remotion-servers/
│   ├── full-service/    # Async rendering service (port 4500)
│   └── product-launch/  # Synchronous product-launch service (port 3100)
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
