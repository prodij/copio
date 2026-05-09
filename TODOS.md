# TODOS — Copio

Deferred work from /plan-ceo-review (2026-05-08) and /plan-eng-review (2026-05-08). Each item has phase, priority, and enough context for a future session to pick up cold.

## Phase 1.5 — Slack + email surfaces

### TODO: Slack bot (OAuth + slash command + DM + reactions)
**What**: Second OAuth flow, cross-surface memory bridge with web chat. Slack-native reaction emoji pipeline (more natural than custom web widget). Async response for diagnostics >2 min via Slack message + web link.
**Why**: CEOs live in Slack during the day; web chat alone forces context-switch. Slack reactions reduce eval-pipeline activation friction.
**Pros**: Wider reach; Slack reactions are native; cross-surface memory makes Copio feel persistent.
**Cons**: Second OAuth flow + identity reconciliation work; per-team install; webhook signing verification.
**Context**: Phase 1.1 ships web-only deliberately. This TODO unlocks once 5-10 paying customers use Phase 1.1 and ask for Slack.
**Effort**: human ~1 week / CC ~1.5 days
**Priority**: P1 (the third locked surface from /office-hours)
**Depends on**: Phase 1.1 stable; cross-surface memory schema designed

### TODO: Email fallback for long diagnostics
**What**: Transactional email (Resend or Postmark) sent if a diagnostic takes >2 min. Email contains link to web answer.
**Why**: CEO closes tab during long diagnostic, never sees the answer.
**Effort**: human ~half-day / CC ~30 min
**Priority**: P2
**Depends on**: Email provider chosen; deliverability + DMARC set up on copio.app domain

## Phase 1.6 — HITL write actions against Amazon

### TODO: HITL write infrastructure
**What**: Generic HITL approval flow — agent drafts an action (PO, listing edit, inventory adjustment), CEO sees diff, approves with 1 tap. Maps to Amazon Tier-2/3 policy compliance. **This is the foundation Phase 2.0 reuses for every other channel.**
**Why**: Earns the right to ship Phase 2.0 multichannel writes. Without this infra, every channel adapter rebuilds approval UI.
**Pros**: Compliance moat; converts diagnostic agent → operating agent.
**Cons**: New trust boundary — bugs here mean CEO accidentally approved wrong thing. Diff UX must be excellent.
**Effort**: human ~2 weeks / CC ~3-4 days
**Priority**: P1 (gates Phase 2.0)
**Depends on**: Phase 1.1 multi-tenant + audit log + persona

### TODO: Specific Amazon write tools
**What**: PO drafting, listing edit, inventory adjustment, A+ content edit (limited), pricing change (with safety bounds).
**Why**: Concrete first uses of HITL infra.
**Effort**: human ~1 week / CC ~1.5 days per write tool (5-7 tools)
**Priority**: P1
**Depends on**: HITL infrastructure

## Phase 2.0 — Multichannel from Amazon source-of-truth

### TODO: Catalog reader + normalized form
**What**: Read Amazon SP-API catalog → normalize to internal schema (one row per (tenant, ASIN, marketplace_id)).
**Effort**: human ~3-4 days / CC ~1 day
**Priority**: P1

### TODO: Hybrid mapping engine (deterministic + LLM-assisted + untranslatable)
**What**: Per /plan-eng-review locked architecture. Rule-based for 70% deterministic attributes (SKU, GTIN, price, weight, dimensions, brand). LLM-assisted for 30% ambiguous (category, free-text descriptions in voice, image set selection). Untranslatable detection + CEO escalation + persistent decision memory.
**Pros**: Wins on agent-native edge (incumbents do pure rule-based or none).
**Cons**: LLM portion adds cost per replication. Untranslatable detection needs ongoing rule maintenance.
**Effort**: human ~2-3 weeks / CC ~4-5 days
**Priority**: P1 (Phase 2.0 core)
**Depends on**: Catalog reader, HITL infrastructure

### TODO: Per-channel adapters (Walmart Item Setup, Shopify Admin API, eBay Inventory API)
**What**: Channel-specific listing-write APIs. Each adapter handles attribute schema, rate limits, error handling, idempotency keys.
**Effort**: human ~1-2 weeks per channel / CC ~2-3 days per channel
**Priority**: P1 (Phase 2.0 core)
**Depends on**: Hybrid mapping engine, HITL infrastructure

