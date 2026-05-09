---
marp: true
theme: default
paginate: true
style: |
  @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700;800&family=Raleway:wght@100;200;300&display=swap');

  :root {
    --a: #007AFF;
    --a2: #0091ff;
    --bg: #000;
    --s: #080808;
    --b: #111;
    --m: #555;
    --t: #fff;
    --g: #22c55e;
    --r: #ef4444;
    --y: #f5a623;
    --body: #999;
    --label: #666;
  }

  section {
    background: var(--bg);
    color: var(--t);
    font-family: 'Raleway', sans-serif;
    font-weight: 200;
    padding: 56px 72px;
    line-height: 1.5;
  }

  h1 { font-family: 'Outfit'; font-weight: 800; font-size: 3em; color: var(--t); letter-spacing: -0.03em; line-height: 1; margin: 0 0 4px; }
  h2 { font-family: 'Raleway'; font-weight: 100; font-size: 1.3em; color: #888; margin: 0 0 20px; }
  h3 { font-family: 'Outfit'; font-weight: 600; font-size: 0.6em; color: var(--m); text-transform: uppercase; letter-spacing: 0.2em; margin: 0 0 4px; }
  strong { color: var(--a); font-weight: 300; }

  section.lead { display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; }
  section.lead h1 { font-size: 3.8em; color: var(--t); }

  section::after { font-family: 'Outfit'; font-size: 0.6em; color: #151515; }

  .tag { font-family: 'Outfit'; font-weight: 600; font-size: 0.55em; letter-spacing: 0.12em; text-transform: uppercase; padding: 3px 10px; border-radius: 4px; display: inline-block; }

  details { background: var(--s); border: 1px solid var(--b); border-radius: 10px; padding: 14px 18px; margin-top: 8px; }
  details summary { color: var(--a); font-family: 'Outfit'; font-weight: 600; font-size: 0.8em; cursor: pointer; letter-spacing: 0.03em; }
  details p { color: var(--body); font-size: 0.78em; margin-top: 8px; line-height: 1.6; }

  .row:hover { background: #0c0c0c; }
  .row { transition: background 0.2s; border-radius: 6px; padding: 0 8px; }

  abbr { text-decoration: none; border-bottom: 1px dotted #333; cursor: help; }

  .inferred { font-style: italic; color: #86868B; font-weight: 200; }
  sup.cite { color: var(--a); font-size: 0.65em; vertical-align: super; font-weight: 700; }
header: ''
footer: ''
---

<!-- _class: lead -->
<!-- _paginate: false -->

![bg brightness:0.12](https://images.unsplash.com/photo-1556761175-b413da4baf72?w=1400)

# Copio

<div style="font-family: 'Raleway'; font-weight: 100; font-size: 1.1em; color: #ffffff80; margin-top: 12px; max-width: 720px;">
The colleague who already read everything overnight. Ask why. Get an honest written answer with citations.
</div>

<div style="display: flex; gap: 8px; margin-top: 24px;">
  <span style="background: #007AFF15; border: 1px solid #007AFF33; border-radius: 20px; padding: 4px 14px; font-family: 'Outfit'; font-size: 0.55em; color: #007AFFcc; font-weight: 400;">Diagnostic Agent</span>
  <span style="background: #007AFF15; border: 1px solid #007AFF33; border-radius: 20px; padding: 4px 14px; font-family: 'Outfit'; font-size: 0.55em; color: #007AFFcc; font-weight: 400;">Amazon SP-API</span>
  <span style="background: #007AFF15; border: 1px solid #007AFF33; border-radius: 20px; padding: 4px 14px; font-family: 'Outfit'; font-size: 0.55em; color: #007AFFcc; font-weight: 400;">Phase 1.0 Dogfood</span>
</div>

---

### Status quo

# CEOs spend hours stitching data into a story

<div style="display: flex; gap: 14px; margin-top: 24px;">
  <div style="flex: 1; background: var(--s); border: 1px solid var(--b); border-radius: 10px; padding: 18px;">
    <div style="font-family: 'Outfit'; font-weight: 600; font-size: 0.55em; color: var(--label); letter-spacing: 0.1em; text-transform: uppercase;">Self-serve</div>
    <div style="font-family: 'Outfit'; font-size: 1.4em; font-weight: 800; color: var(--t); line-height: 1.1; margin-top: 8px;">2 to 4 hours</div>
    <div style="font-size: 0.7em; color: var(--body); margin-top: 8px;">Brand Analytics. Helium 10. Ad console. 3PL. Swivel-chair. Biased toward the data already open.</div>
  </div>
  <div style="flex: 1; background: var(--s); border: 1px solid var(--b); border-radius: 10px; padding: 18px;">
    <div style="font-family: 'Outfit'; font-weight: 600; font-size: 0.55em; color: var(--label); letter-spacing: 0.1em; text-transform: uppercase;">Junior analyst</div>
    <div style="font-family: 'Outfit'; font-size: 1.4em; font-weight: 800; color: var(--t); line-height: 1.1; margin-top: 8px;">$60 to 90K/yr</div>
    <div style="font-size: 0.7em; color: var(--body); margin-top: 8px;">Monday deck nobody reads. Real questions still go through Slack. Hours per question.</div>
  </div>
  <div style="flex: 1; background: var(--s); border: 1px solid var(--b); border-radius: 10px; padding: 18px;">
    <div style="font-family: 'Outfit'; font-weight: 600; font-size: 0.55em; color: var(--label); letter-spacing: 0.1em; text-transform: uppercase;">Agency</div>
    <div style="font-family: 'Outfit'; font-size: 1.4em; font-weight: 800; color: var(--t); line-height: 1.1; margin-top: 8px;">$5 to 15K/mo</div>
    <div style="font-size: 0.7em; color: var(--body); margin-top: 8px;">Monday memo from somebody without full SP-API access. Realtime questions go unanswered.</div>
  </div>
  <div style="flex: 1; background: var(--s); border: 1px solid var(--b); border-radius: 10px; padding: 18px;">
    <div style="font-family: 'Outfit'; font-weight: 600; font-size: 0.55em; color: var(--label); letter-spacing: 0.1em; text-transform: uppercase;">Just don't ask</div>
    <div style="font-family: 'Outfit'; font-size: 1.4em; font-weight: 800; color: var(--r); line-height: 1.1; margin-top: 8px;">Most common</div>
    <div style="font-size: 0.7em; color: var(--body); margin-top: 8px;">Things slide. The cost of finding out feels too high. Compounds quietly into bad calls.</div>
  </div>
</div>

<div style="margin-top: 28px; font-weight: 200; font-size: 0.85em; color: var(--label);">
  The data exists. The interpretation does not. <strong>Copio is the interpretation.</strong>
</div>

---

### The promise

# Ask why. Get a written answer.

<div style="display: flex; gap: 24px; margin-top: 12px;">
  <div style="flex: 1;">
    <div style="background: var(--s); border: 1px solid var(--b); border-radius: 12px; padding: 20px;">
      <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 12px;">
        <div style="width: 24px; height: 24px; border-radius: 50%; background: #FAFAFA; color: #515154; display: flex; align-items: center; justify-content: center; font-size: 0.6em; font-weight: 700;">JA</div>
        <span style="font-size: 0.7em; color: var(--body); font-weight: 300;">James</span>
      </div>
      <div style="font-size: 0.85em; color: #ddd; font-weight: 200;">Why are conversions down on B0CABCD123 this past week?</div>
    </div>
    <div style="background: var(--s); border: 1px solid var(--b); border-radius: 12px; padding: 20px; margin-top: 12px; border-left: 2px solid #007AFF;">
      <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 12px;">
        <div style="width: 24px; height: 24px; border-radius: 50%; background: var(--a); color: white; display: flex; align-items: center; justify-content: center; font-size: 0.55em; font-weight: 700;">C</div>
        <span style="font-size: 0.7em; color: var(--body); font-weight: 300;">copio</span>
      </div>
      <div style="font-size: 0.78em; color: #ddd; line-height: 1.6; font-weight: 200;">
        Conversion fell from 7.8% to 5.4% week-over-week<sup class="cite">1</sup>, a 31% drop. Sessions held flat at 4,820<sup class="cite">2</sup>. Two things broke at once: Buy Box dropped to 58% Wed<sup class="cite">3</sup>, and the 6-pack went out of stock Thu<sup class="cite">4</sup>.
        <br><br>
        <span class="inferred">I infer Buy Box loss is the bigger driver. I'm 70% on this.</span>
      </div>
    </div>
  </div>
  <div style="width: 280px; padding-top: 24px;">
    <div style="font-family: 'Outfit'; font-weight: 600; font-size: 0.55em; color: var(--label); letter-spacing: 0.12em; text-transform: uppercase; margin-bottom: 12px;">Three guarantees</div>
    <div style="font-size: 0.78em; color: var(--body); line-height: 1.7;">
      <strong>Cited.</strong> Every number links to source SP-API data with hover preview.
      <br><br>
      <strong>Calibrated.</strong> "I can see" facts read normal. "I infer" claims are <span class="inferred">italic muted</span>.
      <br><br>
      <strong>Honest.</strong> When data is missing, it says so. No pretending.
    </div>
  </div>
</div>

---

### How it answers

# Seven steps from question to written answer

<div style="display: flex; gap: 0; margin-top: 16px;">
  <div style="flex: 1; padding: 14px 16px; border-right: 1px solid #111; position: relative;">
    <div style="font-family: 'Outfit'; font-size: 1.6em; font-weight: 800; color: var(--a); line-height: 1;">1</div>
    <div style="font-family: 'Outfit'; font-weight: 600; font-size: 0.55em; color: var(--label); letter-spacing: 0.1em; text-transform: uppercase; margin-top: 6px;">Tenant + memory</div>
    <div style="font-size: 0.7em; color: var(--body); margin-top: 6px; font-weight: 200;">Loads LWA token, business profile, prior decisions ("don't suggest Walmart").</div>
  </div>
  <div style="flex: 1; padding: 14px 16px; border-right: 1px solid #111;">
    <div style="font-family: 'Outfit'; font-size: 1.6em; font-weight: 800; color: var(--a); line-height: 1;">2</div>
    <div style="font-family: 'Outfit'; font-weight: 600; font-size: 0.55em; color: var(--label); letter-spacing: 0.1em; text-transform: uppercase; margin-top: 6px;">Plan</div>
    <div style="font-size: 0.7em; color: var(--body); margin-top: 6px; font-weight: 200;">Sonnet 4.6 decomposes the hypothesis tree. Picks 2-4 likely causes.</div>
  </div>
  <div style="flex: 1; padding: 14px 16px; border-right: 1px solid #111;">
    <div style="font-family: 'Outfit'; font-size: 1.6em; font-weight: 800; color: var(--a); line-height: 1;">3</div>
    <div style="font-family: 'Outfit'; font-weight: 600; font-size: 0.55em; color: var(--label); letter-spacing: 0.1em; text-transform: uppercase; margin-top: 6px;">Tool calls</div>
    <div style="font-size: 0.7em; color: var(--body); margin-top: 6px; font-weight: 200;">Parallel SP-API pulls. Cache layer keyed by (tenant, query, day).</div>
  </div>
  <div style="flex: 1; padding: 14px 16px;">
    <div style="font-family: 'Outfit'; font-size: 1.6em; font-weight: 800; color: var(--a); line-height: 1;">4</div>
    <div style="font-family: 'Outfit'; font-weight: 600; font-size: 0.55em; color: var(--label); letter-spacing: 0.1em; text-transform: uppercase; margin-top: 6px;">Reason</div>
    <div style="font-size: 0.7em; color: var(--body); margin-top: 6px; font-weight: 200;">Marks claims as cited vs inferred. Auto-escalates to Opus 4.7 when needed.</div>
  </div>
</div>

<div style="display: flex; gap: 0; margin-top: 0; border-top: 1px solid #111;">
  <div style="flex: 1; padding: 14px 16px; border-right: 1px solid #111;">
    <div style="font-family: 'Outfit'; font-size: 1.6em; font-weight: 800; color: var(--a); line-height: 1;">5</div>
    <div style="font-family: 'Outfit'; font-weight: 600; font-size: 0.55em; color: var(--label); letter-spacing: 0.1em; text-transform: uppercase; margin-top: 6px;">Draft</div>
    <div style="font-size: 0.7em; color: var(--body); margin-top: 6px; font-weight: 200;">Plain prose. Quantified uncertainty. Forbidden vocab blocked at prompt level.</div>
  </div>
  <div style="flex: 1; padding: 14px 16px; border-right: 1px solid #111;">
    <div style="font-family: 'Outfit'; font-size: 1.6em; font-weight: 800; color: var(--a); line-height: 1;">6</div>
    <div style="font-family: 'Outfit'; font-weight: 600; font-size: 0.55em; color: var(--label); letter-spacing: 0.1em; text-transform: uppercase; margin-top: 6px;">Stream</div>
    <div style="font-size: 0.7em; color: var(--body); margin-top: 6px; font-weight: 200;">Token-by-token over SSE. Sub-states cycle: Planning → Fetching → Reasoning.</div>
  </div>
  <div style="flex: 1; padding: 14px 16px; border-right: 1px solid #111;">
    <div style="font-family: 'Outfit'; font-size: 1.6em; font-weight: 800; color: var(--a); line-height: 1;">7</div>
    <div style="font-family: 'Outfit'; font-weight: 600; font-size: 0.55em; color: var(--label); letter-spacing: 0.1em; text-transform: uppercase; margin-top: 6px;">React</div>
    <div style="font-size: 0.7em; color: var(--body); margin-top: 6px; font-weight: 200;">5 emojis feed the eval set. Free-text "what was wrong" is tuning signal.</div>
  </div>
  <div style="flex: 1; padding: 14px 16px;">
    <div style="font-family: 'Outfit'; font-size: 1.6em; font-weight: 800; color: var(--g); line-height: 1;">∞</div>
    <div style="font-family: 'Outfit'; font-weight: 600; font-size: 0.55em; color: var(--label); letter-spacing: 0.1em; text-transform: uppercase; margin-top: 6px;">Audit log</div>
    <div style="font-size: 0.7em; color: var(--body); margin-top: 6px; font-weight: 200;">Append-only. Every tool call, state change, reaction. Tier-1 ready.</div>
  </div>
</div>

<div style="margin-top: 24px; font-weight: 200; font-size: 0.78em; color: var(--label); text-align: center;">
  Target latency: under 60s p50. Under 180s p99 even when Brand Analytics + SQP report polls dominate.
</div>

---

### State machine

# The diagnostic lifecycle

<div style="margin-top: 8px; display: flex; gap: 24px;">
  <div style="flex: 1;">
    <svg width="100%" height="380" viewBox="0 0 480 380">
      <defs>
        <marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#444"/></marker>
        <marker id="arr-r" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#ef4444"/></marker>
        <marker id="arr-g" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#22c55e"/></marker>
      </defs>
      <rect x="180" y="10" width="120" height="36" rx="6" fill="#080808" stroke="#222"/>
      <text x="240" y="33" text-anchor="middle" fill="#ddd" font-family="Outfit" font-size="13" font-weight="600">QUEUED</text>
      <rect x="180" y="70" width="120" height="36" rx="6" fill="#080808" stroke="#222"/>
      <text x="240" y="93" text-anchor="middle" fill="#ddd" font-family="Outfit" font-size="13" font-weight="600">PLANNING</text>
      <rect x="180" y="130" width="120" height="36" rx="6" fill="#080808" stroke="#222"/>
      <text x="240" y="153" text-anchor="middle" fill="#ddd" font-family="Outfit" font-size="13" font-weight="600">TOOL_CALLS</text>
      <rect x="180" y="190" width="120" height="36" rx="6" fill="#080808" stroke="#222"/>
      <text x="240" y="213" text-anchor="middle" fill="#ddd" font-family="Outfit" font-size="13" font-weight="600">REASONING</text>
      <rect x="180" y="250" width="120" height="36" rx="6" fill="#080808" stroke="#222"/>
      <text x="240" y="273" text-anchor="middle" fill="#ddd" font-family="Outfit" font-size="13" font-weight="600">DRAFTING</text>
      <rect x="180" y="310" width="120" height="36" rx="6" fill="#007AFF22" stroke="#007AFF"/>
      <text x="240" y="333" text-anchor="middle" fill="#fff" font-family="Outfit" font-size="13" font-weight="700">COMPLETE</text>
      <line x1="240" y1="46" x2="240" y2="68" stroke="#444" stroke-width="1.2" marker-end="url(#arr)"/>
      <line x1="240" y1="106" x2="240" y2="128" stroke="#444" stroke-width="1.2" marker-end="url(#arr)"/>
      <line x1="240" y1="166" x2="240" y2="188" stroke="#444" stroke-width="1.2" marker-end="url(#arr)"/>
      <line x1="240" y1="226" x2="240" y2="248" stroke="#444" stroke-width="1.2" marker-end="url(#arr)"/>
      <line x1="240" y1="286" x2="240" y2="308" stroke="#444" stroke-width="1.2" marker-end="url(#arr-g)"/>
      <rect x="350" y="70" width="120" height="36" rx="6" fill="#ef444415" stroke="#ef4444"/>
      <text x="410" y="93" text-anchor="middle" fill="#ef4444" font-family="Outfit" font-size="11" font-weight="700">FAILED_INTERNAL</text>
      <line x1="300" y1="88" x2="349" y2="88" stroke="#ef4444" stroke-width="1.2" marker-end="url(#arr-r)" opacity="0.8"/>
      <rect x="350" y="130" width="120" height="36" rx="6" fill="#ef444415" stroke="#ef4444"/>
      <text x="410" y="153" text-anchor="middle" fill="#ef4444" font-family="Outfit" font-size="11" font-weight="700">FAILED_NO_DATA</text>
      <line x1="300" y1="148" x2="349" y2="148" stroke="#ef4444" stroke-width="1.2" marker-end="url(#arr-r)" opacity="0.8"/>
      <rect x="10" y="190" width="120" height="36" rx="6" fill="#f5a62315" stroke="#f5a623"/>
      <text x="70" y="213" text-anchor="middle" fill="#f5a623" font-family="Outfit" font-size="13" font-weight="700">DEGRADED</text>
      <line x1="180" y1="208" x2="131" y2="208" stroke="#f5a623" stroke-width="1.2" opacity="0.8"/>
      <line x1="70" y1="226" x2="70" y2="270" stroke="#f5a623" stroke-width="1.2" opacity="0.8"/>
      <line x1="70" y1="270" x2="178" y2="270" stroke="#f5a623" stroke-width="1.2" marker-end="url(#arr)" opacity="0.8"/>
    </svg>
  </div>
  <div style="width: 220px; padding-top: 12px;">
    <div style="font-family: 'Outfit'; font-weight: 600; font-size: 0.55em; color: var(--label); letter-spacing: 0.12em; text-transform: uppercase; margin-bottom: 12px;">Invariants</div>
    <div style="font-size: 0.74em; color: var(--body); line-height: 1.7;">
      Invalid transitions blocked at the orchestrator. Every state change persists to audit log.
      <br><br>
      <strong>FAILED_NO_DATA</strong> returns honestly: "I couldn't pull anything useful right now."
      <br><br>
      <strong>DEGRADED</strong> renders a 2px cool-amber rail on the message. Prose carries the explanation.
    </div>
  </div>
</div>

---

### Tool palette

# What the agent can do

<div style="display: flex; gap: 12px; margin-top: 16px;">
  <div style="flex: 1; background: var(--s); border: 1px solid var(--b); border-radius: 10px; padding: 18px; position: relative; overflow: hidden;">
    <div style="position: absolute; top: 0; left: 0; width: 100%; height: 2px; background: linear-gradient(90deg, var(--a), transparent);"></div>
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--a)" stroke-width="1.5"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/></svg>
      <span style="font-family: 'Outfit'; font-weight: 600; font-size: 0.5em; color: var(--label); letter-spacing: 0.1em; text-transform: uppercase;">SP-API</span>
    </div>
    <div style="font-family: 'Outfit'; font-weight: 700; font-size: 0.85em; color: var(--t); line-height: 1.3;">get_orders</div>
    <div style="font-family: 'Outfit'; font-weight: 700; font-size: 0.85em; color: var(--t); line-height: 1.3; margin-top: 6px;">get_fba_inventory</div>
    <div style="font-family: 'Outfit'; font-weight: 700; font-size: 0.85em; color: var(--t); line-height: 1.3; margin-top: 6px;">get_report</div>
    <div style="font-size: 0.65em; color: var(--body); margin-top: 12px; font-weight: 200;">Real-time + scheduled. Cached 15min hot, 24h cold. Named exceptions per Error &amp; Rescue Map.</div>
  </div>
  <div style="flex: 1; background: var(--s); border: 1px solid var(--b); border-radius: 10px; padding: 18px; position: relative; overflow: hidden;">
    <div style="position: absolute; top: 0; left: 0; width: 100%; height: 2px; background: linear-gradient(90deg, var(--a), transparent);"></div>
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--a)" stroke-width="1.5"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
      <span style="font-family: 'Outfit'; font-weight: 600; font-size: 0.5em; color: var(--label); letter-spacing: 0.1em; text-transform: uppercase;">Math</span>
    </div>
    <div style="font-family: 'Outfit'; font-weight: 700; font-size: 0.85em; color: var(--t); line-height: 1.3;">summary_stats</div>
    <div style="font-family: 'Outfit'; font-weight: 700; font-size: 0.85em; color: var(--t); line-height: 1.3; margin-top: 6px;">pct_change</div>
    <div style="font-family: 'Outfit'; font-weight: 700; font-size: 0.85em; color: var(--t); line-height: 1.3; margin-top: 6px;">z_score</div>
    <div style="font-size: 0.65em; color: var(--body); margin-top: 12px; font-weight: 200;">Anomaly detection at |z|≥2. WoW deltas. Prevents the model from inventing arithmetic.</div>
  </div>
  <div style="flex: 1; background: var(--s); border: 1px solid var(--b); border-radius: 10px; padding: 18px; position: relative; overflow: hidden;">
    <div style="position: absolute; top: 0; left: 0; width: 100%; height: 2px; background: linear-gradient(90deg, var(--a), transparent);"></div>
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--a)" stroke-width="1.5"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
      <span style="font-family: 'Outfit'; font-weight: 600; font-size: 0.5em; color: var(--label); letter-spacing: 0.1em; text-transform: uppercase;">Memory</span>
    </div>
    <div style="font-family: 'Outfit'; font-weight: 700; font-size: 0.85em; color: var(--t); line-height: 1.3;">remember</div>
    <div style="font-family: 'Outfit'; font-weight: 700; font-size: 0.85em; color: var(--t); line-height: 1.3; margin-top: 6px;">recall</div>
    <div style="font-size: 0.65em; color: var(--body); margin-top: 12px; font-weight: 200;">File-backed JSONL Phase 1.0. Graduates to pgvector RAG in 1.1. Per-tenant scoped.</div>
  </div>
</div>

<div style="margin-top: 20px; font-weight: 200; font-size: 0.74em; color: var(--label);">
  All 8 tool definitions ride the 4th cache breakpoint. Eval rig verifies every tool call returns either real data or a named degraded result.
</div>

---

### The load-bearing visual rule

# "I can see" vs "I infer"

<div style="display: flex; gap: 24px; margin-top: 16px;">
  <div style="flex: 1; background: var(--s); border: 1px solid var(--b); border-radius: 10px; padding: 24px;">
    <div style="font-family: 'Outfit'; font-weight: 600; font-size: 0.55em; color: var(--label); letter-spacing: 0.12em; text-transform: uppercase;">Cited fact</div>
    <div style="margin-top: 12px; font-size: 0.95em; line-height: 1.6; color: #ddd; font-weight: 200;">
      Sales fell 8% MoM<sup class="cite">1</sup>. Ad CPC jumped from $0.74 to $1.12<sup class="cite">2</sup>.
    </div>
    <div style="display: flex; gap: 8px; margin-top: 14px;">
      <span class="tag" style="background: #007AFF12; color: var(--a); border: 1px solid #007AFF22;">Inter regular</span>
      <span class="tag" style="background: #ffffff10; color: #ddd; border: 1px solid #ffffff20;">--text-primary</span>
    </div>
    <div style="font-size: 0.7em; color: var(--body); margin-top: 14px; font-weight: 200;">Citation superscript points to the source SP-API response. Hover to preview the data.</div>
  </div>
  <div style="flex: 1; background: var(--s); border: 1px solid var(--b); border-radius: 10px; padding: 24px;">
    <div style="font-family: 'Outfit'; font-weight: 600; font-size: 0.55em; color: var(--label); letter-spacing: 0.12em; text-transform: uppercase;">Inference</div>
    <div style="margin-top: 12px; font-size: 0.95em; line-height: 1.6;">
      <span class="inferred">I infer this is competitor pressure rather than seasonality, but I'm 70% on this.</span>
    </div>
    <div style="display: flex; gap: 8px; margin-top: 14px;">
      <span class="tag" style="background: #86868b22; color: #86868B; border: 1px solid #86868b33;">Inter italic</span>
      <span class="tag" style="background: #86868b15; color: #86868B; border: 1px solid #86868b22;">--text-muted</span>
    </div>
    <div style="font-size: 0.7em; color: var(--body); margin-top: 14px; font-weight: 200;">No serif italic. Differentiation via color shift + italic style. Quantifies the confidence inline.</div>
  </div>
</div>

<div style="margin-top: 22px; font-weight: 200; font-size: 0.78em; color: var(--label); text-align: center;">
  The brand promise dies if cited facts and judgments render the same. <strong>This is the rule the renderer enforces in voiceParser.ts.</strong>
</div>

---

### Self-improving loop

# Five emojis feed the eval set

<div style="display: flex; gap: 14px; margin-top: 16px;">
  <div style="flex: 1; background: var(--s); border: 1px solid var(--b); border-radius: 10px; padding: 18px; text-align: center;">
    <div style="font-size: 2em;">👍</div>
    <div style="font-family: 'Outfit'; font-weight: 700; font-size: 0.7em; color: var(--g); margin-top: 4px;">Gold candidate</div>
    <div style="font-size: 0.62em; color: var(--body); margin-top: 8px; font-weight: 200; line-height: 1.5;">Promote to golden set on next nightly run.</div>
  </div>
  <div style="flex: 1; background: var(--s); border: 1px solid var(--b); border-radius: 10px; padding: 18px; text-align: center;">
    <div style="font-size: 2em;">👎</div>
    <div style="font-family: 'Outfit'; font-weight: 700; font-size: 0.7em; color: var(--r); margin-top: 4px;">Flag for review</div>
    <div style="font-size: 0.62em; color: var(--body); margin-top: 8px; font-weight: 200; line-height: 1.5;">Inline "tell me what was wrong" input expands. Free-text becomes tuning signal.</div>
  </div>
  <div style="flex: 1; background: var(--s); border: 1px solid var(--b); border-radius: 10px; padding: 18px; text-align: center;">
    <div style="font-size: 2em;">🎯</div>
    <div style="font-family: 'Outfit'; font-weight: 700; font-size: 0.7em; color: var(--g); margin-top: 4px;">Exactly right</div>
    <div style="font-size: 0.62em; color: var(--body); margin-top: 8px; font-weight: 200; line-height: 1.5;">Stronger than 👍. Pinned as the answer template for that question shape.</div>
  </div>
  <div style="flex: 1; background: var(--s); border: 1px solid var(--b); border-radius: 10px; padding: 18px; text-align: center;">
    <div style="font-size: 2em;">❓</div>
    <div style="font-family: 'Outfit'; font-weight: 700; font-size: 0.7em; color: var(--y); margin-top: 4px;">Unclear</div>
    <div style="font-size: 0.62em; color: var(--body); margin-top: 8px; font-weight: 200; line-height: 1.5;">Voice-tuning signal. The answer was right but the prose missed.</div>
  </div>
  <div style="flex: 1; background: var(--s); border: 1px solid var(--b); border-radius: 10px; padding: 18px; text-align: center;">
    <div style="font-size: 2em;">🔁</div>
    <div style="font-family: 'Outfit'; font-weight: 700; font-size: 0.7em; color: var(--r); margin-top: 4px;">Wrong, retry</div>
    <div style="font-size: 0.62em; color: var(--body); margin-top: 8px; font-weight: 200; line-height: 1.5;">Hard regression flag. Auto-adds to the next eval-rig run.</div>
  </div>
</div>

<div style="margin-top: 24px; font-weight: 200; font-size: 0.78em; color: var(--label);">
  Phase 1.0 captures the signal; the loop closes manually. Phase 1.1 wires it to a nightly Inngest cron with regression alerting.
</div>

---

### Prompt cache architecture

# Four explicit breakpoints, eighty percent hit rate gate

<div style="display: flex; gap: 24px; margin-top: 16px;">
  <div style="flex: 1.5;">
    <svg width="100%" height="320" viewBox="0 0 600 320">
      <defs>
        <linearGradient id="cacheGrad" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stop-color="#007AFF" stop-opacity="0.4"/>
          <stop offset="100%" stop-color="#007AFF" stop-opacity="0.05"/>
        </linearGradient>
      </defs>
      <rect x="20" y="40" width="500" height="200" rx="8" fill="url(#cacheGrad)" stroke="#007AFF" stroke-width="1" stroke-dasharray="4,3"/>
      <text x="270" y="32" text-anchor="middle" fill="#007AFFcc" font-family="Outfit" font-size="11" font-weight="700" letter-spacing="2">CACHED PREFIX (most-stable first)</text>
      <rect x="36" y="56" width="468" height="36" rx="6" fill="#080808" stroke="#222"/>
      <text x="50" y="74" fill="#666" font-family="Outfit" font-size="10" font-weight="700">1</text>
      <text x="68" y="74" fill="#ddd" font-family="Outfit" font-size="13" font-weight="700">Tool definitions</text>
      <text x="68" y="86" fill="#666" font-family="Raleway" font-size="10" font-weight="200">8 tools. Stable across requests. Last tool carries cache_control.</text>
      <rect x="36" y="100" width="468" height="36" rx="6" fill="#080808" stroke="#222"/>
      <text x="50" y="118" fill="#666" font-family="Outfit" font-size="10" font-weight="700">2</text>
      <text x="68" y="118" fill="#ddd" font-family="Outfit" font-size="13" font-weight="700">Voice anchor</text>
      <text x="68" y="130" fill="#666" font-family="Raleway" font-size="10" font-weight="200">Persona doc. Rev independently of system prompt.</text>
      <rect x="36" y="144" width="468" height="36" rx="6" fill="#080808" stroke="#222"/>
      <text x="50" y="162" fill="#666" font-family="Outfit" font-size="10" font-weight="700">3</text>
      <text x="68" y="162" fill="#ddd" font-family="Outfit" font-size="13" font-weight="700">Honest-voice system prompt</text>
      <text x="68" y="174" fill="#666" font-family="Raleway" font-size="10" font-weight="200">Forbidden vocab inline. Em-dash ban. Em-dash test guards drift.</text>
      <rect x="36" y="188" width="468" height="36" rx="6" fill="#080808" stroke="#222"/>
      <text x="50" y="206" fill="#666" font-family="Outfit" font-size="10" font-weight="700">4</text>
      <text x="68" y="206" fill="#ddd" font-family="Outfit" font-size="13" font-weight="700">Per-tenant memory snapshot</text>
      <text x="68" y="218" fill="#666" font-family="Raleway" font-size="10" font-weight="200">Most variable. Goes last so 1-3 cache hit even when memory grows.</text>
      <rect x="20" y="252" width="500" height="56" rx="8" fill="#080808" stroke="#222"/>
      <text x="270" y="244" text-anchor="middle" fill="#555" font-family="Outfit" font-size="11" font-weight="700" letter-spacing="2">DYNAMIC (not cached)</text>
      <text x="36" y="276" fill="#888" font-family="Outfit" font-size="13" font-weight="700">Question + tool results</text>
      <text x="36" y="294" fill="#666" font-family="Raleway" font-size="10" font-weight="200">Today's question. The fresh SP-API responses. Per-call cost.</text>
    </svg>
  </div>
  <div style="width: 200px; padding-top: 24px;">
    <div style="font-family: 'Outfit'; font-weight: 600; font-size: 0.55em; color: var(--label); letter-spacing: 0.12em; text-transform: uppercase; margin-bottom: 8px;">Why explicit</div>
    <div style="font-size: 0.72em; color: var(--body); line-height: 1.7;">
      Anthropic API allows max 4 cache_control markers per request.
      <br><br>
      Misplaced breakpoints silently degrade to <strong>full price</strong>.
      <br><br>
      <code style="background: #1a1a1a; padding: 2px 5px; border-radius: 3px; color: #007AFF; font-size: 0.9em;">verify_cache_hit_rate.py</code> runs cold then warm. Asserts hit rate ≥ 0.80.
    </div>
  </div>
</div>

---

### Stack

# Locked in eng review

<div style="margin-top: 8px; font-size: 0.72em;">
  <div class="row" style="display: flex; align-items: center; gap: 14px; padding: 10px 8px; border-bottom: 1px solid #0e0e0e;">
    <div style="width: 130px; font-family: 'Outfit'; font-weight: 700; color: var(--a);">Backend</div>
    <div style="flex: 1; color: #ddd; font-weight: 200;">FastAPI · Python 3.11 · async SQLAlchemy</div>
    <div style="color: var(--body); font-style: italic; font-weight: 200;">streaming SSE + Inngest workers</div>
  </div>
  <div class="row" style="display: flex; align-items: center; gap: 14px; padding: 10px 8px; border-bottom: 1px solid #0e0e0e;">
    <div style="width: 130px; font-family: 'Outfit'; font-weight: 700; color: var(--a);">Database</div>
    <div style="flex: 1; color: #ddd; font-weight: 200;">Vanilla Postgres + pgvector (HNSW)</div>
    <div style="color: var(--body); font-style: italic; font-weight: 200;">no Supabase. Single backup target.</div>
  </div>
  <div class="row" style="display: flex; align-items: center; gap: 14px; padding: 10px 8px; border-bottom: 1px solid #0e0e0e;">
    <div style="width: 130px; font-family: 'Outfit'; font-weight: 700; color: var(--a);">LLM SDK</div>
    <div style="flex: 1; color: #ddd; font-weight: 200;">Anthropic SDK direct</div>
    <div style="color: var(--body); font-style: italic; font-weight: 200;">no LiteLLM/aisuite. caching needs explicit control</div>
  </div>
  <div class="row" style="display: flex; align-items: center; gap: 14px; padding: 10px 8px; border-bottom: 1px solid #0e0e0e;">
    <div style="width: 130px; font-family: 'Outfit'; font-weight: 700; color: var(--a);">Models</div>
    <div style="flex: 1; color: #ddd; font-weight: 200;">Sonnet 4.6 default · Opus 4.7 fallback</div>
    <div style="color: var(--body); font-style: italic; font-weight: 200;">Opus is the eval judge</div>
  </div>
  <div class="row" style="display: flex; align-items: center; gap: 14px; padding: 10px 8px; border-bottom: 1px solid #0e0e0e;">
    <div style="width: 130px; font-family: 'Outfit'; font-weight: 700; color: var(--a);">SP-API</div>
    <div style="flex: 1; color: #ddd; font-weight: 200;">python-amazon-sp-api (Saleweaver)</div>
    <div style="color: var(--body); font-style: italic; font-weight: 200;">named exceptions wrap the lib</div>
  </div>
  <div class="row" style="display: flex; align-items: center; gap: 14px; padding: 10px 8px; border-bottom: 1px solid #0e0e0e;">
    <div style="width: 130px; font-family: 'Outfit'; font-weight: 700; color: var(--a);">Frontend</div>
    <div style="flex: 1; color: #ddd; font-weight: 200;">Next.js 15 + Tailwind 4 + custom streaming hook</div>
    <div style="color: var(--body); font-style: italic; font-weight: 200;">self-hosted Inter Variable</div>
  </div>
  <div class="row" style="display: flex; align-items: center; gap: 14px; padding: 10px 8px; border-bottom: 1px solid #0e0e0e;">
    <div style="width: 130px; font-family: 'Outfit'; font-weight: 700; color: var(--a);">Eval rig</div>
    <div style="flex: 1; color: #ddd; font-weight: 200;">DIY Python, owned end-to-end</div>
    <div style="color: var(--body); font-style: italic; font-weight: 200;">the moat shouldn't be a vendor feature</div>
  </div>
  <div class="row" style="display: flex; align-items: center; gap: 14px; padding: 10px 8px;">
    <div style="width: 130px; font-family: 'Outfit'; font-weight: 700; color: var(--a);">Audit log</div>
    <div style="flex: 1; color: #ddd; font-weight: 200;">Append-only Postgres table</div>
    <div style="color: var(--body); font-style: italic; font-weight: 200;">hash chain + UPDATE/DELETE block in 1.1</div>
  </div>
</div>

---

### Roadmap

# Where this goes

<div style="margin-top: 12px;">
  <div class="row" style="display: flex; align-items: center; gap: 12px; padding: 10px 8px; border-bottom: 1px solid #0e0e0e;">
    <div style="width: 70px; font-family: 'Outfit'; font-weight: 800; color: var(--g); font-size: 1.1em;">1.0</div>
    <div style="flex: 1; font-size: 0.78em; color: #ddd; font-weight: 200;">Single-tenant dogfood. Web chat. Polling pulls. Unnamed honest voice.</div>
    <span class="tag" style="background: #22c55e15; color: var(--g); border: 1px solid #22c55e22;">Shipped</span>
    <div style="width: 100px; text-align: right; color: var(--body); font-weight: 200; font-size: 0.7em;">internal</div>
  </div>
  <div class="row" style="display: flex; align-items: center; gap: 12px; padding: 10px 8px; border-bottom: 1px solid #0e0e0e;">
    <div style="width: 70px; font-family: 'Outfit'; font-weight: 800; color: var(--a); font-size: 1.1em;">1.1</div>
    <div style="flex: 1; font-size: 0.78em; color: #ddd; font-weight: 200;">Multi-tenant + RLS + KMS. Named persona. Nightly eval cron. LWA OAuth onboarding.</div>
    <span class="tag" style="background: #007AFF15; color: var(--a); border: 1px solid #007AFF22;">Next</span>
    <div style="width: 100px; text-align: right; color: var(--body); font-weight: 200; font-size: 0.7em;">$199 to $499/mo</div>
  </div>
  <div class="row" style="display: flex; align-items: center; gap: 12px; padding: 10px 8px; border-bottom: 1px solid #0e0e0e;">
    <div style="width: 70px; font-family: 'Outfit'; font-weight: 800; color: var(--m); font-size: 1.1em;">1.5</div>
    <div style="flex: 1; font-size: 0.78em; color: #ddd; font-weight: 200;">Slack bot. Email fallback for long diagnostics. Cross-surface memory.</div>
    <span class="tag" style="background: #ffffff10; color: var(--m); border: 1px solid #ffffff20;">Planned</span>
    <div style="width: 100px; text-align: right; color: var(--body); font-weight: 200; font-size: 0.7em;">$199 to $499/mo</div>
  </div>
  <div class="row" style="display: flex; align-items: center; gap: 12px; padding: 10px 8px; border-bottom: 1px solid #0e0e0e;">
    <div style="width: 70px; font-family: 'Outfit'; font-weight: 800; color: var(--m); font-size: 1.1em;">1.6</div>
    <div style="flex: 1; font-size: 0.78em; color: #ddd; font-weight: 200;">HITL writes against Amazon (drafted PO/listing/inventory, 1-tap approve). Tier-2 ready.</div>
    <span class="tag" style="background: #ffffff10; color: var(--m); border: 1px solid #ffffff20;">Planned</span>
    <div style="width: 100px; text-align: right; color: var(--body); font-weight: 200; font-size: 0.7em;">$299 to $599/mo</div>
  </div>
  <div class="row" style="display: flex; align-items: center; gap: 12px; padding: 10px 8px; border-bottom: 1px solid #0e0e0e;">
    <div style="width: 70px; font-family: 'Outfit'; font-weight: 800; color: var(--m); font-size: 1.1em;">2.0</div>
    <div style="flex: 1; font-size: 0.78em; color: #ddd; font-weight: 200;">Amazon as source of truth. Listing replication to Walmart/Shopify/eBay. Inventory sync. Order convergence.</div>
    <span class="tag" style="background: #ffffff10; color: var(--m); border: 1px solid #ffffff20;">Strategic</span>
    <div style="width: 100px; text-align: right; color: var(--body); font-weight: 200; font-size: 0.7em;">$499 to $1199/mo</div>
  </div>
  <div class="row" style="display: flex; align-items: center; gap: 12px; padding: 10px 8px; border-bottom: 1px solid #0e0e0e;">
    <div style="width: 70px; font-family: 'Outfit'; font-weight: 800; color: var(--m); font-size: 1.1em;">2.5</div>
    <div style="flex: 1; font-size: 0.78em; color: #ddd; font-weight: 200;">Morning brief. Smart silence. Decision support. Voice memo input.</div>
    <span class="tag" style="background: #ffffff10; color: var(--m); border: 1px solid #ffffff20;">Vision</span>
    <div style="width: 100px; text-align: right; color: var(--body); font-weight: 200; font-size: 0.7em;">$599 to $1299/mo</div>
  </div>
  <div class="row" style="display: flex; align-items: center; gap: 12px; padding: 10px 8px;">
    <div style="width: 70px; font-family: 'Outfit'; font-weight: 800; color: var(--m); font-size: 1.1em;">3.0</div>
    <div style="flex: 1; font-size: 0.78em; color: #ddd; font-weight: 200;">Full chief of staff. Quote-the-CEO-back. Weekly retro. Multi-seat.</div>
    <span class="tag" style="background: #ffffff10; color: var(--m); border: 1px solid #ffffff20;">Vision</span>
    <div style="width: 100px; text-align: right; color: var(--body); font-weight: 200; font-size: 0.7em;">$799 to $1499/mo</div>
  </div>
</div>

---

### Connectors phase 1.0 to 1.6

# Now, and the next two phases

<div style="margin-top: 16px; display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px;">
  <div style="background: var(--s); border: 1px solid var(--b); border-radius: 10px; padding: 16px; position: relative; overflow: hidden;">
    <div style="position: absolute; top: 0; left: 0; width: 100%; height: 2px; background: linear-gradient(90deg, var(--g), transparent);"></div>
    <span class="tag" style="background: #22c55e15; color: var(--g); border: 1px solid #22c55e22;">Phase 1.0</span>
    <div style="font-family: 'Outfit'; font-weight: 700; font-size: 1em; color: var(--t); margin-top: 12px;">Amazon SP-API</div>
    <div style="font-size: 0.6em; color: var(--label); margin-top: 4px; font-weight: 200; letter-spacing: 0.05em; text-transform: uppercase;">read</div>
    <div style="font-size: 0.72em; color: var(--body); margin-top: 10px; font-weight: 200; line-height: 1.55;">Orders. FBA Inventory. Reports (Brand Analytics, SQP, Sales &amp; Traffic). Cached 15min hot, 24h cold.</div>
  </div>
  <div style="background: var(--s); border: 1px solid var(--b); border-radius: 10px; padding: 16px; position: relative; overflow: hidden;">
    <div style="position: absolute; top: 0; left: 0; width: 100%; height: 2px; background: linear-gradient(90deg, var(--a), transparent);"></div>
    <span class="tag" style="background: #007AFF15; color: var(--a); border: 1px solid #007AFF22;">Phase 1.5</span>
    <div style="font-family: 'Outfit'; font-weight: 700; font-size: 1em; color: var(--t); margin-top: 12px;">Slack</div>
    <div style="font-size: 0.6em; color: var(--label); margin-top: 4px; font-weight: 200; letter-spacing: 0.05em; text-transform: uppercase;">surface</div>
    <div style="font-size: 0.72em; color: var(--body); margin-top: 10px; font-weight: 200; line-height: 1.55;">OAuth, slash command, DM, native reaction emojis. Cross-surface memory bridges with web chat.</div>
  </div>
  <div style="background: var(--s); border: 1px solid var(--b); border-radius: 10px; padding: 16px; position: relative; overflow: hidden;">
    <div style="position: absolute; top: 0; left: 0; width: 100%; height: 2px; background: linear-gradient(90deg, var(--a), transparent);"></div>
    <span class="tag" style="background: #007AFF15; color: var(--a); border: 1px solid #007AFF22;">Phase 1.5</span>
    <div style="font-family: 'Outfit'; font-weight: 700; font-size: 1em; color: var(--t); margin-top: 12px;">Email</div>
    <div style="font-size: 0.6em; color: var(--label); margin-top: 4px; font-weight: 200; letter-spacing: 0.05em; text-transform: uppercase;">surface</div>
    <div style="font-size: 0.72em; color: var(--body); margin-top: 10px; font-weight: 200; line-height: 1.55;">Resend or Postmark. Fallback for long diagnostics. Lands the answer if the CEO closes the tab.</div>
  </div>
  <div style="background: var(--s); border: 1px solid var(--b); border-radius: 10px; padding: 16px; position: relative; overflow: hidden;">
    <div style="position: absolute; top: 0; left: 0; width: 100%; height: 2px; background: linear-gradient(90deg, var(--y), transparent);"></div>
    <span class="tag" style="background: #f5a62315; color: var(--y); border: 1px solid #f5a62322;">Phase 1.6</span>
    <div style="font-family: 'Outfit'; font-weight: 700; font-size: 1em; color: var(--t); margin-top: 12px;">Amazon HITL writes</div>
    <div style="font-size: 0.6em; color: var(--label); margin-top: 4px; font-weight: 200; letter-spacing: 0.05em; text-transform: uppercase;">write</div>
    <div style="font-size: 0.72em; color: var(--body); margin-top: 10px; font-weight: 200; line-height: 1.55;">PO. Listing edit. Inventory adjustment. Pricing change. Each drafted, CEO approves with one tap.</div>
  </div>
</div>

<div style="margin-top: 28px; display: flex; gap: 24px; font-size: 0.72em; color: var(--body); font-weight: 200; line-height: 1.6;">
  <div style="flex: 1;">
    <span style="font-family: 'Outfit'; font-weight: 600; font-size: 0.85em; color: var(--label); letter-spacing: 0.1em; text-transform: uppercase;">Compliance.</span> Phase 1.0 is Amazon Tier 1 read-only. Tier 2 + Tier 3 writes gate on Phase 1.6 HITL with full audit log.
  </div>
  <div style="flex: 1;">
    <span style="font-family: 'Outfit'; font-weight: 600; font-size: 0.85em; color: var(--label); letter-spacing: 0.1em; text-transform: uppercase;">Reuse.</span> The HITL pattern built once for Amazon writes is the substrate for every Phase 2.0 channel. <strong>Compliance is a moat, not a tax.</strong>
  </div>
</div>

---

### Connectors phase 2.0 onward

# The multichannel expansion

<div style="margin-top: 16px; display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px;">
  <div style="background: var(--s); border: 1px solid var(--b); border-radius: 10px; padding: 16px; position: relative; overflow: hidden;">
    <div style="position: absolute; top: 0; left: 0; width: 100%; height: 2px; background: linear-gradient(90deg, #cc5515, transparent);"></div>
    <span class="tag" style="background: #cc551515; color: #cc5515; border: 1px solid #cc551533;">Phase 2.0</span>
    <div style="font-family: 'Outfit'; font-weight: 700; font-size: 1em; color: var(--t); margin-top: 12px;">Walmart Marketplace</div>
    <div style="font-size: 0.6em; color: var(--label); margin-top: 4px; font-weight: 200; letter-spacing: 0.05em; text-transform: uppercase;">read + write</div>
    <div style="font-size: 0.72em; color: var(--body); margin-top: 10px; font-weight: 200; line-height: 1.55;">Item Setup API. Listings drafted from the Amazon catalogue. Velocity-aware inventory buffer.</div>
  </div>
  <div style="background: var(--s); border: 1px solid var(--b); border-radius: 10px; padding: 16px; position: relative; overflow: hidden;">
    <div style="position: absolute; top: 0; left: 0; width: 100%; height: 2px; background: linear-gradient(90deg, #cc5515, transparent);"></div>
    <span class="tag" style="background: #cc551515; color: #cc5515; border: 1px solid #cc551533;">Phase 2.0</span>
    <div style="font-family: 'Outfit'; font-weight: 700; font-size: 1em; color: var(--t); margin-top: 12px;">Shopify</div>
    <div style="font-size: 0.6em; color: var(--label); margin-top: 4px; font-weight: 200; letter-spacing: 0.05em; text-transform: uppercase;">read + write</div>
    <div style="font-size: 0.72em; color: var(--body); margin-top: 10px; font-weight: 200; line-height: 1.55;">Admin API. Storefront drafted from Amazon catalogue. Inventory sync. Order convergence.</div>
  </div>
  <div style="background: var(--s); border: 1px solid var(--b); border-radius: 10px; padding: 16px; position: relative; overflow: hidden;">
    <div style="position: absolute; top: 0; left: 0; width: 100%; height: 2px; background: linear-gradient(90deg, #cc5515, transparent);"></div>
    <span class="tag" style="background: #cc551515; color: #cc5515; border: 1px solid #cc551533;">Phase 2.0</span>
    <div style="font-family: 'Outfit'; font-weight: 700; font-size: 1em; color: var(--t); margin-top: 12px;">eBay</div>
    <div style="font-size: 0.6em; color: var(--label); margin-top: 4px; font-weight: 200; letter-spacing: 0.05em; text-transform: uppercase;">read + write</div>
    <div style="font-size: 0.72em; color: var(--body); margin-top: 10px; font-weight: 200; line-height: 1.55;">Inventory API. Returns triage. Per-channel attribute mapping with untranslatable handling.</div>
  </div>
  <div style="background: var(--s); border: 1px solid var(--b); border-radius: 10px; padding: 16px; position: relative; overflow: hidden;">
    <div style="position: absolute; top: 0; left: 0; width: 100%; height: 2px; background: linear-gradient(90deg, var(--m), transparent);"></div>
    <span class="tag" style="background: #ffffff10; color: var(--m); border: 1px solid #ffffff20;">Phase 2.5</span>
    <div style="font-family: 'Outfit'; font-weight: 700; font-size: 1em; color: var(--t); margin-top: 12px;">TikTok Shop</div>
    <div style="font-size: 0.6em; color: var(--label); margin-top: 4px; font-weight: 200; letter-spacing: 0.05em; text-transform: uppercase;">read + write</div>
    <div style="font-size: 0.72em; color: var(--body); margin-top: 10px; font-weight: 200; line-height: 1.55;">Fastest-growing channel. Own agent rules and content moderation surface. Separate eng-review pass.</div>
  </div>
</div>

<div style="margin-top: 28px; font-size: 0.72em; color: var(--body); font-weight: 200; line-height: 1.7;">
  <span style="font-family: 'Outfit'; font-weight: 600; font-size: 0.85em; color: var(--label); letter-spacing: 0.1em; text-transform: uppercase;">Phase 3 surfaces.</span> iMessage and SMS (most intimate channel). Calendar awareness (agent learns when not to brief). Multi-seat tenancy (invite team, per-seat permissions, shared memory). The agent reaches the CEO where they live.
</div>

---

### Phase 2.0 architecture

# Amazon catalogue is the canonical source

<div style="display: flex; gap: 24px; margin-top: 12px;">
  <div style="flex: 1.4;">
    <svg width="100%" height="380" viewBox="0 0 580 380">
      <defs>
        <marker id="m2-arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#444"/></marker>
        <marker id="m2-arr-a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#007AFF"/></marker>
      </defs>
      <rect x="220" y="10" width="140" height="40" rx="8" fill="#22c55e15" stroke="#22c55e"/>
      <text x="290" y="34" text-anchor="middle" fill="#22c55e" font-family="Outfit" font-size="13" font-weight="700">AMAZON CATALOGUE</text>
      <text x="290" y="48" text-anchor="middle" fill="#22c55e" font-family="Raleway" font-size="9" font-weight="200" opacity="0.8">canonical source of truth</text>
      <line x1="290" y1="60" x2="290" y2="86" stroke="#444" stroke-width="1.2" marker-end="url(#m2-arr)"/>
      <rect x="200" y="92" width="180" height="40" rx="8" fill="#080808" stroke="#222"/>
      <text x="290" y="116" text-anchor="middle" fill="#ddd" font-family="Outfit" font-size="13" font-weight="700">CATALOG READER</text>
      <text x="290" y="130" text-anchor="middle" fill="#666" font-family="Raleway" font-size="9" font-weight="200">normalized form per (tenant, ASIN)</text>
      <line x1="290" y1="142" x2="290" y2="168" stroke="#444" stroke-width="1.2" marker-end="url(#m2-arr)"/>
      <rect x="160" y="174" width="260" height="56" rx="8" fill="#007AFF15" stroke="#007AFF"/>
      <text x="290" y="198" text-anchor="middle" fill="#fff" font-family="Outfit" font-size="13" font-weight="700">HYBRID MAPPING ENGINE</text>
      <text x="290" y="216" text-anchor="middle" fill="#007AFFcc" font-family="Raleway" font-size="10" font-weight="200">70% rule-based  +  30% LLM-assisted  +  untranslatable detection</text>
      <line x1="290" y1="240" x2="290" y2="266" stroke="#007AFF" stroke-width="1.2" marker-end="url(#m2-arr-a)"/>
      <rect x="200" y="272" width="180" height="40" rx="8" fill="#080808" stroke="#222"/>
      <text x="290" y="290" text-anchor="middle" fill="#ddd" font-family="Outfit" font-size="13" font-weight="700">DRAFTED LISTINGS</text>
      <text x="290" y="304" text-anchor="middle" fill="#666" font-family="Raleway" font-size="9" font-weight="200">batched 10 at a time, untranslatable flagged</text>
      <line x1="290" y1="324" x2="290" y2="346" stroke="#007AFF" stroke-width="1.2" marker-end="url(#m2-arr-a)"/>
      <rect x="220" y="346" width="140" height="30" rx="8" fill="#007AFF22" stroke="#007AFF"/>
      <text x="290" y="365" text-anchor="middle" fill="#fff" font-family="Outfit" font-size="12" font-weight="700">CEO HITL APPROVAL</text>
      <line x1="220" y1="361" x2="80" y2="361" stroke="#007AFF" stroke-width="1.2" opacity="0.5"/>
      <line x1="80" y1="361" x2="80" y2="200" stroke="#007AFF" stroke-width="1.2" opacity="0.5"/>
      <text x="40" y="280" fill="#666" font-family="Raleway" font-size="9" font-weight="200">decision</text>
      <text x="40" y="293" fill="#666" font-family="Raleway" font-size="9" font-weight="200">memory</text>
      <text x="40" y="306" fill="#666" font-family="Raleway" font-size="9" font-weight="200">override</text>
      <line x1="80" y1="200" x2="158" y2="200" stroke="#007AFF" stroke-width="1.2" marker-end="url(#m2-arr-a)" opacity="0.5"/>
      <rect x="450" y="92" width="120" height="32" rx="6" fill="#080808" stroke="#cc5515"/>
      <text x="510" y="113" text-anchor="middle" fill="#cc5515" font-family="Outfit" font-size="11" font-weight="700">WALMART API</text>
      <rect x="450" y="134" width="120" height="32" rx="6" fill="#080808" stroke="#cc5515"/>
      <text x="510" y="155" text-anchor="middle" fill="#cc5515" font-family="Outfit" font-size="11" font-weight="700">SHOPIFY ADMIN</text>
      <rect x="450" y="176" width="120" height="32" rx="6" fill="#080808" stroke="#cc5515"/>
      <text x="510" y="197" text-anchor="middle" fill="#cc5515" font-family="Outfit" font-size="11" font-weight="700">EBAY INVENTORY</text>
      <line x1="362" y1="361" x2="510" y2="361" stroke="#22c55e" stroke-width="1.2" opacity="0.4"/>
      <line x1="510" y1="361" x2="510" y2="212" stroke="#22c55e" stroke-width="1.2" opacity="0.4"/>
      <line x1="510" y1="212" x2="510" y2="208" stroke="#22c55e" stroke-width="1.2" marker-end="url(#m2-arr)"/>
      <text x="510" y="230" text-anchor="middle" fill="#22c55e" font-family="Outfit" font-size="9" font-weight="700" opacity="0.7">approved batch</text>
    </svg>
  </div>
  <div style="width: 240px; padding-top: 20px;">
    <div style="font-family: 'Outfit'; font-weight: 600; font-size: 0.55em; color: var(--label); letter-spacing: 0.12em; text-transform: uppercase; margin-bottom: 10px;">Why this beats incumbents</div>
    <div style="font-size: 0.66em; color: var(--body); line-height: 1.65; font-weight: 200;">
      Incumbents treat each channel as independent. <strong>Hours of form-filling per SKU per channel.</strong>
      <br><br>
      Copio treats Amazon as canonical. Every other channel is a derived view. <strong>Forty-seven listings replicated to Walmart in one approval session.</strong>
      <br><br>
      <strong>HITL built in Phase 1.6 reuses across every Phase 2.0 channel.</strong>
    </div>
  </div>
</div>

---

### What ships in Phase 1.0

# The dogfood box

<div style="display: flex; gap: 14px; margin-top: 12px;">
  <div style="flex: 1; background: var(--s); border: 1px solid var(--b); border-radius: 10px; padding: 18px;">
    <div style="font-family: 'Outfit'; font-weight: 600; font-size: 0.5em; color: var(--g); letter-spacing: 0.12em; text-transform: uppercase;">Done</div>
    <div style="font-family: 'Outfit'; font-size: 1.6em; font-weight: 800; color: var(--g); line-height: 1; margin-top: 8px;">14</div>
    <div style="font-size: 0.65em; color: var(--body); font-weight: 200; margin-top: 8px; line-height: 1.6;">Backend, frontend, eval rig, audit log, streaming UI, citations, reactions, honest-voice rendering, named exception map.</div>
  </div>
  <div style="flex: 1; background: var(--s); border: 1px solid var(--b); border-radius: 10px; padding: 18px;">
    <div style="font-family: 'Outfit'; font-weight: 600; font-size: 0.5em; color: var(--a); letter-spacing: 0.12em; text-transform: uppercase;">Tests</div>
    <div style="font-family: 'Outfit'; font-size: 1.6em; font-weight: 800; color: var(--a); line-height: 1; margin-top: 8px;">32</div>
    <div style="font-size: 0.65em; color: var(--body); font-weight: 200; margin-top: 8px; line-height: 1.6;">Prompt anti-vocab, em-dash ban, all 5 emojis, math tools, memory isolation, cache placement, SP-API exceptions.</div>
  </div>
  <div style="flex: 1; background: var(--s); border: 1px solid var(--b); border-radius: 10px; padding: 18px;">
    <div style="font-family: 'Outfit'; font-weight: 600; font-size: 0.5em; color: var(--y); letter-spacing: 0.12em; text-transform: uppercase;">Founder authoring</div>
    <div style="font-family: 'Outfit'; font-size: 1.6em; font-weight: 800; color: var(--y); line-height: 1; margin-top: 8px;">5 → 20</div>
    <div style="font-size: 0.65em; color: var(--body); font-weight: 200; margin-top: 8px; line-height: 1.6;">Golden questions ship as scaffold templates. Real Nutragroup ones replace before first eval run.</div>
  </div>
  <div style="flex: 1; background: var(--s); border: 1px solid var(--b); border-radius: 10px; padding: 18px;">
    <div style="font-family: 'Outfit'; font-weight: 600; font-size: 0.5em; color: var(--m); letter-spacing: 0.12em; text-transform: uppercase;">Locked for 1.1</div>
    <div style="font-family: 'Outfit'; font-size: 1.6em; font-weight: 800; color: var(--t); line-height: 1; margin-top: 8px;">8</div>
    <div style="font-size: 0.65em; color: var(--body); font-weight: 200; margin-top: 8px; line-height: 1.6;">Multi-tenant RLS, KMS, hash chain, persona name, nightly cron, reaction pipeline, dark mode, onboarding wizard.</div>
  </div>
</div>

<div style="margin-top: 24px;">
  <div style="font-family: 'Outfit'; font-weight: 600; font-size: 0.55em; color: var(--label); letter-spacing: 0.12em; text-transform: uppercase; margin-bottom: 12px;">Ship gates (2am Friday rule)</div>
  <div style="display: flex; gap: 30px; justify-content: flex-start;">
    <div style="text-align: center;">
      <svg width="120" height="120" viewBox="0 0 180 180">
        <circle cx="90" cy="90" r="74" fill="none" stroke="#111" stroke-width="8"/>
        <circle cx="90" cy="90" r="74" fill="none" stroke="var(--g)" stroke-width="8" stroke-dasharray="465" stroke-dashoffset="93" stroke-linecap="round" transform="rotate(-90 90 90)"/>
        <text x="90" y="84" text-anchor="middle" fill="#fff" font-family="Outfit" font-size="36" font-weight="800">80%</text>
        <text x="90" y="106" text-anchor="middle" fill="#666" font-family="Outfit" font-size="11" font-weight="600" letter-spacing="1.5">CACHE HIT</text>
      </svg>
    </div>
    <div style="text-align: center;">
      <svg width="120" height="120" viewBox="0 0 180 180">
        <circle cx="90" cy="90" r="74" fill="none" stroke="#111" stroke-width="8"/>
        <circle cx="90" cy="90" r="74" fill="none" stroke="var(--a)" stroke-width="8" stroke-dasharray="465" stroke-dashoffset="116" stroke-linecap="round" transform="rotate(-90 90 90)"/>
        <text x="90" y="84" text-anchor="middle" fill="#fff" font-family="Outfit" font-size="36" font-weight="800">7.5</text>
        <text x="90" y="106" text-anchor="middle" fill="#666" font-family="Outfit" font-size="11" font-weight="600" letter-spacing="1.5">JUDGE MIN</text>
      </svg>
    </div>
    <div style="text-align: center;">
      <svg width="120" height="120" viewBox="0 0 180 180">
        <circle cx="90" cy="90" r="74" fill="none" stroke="#111" stroke-width="8"/>
        <circle cx="90" cy="90" r="74" fill="none" stroke="var(--g)" stroke-width="8" stroke-dasharray="465" stroke-dashoffset="46" stroke-linecap="round" transform="rotate(-90 90 90)"/>
        <text x="90" y="84" text-anchor="middle" fill="#fff" font-family="Outfit" font-size="32" font-weight="800">180s</text>
        <text x="90" y="106" text-anchor="middle" fill="#666" font-family="Outfit" font-size="11" font-weight="600" letter-spacing="1.5">P99 LATENCY</text>
      </svg>
    </div>
    <div style="flex: 1; padding-top: 22px; font-size: 0.7em; color: var(--body); line-height: 1.7; font-weight: 200;">
      All three gates fire on every release. Phase 1.1 adds: nightly judge regression alert if any case drops &gt; 0.5 vs 7-day baseline, plus cross-tenant contamination probe.
    </div>
  </div>
</div>

---

<!-- _class: lead -->
<!-- _paginate: false -->

![bg brightness:0.1](https://images.unsplash.com/photo-1515187029135-18ee286d815b?w=1400)

<svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#007AFF" stroke-width="1.2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>

# Deep dives

<div style="font-family: 'Raleway'; font-weight: 100; font-size: 0.9em; color: #ffffff44;">Click to expand each layer</div>

---

### Behind the curtain

<details>
<summary>Why "honest" instead of "helpful"</summary>
<p>Most AI agents optimize for sycophancy because it scores well on quick UX tests. The CEO's job is the opposite: pay for honest counter-evidence, not validation. Forbidden vocab (leverage, optimize, drive engagement, etc.) is enforced at the prompt level and guarded by <strong>tests/unit/test_prompts.py</strong>. The em-dash test caught two real violations during the build.</p>
</details>

<details>
<summary>Why named exceptions instead of "except Exception"</summary>
<p>Every SP-API failure mode maps to a named class: SPAPIRateLimit, SPAPIAuthExpired, SPAPIUpstreamDown, SPAPIBadResponse, SPAPIPermissionDenied, SPAPINotConfigured. Each one has a documented rescue: backoff+retry, refresh+retry, fallback to cache, etc. <strong>Zero `except Exception:` blocks in src/.</strong> Confirmed by grep.</p>
</details>

<details>
<summary>Why streaming sub-states matter</summary>
<p>Planning → Fetching SP-API → Reasoning → tokens. Each phase shows for at least 800ms (no flashing). Aria-live polite for screen readers. The CEO sees the agent is actually doing work, not stalling. Cmd+. universally cancels.</p>
</details>

<details>
<summary>Why Inngest, not Celery</summary>
<p>Inngest is the 2026 LLM-agent ecosystem standard. Durable steps, per-step retry policy, cron triggers, native step.ai.infer primitive. Celery is dated. Temporal is overkill. Phase 1.0 wires the infrastructure but runs the diagnostic inline through FastAPI streaming for simplicity. Inngest takes the load in 1.1 (nightly eval) and 1.5 (Slack delivery).</p>
</details>

<details>
<summary>Why dogfood-first beats concierge</summary>
<p>The founder is a 7-figure Amazon Nutra seller. He <em>is</em> user 1. Building for himself first means real usage from day 1, no GTM friction, and a clear gate to Phase 1.1: the founder's own usage shows real value AND 3 external CEOs commit to pay before code ships. PG playbook.</p>
</details>

---

<!-- _class: lead -->
<!-- _paginate: false -->

![bg brightness:0.08](https://images.unsplash.com/photo-1554224155-6726b3ff858f?w=1400)

# Now the founder uses it

<div style="font-family: 'Raleway'; font-weight: 100; font-size: 0.9em; color: #ffffff66; max-width: 600px; margin-top: 12px;">
Set ANTHROPIC_API_KEY. Connect SP-API. Author 20 real Nutragroup golden questions. Then ask the first real diagnostic and let the eval rig grow from there.
</div>

<div style="display: flex; gap: 8px; margin-top: 24px;">
  <span class="tag" style="background: #007AFF20; color: #007AFFcc; border: 1px solid #007AFF44;">Phase 1.0 shipped</span>
  <span class="tag" style="background: #f5a62320; color: #f5a623cc; border: 1px solid #f5a62344;">Founder gates Phase 1.1</span>
</div>