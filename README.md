# Copio

**A diagnostic agent for the CEO of an Amazon-native e-commerce business.** Not a dashboard. Not a sync tool. A colleague who already read everything overnight and has a point of view.

Ask *"why is X happening with my Amazon business?"* and get a written causal narrative with linked evidence in under 90 seconds. Calibrated for honesty: every quantitative claim is cited, every inference is marked, uncertainty is quantified, and the agent says so when it does not know.

## Why this exists

CEOs of $1M to $50M Amazon brands spend hours per week stitching Brand Analytics, Search Query Performance, ad spend, 3PL data, and Slack threads into a story. The recurring "why did X happen this week?" question gets answered slowly, badly, or expensively. The data exists. The interpretation does not. Copio is the interpretation, written in honest prose with citations, on demand, by an agent that already read everything.

## What it does (Phase 1.0)

- **Diagnostic on demand.** Ask about a conversion drop, a returns spike, an ad spend question, a re-buy decision. The agent plans tool calls, pulls Orders / FBA inventory / Brand Analytics / SQP reports, decomposes the hypothesis, and writes the answer in prose with inline citations.
- **Honest voice.** Distinguishes "I can see X" facts (cited) from "I infer Y" judgments (italic muted). Quantifies uncertainty. Apologizes when wrong. Forbidden vocabulary is enforced at the prompt level and guarded by tests.
- **Real eval rig from day 1.** 20 founder-authored golden questions, manual judge runs (Opus 4.7 scoring Sonnet 4.6 output), cache-hit-rate verification on the 4-breakpoint prompt structure. Phase 1.1 graduates this to a nightly cron.

## What it will be (roadmap)

| Phase | Capability | Pricing |
|---|---|---|
| **1.0 (now)** | Single-tenant dogfood against Nutragroup. Diagnostic-only, web chat, polling pulls, unnamed honest voice. | internal |
| **1.1** | Multi-tenant, named persona, full eval rig with nightly regression + reaction pipeline + cross-tenant contamination probe, LWA OAuth onboarding. | $199 to $499/mo |
| **1.5** | Slack bot. Email fallback for long diagnostics. Cross-surface memory. | $199 to $499/mo |
| **1.6** | HITL write actions against Amazon (drafted PO / listing edit / inventory adjustment, CEO approves with one tap). Maps to Amazon's March 2026 AI Agent Policy. | $299 to $599/mo |
| **2.0** | Amazon as the source of truth. Listing replication to Walmart / Shopify / eBay. Inventory sync with velocity-aware buffers. Order convergence. Returns triage. The agent IS the dashboard. | $499 to $1199/mo |
| **2.5** | Morning brief. Smart silence. Decision support. Voice memo input. | $599 to $1299/mo |
| **3.0** | Full chief of staff. Quote-the-CEO-back. Weekly retro ("here's how that played out"). Multi-seat. | $799 to $1499/mo |

The 12-month vision is the AI chief of staff: it reads everything overnight, has a point of view, tells the truth, gets sharper every week, writes actual prose with citations and confidence levels, and learns when not to brief. The MVP is one capability of that vision.

## Architecture (Phase 1.0)

- **Backend**: FastAPI (Python 3.11), Postgres + pgvector (HNSW), Alembic, Anthropic SDK direct with 4 explicit prompt-cache breakpoints (voice → system → memory → tools), python-amazon-sp-api with named exception classes per the Error & Rescue Map (no `except Exception:` anywhere in `src/`), Inngest worker infrastructure, append-only audit log.
- **Frontend**: Next.js 15 App Router, Tailwind 4, self-hosted Inter Variable. Apple light-mode aesthetic per [DESIGN.md](DESIGN.md). Cardless prose, persona avatar (Apple-blue circle), citation pills with hover popovers, italic-muted "I infer" rendering, 5-emoji reaction widget (👍 👎 🎯 ❓ 🔁) with thumbs-down inline input, streaming sub-states (Planning → Fetching SP-API → Reasoning → tokens), Cmd+. abort, capability ready states, degraded-answer left rail.
- **Models**: Sonnet 4.6 default, Opus 4.7 fallback. Prompt caching gated at ≥80% hit rate by the eval rig.

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

# 4) Inngest dev server (separate terminal, optional. needed only for queued workers)
npx inngest-cli@latest dev -u http://localhost:8001/api/inngest

# 5) Verify the prompt-cache breakpoints actually cache (≥80% hit rate gate)
cd packages/api
uv run python scripts/verify_cache_hit_rate.py