### TODO: Inventory sync across channels (velocity-aware buffers)
**What**: Real-time Amazon FBA + FBM event → per-channel buffer recalculated → Walmart/Shopify/eBay channel inventory updated <30s. Velocity-aware: hot SKUs get larger buffer; auto-increases under high-volume periods. Recycles prior Copio "never oversell" thesis.
**Effort**: human ~2 weeks / CC ~3 days
**Priority**: P1 (Phase 2.0 core)
**Depends on**: Per-channel adapters

### TODO: Order convergence (unified orderbook)
**What**: Cross-channel orders aggregated into one view. Daily written summary at 7am. Agent triage: which orders need attention, which are routine, which are surprising.
**Effort**: human ~1 week / CC ~1.5 days
**Priority**: P1 (Phase 2.0 core)

### TODO: Return/refund classification + drafted responses (HITL)
**What**: Agent reads return reason text across channels → classifies (defective / wrong-item / customer-changed-mind / sizing) → drafts response in honest persona voice → CEO approves with 1 tap → response posts via channel API.
**Effort**: human ~1 week / CC ~2 days
**Priority**: P2 (Phase 2.0 nice-to-have)
**Depends on**: Per-channel adapters; HITL infrastructure

### TODO: TikTok Shop integration (separate evaluation)
**What**: Fastest-growing channel. Has own agent rules + content moderation surface.
**Why**: TAM expansion if D2C-Amazon brands also sell TikTok.
**Effort**: human ~2 weeks / CC ~3-4 days
**Priority**: P2 — defer until Phase 2.0 stable + TikTok Shop is a buyer-pool requirement
**Depends on**: Phase 2.0 multichannel core; separate /plan-eng-review pass

## Phase 2.5 — Brief surface

### TODO: Morning brief
**What**: 7am written brief — what changed, what matters today, what to ignore. Ranks events. "3 things matter today; 1 you'd miss if I didn't say it."
**Why**: The "agent that already read everything overnight" framing in CEO plan vision.
**Effort**: human ~1 week / CC ~1.5 days
**Priority**: P1 (Phase 2.5 core)

### TODO: Smart silence
**What**: Agent recognizes when nothing material happened; brief is one sentence ("Nothing material today. I'll wake you for X.").
**Why**: Trust-builder. The agent that knows when to shut up is rare.
**Effort**: human ~3-4 days / CC ~1 day
**Priority**: P2

### TODO: Brief tone toggle
**What**: "Today, give it to me straight" / "Give it to me kind." Same data, different prose.
**Effort**: human ~2-3 days / CC ~half-day
**Priority**: P3

### TODO: Decision support
**What**: "Should I order 2k or 5k of SKU-A?" Agent runs the math + makes a recommendation with uncertainty markers.
**Effort**: human ~1 week / CC ~1.5 days
**Priority**: P1

### TODO: Voice memo input
**What**: CEO records voice memo while walking the dog; agent transcribes + threads into next brief.
**Effort**: human ~3-4 days / CC ~1 day
**Priority**: P3 (delight)

## Phase 3 — Full chief of staff

### TODO: Quote-the-CEO-back ("Last quarter you wrote: 'I refuse to discount'")
**Effort**: human ~3-4 days / CC ~1 day
**Priority**: P3 (delight)

### TODO: Weekly retro ("here's how that played out")
**What**: Weekly self-evaluation. Agent reviews prior week's recommendations vs actual outcomes. Compounding trust.
**Effort**: human ~1 week / CC ~1.5 days
**Priority**: P1 (Phase 3 core — drives the brand promise)

### TODO: Multi-seat per tenant
**What**: Invite team members; per-seat permissions; shared memory.
**Effort**: human ~1-2 weeks / CC ~2-3 days
**Priority**: P1 (Phase 3 — required for $799+ ARPU enterprise tier)

### TODO: AI agents drafting PRs (Loop 2 from feedback architecture)
**What**: Inngest scheduled workflow reads triage findings + eval failures + prod errors → categorizes → spawns appropriate sub-agent (CC: /investigate, /qa, /design-consultation) → drafts PR. Tightly scoped (prompts + tests + docs only). All DRAFT, all human-reviewed. Cost budget per finding. Eval rig itself prohibited from agent modification.
**Why**: Self-improving brand promise made real at the codebase level, not just prompt level.
**Effort**: human ~3 weeks / CC ~5 days
**Priority**: P1 (Phase 3 — flagship capability)
**Depends on**: Loop 1 production telemetry + triage agent (Phase 2.0+)

## Phase 4 — Memory as moat / iMessage / GDPR

### TODO: iMessage / SMS surface
**What**: Most intimate channel — "agent texts the CEO." Apple-aesthetic, on-brand for "love" framing. iMessage Business API or SMS fallback (Twilio).
**Effort**: human ~1-2 weeks / CC ~2-3 days
**Priority**: P2 (Phase 4 delight)

