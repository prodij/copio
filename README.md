# Copio

Diagnostic agent for Amazon-native CEOs. Phase 1.0 — single-tenant dogfood against Nutragroup.

## Stack

- **Backend** — FastAPI (Python 3.11), Postgres + pgvector, Anthropic SDK direct, python-amazon-sp-api, Inngest
- **Frontend** — Next.js 15 App Router, Tailwind, Vercel AI SDK `useChat`, self-hosted Inter Display + Inter
- **Models** — Sonnet 4.6 default, Opus 4.7 fallback, prompt caching with 4 explicit breakpoints

## Quickstart

```bash
# 1) Start Postgres
docker compose -f docker-compose.dev.yml up -d

# 2) Backend
cd packages/api
cp ../../.env.example ../../.env   # then fill in API keys
uv sync
uv run alembic upgrade head
uv run uvicorn copio_api.main:app --host 0.0.0.0 --port 8001 --reload

# 3) Frontend (separate terminal)
cd packages/web
pnpm install
pnpm dev   # http://localhost:3030

# 4) Inngest dev server (separate terminal — needed for queued workers)
npx inngest-cli@latest dev -u http://localhost:8001/api/inngest

# 5) Run the eval rig
cd packages/api
uv run python scripts/run_eval.py
```

## Layout

```
copio/
├── packages/
│   ├── api/        FastAPI backend, agent runtime, eval rig
│   └── web/        Next.js chat UI
├── docs/
│   └── EXAMPLES.md 3 worked diagnostic examples (founder-authored anchor)
├── DESIGN.md       Apple-aesthetic design system (rev 2)
├── TODOS.md        Deferred Phase 1.5+ work
└── docker-compose.dev.yml
```

## Phase 1.0 done definition

See [`/Users/james/.gstack/projects/Copio/ceo-plans/2026-05-08-copio-diagnostic-agent.md`](../.gstack/projects/Copio/ceo-plans/2026-05-08-copio-diagnostic-agent.md).
