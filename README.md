```
avsar/
├─ frontend/                 web dashboard (static, GitHub Pages)      ← UI only
│  └─ index.html
├─ backend/                                                            ← all logic + data
│  ├─ worker/                Telegram bot + REST API + .ics feed (Cloudflare)
│  ├─ scanner/               scan.py + config.json (GitHub Actions job)
│  └─ database/              Postgres schema + migrations (Supabase)
├─ .github/workflows/        avsar.yml (backend jobs) · pages.yml (frontend deploy)
├─ docs/                     ARCHITECTURE.md · SETUP_GUIDE.md
└─ setup.sh                  one-command setup
```
Frontend ↔ backend contract: the dashboard only calls the Worker's `/api/*` endpoints with a Bearer token
(API address + token arrive in the /login link). Nothing else is shared.

# Avsar v3 – contests + internships radar (multi-user, Telegram + web dashboard)
See ARCHITECTURE.md for the design. Quick setup (~30 min, all free tiers except an optional paid LLM):

1. **Telegram**: @BotFather → /newbot → TOKEN. Message your bot once, then open
   https://api.telegram.org/botTOKEN/getUpdates to read your own chat id (= ADMIN_CHAT_ID).
2. **Supabase**: new project → SQL Editor → run `backend/database/schema.sql` (already on v2? run `migrate_from_v2.sql`).
   Settings → API: copy Project URL + `service_role` key (secret!).
3. **GitHub**: new PUBLIC repo with all files (keep `.github`). Settings → Pages → Source: GitHub Actions (deploys `frontend/`) →
   note the page URL (= DASHBOARD_URL, e.g. https://you.github.io/avsar/).
4. **Cloudflare Worker**: paste `backend/worker/index.js`. Add these as Secrets/Variables:
   TELEGRAM_TOKEN, SUPABASE_URL, SUPABASE_SERVICE_KEY, WEBHOOK_SECRET (random), SESSION_SECRET (random, long),
   DASHBOARD_URL, WORKER_URL (the worker's own https URL), ADMIN_CHAT_ID,
   LLM_BASE_URL, LLM_MODEL, LLM_API_KEY (only for poster photos; model must support images).
5. **Webhook** (open once in a browser):
   https://api.telegram.org/botTOKEN/setWebhook?url=WORKER_URL&secret_token=WEBHOOK_SECRET
6. **GitHub → Settings → Secrets → Actions**: TELEGRAM_TOKEN, SUPABASE_URL, SUPABASE_SERVICE_KEY, ADMIN_CHAT_ID,
   LLM_BASE_URL, LLM_MODEL, LLM_API_KEY (free LLM, see below). Optional paid mode: ANTHROPIC_API_KEY + Variable PROVIDER=anthropic.
7. Actions → avsar → Run workflow. Share t.me/YOUR_BOT. Users: /start → /interests → /login.

## Free LLM options (limits change, check them)
Google AI Studio `https://generativelanguage.googleapis.com/v1beta/openai` · Groq `https://api.groq.com/openai/v1` ·
OpenRouter `https://openrouter.ai/api/v1` (":free" models) · Ollama on your own PC `http://localhost:11434/v1`.

## Adding sources (backend/scanner/config.json → "sources")
Institute fest/club/placement/internship pages, Devfolio/Unstop pages, Google Alerts RSS feeds
(alert "IIT Bombay summer internship" → deliver to RSS feed). Static pages/feeds work best; JavaScript-only pages
come back empty. Unchanged pages cost zero LLM calls. 3 failures in a row → you get an admin alert.

## User commands
/start /interests /login /list /github <user> /stop /resume /delete (+ photo of a poster). Admin: /stats.

## Institute registration
Anyone can register an institute: bot `/addinstitute Name | https://site | https://page1,https://page2 | contact | info`
or the dashboard's 🏛 Institutes tab. Max 3 pending per person, https only, private/internal addresses blocked.
You (ADMIN_CHAT_ID) get a message with an official-domain check and approve with `/approve ID` or `/reject ID`.
Approved institutes are scanned automatically and their domains earn a trust bonus. Run `backend/database/migrate_v3_institutes.sql`
if your database is already on v3. Institutes keep publishing on their own site; Avsar reads those pages (no posting API).

## Reliability check
Every item gets a 0-100 trust score from: institute (.ac.in/.edu.in) vs lookalike domains, shorteners, IP links, risky
TLDs, http, domain age (RDAP), and scam wording (fees/UPI/deposits/WhatsApp-only). <25 is never sent; <40 is flagged 🚩.
It is a risk signal, NOT a guarantee: always confirm on the institute's own website.

## Not included yet
Team finder, WhatsApp/email/web-push alerts, embedding-based matching (synonym matching is used), CV upload review,
admin web panel.