### TODO: GDPR / data retention / right-to-delete / export
**What**: Audit log immutable but tenant deletion + data export must exist for EU/CCPA compliance.
**Why**: Phase 4 enterprise tier serves EU brands; current MVP scopes US-only via ToS.
**Effort**: human ~2 weeks / CC ~3 days
**Priority**: P1 (Phase 4 — gates EU expansion)

### TODO: Calendar awareness
**What**: Agent learns when not to brief — launch week, weekend, kid's birthday. Connects to Google Calendar / Apple Calendar.
**Effort**: human ~1 week / CC ~1.5 days
**Priority**: P3 (delight)

## Cross-cutting / Always

### TODO: copio-webpage reframe (chief-of-staff narrative, bento aesthetic)
**What**: Current copy is for the prior "never oversell sync tool" product. Phase 1.1 needs new manifesto-style copy aligned with the diagnostic agent / chief-of-staff framing. Implementation: build the rev 2 bento layout per [DESIGN.md](DESIGN.md) and the approved mockup at `~/.gstack/projects/Copio/designs/landing-bento-20260508/variant-A.png`. Sample brief cells must use real Nutragroup ASINs and real numbers (per design review Pass 4 lock-in). Voice-driven copy required in every cell — template-feel ("Powerful AI insights", "Built for scale") is forbidden.
**Effort**: human ~3-5 days / CC ~1 day (writing-heavy, founder-led)
**Priority**: P1 (Phase 1.1 launch deliverable)

### TODO: `.deprecated/api/` audit before Phase 1.1 starts
**What**: Inspect prior `.deprecated/api/` for what lifts cleanly to Phase 1.1 multi-tenancy. If <70% lifts, fall back to single-tenant for Phase 1.1.
**Effort**: human ~half-day / CC ~30 min
**Priority**: P1 (gates Phase 1.1)

### TODO: Pricing validation experiment
**What**: $50 waitlist deposit on copio-webpage before Phase 1.1 ships. Or "annual prepay $1500 for first 12 months" alternative. Conversion target: 10%+.
**Effort**: human ~2-3 days / CC ~half-day (Stripe + landing page copy)
**Priority**: P1 (gates Phase 1.1 GTM)

### TODO: External CEO conversation process
**What**: Phase 1.1 gates on 3 external CEOs committing to pay. Need: outreach script, pitch deck, founding member offer, founder calendar block.
**Effort**: human ~2-3 days founder time
**Priority**: P1 (gates Phase 1.1 launch)

### TODO: Persona authoring sprint
**What**: Half-day founder-led sprint. Output: persona name, 5-page voice doc, 10 example diagnostics in voice. The persona name flows into: avatar initials, sidebar wordmark interaction, empty-state hero ("I read your Amazon overnight"), input field placeholder ("Ask [name] about your business..."), aria-labels ("Agent message from [name]:"), persona attribution row beside avatar on first message of session. Streaming abort copy ("(stopped — ask again or refine)") also gets persona-voiced here.
**Effort**: human 4-6 hours
**Priority**: P0 (gates Phase 1.1 — voice consistency eval depends on this existing)

### TODO: Wordmark / logo treatment
**What**: Currently DESIGN.md specifies plain "copio" in Inter Display 16-18px medium as the wordmark. Founder may want a custom letter-form, ligature, or simple glyph. Not a full logo system — just a wordmark treatment that owns the cool/Apple aesthetic without becoming AI-slop (no abstract gradient C, no orbital ring, no bezel-text). Also: favicon, OG image, email signature.
**Why**: Brand identity drift if implementer picks their own treatment.
**Effort**: human ~3-5 hours / CC ~30 min once founder lands on direction
**Priority**: P2 (Phase 1.1 — needed before public launch, not blocking dogfood)
**Depends on**: persona authoring sprint (informs the brand voice the wordmark expresses)

### TODO: Reaction confirmation feedback (non-👎 emojis)
**What**: 👎 has spec'd inline-input + "Thanks — logged" fade. The other emojis (👍 🎯 ❓ 🔁) currently just toggle highlight. Decide whether they should also show a tiny confirmation (e.g. micro-pulse + 1.5s "Logged" text in `--text-muted`). Or stay silent (selection IS the confirmation).
**Why**: If the eval-pipeline activation feels like a black box (click 👍, nothing happens), users stop reacting and the self-improving moat erodes.
**Effort**: human ~2 hours / CC ~20 min
**Priority**: P3 (Phase 1.1 polish — small UX choice)

