# DESIGN — PRAHARI

Visual and interaction spec. These tokens are locked. Do not invent values.

---

## 1. Direction

**Reference world:** the district emergency operations room. Radar consoles, IMD cyclone bulletins, nautical survey charts, and the handwritten radio log that sits beside the officer all night.

**The one design decision everything follows from:**

> The interface is monochrome. Colour appears **only** where data is severe.

Every chrome element — panels, rules, labels, buttons, type — is greyscale on a cool chart ground. The IMD warning ladder is the only chromatic vocabulary in the product, and it never decorates. If you see orange on this screen, something is at alert level. Nothing else earns colour.

This is a hard constraint, not a preference. It also does the demo a favour: when the risk map lights up, it is the only colour in the room.

**The signature element:** the dispatch ledger. A full-height monospace append-only log down the right rail, always visible, never collapsible. Timestamped, channel-tagged, unstyled. It reads like a real ops log because it is one — every solve, every fallback, every road closure, in order. It is the thing people will remember, and it is also the thing that proves the system is making decisions rather than drawing pictures.

---

## 2. Banned

Hard bans. If any of these appear, the design has failed.

- **Gradients.** No `linear-gradient`, no `radial-gradient`, no `bg-gradient-to-*`. None. Anywhere.
- Glassmorphism, `backdrop-filter`, translucent frosted panels
- Purple, violet, indigo, magenta — in any form
- Glow effects, coloured shadows, `box-shadow` with any hue
- `border-radius` above `2px`
- Emoji in the UI
- Icon-only buttons without a text label
- Drop shadows to imply elevation — use a hairline rule instead
- Animated background, particles, blobs, mesh, aurora
- Centred hero text with a big number and a small label
- shadcn defaults, Material, Bootstrap, DaisyUI
- Rounded pill badges
- Any colour not in section 3

---

## 3. Colour tokens

```css
:root {
  /* Ground — cool chart slate. Lifted off pure black on purpose:
     black backgrounds crush the low end of the severity ladder. */
  --ground-000: #101A1E;   /* page */
  --ground-100: #17242A;   /* panel */
  --ground-200: #1E2F36;   /* raised: table header, active row */
  --ground-300: #263B44;   /* hairline rules, dividers */
  --ground-400: #34505C;   /* disabled, inactive stroke */

  /* Ink — warm bone on cool ground. The warm/cool tension is the
     whole reason this reads as a chart rather than a dashboard. */
  --ink-000:    #F0EBE1;   /* primary text, headings */
  --ink-100:    #C9C3B8;   /* body */
  --ink-200:    #9A968D;   /* secondary, captions */
  --ink-300:    #6B6862;   /* tertiary, placeholder */

  /* Severity — IMD warning ladder. Data only. Never chrome.
     These are the standard India Meteorological Department
     colour codes; they are not an aesthetic choice. */
  --sev-0:      #4A5D52;   /* normal   — desaturated, recedes */
  --sev-1:      #C9A227;   /* watch    — yellow */
  --sev-2:      #D97B1F;   /* alert    — orange */
  --sev-3:      #C23B22;   /* warning  — red */
  --sev-4:      #7A1E14;   /* severe   — deep red */

  /* System state. Used sparingly, never for emphasis. */
  --state-ok:   #5C8A6E;
  --state-warn: #C9A227;   /* deliberately identical to sev-1 */
  --state-err:  #C23B22;   /* deliberately identical to sev-3 */
}
```

**Severity is the only colour language.** A "Dispatch" button is `--ink-000` on `--ground-200`, not orange. A selected map layer is a `--ink-000` hairline, not a highlight.

---

## 4. Type

```css
--font-display: "IBM Plex Sans Condensed", sans-serif;  /* 600 */
--font-body:    "IBM Plex Sans", sans-serif;            /* 400, 500 */
--font-data:    "IBM Plex Mono", monospace;             /* 400, 500 */
```

One family, three widths. Institutional rather than corporate, free, and not the Inter default that every hackathon ships.

**Role assignment is strict:**

| Role | Face | Size / spacing |
|---|---|---|
| Section eyebrow | Condensed 600, uppercase | 11px / `0.12em` |
| Panel title | Condensed 600 | 15px / `0.02em` |
| Body | Plex Sans 400 | 14px / `1.5` |
| Secondary | Plex Sans 400 | 13px, `--ink-200` |
| **All numerals** | **Plex Mono 500** | tabular, always |
| Coordinates, IDs, timestamps | Plex Mono 400 | 12px |
| Log lines | Plex Mono 400 | 12px / `1.45` |

**Every number in this product is monospace.** Severity scores, qubit counts, solve times, people counts, lat/long. Numbers in a proportional face jitter as they update, and this interface updates constantly. This rule is not negotiable.

Scale: `11 · 12 · 13 · 14 · 15 · 18 · 22 · 28`. Nothing else.

---

## 5. Layout

