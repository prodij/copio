---
marp: true
theme: default
paginate: true
style: |
  @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700;800&family=Raleway:wght@100;200;300;400&family=JetBrains+Mono:wght@300;400&display=swap');
  :root {
    --accent: #ff6b1a; --accent-soft: #ff6b1a14; --accent-line: #ff6b1a40;
    --dark: #000; --card: #0a0a0a; --border: #1a1a1a;
    --body: #9a9a9a; --label: #6a6a6a; --muted: #5a5a5a; --light: #fff;
    --green: #22c55e; --red: #ef4444; --yellow: #f5a623; --blue: #60a5fa;
  }
  section { background: var(--dark); color: var(--light); font-family: 'Raleway', sans-serif; font-weight: 200; padding: 52px 68px; font-size: 26px; line-height: 1.45; }
  h1 { font-family: 'Outfit'; font-weight: 800; font-size: 2.3em; color: var(--light); letter-spacing: -0.02em; line-height: 1.05; margin: 0 0 6px; }
  h2 { font-family: 'Raleway'; font-weight: 200; font-size: 1.05em; color: #888; margin: 0 0 18px; }
  h3 { font-family: 'Outfit'; font-weight: 600; font-size: 0.55em; color: var(--accent); text-transform: uppercase; letter-spacing: 0.22em; margin: 0 0 8px; }
  strong { color: var(--accent); font-weight: 400; }
  code { font-family: 'JetBrains Mono', monospace; font-weight: 300; font-size: 0.82em; background: #111; color: #ddd; padding: 1px 6px; border-radius: 4px; }
  section.lead { display: flex; flex-direction: column; justify-content: center; }
  section::after { font-family: 'Outfit'; font-size: 0.5em; color: #333; }
  .grid { display: grid; gap: 12px; }
  .card { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 14px 18px; position: relative; overflow: hidden; }
  .card .k { font-family: 'Outfit'; font-weight: 600; font-size: 0.62em; color: var(--label); text-transform: uppercase; letter-spacing: 0.14em; }
  .card .t { font-family: 'Outfit'; font-weight: 600; font-size: 0.82em; color: var(--light); margin: 2px 0 4px; }
  .card .b { font-size: 0.66em; color: var(--body); line-height: 1.45; }
  .bar { position: absolute; top: 0; left: 0; right: 0; height: 2px; background: linear-gradient(90deg, var(--accent), transparent); }
  .tag { font-family: 'Outfit'; font-weight: 600; font-size: 0.5em; letter-spacing: 0.12em; text-transform: uppercase; padding: 2px 8px; border-radius: 4px; display: inline-block; }
  .t-green { background: #22c55e14; color: var(--green); border: 1px solid #22c55e30; }
  .t-yellow { background: #f5a62314; color: var(--yellow); border: 1px solid #f5a62330; }
  .t-red { background: #ef444414; color: var(--red); border: 1px solid #ef444430; }
  .t-acc { background: var(--accent-soft); color: var(--accent); border: 1px solid var(--accent-line); }
  .row { display: flex; align-items: baseline; gap: 16px; padding: 9px 0; border-bottom: 1px solid #111; font-size: 0.7em; }
  .row .c1 { flex: 0 0 34%; color: var(--light); font-weight: 400; }
  .row .c2 { flex: 1; color: var(--body); }
  .term { background: #070707; border: 1px solid var(--border); border-radius: 10px; overflow: hidden; }
  .term .bar3 { display: flex; gap: 6px; padding: 9px 12px; border-bottom: 1px solid #111; }
  .term .bar3 span { width: 9px; height: 9px; border-radius: 50%; display: inline-block; }
  .term pre { margin: 0; padding: 14px 18px; background: transparent; font-family: 'JetBrains Mono', monospace; font-weight: 300; font-size: 0.56em; line-height: 1.55; color: #bbb; }
  .note { font-size: 0.62em; color: var(--label); margin-top: 14px; }
---

<!-- _class: lead -->
<!-- _paginate: false -->

### Copio · milestone 1 · 2026-10-31

# A SaaS boilerplate<br>you copy, not rebuild

## Sign-in, workspaces, billing and feature access, working on day one. Design and implementation plan.

<div style="display:flex; gap:10px; margin-top:26px;">
  <span class="tag t-acc">prodij/copio</span>
  <span class="tag t-green">spec approved</span>
  <span class="tag t-yellow">plan awaiting review</span>
  <span class="tag" style="color:#777; border:1px solid #222;">personal project · not NG / Skylit</span>
</div>

---

### Definition of done

# One test proves it

## In a freshly generated product, on your laptop, with Stripe in test mode:

<div style="display:flex; align-items:stretch; gap:10px; margin-top:22px;">
  <div class="card" style="flex:1;"><div class="bar"></div><div class="k">1</div><div class="t">Sign up</div><div class="b">Branded Zitadel login, self-registration</div></div>
  <div style="align-self:center; color:#333; font-size:1.2em;">→</div>
  <div class="card" style="flex:1;"><div class="bar"></div><div class="k">2</div><div class="t">Workspace</div><div class="b">A Zitadel organization + Lago customer</div></div>
  <div style="align-self:center; color:#333; font-size:1.2em;">→</div>
  <div class="card" style="flex:1;"><div class="bar"></div><div class="k">3</div><div class="t">Pay</div><div class="b">Stripe-hosted page, card <code>4242…</code></div></div>
  <div style="align-self:center; color:#333; font-size:1.2em;">→</div>
  <div class="card" style="flex:1; border-color:var(--accent-line);"><div class="bar"></div><div class="k">4</div><div class="t" style="color:var(--accent);">Feature on</div><div class="b"><code>premium_report</code> unlocks when the <strong>Lago webhook</strong> lands</div></div>
</div>

<div class="term" style="margin-top:26px; width:60%;">
  <div class="bar3"><span style="background:#ff5f57"></span><span style="background:#febc2e"></span><span style="background:#28c840"></span></div>
<pre>$ make env && make up && make bootstrap && make e2e
  ✓ sign up → workspace → pay → premium report   1 passed</pre>
</div>

<div class="note">Returning from Stripe proves nothing. Access changes only when Lago confirms the payment.</div>

---

### The pattern

# Boilerplate → intent → product

<svg viewBox="0 0 1140 330" width="100%" style="margin-top:6px;">
  <defs><marker id="a" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0,8 3,0 6" fill="#555"/></marker>
  <marker id="ao" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0,8 3,0 6" fill="#ff6b1a"/></marker></defs>
  <line x1="250" y1="60" x2="410" y2="60" stroke="#555" stroke-width="1.5" marker-end="url(#a)"/>
  <text x="330" y="48" fill="#777" font-size="13" font-family="Outfit" text-anchor="middle" letter-spacing="1.5">EXTRACT INTENT</text>
  <path d="M530,92 V150 Q530,160 540,160 H640 Q650,160 650,170 V212" fill="none" stroke="#ff6b1a" stroke-width="1.5" marker-end="url(#ao)"/>
  <text x="560" y="140" fill="#ff6b1a" font-size="13" font-family="Outfit" letter-spacing="1.5">IMPLEMENT FRESH</text>
  <line x1="250" y1="250" x2="560" y2="250" stroke="#555" stroke-width="1.5" marker-end="url(#a)"/>
  <text x="405" y="238" fill="#777" font-size="13" font-family="Outfit" text-anchor="middle" letter-spacing="1.5">COPIER COPY</text>
  <path d="M650,290 V312 Q650,320 640,320 H160 Q150,320 150,312 V290" fill="none" stroke="#444" stroke-width="1.2" stroke-dasharray="5,4" marker-end="url(#a)"/>
  <text x="405" y="312" fill="#666" font-size="12" font-family="Outfit" text-anchor="middle" letter-spacing="1.5">GENERIC FIXES FLOW BACK · copier update</text>
  <line x1="740" y1="250" x2="880" y2="250" stroke="#444" stroke-width="1.2" stroke-dasharray="5,4" marker-end="url(#a)"/>
  <text x="810" y="238" fill="#666" font-size="12" font-family="Outfit" text-anchor="middle" letter-spacing="1.5">REPEAT</text>
  <rect x="50" y="28" width="200" height="64" rx="8" fill="#0a0a0a" stroke="#333"/>
  <text x="150" y="56" fill="#fff" font-size="17" font-family="Outfit" font-weight="600" text-anchor="middle">Existing system</text>
  <text x="150" y="78" fill="#888" font-size="12" font-family="JetBrains Mono" text-anchor="middle">code · plans · tests</text>
  <rect x="410" y="28" width="240" height="64" rx="8" fill="#0a0a0a" stroke="#555"/>
  <text x="530" y="56" fill="#fff" font-size="17" font-family="Outfit" font-weight="600" text-anchor="middle">Intent notes</text>
  <text x="530" y="78" fill="#888" font-size="12" font-family="JetBrains Mono" text-anchor="middle">~/brain · rules · examples</text>
  <rect x="50" y="218" width="200" height="72" rx="8" fill="#0a0a0a" stroke="#888"/>
  <text x="150" y="250" fill="#fff" font-size="17" font-family="Outfit" font-weight="600" text-anchor="middle">Boilerplate</text>
  <text x="150" y="272" fill="#888" font-size="12" font-family="JetBrains Mono" text-anchor="middle">prodij/copio</text>
  <rect x="560" y="212" width="180" height="78" rx="8" fill="#ff6b1a12" stroke="#ff6b1a"/>
  <text x="650" y="246" fill="#fff" font-size="17" font-family="Outfit" font-weight="600" text-anchor="middle">Product</text>
  <text x="650" y="268" fill="#888" font-size="12" font-family="JetBrains Mono" text-anchor="middle">shell + logic</text>
  <rect x="880" y="218" width="200" height="64" rx="8" fill="none" stroke="#333" stroke-dasharray="5,4"/>
  <text x="980" y="248" fill="#bbb" font-size="17" font-family="Outfit" font-weight="600" text-anchor="middle">Next product</text>
  <text x="980" y="268" fill="#666" font-size="12" font-family="JetBrains Mono" text-anchor="middle">same steps</text>
</svg>

<div class="note">Business logic never moves as code. First product through the pattern: the Copio diagnostic agent, rebuilt from its own extracted intent.</div>

---

### Decisions · shape

# Independent and simple

<div class="row"><div class="c1"><span class="tag t-acc">D1</span>&nbsp; Each product stands alone</div><div class="c2">One repo, later one AWS account. No shared platform until duplication actually hurts.</div></div>
<div class="row"><div class="c1"><span class="tag t-acc">D2</span>&nbsp; One repo per product</div><div class="c2"><code>frontend/</code> <code>backend/</code> <code>jobs/</code> <code>infra/</code>: one PR per change, no copied API contract.</div></div>
<div class="row"><div class="c1"><span class="tag t-acc">D3</span>&nbsp; Folders ship on their own</div><div class="c2">Path-filtered CI; a frontend push checks and later deploys only the frontend.</div></div>
<div class="row"><div class="c1"><span class="tag t-acc">D8</span>&nbsp; Copier, not a GitHub template</div><div class="c2"><code>copier update</code> brings template fixes to existing products as a reviewable diff.</div></div>
<div class="row"><div class="c1"><span class="tag t-acc">D10</span>&nbsp; Local first</div><div class="c2">Milestone 1 is Docker Compose. AWS (personal account) is milestone 2.</div></div>
<div class="row" style="border:none;"><div class="c1"><span class="tag t-acc">D12</span>&nbsp; Written fresh</div><div class="c2">Same stack choices as NG, no code copied from NG or Skylit repos.</div></div>

---

### Decisions · building blocks

# Open source, unmodified

<div class="grid" style="grid-template-columns: 1fr 1fr 1fr; margin-top:14px;">
  <div class="card"><div class="bar"></div><div class="k">D4 · sign-in</div><div class="t">Zitadel per product</div><div class="b">Branded login pages and emails. Organizations = workspaces, invites built in.</div></div>
  <div class="card"><div class="bar"></div><div class="k">D5 · billing</div><div class="t">Lago + Stripe</div><div class="b">Run as stock images. No fork, so no upgrade or AGPL burden.</div></div>
  <div class="card"><div class="bar"></div><div class="k">D6 · pricing</div><div class="t">Tier + usage ready</div><div class="b">Launch one flat plan; usage events already flow to Lago, unpriced.</div></div>
  <div class="card"><div class="bar"></div><div class="k">D7 · scheduled work</div><div class="t">Lambda-shaped jobs</div><div class="b">Raw data to storage first, then processed. Replay without re-calling APIs.</div></div>
  <div class="card"><div class="bar"></div><div class="k">D9 · look</div><div class="t">One brand file</div><div class="b"><code>brand.yaml</code> drives app theme, Zitadel login and Lago invoices.</div></div>
  <div class="card"><div class="bar"></div><div class="k">D11 · stack</div><div class="t">React + FastAPI</div><div class="b">Vite, shadcn/ui on Base UI, Tailwind · SQLAlchemy, Alembic, Postgres.</div></div>
</div>

---

### Runtime

# One product, one account

<svg viewBox="0 0 1140 400" width="100%">
  <defs><marker id="r" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0,8 3,0 6" fill="#666"/></marker>
  <marker id="rp" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0,8 3,0 6" fill="#a78bfa"/></marker></defs>
  <rect x="200" y="20" width="700" height="350" rx="10" fill="#050505" stroke="#1c1c1c"/>
  <text x="216" y="40" fill="#444" font-size="11" font-family="Outfit" letter-spacing="2">ONE REPO · DOCKER COMPOSE NOW · AWS IN MILESTONE 2</text>
  <line x1="150" y1="90" x2="230" y2="90" stroke="#666" stroke-width="1.4" marker-end="url(#r)"/>
  <line x1="390" y1="90" x2="720" y2="90" stroke="#666" stroke-width="1.4" marker-end="url(#r)"/>
  <text x="555" y="80" fill="#777" font-size="12" font-family="Outfit" text-anchor="middle" letter-spacing="1.5">BRANDED LOGIN</text>
  <path d="M310,118 V200 Q310,208 318,208 H470" fill="none" stroke="#666" stroke-width="1.4" marker-end="url(#r)"/>
  <text x="320" y="165" fill="#777" font-size="12" font-family="Outfit" letter-spacing="1.5">API</text>
  <path d="M600,182 V140 Q600,132 608,132 H792 Q800,132 800,124 V118" fill="none" stroke="#666" stroke-width="1.4" marker-end="url(#r)"/>
  <text x="700" y="124" fill="#777" font-size="12" font-family="Outfit" text-anchor="middle" letter-spacing="1.5">ORGS</text>
  <path d="M630,220 H770 Q778,220 778,228 V300" fill="none" stroke="#666" stroke-width="1.4" marker-end="url(#r)"/>
  <text x="690" y="212" fill="#777" font-size="12" font-family="Outfit" text-anchor="middle" letter-spacing="1.5">SUBSCRIBE</text>
  <path d="M830,300 V206 Q830,198 822,198 H630" fill="none" stroke="#666" stroke-width="1.2" stroke-dasharray="5,4" marker-end="url(#r)"/>
  <text x="840" y="260" fill="#777" font-size="12" font-family="Outfit" letter-spacing="1.5">WEBHOOK</text>
  <line x1="880" y1="328" x2="960" y2="328" stroke="#a78bfa" stroke-width="1.4" marker-end="url(#rp)"/>
  <line x1="550" y1="246" x2="550" y2="300" stroke="#666" stroke-width="1.4" marker-end="url(#r)"/>
  <line x1="390" y1="328" x2="470" y2="328" stroke="#666" stroke-width="1.4" marker-end="url(#r)"/>
  <line x1="230" y1="328" x2="150" y2="328" stroke="#a78bfa" stroke-width="1.4" marker-end="url(#rp)"/>
  <text x="190" y="318" fill="#a78bfa" font-size="12" font-family="Outfit" text-anchor="middle" letter-spacing="1.5">PULL</text>
  <g font-family="Outfit" text-anchor="middle">
    <rect x="30" y="62" width="120" height="56" rx="8" fill="#111" stroke="#444"/><text x="90" y="90" fill="#fff" font-size="15" font-weight="600">Customers</text><text x="90" y="108" fill="#777" font-size="11" font-family="JetBrains Mono">seller teams</text>
    <rect x="230" y="62" width="160" height="56" rx="8" fill="#0a0a0a" stroke="#888"/><text x="310" y="90" fill="#fff" font-size="15" font-weight="600">Frontend</text><text x="310" y="108" fill="#777" font-size="11" font-family="JetBrains Mono">React SPA</text>
    <rect x="720" y="62" width="160" height="56" rx="8" fill="#0a0a0a" stroke="#888"/><text x="800" y="90" fill="#fff" font-size="15" font-weight="600">Zitadel</text><text x="800" y="108" fill="#777" font-size="11" font-family="JetBrains Mono">orgs = workspaces</text>
    <rect x="470" y="182" width="160" height="64" rx="8" fill="#ff6b1a12" stroke="#ff6b1a"/><text x="550" y="210" fill="#fff" font-size="15" font-weight="600">Backend</text><text x="550" y="230" fill="#999" font-size="11" font-family="JetBrains Mono">the only access check</text>
    <rect x="470" y="300" width="160" height="56" rx="8" fill="#111" stroke="#555"/><text x="550" y="328" fill="#fff" font-size="15" font-weight="600">Postgres</text><text x="550" y="346" fill="#777" font-size="11" font-family="JetBrains Mono">3 tables in the shell</text>
    <rect x="230" y="300" width="160" height="56" rx="8" fill="#0a0a0a" stroke="#888"/><text x="310" y="328" fill="#fff" font-size="15" font-weight="600">Jobs</text><text x="310" y="346" fill="#777" font-size="11" font-family="JetBrains Mono">raw → S3 first</text>
    <rect x="720" y="300" width="160" height="56" rx="8" fill="#0a0a0a" stroke="#888"/><text x="800" y="328" fill="#fff" font-size="15" font-weight="600">Lago</text><text x="800" y="346" fill="#777" font-size="11" font-family="JetBrains Mono">plans · invoices</text>
    <rect x="960" y="300" width="140" height="56" rx="8" fill="#111" stroke="#333"/><text x="1030" y="328" fill="#fff" font-size="15" font-weight="600">Stripe</text><text x="1030" y="346" fill="#777" font-size="11" font-family="JetBrains Mono">test mode</text>
    <rect x="30" y="300" width="120" height="56" rx="8" fill="#111" stroke="#333"/><text x="90" y="328" fill="#fff" font-size="15" font-weight="600">Data APIs</text><text x="90" y="346" fill="#777" font-size="11" font-family="JetBrains Mono">e.g. Amazon</text>
  </g>
</svg>

---

### Repo layout

# What a new product gets

<div style="display:flex; gap:22px; margin-top:10px;">
<div class="term" style="flex:1.25;">
  <div class="bar3"><span style="background:#ff5f57"></span><span style="background:#febc2e"></span><span style="background:#28c840"></span></div>
<pre>acme-reports/
├── frontend/   React · Vite · shadcn · typed client
├── backend/    FastAPI · auth · workspaces
│               billing · access · Alembic
├── jobs/       handlers · schedules.yaml
├── infra/      (milestone 2: Terraform)
├── brand/      brand.yaml · logo.svg
├── docker-compose.yml
├── Makefile    up · bootstrap · check · e2e
├── .env.example   names only, never values
└── CLAUDE.md + .claude/   agent rules + guard</pre>
</div>
<div style="flex:1;">
  <div class="card" style="margin-bottom:10px;"><div class="k">Copier asks</div><div class="b" style="margin-top:4px;">name · slug · domain · brand colours · font · starter price · interval</div></div>
  <div class="card" style="margin-bottom:10px;"><div class="k">Template self-test</div><div class="b" style="margin-top:4px;">CI generates a throwaway product, runs every check and the e2e on it.</div></div>
  <div class="card"><div class="k">Public repo</div><div class="b" style="margin-top:4px;">The self-test fails on anything that looks like a key.</div></div>
</div>
</div>

---

### Sign-in & workspaces

# Creating a workspace can't half-fail

<div style="display:flex; gap:28px; margin-top:12px;">
<div style="flex:1; border-left:1px solid #222; padding-left:20px;">
  <div style="margin-bottom:14px;"><span class="tag t-acc">1</span>&nbsp; <span style="font-size:0.72em;">Insert row, <code>status = creating</code></span></div>
  <div style="margin-bottom:14px;"><span class="tag t-acc">2</span>&nbsp; <span style="font-size:0.72em;">Zitadel organization → <code>zitadel_org_id</code></span></div>
  <div style="margin-bottom:14px;"><span class="tag t-acc">3</span>&nbsp; <span style="font-size:0.72em;">Project grant + caller as <code>owner</code></span></div>
  <div style="margin-bottom:14px;"><span class="tag t-acc">4</span>&nbsp; <span style="font-size:0.72em;">Lago customer (linked to Stripe)</span></div>
  <div><span class="tag t-green">5</span>&nbsp; <span style="font-size:0.72em;"><code>status = ready</code></span></div>
</div>
<div style="flex:1.1;">
  <div class="card" style="margin-bottom:10px;"><div class="bar"></div><div class="t">Each step is committed</div><div class="b">A retry resumes from the last finished step, never a second org or customer.</div></div>
  <div class="card" style="margin-bottom:10px;"><div class="t">Roles live in the token</div><div class="b">Zitadel puts <code>owner</code>/<code>member</code> per org in the JWT; the backend checks signature, issuer, audience.</div></div>
  <div class="card"><div class="t">Invites stay in Zitadel</div><div class="b">The backend keeps one workspace row, no member copy.</div></div>
</div>
</div>

---

### Billing

# Plans are code, payment gates access

<div class="grid" style="grid-template-columns: 1fr 1fr; margin-top:12px;">
  <div class="card"><div class="bar"></div><div class="k">plans.yaml</div><div class="b" style="margin-top:6px; font-family:'JetBrains Mono'; font-size:0.6em; color:#bbb; line-height:1.6;">- code: starter<br>&nbsp;&nbsp;amount_cents: 2900<br>&nbsp;&nbsp;interval: month<br>&nbsp;&nbsp;features:<br>&nbsp;&nbsp;&nbsp;&nbsp;premium_report: true<br>&nbsp;&nbsp;&nbsp;&nbsp;seats: 5</div><div class="b" style="margin-top:8px;"><code>make sync-plans</code> pushes to Lago. Reviewed in PRs.</div></div>
  <div class="card"><div class="k">Checkout</div>
    <div class="b" style="margin-top:6px;">
      <span class="tag t-acc">1</span> backend creates a Lago subscription with a <strong>payment activation rule</strong> (stays <code>incomplete</code>)<br><br>
      <span class="tag t-acc">2</span> Lago returns a Stripe-hosted checkout URL<br><br>
      <span class="tag t-acc">3</span> card paid → Lago sends <code>subscription.started</code><br><br>
      <span class="tag t-green">4</span> webhook verified, stored once, state → <code>active</code>
    </div>
  </div>
</div>

<div class="note">Webhooks: JWT RS256 signature, issuer = Lago's API URL, signed body must equal received body, deduplicated by <code>X-Lago-Unique-Key</code>.</div>

---

### Subscription states

# Every arrow is a Lago event

<svg viewBox="0 0 1140 250" width="100%" style="margin-top:20px;">
  <defs><marker id="s" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0,8 3,0 6" fill="#666"/></marker></defs>
  <circle cx="24" cy="120" r="7" fill="#fff"/>
  <line x1="32" y1="120" x2="60" y2="120" stroke="#666" stroke-width="1.4" marker-end="url(#s)"/>
  <line x1="200" y1="120" x2="300" y2="120" stroke="#666" stroke-width="1.4" marker-end="url(#s)"/>
  <text x="250" y="108" fill="#777" font-size="12" font-family="Outfit" text-anchor="middle" letter-spacing="1.2">CHECKOUT</text>
  <line x1="440" y1="120" x2="540" y2="120" stroke="#666" stroke-width="1.4" marker-end="url(#s)"/>
  <text x="490" y="108" fill="#777" font-size="12" font-family="Outfit" text-anchor="middle" letter-spacing="1.2">STARTED</text>
  <line x1="680" y1="120" x2="780" y2="120" stroke="#666" stroke-width="1.4" marker-end="url(#s)"/>
  <text x="730" y="108" fill="#777" font-size="12" font-family="Outfit" text-anchor="middle" letter-spacing="1.2">PAY FAILED</text>
  <line x1="920" y1="120" x2="980" y2="120" stroke="#666" stroke-width="1.4" marker-end="url(#s)"/>
  <path d="M850,92 V54 Q850,46 842,46 H618 Q610,46 610,54 V92" fill="none" stroke="#666" stroke-width="1.4" marker-end="url(#s)"/>
  <text x="730" y="38" fill="#777" font-size="12" font-family="Outfit" text-anchor="middle" letter-spacing="1.2">RETRY PAID</text>
  <path d="M610,148 V196 Q610,204 618,204 H1042 Q1050,204 1050,196 V148" fill="none" stroke="#666" stroke-width="1.4" marker-end="url(#s)"/>
  <text x="830" y="228" fill="#777" font-size="12" font-family="Outfit" text-anchor="middle" letter-spacing="1.2">CANCELED / TERMINATED</text>
  <g font-family="Outfit" text-anchor="middle">
    <rect x="60" y="92" width="140" height="56" rx="10" fill="#0a0a0a" stroke="#555"/><text x="130" y="126" fill="#fff" font-size="17" font-weight="600">No plan</text>
    <rect x="300" y="92" width="140" height="56" rx="10" fill="#0a0a0a" stroke="#555"/><text x="370" y="126" fill="#fff" font-size="17" font-weight="600">Pending</text>
    <rect x="540" y="92" width="140" height="56" rx="10" fill="#ff6b1a12" stroke="#ff6b1a"/><text x="610" y="118" fill="#fff" font-size="17" font-weight="600">Active</text><text x="610" y="138" fill="#22c55e" font-size="10" letter-spacing="1.5">ACCESS ON</text>
    <rect x="780" y="92" width="140" height="56" rx="10" fill="#0a0a0a" stroke="#555"/><text x="850" y="118" fill="#fff" font-size="17" font-weight="600">Past due</text><text x="850" y="138" fill="#f5a623" font-size="10" letter-spacing="1.5">ACCESS ON · GRACE</text>
    <rect x="980" y="92" width="140" height="56" rx="10" fill="#111" stroke="#333"/><text x="1050" y="126" fill="#888" font-size="17" font-weight="600">Canceled</text>
  </g>
</svg>

<div class="note">A 15-minute reconcile job asks Lago for each subscription and repairs any state a missed webhook left wrong.</div>

---

### Access

# One function decides

<div style="display:flex; gap:22px; margin-top:10px;">
<div class="term" style="flex:1.2;">
  <div class="bar3"><span style="background:#ff5f57"></span><span style="background:#febc2e"></span><span style="background:#28c840"></span></div>
<pre>@router.get("/demo/premium-report")
def premium_report(
    current = Depends(require_feature("premium_report")),
): ...
&#35; allowed  → state ∈ {active, past_due}
&#35;             and plan grants the feature
&#35; denied   → 402 "plan 'free' does not
&#35;             include premium_report"</pre>
</div>
<div style="flex:1;">
  <div class="card" style="margin-bottom:10px;"><div class="bar"></div><div class="t">50 combinations tested</div><div class="b">5 states × 3 plans (incl. none) × 3 features, table-driven.</div></div>
  <div class="card" style="margin-bottom:10px;"><div class="t"><code>GET /me/access</code></div><div class="b">Frontend shows/hides UI; the backend checks again every time.</div></div>
  <div class="card"><div class="t">Usage, unpriced</div><div class="b"><code>reports_generated</code> already flows to Lago.</div></div>
</div>
</div>

---

### Jobs · branding

# Scheduled work and one brand file

<div class="grid" style="grid-template-columns: 1fr 1fr; margin-top:12px;">
  <div class="card"><div class="bar"></div><div class="k">jobs/</div><div class="t">Raw first, then rows</div>
    <div class="b"><code>raw/&lt;source&gt;/&lt;workspace&gt;/yyyy/mm/dd/&lt;run&gt;</code> lands before parsing, so a parser fix replays from storage.<br><br>
    <code>ScopedDb</code> refuses any query without <code>:workspace_id</code>.<br><br>
    <code>schedules.yaml</code> runs locally now, becomes EventBridge later. Same handler code becomes a Lambda.</div></div>
  <div class="card"><div class="bar"></div><div class="k">brand/</div><div class="t"><code>make brand</code> writes three things</div>
    <div class="b">
      <span class="tag t-acc">app</span> <code>brand.css</code>: light + dark tokens for shadcn<br><br>
      <span class="tag t-acc">login</span> Zitadel label policy, logo, font<br><br>
      <span class="tag t-acc">invoice</span> Lago <code>legalName</code> + logo<br><br>
      Dark palette computed when not given.</div></div>
</div>

---

### Local stack

# Two commands to a running stack

<div class="grid" style="grid-template-columns: repeat(4, 1fr); margin-top:14px;">
  <div class="card"><div class="k">data</div><div class="b">Postgres (app · zitadel · lago)<br>Redis · MinIO</div></div>
  <div class="card"><div class="k">identity</div><div class="b">Zitadel API v4.20.0<br>Login UI v2</div></div>
  <div class="card"><div class="k">billing</div><div class="b">Lago v1.55.0: api, worker, clock, front, pdf</div></div>
  <div class="card"><div class="k">product</div><div class="b">backend · frontend · jobs scheduler · stripe-cli</div></div>
</div>

<div class="row" style="margin-top:18px;"><div class="c1">Bootstrap is safe to re-run</div><div class="c2">Each step checks before creating: project, roles, OIDC app, backend machine user, Stripe provider, webhook, metric.</div></div>
<div class="row"><div class="c1"><code>make env</code></div><div class="c2">Generates every local secret with <code>openssl</code>; you paste only two Stripe <strong>test</strong> keys.</div></div>
<div class="row" style="border:none;"><div class="c1"><code>make doctor</code></div><div class="c2">Lists stuck workspaces, stale pending subscriptions, unprocessed webhooks.</div></div>

---

### Failure handling

# Never pretend it worked

<div class="row"><div class="c1">Zitadel or Lago down</div><div class="c2"><span class="tag t-red">503</span>&nbsp; names the dependency; nothing reported as created</div></div>
<div class="row"><div class="c1">Workspace creation interrupted</div><div class="c2"><span class="tag t-yellow">resume</span>&nbsp; from the recorded step on retry</div></div>
<div class="row"><div class="c1">Bad webhook signature</div><div class="c2"><span class="tag t-red">400</span>&nbsp; logged, no state change</div></div>
<div class="row"><div class="c1">Duplicate webhook</div><div class="c2"><span class="tag t-green">200</span>&nbsp; acknowledged and ignored</div></div>
<div class="row"><div class="c1">Missed or late webhook</div><div class="c2"><span class="tag t-yellow">reconcile</span>&nbsp; fixed within 15 minutes</div></div>
<div class="row" style="border:none;"><div class="c1">Frontend missing data</div><div class="c2">skeleton · status + message · "Unavailable", <strong>never 0</strong></div></div>

---

### Testing & agent guardrails

# Built to be worked on by agents

<div class="grid" style="grid-template-columns: 1.1fr 0.9fr; margin-top:12px;">
  <div>
    <div class="row"><div class="c1">Backend</div><div class="c2">pytest; Zitadel/Lago faked at HTTP with respx</div></div>
    <div class="row"><div class="c1">Isolation</div><div class="c2">every route authenticated; no reach into another workspace</div></div>
    <div class="row"><div class="c1">Frontend</div><div class="c2">Vitest + Testing Library; raw <code>fetch</code> is a lint error</div></div>
    <div class="row"><div class="c1">End to end</div><div class="c2">Playwright, real containers, Stripe test mode, nightly</div></div>
    <div class="row" style="border:none;"><div class="c1">Template</div><div class="c2">generate → lint → typecheck → test → e2e</div></div>
  </div>
  <div class="card"><div class="bar"></div><div class="k">guard hook blocks</div>
    <div class="b" style="line-height:1.9;">reading <code>.env</code> / bootstrap tokens<br>any <code>sk_live_</code> key<br>pushing to <code>main</code><br>force pushes</div>
    <div class="b" style="margin-top:8px;">The hook has its own tests.</div></div>
</div>

---

### Implementation plan · 13 tasks

# Test-first, in dependency order

<div class="grid" style="grid-template-columns: repeat(4, 1fr); gap:9px; margin-top:8px;">
  <div class="card"><div class="k">1</div><div class="b">Archive tag, template skeleton, secret scan</div></div>
  <div class="card"><div class="k">2</div><div class="b">Backend foundation, test-mode-only Stripe</div></div>
  <div class="card"><div class="k">3</div><div class="b">Zitadel token → Principal</div></div>
  <div class="card"><div class="k">4</div><div class="b">Clients + resumable workspaces</div></div>
  <div class="card"><div class="k">5</div><div class="b">Plans as code + checkout</div></div>
  <div class="card"><div class="k">6</div><div class="b">Webhooks + state machine</div></div>
  <div class="card"><div class="k">7</div><div class="b"><code>require_feature</code>, usage, premium demo</div></div>
  <div class="card"><div class="k">8</div><div class="b">Jobs: raw store, scoped db, reconcile</div></div>
  <div class="card"><div class="k">9</div><div class="b">Frontend foundation + states</div></div>
  <div class="card"><div class="k">10</div><div class="b">Sign-in + pages</div></div>
  <div class="card"><div class="k">11</div><div class="b">Branding generator</div></div>
  <div class="card"><div class="k">12</div><div class="b">Compose, bootstrap, doctor</div></div>
  <div class="card" style="grid-column: span 4; border-color:var(--accent-line);"><div class="bar"></div><div class="k" style="color:var(--accent);">13 · done when this passes</div><div class="b">Guard hook, isolation test, path-filtered CI, and the sign-up → premium end-to-end test</div></div>
</div>

<div class="note">Every task: failing test → see it fail → implement → pass → commit. Work happens in <code>.dev/acme</code>, re-rendered from <code>template/</code> by <code>make dev</code>.</div>

---

### Review focus

# Five things most likely to bite

<div class="row"><div class="c1"><span class="tag t-red">1</span>&nbsp; Webhooks twice or out of order</div><div class="c2">state ends correct; each event applies once</div></div>
<div class="row"><div class="c1"><span class="tag t-red">2</span>&nbsp; Double-click "create workspace"</div><div class="c2">returns the existing one; one org, one customer</div></div>
<div class="row"><div class="c1"><span class="tag t-red">3</span>&nbsp; Token for an unknown org</div><div class="c2"><code>403</code>, never another workspace's data</div></div>
<div class="row"><div class="c1"><span class="tag t-red">4</span>&nbsp; Dependency dies mid-request</div><div class="c2"><code>503</code> naming it; retry resumes cleanly</div></div>
<div class="row" style="border:none;"><div class="c1"><span class="tag t-red">5</span>&nbsp; Plan removed while in use</div><div class="c2"><code>402 unknown plan</code>, not a crash</div></div>

<div class="note">Each one has a named test in the task that owns the code.</div>

---

### Checked against upstream · 2026-10-31

# What the research changed

<div class="grid" style="grid-template-columns: 1fr 1fr; margin-top:12px;">
  <div class="card"><div class="bar"></div><div class="t">Payment-gated subscriptions</div><div class="b">Lago now holds a subscription <code>incomplete</code> until the first payment, with webhooks per step: our states map directly.</div></div>
  <div class="card"><div class="bar"></div><div class="t">Webhook issuer</div><div class="b">Self-hosted Lago signs with <code>iss = LAGO_API_URL</code>, not api.getlago.com.</div></div>
  <div class="card"><div class="bar"></div><div class="t">Stripe can't reach localhost</div><div class="b">Bootstrap gives Lago the Stripe CLI's signing secret; <code>stripe listen</code> forwards events.</div></div>
  <div class="card"><div class="bar"></div><div class="t">Pinned versions</div><div class="b">Zitadel v4.20.0 · Lago v1.55.0 · Copier 9.19.1 · Stripe CLI 1.55.6</div></div>
</div>

---

### What's next

# Four pieces, two can start now

<div class="grid" style="grid-template-columns: repeat(4, 1fr); margin-top:12px;">
  <div class="card"><div class="bar"></div><div class="k">0 · now</div><div class="t">Archive + extract</div><div class="b">Tag old Copio, write its intent into <code>~/brain</code></div></div>
  <div class="card" style="border-color:var(--accent-line);"><div class="bar"></div><div class="k" style="color:var(--accent);">1 · now</div><div class="t">This plan</div><div class="b">Boilerplate milestone 1, local</div></div>
  <div class="card"><div class="k">2 · after 1</div><div class="t">AWS</div><div class="b">Terraform for a personal account</div></div>
  <div class="card"><div class="k">3 · after 0 + 1</div><div class="t">Copio agent</div><div class="b">First product through the pattern</div></div>
</div>

<div style="display:flex; gap:22px; margin-top:22px;">
  <div style="flex:1;"><h3 style="color:var(--label);">Not in milestone 1</h3><div style="font-size:0.66em; color:var(--body); line-height:1.7;">AWS · passkeys & social login (after the real domain) · sales tax beyond Lago's rates · team/seat screens · usage prices</div></div>
  <div style="flex:1;"><h3 style="color:var(--label);">Needs you</h3><div style="font-size:0.66em; color:var(--body); line-height:1.7;">Push tag <code>v1-diagnostic-archive</code> · paste Stripe <strong>test</strong> keys · choose execution mode · review the final PR</div></div>
</div>
