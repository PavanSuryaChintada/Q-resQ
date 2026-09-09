# CITIZEN APP — design and flow

Complete specification for `apps/citizen`. This supersedes any prior citizen-app styling.

**Read `docs/DESIGN.md` first.** This document inherits its tokens and its ban list, and adapts them for a different context.

---

## 0. Fix the build before reading the rest

The current build renders unstyled HTML — serif type, default table borders, no layout. That is not a design problem. The stylesheet is not loading.

Check, in order:

1. **Is Tailwind compiling?** `tailwind.config.js` `content` must include `./index.html` and `./src/**/*.{ts,tsx}`. If the glob misses, Tailwind emits an empty stylesheet and every class silently does nothing.
2. **Is the CSS entry imported?** `main.tsx` needs `import './styles/index.css'`, and that file needs the `@tailwind` directives.
3. **Is the built CSS 404ing?** Open devtools → Network. If `assets/index-*.css` fails, it is a `base` path problem in `vite.config.ts`. Serving from a subpath with `base: '/'` breaks asset URLs.
4. **Are those `<table>` elements real?** The nav renders as a bordered table in the screenshot. If that is an actual `<table>`, rewrite it as flex — a nav is not tabular data.

No amount of design specification fixes a missing stylesheet. Fix this first.

---

## 1. Design direction

The admin console is a dark operations console for a control room. **The citizen app is its light counterpart.**

Same design language, inverted ground, for a different context:

| | Admin | Citizen |
|---|---|---|
| Where | Indoors, desk, controlled light | **Outdoors, daylight, rain** |
| Who | Trained officer, daily use | **Anyone, once, under stress** |
| Device | Desktop | **Phone, one hand, possibly wet** |
| Ground | Dark slate | **Light bone** |

Dark backgrounds are unreadable in direct sun. The ground inverts; **everything else carries** — the same IMD warning ladder, the same type, the same zero-radius geometry, the same ban list.

This is a defensible design decision, not a departure. Say so if asked: same system, different environment.

### Tokens

```css
:root {
  /* Ground — warm bone. Readable in sunlight. */
  --ground-000: #F4F1EA;   /* page */
  --ground-100: #FFFFFF;   /* card */
  --ground-200: #E8E3D8;   /* raised / pressed */
  --ground-300: #D2CCBE;   /* hairline rules */
  --ground-400: #A8A091;   /* disabled */

  /* Ink — near-black, high contrast */
  --ink-000: #14181A;      /* primary */
  --ink-100: #3A4145;      /* body */
  --ink-200: #6B7276;      /* secondary */
  --ink-300: #9AA0A3;      /* placeholder */

  /* Severity — IMD warning ladder, UNCHANGED from the admin console.
     Darkened slightly for contrast on light ground. */
  --sev-0: #3D6B4F;        /* normal   */
  --sev-1: #B8901F;        /* watch    */
  --sev-2: #C26A15;        /* alert    */
  --sev-3: #B02E18;        /* warning  */
  --sev-4: #6E1810;        /* severe   */

  --emergency: #B02E18;    /* = sev-3. The SOS button. Nothing else uses it. */
}
```

### Type

```css
--font-display: "IBM Plex Sans Condensed", sans-serif;
--font-body:    "IBM Plex Sans", sans-serif;
--font-data:    "IBM Plex Mono", monospace;
```

**Minimum body size is 16px.** This is not the admin console — it is read outdoors, in poor light, possibly by someone in distress. Scale: `14 · 16 · 18 · 22 · 28 · 36`.

All numerals in mono, as in the admin console.

### Bans — inherited, unchanged

No gradients. No glassmorphism. No purple. No glow. No `border-radius` above 2px. **No emoji.** No shadows for elevation — use a hairline rule.

Colour encodes severity only. The SOS button is the single exception, and it uses `--sev-3`, not a new colour.

### Touch

- Every tappable target **≥ 56px tall**. Not 44. This is used one-handed in the rain.
- SOS button ≥ 96px.
- 16px minimum between adjacent targets.
- No hover states. There is no hover on a phone.

---

## 2. Screen map

