---
status: ACTIVE
type: design-history
date: 2026-05-08
tags: [designs, history, copio]
---

# Design rev history

Three rounds of `/plan-design-review` on 2026-05-08. Final approved direction is **rev 2** (Apple aesthetic). Rev 1 was Claude.ai-flavored (warm ochre, dark mode, serif italic) and explicitly superseded.

## ✅ Approved (rev 2 — implement against these)

> [!success] Locked
> The implementation in `packages/web/` calibrates against these mockups. Voice rules + token system live in [[../../DESIGN|DESIGN.md]].

### Chat UI — chat-apple-20260508 / Variant B

![[approved/chat-variant-B-APPROVED.png]]

Light mode primary, macOS-Sequoia-feel sidebar with "+ New diagnostic" button, persona avatar (initials in Apple-blue circle), Amazon-domain thread titles, prose paragraph with citation superscripts and italic-sans-muted uncertainty markers, 5-emoji reaction widget (👍 👎 🎯 ❓ 🔁), "Fetching SP-API…" streaming sub-state visible.

Other rev-2 chat variants (not selected, kept for reference):
- ![[approved/chat-variant-A.png]]
- ![[approved/chat-variant-C.png]]

Design review records: [chat-approved.json](approved/chat-approved.json), [chat-feedback.json](approved/chat-feedback.json)

### Landing — landing-bento-20260508 / Variant A

![[approved/landing-variant-A-APPROVED.png]]

Apple-aesthetic bento on light cool-gray page bg. Hero band with display headline *"The brief your CEO has been waiting for"* + Apple-blue "Get a brief" CTA. Three sample diagnostic cells (real Nutragroup ASINs + numbers, citation pills, italic uncertainty markers) as proof. "WHO COPIO IS FOR" + three differentiator cells (asymmetric, voice-driven). Founder line + pricing cell + minimal footer.

Other rev-2 landing variants (not selected, kept for reference):
- ![[approved/landing-variant-B.png]]
- ![[approved/landing-variant-C.png]]

Design review records: [landing-approved.json](approved/landing-approved.json), [landing-feedback.json](approved/landing-feedback.json)

## ❌ Superseded — do NOT implement against

> [!warning] Replaced
> Preserved here for context only. Implementing against any of these is a regression.

### Chat — rev 1 (chat-ui-20260508)

Dark mode + warm ochre + Tiempos serif italic. Replaced because the aesthetic landed too Claude.ai and undercut the "Apple quality, not a chatbot" brand promise.

- ![[superseded/chat-rev1-variant-A.png]]
- ![[superseded/chat-rev1-variant-B.png]]
- ![[superseded/chat-rev1-variant-C.png]]

### Landing — rev 1 (landing-page-20260508)

Original variants. Replaced for the same reason as chat rev 1.

- ![[superseded/landing-rev1-variant-A.png]]
- ![[superseded/landing-rev1-variant-B.png]]
- ![[superseded/landing-rev1-variant-C.png]]

### Landing — rev 1.5 (landing-page-20260508-v2)

Dark navy + ochre, intermediate iteration. Replaced; rev 2 landed on bento layout in pure Apple aesthetic.

- ![[superseded/landing-rev1v2-variant-A.png]]
- ![[superseded/landing-rev1v2-variant-B.png]]
- ![[superseded/landing-rev1v2-variant-C.png]]

## Anti-patterns (carried forward into [[../../DESIGN|DESIGN.md]])

The rev 1 → rev 2 jump locked these forbidden patterns:
- Purple/violet/indigo gradients
- Warm ochre / amber as brand accent
- Serif italic for uncertainty markers
- Dark-mode-primary surfaces (dark mode is a Phase 1.1 toggle, never the default)
- Generic placeholder content ("SKU-A", "$XYZ") — sample brief cells must use real Nutragroup ASINs
- Template-voice copy ("Powerful AI insights", "Built for scale")

Full anti-pattern list lives in [[../../DESIGN|DESIGN.md]].