### TODO: Cost-budget warning visual chrome
**What**: When tenant hits 80% of daily budget, agent surfaces inline message ("I'm approaching today's budget; should we be selective?"). DESIGN.md leaves the visual at "prose handles it." Optional: add a subtle warning pill at top of message in `--warning` (#FF9500) muted, OR a brief banner above input. Decide if visual chrome adds value or noise.
**Why**: Trust calibration — the user should understand the budget is real, not silent throttling.
**Effort**: human ~3 hours / CC ~30 min
**Priority**: P3 (Phase 1.1+)

### TODO: Persona avatar fill — solid vs tint
**What**: DESIGN.md specifies persona avatar as 32px circle in `--accent` (Apple blue) with white initials. Open call: solid full-saturation #007AFF, OR a 15% tint of accent (softer, blends into the page more). Implementer should test both during Phase 1.0 build, pick what reads "premium colleague" not "default UI chip."
**Effort**: human ~30 min visual review / CC ~5 min implementation
**Priority**: P3 (Phase 1.0 micro-decision)

### TODO: Citation popover content layout — implementation tuning
**What**: DESIGN.md specifies the popover layout in detail (source label + 1-line specifier + 4-row data preview + "Open in Amazon ↗" link). Real implementation may need tuning: how much data to preview before the popover gets too tall? Should the "Open in Amazon" link deep-link to Brand Analytics dashboard, Seller Central listing, or Amazon Reports console (depends on source)? What does the popover look like for an inferred-not-cited claim that has NO popover content?
**Why**: The popover IS the proof element. Implementation must not undersell it.
**Effort**: human ~4-6 hours / CC ~1-2 hours
**Priority**: P1 (Phase 1.1 — gates the "every claim cited" brand promise)
**Depends on**: SP-API integration; deep-link URLs by source type

### TODO: Onboarding wizard visual flow (LWA OAuth, first-run survey)
**What**: Separate design pass for the LWA OAuth flow + first-run survey + Slack integration UX (Phase 1.5). DESIGN.md defers all onboarding visuals.
**Why**: Onboarding is the highest-friction surface; deserves its own /plan-design-review pass once Phase 1.1 sign-up infra exists.
**Effort**: human ~1 day / CC ~3-4 hours
**Priority**: P1 (Phase 1.1 launch — gates external CEO commitments)

### TODO: Admin views design pass (eval rig dashboard, audit log, agent inner-monologue)
**What**: Internal-use admin surfaces. Eval rig dashboard (judge variance, golden set growth, regression alerts), audit log view with hash-chain integrity badge, "agent inner monologue" admin-only view. Separate design pass — internal use means lower polish bar but still needs to be navigable.
**Effort**: human ~1 day / CC ~3-4 hours
**Priority**: P2 (Phase 1.1+ internal tooling)

### TODO: Phase 1.6 HITL approval card UI design pass
**What**: When agent drafts a write action (PO, listing edit, inventory adjustment), the CEO sees a card showing the diff before approving with 1 tap. This is THE interaction where cards ARE the interaction (per DESIGN.md "cardless by default" exception). Card layout: source data → proposed change → diff visualization → approve/reject. Maps to Amazon T2/T3 compliance. Separate design pass when Phase 1.6 is in scope.
**Why**: This is the surface where bugs mean CEO approves the wrong thing. Diff UX must be excellent.
**Effort**: human ~2-3 days / CC ~1 day
**Priority**: P1 (Phase 1.6 core)
**Depends on**: HITL infrastructure built; specific Amazon write tools chosen

### TODO: Phase 2.0 catalog replication batch UI design pass
**What**: Listing replication batch surface — agent drafts 47 Walmart listings from Amazon catalog, CEO approves in batches of 10. Untranslatable-attribute escalation UX ("Can't replicate X to Walmart for SKU-A. Use closest equivalent / omit / override?"). Separate design pass when Phase 2.0 is in scope.
**Why**: Phase 2.0 wedge depends on this UX being radically better than incumbents' per-SKU forms.
**Effort**: human ~2-3 days / CC ~1 day
**Priority**: P1 (Phase 2.0 core)
**Depends on**: Phase 2.0 mapping engine + per-channel adapters in scope

### TODO: Worked-examples library (`docs/EXAMPLES.md`)
**What**: 3 worked examples of good vs bad diagnostics in honest voice. Used as runtime style anchor in Phase 1.0.
**Effort**: human 2-3 hours / CC 30 min
**Priority**: P0 (gates Phase 1.0 — runtime style anchor)