```
FIRST RUN                    MAIN
┌──────────────┐            ┌──────────────┐
│  1 Welcome   │            │   4 Home     │◄──────┐
│  what this   │            │  risk · SOS  │       │
│  app does    │            │  report ·    │       │
└──────┬───────┘            │  alerts      │       │
       ▼                    └──┬───┬───┬───┘       │
┌──────────────┐               │   │   │           │
│  2 Details   │               ▼   ▼   ▼           │
│  name, phone │        ┌──────┐ ┌────┐ ┌───────┐  │
│  household,  │        │ 5 SOS│ │ 6  │ │ 7     │  │
│  contact     │        │      │ │Rep-│ │Alerts │  │
└──────┬───────┘        │      │ │ort │ │       │  │
       ▼                └───┬──┘ └─┬──┘ └───────┘  │
┌──────────────┐            │      │               │
│  3 Location  │            ▼      ▼               │
│  permission  │        ┌──────────────┐           │
│  + why       │        │  8 Status    │───────────┘
└──────┬───────┘        │  sent/queued │
       └────────────────►  + progress  │
                        └──────────────┘
                        ┌──────────────┐
                        │  9 Profile   │
                        │  edit, clear │
                        └──────────────┘
```

---

## 3. First run

Three screens. Skippable except location. **Under 60 seconds.**

### Screen 1 — Welcome

```
Q-ResQ

Landslide warning for Aizawl district

We tell you when a slope near you is
at risk, and let you call for help
if you need it.

Works without signal.

              [ Continue ]
```

Plain statement of what the app does. No marketing.

### Screen 2 — Your details

The rationale line matters — people abandon forms that do not explain themselves.

```
Your details

If you send an emergency alert, we
send this with it. It saves you typing
when you have no time.

Name              [                    ]
Phone             [                    ]
People in your
household         [  4  ]  − +
Village / area    [                    ]

Emergency contact (optional)
Name              [                    ]
Phone             [                    ]

Anything responders should know?
(optional)
[                                      ]
e.g. elderly resident, someone who
cannot walk

         [ Skip ]      [ Save ]
```

**Storage: local only.** IndexedDB on the device. Not uploaded until an SOS or a report is sent. Say this on screen:

> Stored on your phone. Only sent when you ask for help.

That sentence is worth including for its own sake and it is also the right answer if a panel asks about data handling.

The free-text field is deliberately open rather than a medical checklist. Responders need operational context, and an open field avoids collecting structured health records.

### Screen 3 — Location

```
Location

We use your location to:
  ■  warn you about slopes near you
  ■  tell responders where you are

Only while the app is open. Never in
the background.

      [ Not now ]   [ Allow location ]
```

**The app must remain fully usable if declined.** Manual map pin for reports, manual area entry for SOS. Never dead-end on a denied permission.

---

## 4. Home

The only screen most people will see. One glance answers: *am I in danger, and what do I do?*

```
┌────────────────────────────────────┐
│ Q-ResQ            ● Online   [≡]   │  56px
├────────────────────────────────────┤
│                                    │
│  YOUR AREA                         │
│  ■ ALERT                           │  ← sev colour block + word
│  Chaltlang                         │
│                                    │
│  Heavy rain over the last 3 days.  │
│  Slopes near you are at raised     │
│  risk.                             │
│                                    │
│  Updated 14:22            [ Map ]  │
├────────────────────────────────────┤
│                                    │
│  ┌──────────────────────────────┐  │
│  │                              │  │
│  │        EMERGENCY             │  │  96px
│  │   I need help right now      │  │  --sev-3
│  │                              │  │
│  └──────────────────────────────┘  │
│                                    │
│  ┌──────────────────────────────┐  │
│  │  Report what you see         │  │  64px
│  │  Cracks, slipping, blocked   │  │
│  └──────────────────────────────┘  │
│                                    │
│  ┌──────────────────────────────┐  │
│  │  Alerts                   2  │  │  64px
│  └──────────────────────────────┘  │
│                                    │
├────────────────────────────────────┤
│  2 reports waiting to send    [→]  │  only when queue is non-empty
└────────────────────────────────────┘
```

### Risk banner

Full-width block in the severity colour, with the band **spelled out in words** beside a filled square. Severity is never colour alone — that rule is inherited and it matters more here, because a colour-blind user in an emergency is a failure case, not an edge case.

