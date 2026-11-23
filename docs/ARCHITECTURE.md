# Avsar architecture

**Separation:** `frontend/` = presentation only (no secrets, no DB access, no scraping). `backend/` = everything else:
`worker/` (always-on API + bot), `scanner/` (scheduled collector), `database/` (schema). The only link between them is
the Worker's REST API: `GET /api/items`, `POST /api/status`, `GET /api/institutes`, `POST /api/institute` (Bearer token).

```mermaid
flowchart LR
  subgraph Sources
    P[Institute / fest / club pages]:::s
    F[Google Alerts RSS feeds]:::s
    A[Devfolio / Unstop]:::s
    POST[Poster photo from user]:::s
  end
  subgraph GitHub Actions - scheduler
    S[scan.py<br/>fetch + hash-skip]-->L[LLM extractor<br/>free OpenAI-compatible or Claude]
    L-->T[Trust scorer<br/>domain, scam text, RDAP age]
    T-->M[Matcher<br/>interests + synonyms]
    R[Reminders 7/3/1/0d + weekly digest]
  end
  subgraph Cloudflare Worker - always on
    W[Telegram webhook<br/>commands + buttons]
    API[REST API + calendar .ics]
    V[Poster reader - vision LLM]
  end
  DB[(Supabase Postgres<br/>users items user_items meta inbox)]
  TG[Telegram]:::c
  D[Web dashboard<br/>GitHub Pages]:::c
  P & F & A --> S
  S <--> DB
  M --> TG
  R --> TG
  TG <--> W
  W <--> DB
  D -->|Bearer token| API
  API <--> DB
  POST --> W --> V --> DB
  DB -->|inbox| S
  classDef s fill:#fff3e0;classDef c fill:#e8f5e9;
```

## Components
| Layer | Tech | Job |
|---|---|---|
| Collector | Python (stdlib), GitHub Actions cron: scan 2×/day, remind every 3h | fetch pages, skip unchanged (hash), extract, score, notify |
| Extractor | any OpenAI-compatible LLM (free) or Claude + web search | text → structured JSON (name, inst, type, deadline, fee, link, brochure, tags) |
| Trust scorer | pure Python + RDAP | 0-100 legit score + reasons |
| Matcher | keyword + synonym | 1 hit = alert, 2+ = auto-track |
| Bot/API | Cloudflare Worker (JS) | instant replies, buttons, /login, dashboard API, calendar feed, poster OCR |
| DB | Supabase Postgres, RLS on, service key only server-side | users, items, user_items(status), meta, inbox |
| UI | Telegram + static dashboard (GitHub Pages) | tabs Remaining/Applied/New/Skipped, sort, filter, search |

## Institute registration flow
User/institute submits (bot or dashboard) → `institutes` row `pending` → admin gets alert with domain check → `/approve` →
next scan adds its website + pages as sources, hosts join the trusted-domain list (trust +25). Guards: https only, SSRF block
(private IPs/localhost) in Worker and scanner, 3-pending cap, admin approval before anything is fetched.

## Key flows
1. **Scan**: cron → fetch sources → hash unchanged? skip → LLM extracts → dedupe id=md5(normalised name+deadline) → trust score → insert → alert each matching user (trust<25 never sent).
2. **Reminder**: tracked & not applied → message at 7/3/1/0 days (dedupe via `rem[]`). Applied items stop reminding.
3. **Login**: /login → Worker signs a 30-day HMAC token for your chat id → dashboard link + calendar link. No passwords; revoke by rotating SESSION_SECRET.
4. **Poster**: photo → vision LLM → `inbox` → next job verifies (trust) → added to that user's list only.

## Security
RLS blocks the public key; secrets only in Worker/GitHub secrets; webhook verified by secret header; tokens HMAC-signed with expiry;
all scraped text escaped in the dashboard; links open with noopener. Calendar URL contains the token: treat as private.

## Scaling and limits
One scan serves all users (LLM cost independent of user count). Telegram sends are throttled (~16/s). Free tiers are enough for hundreds of users;
beyond ~1k users move scheduling to a small VPS and add a queue. Known limits: no Instagram API (only public pages/feeds), trust score is heuristic.
