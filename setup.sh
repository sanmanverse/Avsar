#!/usr/bin/env bash
# Avsar one-command setup. Run from this folder:  bash setup.sh
# Secrets are typed hidden, kept in memory/temp files only, and pushed to Cloudflare + GitHub secrets.
set -euo pipefail
cd "$(dirname "$0")"
say(){ printf '\n\033[1m%s\033[0m\n' "$*"; }
die(){ printf '\033[31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }
need(){ command -v "$1" >/dev/null 2>&1 || die "Missing '$1'. $2"; }
need git "Install git"; need python3 "Install Python 3"; need curl "Install curl"
need npx "Install Node.js 18+ from nodejs.org"; need gh "Install GitHub CLI from cli.github.com"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
ask(){ # ask VAR "prompt" [secret|""] [default]
  local p="$2" s="${3:-}" d="${4:-}" x
  [ -n "$d" ] && p="$p [$d]"
  if [ "$s" = "secret" ]; then read -rsp "$p: " x; echo; else read -rp "$p: " x; fi
  x="${x:-$d}"; [ -n "$x" ] || die "$2 is required"
  printf -v "$1" '%s' "$x"
}
rnd(){ python3 -c 'import secrets;print(secrets.token_hex(24))'; }

say "Step 1/7: your details (hidden input, never written to disk)"
ask TELEGRAM_TOKEN "Telegram bot token (from @BotFather)" secret
ask SB_REF "Supabase project ref (the xxxx in https://xxxx.supabase.co)"
ask SB_PAT "Supabase access token (supabase.com/dashboard/account/tokens)" secret
ask LLM_BASE_URL "LLM base URL" "" "https://generativelanguage.googleapis.com/v1beta/openai"
ask LLM_MODEL "LLM model name" "" "gemini-2.5-flash"
ask LLM_API_KEY "LLM API key" secret
ask REPO "GitHub repo name to create" "" "avsar"
ME=$(curl -fsS "https://api.telegram.org/bot$TELEGRAM_TOKEN/getMe") || die "Telegram rejected that bot token."
BOT=$(printf '%s' "$ME" | python3 -c 'import sys,json;print(json.load(sys.stdin)["result"]["username"])')

say "Step 2/7: find your Telegram chat id (you become the admin)"
echo "Open https://t.me/$BOT , press Start, then come back here."
read -rp "Press Enter when done... " _
ADMIN_CHAT_ID=$(curl -fsS "https://api.telegram.org/bot$TELEGRAM_TOKEN/getUpdates" 2>/dev/null | python3 -c '
import sys,json
try:
    ids=[(u.get("message") or {}).get("chat",{}).get("id") for u in json.load(sys.stdin)["result"]]
    ids=[i for i in ids if i]; print(ids[-1] if ids else "")
except Exception: print("")' || true)
[ -n "$ADMIN_CHAT_ID" ] || ask ADMIN_CHAT_ID "Could not detect it. Enter your numeric Telegram chat id"

say "Step 3/7: creating database tables in Supabase"
sed 's/^create table /create table if not exists /' backend/database/schema.sql > "$TMP/schema.sql"
python3 -c 'import sys,json;print(json.dumps({"query":open(sys.argv[1]).read()}))' "$TMP/schema.sql" > "$TMP/q.json"
HTTP=$(curl -sS -o "$TMP/out" -w '%{http_code}' -X POST "https://api.supabase.com/v1/projects/$SB_REF/database/query" \
  -H "Authorization: Bearer $SB_PAT" -H 'Content-Type: application/json' --data @"$TMP/q.json")
case "$HTTP" in 200|201) echo "Tables ready.";; *) cat "$TMP/out"; die "Supabase rejected the schema (HTTP $HTTP). Check project ref/token and that the project finished creating.";; esac
KEYS=$(curl -sS "https://api.supabase.com/v1/projects/$SB_REF/api-keys?reveal=true" -H "Authorization: Bearer $SB_PAT" || true)
SB_KEY=$(printf '%s' "$KEYS" | python3 -c '
import sys,json
try:
    for k in json.load(sys.stdin):
        if k.get("name")=="service_role" and k.get("api_key"): print(k["api_key"]); break
except Exception: pass' || true)
if [ -z "$SB_KEY" ]; then
  echo "Could not fetch the key automatically. Use the LEGACY 'service_role' key (Settings -> API Keys -> Legacy)."
  ask SB_KEY "Paste the service_role key" secret
fi
SB_URL="https://$SB_REF.supabase.co"
CODE=$(curl -s -o /dev/null -w '%{http_code}' "$SB_URL/rest/v1/users?select=chat_id&limit=1" -H "apikey: $SB_KEY" -H "Authorization: Bearer $SB_KEY")
[ "$CODE" = 200 ] || die "The service key did not work against the database (HTTP $CODE). Use the legacy service_role JWT (starts with eyJ)."

say "Step 4/7: logging in to GitHub and Cloudflare (a browser window may open)"
gh auth status >/dev/null 2>&1 || gh auth login -w
OWNER=$(gh api user -q .login)
DASH="https://$OWNER.github.io/$REPO/"
if npx --yes wrangler@latest whoami 2>&1 | grep -qi "not authenticated"; then npx --yes wrangler@latest login; fi

say "Step 5/7: deploying the bot/API Worker to Cloudflare"
( cd backend/worker && npx --yes wrangler@latest deploy 2>&1 | tee "$TMP/deploy.log" )
WORKER_URL=$(grep -Eo 'https://[A-Za-z0-9.-]+\.workers\.dev' "$TMP/deploy.log" | head -1 || true)
[ -n "$WORKER_URL" ] || ask WORKER_URL "Could not detect the Worker URL. Paste it (https://....workers.dev)"
WEBHOOK_SECRET=$(rnd); SESSION_SECRET=$(rnd)
export TELEGRAM_TOKEN SB_URL SB_KEY WEBHOOK_SECRET SESSION_SECRET DASH WORKER_URL ADMIN_CHAT_ID LLM_BASE_URL LLM_MODEL LLM_API_KEY
python3 - > "$TMP/secrets.json" <<'PY'
import os,json
m={"TELEGRAM_TOKEN":"TELEGRAM_TOKEN","SUPABASE_URL":"SB_URL","SUPABASE_SERVICE_KEY":"SB_KEY","WEBHOOK_SECRET":"WEBHOOK_SECRET","SESSION_SECRET":"SESSION_SECRET","DASHBOARD_URL":"DASH","WORKER_URL":"WORKER_URL","ADMIN_CHAT_ID":"ADMIN_CHAT_ID","LLM_BASE_URL":"LLM_BASE_URL","LLM_MODEL":"LLM_MODEL","LLM_API_KEY":"LLM_API_KEY"}
print(json.dumps({k:os.environ[v] for k,v in m.items()}))
PY
chmod 600 "$TMP/secrets.json"
( cd backend/worker && npx --yes wrangler@latest secret bulk "$TMP/secrets.json" )

say "Step 6/7: connecting Telegram to the Worker"
curl -fsS "https://api.telegram.org/bot$TELEGRAM_TOKEN/setWebhook" --data-urlencode "url=$WORKER_URL" \
  --data-urlencode "secret_token=$WEBHOOK_SECRET" | grep -q '"ok":true' || die "setWebhook failed"
curl -fsS "$WORKER_URL" | grep -q "Avsar running" && echo "Worker is live."

say "Step 7/7: GitHub repo, secrets, dashboard (Pages) and first run"
[ -f .gitignore ] || printf '__pycache__/\n*.pyc\n' > .gitignore
[ -d .git ] || git init -q -b main
git add -A
git -c user.name="$OWNER" -c user.email="$OWNER@users.noreply.github.com" commit -qm "Avsar" || true
if gh repo view "$OWNER/$REPO" >/dev/null 2>&1; then
  git remote remove origin 2>/dev/null || true
  git remote add origin "https://github.com/$OWNER/$REPO.git"; git push -u origin main
else
  gh repo create "$REPO" --public --source=. --remote=origin --push
fi
setsec(){ printf '%s' "$2" | gh secret set "$1" --repo "$OWNER/$REPO" >/dev/null; }
setsec TELEGRAM_TOKEN "$TELEGRAM_TOKEN"; setsec SUPABASE_URL "$SB_URL"; setsec SUPABASE_SERVICE_KEY "$SB_KEY"
setsec ADMIN_CHAT_ID "$ADMIN_CHAT_ID"; setsec LLM_BASE_URL "$LLM_BASE_URL"; setsec LLM_MODEL "$LLM_MODEL"; setsec LLM_API_KEY "$LLM_API_KEY"
gh api -X POST "repos/$OWNER/$REPO/pages" -f build_type=workflow >/dev/null 2>&1 \
  || gh api -X PUT "repos/$OWNER/$REPO/pages" -f build_type=workflow >/dev/null 2>&1 \
  || echo "(Enable manually: repo Settings -> Pages -> Source: GitHub Actions)"
sleep 6
gh workflow run pages.yml --repo "$OWNER/$REPO" || echo "(Run manually: Actions -> dashboard -> Run workflow)"
gh workflow run avsar.yml --repo "$OWNER/$REPO" || echo "(Run manually: Actions -> avsar -> Run workflow)"

say "DONE"
echo "Bot:        https://t.me/$BOT   (share this link with users)"
echo "Dashboard:  $DASH   (open via the /login link the bot sends)"
echo "Actions:    https://github.com/$OWNER/$REPO/actions"
echo "Next: in Telegram send /start, /interests hackathon, internship, ai, then /login"