| Band | Word | Message |
|---|---|---|
| 0 | NORMAL | No raised risk in your area. |
| 1 | WATCH | Conditions are being monitored. |
| 2 | ALERT | Slopes near you are at raised risk. |
| 3 | WARNING | High risk. Be ready to move. |
| 4 | SEVERE | Move to safe ground now. |

### Connection status

Three states, in the header, always visible:

```
● Online          --sev-0
● No signal       --ink-200        "Saved on your phone"
● Sending…        --sev-1
```

Never hide offline state. A user who does not know their report is queued will send it five more times.

---

## 5. SOS

The single most important flow. **Design principle: nobody fills a form during an emergency.**

Everything comes from the profile. The user confirms, they do not compose.

### 5.1 Tap → countdown

```
┌────────────────────────────────────┐
│                                    │
│        SENDING IN                  │
│                                    │
│             3                      │  72px mono
│                                    │
│   Your location and details will   │
│   be sent to the district          │
│   emergency team.                  │
│                                    │
│  ┌──────────────────────────────┐  │
│  │          CANCEL              │  │  96px
│  └──────────────────────────────┘  │
│                                    │
└────────────────────────────────────┘
```

Three seconds. Long enough to cancel a pocket tap, short enough not to matter in a real emergency. Countdown in mono, very large.

**Do not** require a long-press or a slide-to-confirm. Those fail with wet hands, gloves, and shaking.

### 5.2 Sent

```
┌────────────────────────────────────┐
│  ■ SENT                            │
│                                    │
│  Your emergency alert has been     │
│  received by the district team.    │
│                                    │
│  Sent at        14:26:31           │  mono
│  Reference      SOS-0184           │  mono
│  Location       23.7412, 92.7180   │  mono
│  People         4                  │
│                                    │
│  ────────────────────────────────  │
│                                    │
│  What happens next                 │
│  ■ Received                        │
│  □ Being assessed                  │
│  □ Help assigned                   │
│                                    │
│  ┌──────────────────────────────┐  │
│  │   Add more information       │  │
│  └──────────────────────────────┘  │
└────────────────────────────────────┘
```

The reference number matters — it is what someone reads out over a phone call.

The three-step progress tracks real request status (`open` → `assigned` → `in_progress`) via Realtime. **Do not fake progress.** If the state does not change, the display does not change.

### 5.3 Sent while offline

```
┌────────────────────────────────────┐
│  ■ SAVED — NO SIGNAL               │  --sev-1
│                                    │
│  Your alert is saved on your       │
│  phone. It will send the moment    │
│  you have signal.                  │
│                                    │
│  Do not close the app.             │
│                                    │
│  Saved at       14:26:31           │
│  Trying again…                     │
│                                    │
│  ────────────────────────────────  │
│                                    │
│  If you can, also:                 │
│  ■  Call 112                       │
│  ■  Move to open, flat ground      │
│  ■  Tell a neighbour               │
└────────────────────────────────────┘
```

**Never say "sent" when it is queued.** In an emergency that is the most damaging possible lie, and a judge will test exactly this.

The fallback actions matter. If the app cannot reach anyone, it should say what a person can actually do.

### 5.4 Add more information

Optional, after the SOS is away. Photo, free text, adjust people count. Never blocks the initial send.

---

## 6. Report

For hazards observed, not emergencies. Four steps, one per screen.

```
STEP 1 — What did you see?

  ┌──────────────────────────────┐
  │  Crack in the ground         │  64px each
  └──────────────────────────────┘
  ┌──────────────────────────────┐
  │  Slope slipping or bulging   │
  └──────────────────────────────┘
  ┌──────────────────────────────┐
  │  Road blocked                │
  └──────────────────────────────┘
  ┌──────────────────────────────┐
  │  Water coming out of a slope │
  └──────────────────────────────┘
  ┌──────────────────────────────┐
  │  Something else              │
  └──────────────────────────────┘
```

Plain descriptions, not jargon. "Water coming out of a slope" — not "seepage."

```
STEP 2 — Photo

  ┌──────────────────────────────┐
  │       Take a photo           │  96px
  └──────────────────────────────┘
  ┌──────────────────────────────┐
  │     Choose from gallery      │
  └──────────────────────────────┘
              Skip photo

  [after capture, on-device classifier:]

  ┌──────────────────────────────┐
  │  [ photo thumbnail ]         │
  │                              │
  │  This looks like a crack     │
  │  Not right?  [ Change ]      │
  └──────────────────────────────┘
```

