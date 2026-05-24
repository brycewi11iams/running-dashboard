# Running Dashboard — Claude Context

## Project at a glance
- **Live site:** https://brycewi11iams.github.io/running-dashboard/
- **Repo:** https://github.com/brycewi11iams/running-dashboard
- **Stack:** Single-file static site — all CSS, HTML, and JS live in `index.html`. No build step, no framework, no bundler. Deployed via GitHub Pages from `main`.
- **Other files:** `data/daily.json` (Coros run data, pushed by a separate Claude chat via Coros MCP + GitHub MCP), `data/userdata.json` (health sync file, written by the dashboard itself via GitHub API)

## Permissions
You have full permission to read and edit `index.html` directly — no need to ask. Make changes, commit, and push to `main` without confirmation unless the change is architecturally significant or destructive.

## Working rule — never read the whole file
`index.html` is ~3700 lines. Always use **Grep** to find the exact lines needed, then **Read** only that range. Full-file reads are slow and almost never necessary.

---

## Storage layer

Three layers, innermost is fastest:

| Layer | Purpose |
|---|---|
| `localStorage` | Instant read/write cache — source of truth for rendering |
| Firebase Firestore | Legacy cross-device sync (compat SDK v10.12.0). Test-mode rules expired in the past — may not be writing reliably. |
| `data/userdata.json` | Primary cross-device sync via GitHub API |

### Storage helpers (defined early in `<script>`)
```
storeGet(k)        → JSON.parse(localStorage.getItem(k))
storeSet(k,v)      → writes localStorage + Firestore + schedules GitHub push
storeDel(k)        → removes from localStorage + Firestore
storeKeys(pfx)     → all localStorage keys starting with pfx
```

`storeSet` automatically calls `_scheduleGhPush()` when the key starts with a synced prefix.

### Health data helpers
```
hGet(date)     → storeGet('health:'+date)  — returns object with sleep/hrv/rhr/mood/water/etc.
hSet(date,v)   → storeSet('health:'+date, v)
```