# 6) Run the eval rig (manual run; Phase 1.1 graduates to a nightly cron)
uv run python scripts/run_eval.py
```

## Layout

```
copio/
├── packages/
│   ├── api/                 FastAPI backend, agent runtime, eval rig
│   │   ├── src/copio_api/
│   │   │   ├── agent/       Orchestrator, LLM client, tools, prompts, memory
│   │   │   ├── api/         Streaming chat, threads, reactions, LWA OAuth
│   │   │   ├── integrations/spapi/   python-amazon-sp-api wrapper + named exceptions
│   │   │   ├── db/          Postgres models + pgvector
│   │   │   └── workers/     Inngest functions
│   │   ├── alembic/         Migrations
│   │   ├── tests/           Unit + integration + eval golden set
│   │   └── scripts/         run_eval.py, verify_cache_hit_rate.py
│   └── web/                 Next.js 15 chat UI
│       └── src/
│           ├── app/chat/    Main chat page
│           ├── components/  Sidebar, Message, ReactionWidget, CitationPill, EmptyHero, …
│           ├── hooks/       useDiagnostic streaming hook
│           └── lib/         voiceParser (honest-voice renderer), api client
├── docs/EXAMPLES.md         3 worked diagnostics in honest voice (runtime style anchor)
├── obsidian/                Plan + design history (open as Obsidian vault root)
│   ├── plans/               CEO plan, design strategy, test plan
│   └── designs/             Approved + superseded mockups
├── DESIGN.md                Apple-aesthetic design system (rev 2)
├── TODOS.md                 Deferred Phase 1.1+ work
└── docker-compose.dev.yml
```

## What's locked

- **Scope**: Phase 1.0 is single-tenant against Nutragroup. No multi-tenancy / RLS / KMS / Slack / writes / multichannel until Phase 1.1+.
- **Stack**: Inngest + vanilla Postgres + pgvector + Anthropic SDK direct + python-amazon-sp-api + Vercel AI SDK `useChat`. See [`obsidian/plans/ceo-plan-2026-05-08.md`](obsidian/plans/ceo-plan-2026-05-08.md).
- **Voice**: Forbidden vocabulary enforced in `tests/unit/test_prompts.py`. Em dashes are forbidden. Sycophantic openers are forbidden. The full list is in [DESIGN.md](DESIGN.md) + [docs/EXAMPLES.md](docs/EXAMPLES.md).
- **Design**: Apple light-mode primary, Inter Display + Inter, Apple-blue `#007AFF` accent. Approved mockups under [`obsidian/designs/approved/`](obsidian/designs/). Anti-pattern blacklist in [DESIGN.md](DESIGN.md).
- **Compliance**: Phase 1.0 is read-only (Amazon Tier 1). Writes (Tier 2/3) gate on the Phase 1.6 HITL infrastructure.

## How "self-improving" actually works

Operationally defined as eval-guided prompt iteration with humans in the loop, not runtime learning. The 5-emoji reaction widget feeds the eval set: 👍 surfaces gold-standard candidates, 👎 flags for review, free-text "tell me what was wrong" captures tuning signal. Phase 1.1 wires this into a nightly regression run; Phase 1.0 captures the signal but the loop closes manually.

## Status

| Component | Phase 1.0 | Phase 1.1 |
|---|---|---|
| FastAPI + Postgres + pgvector | ✅ shipped |   |
| LWA OAuth + SP-API client (Orders / FBA / Reports) | ✅ shipped |   |
| Anthropic SDK with 4 explicit cache breakpoints | ✅ shipped |   |
| Diagnostic orchestrator with state machine | ✅ shipped |   |
| Streaming chat UI matching variant-B mockup | ✅ shipped |   |
| Citations + reactions + honest-voice rendering | ✅ shipped |   |
| Audit log (append-only) | ✅ shipped | hash chain + UPDATE/DELETE trigger |
| Eval rig (manual runner + cache verification) | ✅ shipped | nightly cron + reaction pipeline |
| 20 founder-authored golden questions | scaffold (5 templates) | expand to 60 |
| Honest-voice persona | unnamed placeholder | named, 5-page voice doc |
| Multi-tenancy | n/a | RLS + KMS + per-tenant prompts |
| Onboarding wizard | env-var bootstrap | LWA OAuth flow + first-run survey |
| Slack bot | n/a | deferred to Phase 1.5 |

## Provenance

Built by [James Han](https://github.com/prodij), 7-figure Amazon Nutra seller (Nutragroup). The full discussion that led to this implementation is preserved in [`obsidian/`](obsidian/). Open that folder as an Obsidian vault root and the wikilinks resolve.