**"This looks like"** — never "detected." The classifier is triage assistance and the user can always override it. Present the correction affordance prominently; a wrong label the user cannot fix is worse than no label.

```
STEP 3 — Where

  [ map with a draggable pin ]

  Using your location
  23.7412, 92.7180  ±12m           mono

  [ Move the pin ]

STEP 4 — Anything to add?  (optional)

  [                              ]

  ┌──────────────────────────────┐
  │       Send report            │
  └──────────────────────────────┘
```

If location is denied, step 3 opens with a map centred on the last known area and requires a manual pin. **Never block on permission.**

---

## 7. Alerts

```
┌────────────────────────────────────┐
│  Alerts                            │
├────────────────────────────────────┤
│  ■ WARNING          14:02 today    │
│  Chaltlang, Zemabawk               │
│                                    │
│  High risk of slope failure over   │
│  the next 12 hours. Avoid the      │
│  hillside road. Be ready to move.  │
│                                    │
│  [ What should I do? ]             │
├────────────────────────────────────┤
│  ■ WATCH             09:30 today   │
│  Aizawl district                   │
│  Heavy rain expected. Conditions   │
│  being monitored.                  │
├────────────────────────────────────┤
│  ── older ──                       │
└────────────────────────────────────┘
```

Sorted newest first. Severity square plus the band word. Geo-fences are cached and **evaluated on-device**, so alerts work with no signal — which is the point, since losing connectivity is exactly when an alert matters most.

"What should I do?" expands to concrete actions for that band. Not generic advice — band-specific.

---

## 8. Profile

```
Your details            [ Edit ]

Name         Lalthanpuii
Phone        +91 98••• •••21
Household    4 people
Area         Chaltlang

Emergency contact
             Lalrinawma  +91 98••• •••44

Notes        Elderly resident on ground floor

────────────────────────────────────

Location     ■ Allowed        [ Change ]
Language     English

────────────────────────────────────

Your data is stored on this phone.
It is sent only when you send an
alert or a report.

[ Delete my details ]
```

Phone numbers partially masked in display. Delete must actually delete — clear IndexedDB, not just hide.

---

## 9. Offline behaviour

| State | Home banner | Behaviour |
|---|---|---|
| Online | `● Online` | Normal |
| Offline, empty queue | `● No signal` | All actions still work, submissions queue |
| Offline, queued | `● No signal · 2 waiting` | Footer shows queue with a manual retry |
| Reconnecting | `● Sending…` | Auto-flush, then per-item confirmation |

**A service worker is not required for this.** IndexedDB works in a plain page. What a service worker adds is loading the *app* while offline; queueing submissions while the app is already open needs only `navigator.onLine`, an `online` event listener, and IndexedDB.

If the PWA build is unavailable, the queue still works — say so honestly: *"Submissions queue in IndexedDB. Full offline app loading requires the PWA build, which is configured but not in this build."*

Every queued item shows its own state. Never a single global spinner.

---

## 10. Copy rules

| Write | Not |
|---|---|
| Saved on your phone. Will send when you have signal. | Offline mode |
| Sent to the district team | Success! |
| This looks like a crack | Crack detected |
| No signal | Network error |
| Move to safe ground now | SEVERE ALERT ⚠️ |
| I need help right now | SOS |
| What happens next | Status tracker |

Short sentences. Second person. No jargon: not "geofence," not "severity index," not "deformation."

**Never** claim something was sent when it was queued.

---

## 11. Build order

Six days is gone; build in this order and stop wherever you run out.

1. **Fix the CSS.** Nothing else matters until the app renders.
2. Home with the risk banner and connection status
3. SOS: countdown → send → sent/queued states
4. Profile capture (first run screens 2–3)
5. Report flow, steps 1–4
6. Alerts list
7. Profile edit and delete
8. Welcome screen

Items 1–3 are the demo. Everything after strengthens it.

---

## 12. Quality floor

- Contrast: `--ink-100` on `--ground-000` ≥ 7:1
- Every target ≥ 56px, SOS ≥ 96px
- Severity never encoded by colour alone — always paired with the band word
- Works fully with location denied
- Works fully offline, including SOS
- Visible focus outline: 2px `--ink-000`, 2px offset
- No layout shift when the connection state changes — reserve the space