### Key prefixes
| Prefix | Content |
|---|---|
| `health:YYYY-MM-DD` | Sleep, HRV, RHR, mood/energy stars, water oz, tiredness, soreness |
| `runs:YYYY-MM-DD` | Array of run objects `{dist, dur, pace, hr, effort, notes, shoeId, temp, humidity, rest}` |
| `elyte:YYYY-MM-DD` | Liquid IV / electrolyte count |
| `note:YYYY-MM-DD` | Daily notes text |
| `goals:YYYY-MM-DD` | Array of goal objects |
| `narrative:YYYY-MM-DD` | Weekly reflection text (keyed to week's Monday) |
| `weather:YYYY-MM-DD` | `{temp, humidity}` — written when user enters temp/humidity on a run |
| `coros_daily:YYYY-MM-DD` | Raw Coros data from `data/daily.json` |
| `shoe:*` | Shoe objects |

---

## Date system
```
activeDate()   → YYYY-MM-DD string using a 5 AM boundary (before 5 AM = yesterday)
localYMD(dt)   → formats a Date object as YYYY-MM-DD in local time
lastNDays(n)   → array of n date strings ending with activeDate()
```

---

## GitHub sync
- **Read:** `loadGhUserdata()` — fetches `data/userdata.json` from raw GitHub URL (public, no auth). Called on init.
- **Write:** `_ghPush()` — writes synced keys to `data/userdata.json` via GitHub API PUT. Debounced 30s via `_scheduleGhPush()`.
- **Token:** Stored in `localStorage['gh_token']` only — never in source code. User sets it via the **⚙ Sync Settings** panel at the very bottom of the page.
- **Synced prefixes:** `health:`, `elyte:`, `note:`, `goals:`, `narrative:`
- **Constants (top of `<script>`):** `GITHUB_REPO`, `GITHUB_BRANCH`, `USERDATA_PATH`, `GH_SYNC_PREFIXES`, `getGhToken()`

---

## Coros sync
- A **separate Claude chat** (uses Coros MCP + GitHub MCP) fetches today's Coros data and pushes it to `data/daily.json`.
- `loadCorosData()` fetches `./data/daily.json` on init. Auto-fills `sleep`, `hrv`, `rhr` in `health:today` if those fields are still null.
- Weather/temp/humidity from Coros runs goes to `weather:YYYY-MM-DD` via the run's inline edit temp/humidity fields.
- Coros data also powers: Recovery Trend panel, Weekly Training Load chart, 7-Day Feel Recap.

---

## Key JS functions (grep to find exact lines)

| Function | What it does |
|---|---|
| `calcReadinessScore(d)` | Readiness 0–100. Weights: sleep 30%, HRV 30%, tiredness 25%, energy/mood 15%. Returns `{score, cls, labelText, summary, sleepRec}` |
| `updateReadiness()` | Reads today's health data, calls `calcReadinessScore`, updates score card + ring badge |
| `loadHealth()` | Renders all health metric displays + sparklines, calls `updateReadiness()` |
| `loadMorningReadiness()` | Renders soreness/fatigue star inputs |
| `renderHeatAdjCallout()` | Shows heat-adjusted pace banner. Reads `weather:today`. Only shows if heat index adds ≥10 sec/mi |
| `loadRunLog()` | Renders the full run log table including inline edit rows (effort, shoe, notes, temp, humidity) |
| `loadCorosData()` | Fetches `data/daily.json`, auto-fills health, triggers Coros panels |
| `loadGhUserdata()` | Pulls `data/userdata.json` from GitHub, merges into localStorage |
| `_scheduleGhPush()` | Debounces `_ghPush()` 30s |
| `_reRenderAll()` | Full re-render of all sections — called after Firestore/storage sync |
| `onNewDay()` | Called when `activeDate()` changes — resets daily fields, re-renders everything |
| `renderFeelRecap()` | 7-Day Feel Recap chart: sleep score (blue), HRV relative (green), run effort (orange) — all drawn as connected lines |
| `renderRecoveryTrend()` | Coros recovery % panel + 7-day sparkline |
| `renderTrainingLoadPanel()` | Weekly Training Load chart from Coros data |
| `calcHeatIndex(T,RH)` | Returns heat index °F |
| `calcHeatAdjSec(T,RH)` | Returns sec/mi pace adjustment for heat |
| `getAllRuns()` | All runs across all dates, each annotated with `_runDate` and `_runIdx` |
| `storeSet / storeGet / storeDel / storeKeys` | Storage abstraction — always use these, never localStorage directly |

---

## Page sections (HTML order, top → bottom)
1. Page title + date
2. Goal ticker (live scrolling)
3. Day ring (progress + phase + readiness badge)
4. Weekly summary strip (run streak, miles, sleep, HRV, energy, water, goals, XT, strength, Liquid IV)
5. Weekly miles target bar
6. **Running** — run log, inline edit rows, pace chart, mileage chart, training load, feel recap
7. **Health & Fitness** — water, electrolytes, iron, vitamins, morning readiness, readiness score, Coros recovery, sweat calc, daily notes, shoe tracker
8. **To Do List** — today's goals + plan tomorrow
9. **Weekly Reflection** — narrative textarea
10. **⚙ Sync Settings** — GitHub PAT input (collapsed by default)

---

## Run object shape
```js
{
  dist: Number,       // miles
  dur: String,        // "H:MM:SS" or "MM:SS"
  pace: String,       // "M:SS /mi"
  hr: Number|null,    // avg heart rate bpm
  effort: Number|null,// 1–10, manually entered
  notes: String,      // free text
  shoeId: String|null,// references shoe key
  temp: Number|null,  // °F, entered in inline edit row
  humidity: Number|null, // %, entered in inline edit row
  rest: Boolean,      // true = rest day log
  date: String        // YYYY-MM-DD (on Coros-pushed runs)
}
```

---

## CSS conventions
- CSS variables: `--text-primary`, `--text-secondary`, `--text-tertiary`, `--font-mono`
- Card class: `.gm-card` — standard dark rounded card
- Section class: `.section` + `.section-title`
- Eyebrow label: `.gm-ey`
- Health metric inputs: `.hm-input`, `.hm-lbl`, `.hm-item`, `.health-grid`
- Run inline edit: `.run-edit-inp`, `.run-edit-field`, `.run-edit-lbl`, `.run-edit-fields`
- Star inputs built with `buildStars(el, value, onChange)`

---

## Important notes
- **No Morning Conditions card** — was removed; temp/humidity now comes from run inline edit fields
- **No body map** — was added then removed entirely
- **Firestore** may have expired security rules — data loss risk; GitHub sync is the reliable path
- **Energy/mood stars** re-trigger readiness score live — no page reload needed
- **Effort in Feel Recap** only appears for runs where user manually entered 1–10; Coros doesn't provide effort