```
┌──────────────────────────────────────────────────────────────────┐
│ PRAHARI            SRIKAKULAM · 11 OCT 2018 · 14:22 IST     [▼]  │  48px
├───────────┬──────────────────────────────────┬───────────────────┤
│           │                                  │                   │
│  LAYERS   │                                  │  DISPATCH LEDGER  │
│           │            MAP                   │                   │
│  ■ risk   │                                  │  14:22:07 dispat  │
│  □ elev   │                                  │  ch  round 12 so  │
│  ■ roads  │                                  │  lved · 40 zones  │
│  ■ units  │                                  │  · qaoa · 3.1s    │
│           │                                  │                   │
│  ───────  │                                  │  14:22:07 road    │
│           │                                  │  NH516 segment 4  │
│  UNITS    ├──────────────────────────────────┤  impassable       │
│           │                                  │                   │
│  Boat 03  │        REQUEST QUEUE             │  14:21:55 intake  │
│  Boat 07  │   severity-ordered table         │  REQ-0187 queued  │
│  Amb 02   │                                  │  offline          │
│           │                                  │                   │
│  200px    │            fluid                 │      280px        │
└───────────┴──────────────────────────────────┴───────────────────┘
```

- Grid: 8px base. Every dimension is a multiple.
- Panels are separated by a 1px `--ground-300` rule. **No shadows, no gaps, no cards.** The interface is one continuous surface divided by rules, the way a chart is.
- The ledger rail is fixed and never collapses. It is the signature — do not let it become a drawer.
- Below 900px: ledger moves to a bottom sheet at 160px, still always visible. Layers become a top bar.

---

## 6. Components

**Panel**
`background: --ground-100`, `border: 1px solid --ground-300`, `radius: 0`. Header row 32px, `--ground-200`, eyebrow type.

**Table**
Header `--ground-200`, condensed uppercase 11px. Rows 36px, 1px bottom rule `--ground-300`. Hover `--ground-200`. Selected row: 2px left border in the row's severity colour — the only place severity touches chrome, and only because the row *is* the data.

**Severity chip**
12px square, no radius, filled with the band colour, adjacent to a mono numeral. No text inside the chip. No pill.

**Button**
Primary: `--ink-000` text on `--ground-300`, 1px `--ground-400`, 32px tall, radius 2px, condensed uppercase 12px.
Secondary: transparent, 1px `--ground-300`.
Destructive: 1px `--sev-3`, text `--sev-3`. Never a filled red button.

**Map**
Basemap desaturated to greyscale — MapLibre style with all `fill-color` on `--ground-*`, labels `--ink-200`. The basemap must not compete. Risk choropleth uses the five severity fills at `0.55` opacity. Roads: passable `--ink-300` 1px, impassable `--sev-3` 1.5px dashed. Units: 8px squares, not pins, not circles. Requests: 6px squares in their severity colour.

**Ledger line**
```
14:22:07  dispatch  round 12 solved · 40 zones · qaoa · 3.14s
──mono    ──chan    ──message
--ink-300  --ink-200   --ink-100
```
Channel tag is condensed uppercase 10px. New lines enter with an 80ms opacity fade — no slide, no bounce. Severity ≥ 3 lines get a 2px left border in `--sev-3`.

**Benchmark table**
Four rows, one per solver. Columns: backend · objective · solve time · constraints valid · qubits. The winning row is marked with a `--ink-000` left border, **whichever solver wins**. Do not style QAOA as the hero. The table's credibility is the point.

---

## 7. Motion

Almost none. This is an emergency console, not a landing page.

- Transitions: 120ms `ease-out`, opacity and background only. Never transform, never scale.
- Ledger entries: 80ms opacity fade in.
- Map layer toggle: instant.
- Solve in progress: a 2px `--ink-200` bar at the top of the dispatch panel, indeterminate, 1200ms cycle. No spinner.
- `prefers-reduced-motion`: everything becomes instant.

**Banned:** page-load sequences, scroll reveals, hover lift, parallax, count-up numerals, skeleton shimmer.

---

## 8. Copy

Sentence case. Active voice. Plain verbs.

| Write | Not |
|---|---|
| Dispatch | Submit |
| Dispatched | Success! |
| No open requests. Requests appear here as they arrive. | No data |
| Solver timed out. Fell back to simulated annealing. | Something went wrong |
| 3 units offline | ⚠ Warning: units unavailable |
| Rescue units | Resources |
| Zones | Clusters |

An action keeps its name through the whole flow: the button says **Dispatch**, the toast says **Dispatched**, the log says **dispatched**.

Errors say what happened and what to do. They do not apologise. Empty states are instructions, not decoration.

Never write: leverage, seamless, powerful, revolutionize, cutting-edge, harness, unlock, empower.

---

## 9. Quantum in the UI

Wherever the interface mentions the solver:

- The backend is shown as a plain label: `qaoa` · `annealing` · `ortools` · `greedy`. Lowercase, mono, no badge, no icon.
- A fallback is stated, not hidden: `qaoa timed out → annealing`.
- The benchmark table shows real numbers including losses.
- Qubit count is displayed as a fact: `20 qubits · zone 07`.

**Nowhere in the UI does the word "quantum" appear next to a claim of speed or superiority.** No "quantum-powered", no lightning icon, no purple. Treat it as an implementation detail shown honestly, and it becomes more credible than any badge.

---

## 10. Quality floor

- Responsive to 380px
- Visible keyboard focus: 2px `--ink-000` outline, 2px offset. Never `outline: none`.
- Contrast: `--ink-100` on `--ground-100` ≥ 7:1
- Severity is never encoded by colour alone — always paired with a mono numeral or a text band label. An emergency system that fails for a colour-blind officer is a broken emergency system.
- All interactive elements ≥ 32px tall, ≥ 44px on touch
