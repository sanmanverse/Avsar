# Avsar setup guide
Accounts needed (all free): Telegram, Supabase, Cloudflare, GitHub, and a free LLM key (e.g. aistudio.google.com/apikey).
Tools on your computer: git, Python 3, Node.js 18+, GitHub CLI (gh). Windows: use WSL or Git Bash.

Before running: (1) @BotFather -> /newbot -> copy token. (2) supabase.com -> New project -> wait until ready -> copy the
project ref. (3) supabase.com/dashboard/account/tokens -> create an access token. (4) get your free LLM key.
Then: unzip, `cd avsar`, `bash setup.sh`, answer the prompts, approve the GitHub/Cloudflare browser logins.
After: send /start to your bot, /interests hackathon, internship, ai, then /login.
Troubleshooting: see the chat guide or re-run `bash setup.sh` (it is safe to re-run).
