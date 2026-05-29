# telegramtorubika (Tele2Rub)

Telegram bot to transfer files to **Rubika**, plus optional **Bale**, **Google Drive**, **SSH**, a **toolkit** (DNS, ping, hashes, …), **world tools** (weather, RSS feeds), and a **Telegram Mini App** (browser tools using the user’s real IP).

Repository: [github.com/mostafaafrouzi/telegramtorubika](https://github.com/mostafaafrouzi/telegramtorubika)

---

## Features

| Area | What you get |
|------|----------------|
| **Transfer** | Per-user Rubika (`/rubika_connect`), Bale bot, Google Drive (service account or Google OAuth), SSH upload/download |
| **Queue** | SQLite queue, batch ZIP/split, direct URL download, confirm/cancel before send |
| **Toolkit** | DNS, ping, whois, IP info, HTTP headers, port check, subnet, SSL, blacklist, MAC vendor, email check, MD5/SHA256/Base64, password, … |
| **Mini App** | WebApp hub: My IP + geo, DNS (Cloudflare DoH), latency test, password/timestamp/subnet/Base64/SHA-256 — runs in **the user’s browser**, not the server |
| **World** | Weather, calendar, currency, earthquakes, RSS/feed reader with push poll |
| **Admin** | Plans/quotas, `/admin`, logs, billing stub |
| **Installer** | `installer.sh` install/update/backup on Linux (systemd) |

---

## Quick server install

```bash
curl -fsSL https://raw.githubusercontent.com/mostafaafrouzi/telegramtorubika/main/installer.sh -o installer.sh
sudo bash installer.sh
```

Quick update (no backup):

```bash
curl -fsSL https://raw.githubusercontent.com/mostafaafrouzi/telegramtorubika/main/installer.sh | sudo bash -s -- --update-quick
```

Default install path: `/opt/tele2rub`, service: `tele2rub.service`.

---

## Manual development setup

```bash
git clone https://github.com/mostafaafrouzi/telegramtorubika.git
cd telegramtorubika
python3 -m venv venv
# Windows: venv\Scripts\activate
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env — at minimum API_ID, API_HASH, BOT_TOKEN, ADMIN_IDS
python main.py
```

Split processes (optional, less RAM per process): run `python telebot.py` and `python rub.py` separately — see `deploy/systemd/*.example`.

---

## Required environment (minimum)

| Variable | Description |
|----------|-------------|
| `API_ID` | From [my.telegram.org](https://my.telegram.org) → API development tools |
| `API_HASH` | Same page |
| `BOT_TOKEN` | From [@BotFather](https://t.me/BotFather) `/newbot` |
| `ADMIN_IDS` | Comma-separated Telegram user IDs (`@userinfobot`) |
| `RUBIKA_SESSION` | Legacy default session name, e.g. `rubika_session` |
| `DEFAULT_PART_SIZE_MB` | ZIP split size, e.g. `1900` |

Copy `.env.example` → `.env` and fill values. The installer can create `.env` for you.

---

## Optional environment (enable extra features)

### Transfer & providers

| Variable | Enables |
|----------|---------|
| `BALE_BOT_TOKEN` | Legacy global Bale token (prefer per-user `/bale_connect`) |
| `BALE_API_BASE` | Bale API base (default `https://tapi.bale.ai`) |
| `GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON` | Legacy global Drive SA path |
| `GOOGLE_DRIVE_FOLDER_ID` | Legacy global Drive folder |
| `GOOGLE_DRIVE_OAUTH_CLIENT_ID` | Per-user Google sign-in for Drive |
| `GOOGLE_DRIVE_OAUTH_CLIENT_SECRET` | OAuth client secret |
| `GOOGLE_DRIVE_OAUTH_REDIRECT_URI` | Optional; default `{MINIAPP_BASE_URL}/oauth/google/callback` |
| `TRANSFER_V2_VALIDATE` | Worker pre-validates Rubika session |
| `MAX_FILE_MB` | Reject uploads over N MB (`0` = no limit) |
| `UPLOAD_TIMEOUT_SECONDS` | Worker timeout per job (default 6h) |

### Toolkit

| Variable | Enables |
|----------|---------|
| `TOOLKIT_NETWORK_LIGHT=1` | `/dns`, `/myip`, `/ping`, network extras, Mini App network tools |
| `TOOLKIT_UTILITY_LIGHT=1` | `/md5`, `/sha256`, `/b64e`, `/b64d`, password, lorem, … |
| `TOOLKIT_DAILY_LIMIT_PER_USER` | Hard daily cap on toolkit commands (`0` = tier only) |
| `GOOGLE_CSE_API_KEYS` + `GOOGLE_CSE_ID` | `/gsearch`, `/gisearch` |

### Mini App (WebApp)

| Variable | Enables |
|----------|---------|
| `MINIAPP_BASE_URL` | Public **HTTPS** URL prefix for static files under `web/` (see below) |
| `MINIAPP_SERVE_LOCAL=1` | Bot serves `web/` on `MINIAPP_PORT` (dev/small VPS) |
| `MINIAPP_PORT` | Default `8788` |

**Important:** `/myip` in the bot opens the Mini App so users see **their** public IP. Without `MINIAPP_BASE_URL`, only a setup hint is shown (no server IP leak).

### RSS / feeds

| Variable | Enables |
|----------|---------|
| `RSS_POLL_ENABLE=1` | Background feed push |
| `RSS_POLL_INTERVAL_SEC` | Poll interval (default 900) |
| `RSSHUB_BASE_URL` | X/Twitter → RSS via RSSHub (default `https://rsshub.app`) |

### Billing / admin

| Variable | Enables |
|----------|---------|
| `DISABLE_USAGE_LIMITS=1` | Disable quotas (private hosts) |
| `BILLING_STUB_CHECKOUT=1` | Stub `/purchase` flow |
| `PAYMENT_WEBHOOK_SECRET` + `WEBHOOK_PORT` | `tools/payment_webhook_stub.py` |
| `ENABLE_UPLOAD_CHECKSUM=1` | MD5 log before Rubika upload |

### Other

| Variable | Enables |
|----------|---------|
| `APP_BUILD_VERSION` | Shown on `/version` |
| `V2_EPHEMERAL_READ_PRIMARY_SQLITE` | Prefer SQLite for wizard state reads |
| `DISABLE_UPDATE_BROADCAST=1` | Skip post-update broadcast |

Cloudflare uses **per-user** `/cf_connect` tokens in SQLite (no global token).

---

## Telegram Mini App — setup guide

The Mini App lives in `web/miniapp/`:

| Page | Purpose |
|------|---------|
| `index.html` | Hub / launcher |
| `myip.html` | Public IP, geo/ISP, latency |
| `dns.html` | DNS A / AAAA / MX (Cloudflare DoH) |
| `whois.html` | IP/domain WHOIS (via bot API) |
| `headers.html` | HTTP headers & site status (via bot API) |
| `network.html` | Multi-host latency from the user’s browser |
| `utils.html` | Password, timestamp, subnet, Base64, SHA-256 |

**Server API** (`/miniapp/api/headers`, `/whois`, `/status`): runs in the bot HTTP thread when `MINIAPP_SERVE_LOCAL=1`, or proxy that path to `MINIAPP_PORT` in nginx (see `deploy/nginx/miniapp-location.conf.example`). Pure-static nginx **without** this proxy will not power whois/headers pages.

Bot commands: `/myip`, `/miniapp` (opens WebApp buttons). Main menu button: **Mini App** (when `MINIAPP_BASE_URL` is set, opens hub). Glass menu: **Toolkit** → **Mini App hub** (when configured).

### 1) Choose how to host static files

**Production (recommended):** nginx (or Caddy) serves `web/` over HTTPS. Set:

```env
MINIAPP_BASE_URL=https://YOUR_DOMAIN/tele2rub
MINIAPP_SERVE_LOCAL=0
```

Example URL for the hub: `https://YOUR_DOMAIN/tele2rub/miniapp/index.html`

See `deploy/nginx/miniapp-location.conf.example`.

**Development / single VPS:** let the bot serve files:

```env
MINIAPP_BASE_URL=https://YOUR_DOMAIN:8788
MINIAPP_SERVE_LOCAL=1
MINIAPP_PORT=8788
```

Use a tunnel (ngrok, cloudflared) or reverse proxy so Telegram sees **HTTPS**.

### 2) TLS (required)

Telegram WebApp only works with **HTTPS**. Use Let’s Encrypt:

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d YOUR_DOMAIN
```

### 3) BotFather (optional but nice)

1. Open [@BotFather](https://t.me/BotFather) → your bot → **Bot Settings** → **Menu Button** or **Configure Mini App**.
2. Set the URL to: `{MINIAPP_BASE_URL}/miniapp/index.html`

### 4) Google Drive OAuth (optional)

If you use **Sign in with Google** for Drive:

1. [Google Cloud Console](https://console.cloud.google.com/) → APIs → Drive API → OAuth client (Web).
2. Authorized redirect URI: `{MINIAPP_BASE_URL}/oauth/google/callback`
3. `.env`:

```env
GOOGLE_DRIVE_OAUTH_CLIENT_ID=...
GOOGLE_DRIVE_OAUTH_CLIENT_SECRET=...
```

With `MINIAPP_SERVE_LOCAL=1`, the bot handles the callback on the same port. With nginx-only static hosting, proxy `/tele2rub/oauth/` to the bot port (see nginx example).

Users: `/drive_connect` → **Sign in with Google** → folder ID.

### 5) Verify

1. Restart bot: `sudo systemctl restart tele2rub`
2. In Telegram: `/miniapp` or `/myip` → open **Mini App hub**
3. Confirm IP/country match **your** connection, not the VPS

---

## Per-user connections (transfer hub)

| Service | Command | Notes |
|---------|---------|--------|
| Rubika | `/rubika_connect` | Phone + code; session per Telegram user |
| Bale | `/bale_connect` | User’s Bale bot token + chat id |
| Google Drive | `/drive_connect` | Service-account JSON **or** Google OAuth + folder id |
| SSH | `/ssh_add` | Password or `key:/path/to/id_rsa` |
| Cloudflare | `/cf_connect` | Per-user API token |

Then use menus: **Transfer** → Rubika / Bale / Drive / SSH, or `/directmode rubika|bale|drive on`.

---

## Bot usage basics

1. `/start` or `/menu`
2. `/rubika_connect` (and optionally Bale/Drive/SSH)
3. Send files or links; confirm send to Rubika (or direct mode)
4. `/usage` — quotas · `/plan` — tiers

**Glass menu:** `/imenu` — inline navigation.

**Toolkit:** main menu → Toolkit → Network / Crypto, or commands like `/dns example.com`, `/ping host:443`.

**Feeds:** `/feeds` or world menu → add RSS/YouTube/X (with `RSSHUB_BASE_URL` for X).

---

## Split bot + worker (low RAM)

Use **either** `main.py` **or** `tele2rub-bot` + `tele2rub-worker` units — not both for the same directory.

```bash
journalctl -u tele2rub-bot -u tele2rub-worker -f -n 120
```

---

## Troubleshooting

| Issue | Check |
|-------|--------|
| Mini App “not configured” | `MINIAPP_BASE_URL` set, HTTPS works, `web/miniapp/index.html` reachable in browser |
| WebApp blank / SSL error | Certificate, mixed content, correct path alias |
| Drive OAuth fails | Redirect URI exact match; `MINIAPP_SERVE_LOCAL` or nginx proxy to `/oauth/` |
| Rubika upload OOM | Add RAM/swap, lower `MAX_FILE_MB`, split ZIPs |
| Job stuck | `python3 log_analyzer.py --job-id ID --queue-dir /opt/tele2rub/queue` |

**Logs:**

```bash
journalctl -u tele2rub -f -n 120
tail -n 200 /opt/tele2rub/queue/bot_events.jsonl
tail -n 200 /opt/tele2rub/queue/worker_events.jsonl
```

Installer log bundle:

```bash
sudo bash installer.sh --all-logs
```

### Large ZIP / Rubika errors

| Symptom | Likely cause | Mitigation |
|--------|----------------|------------|
| `502` on `*.iranlms.ir` | Rubika API instability | Retry; different VPS region |
| OOM during Telegram download | Low RAM | Swap, smaller files, split archives |

---

## Installer menu

Install · Update · Uninstall · Backup · Restore · Service logs · Export all logs

Flags: `--install`, `--update`, `--update-quick`, `--env-sync`, `--all-logs`, …

---

## Project layout (short)

| Path | Role |
|------|------|
| `telebot.py` | Telegram bot, menus, handlers |
| `rub.py` | Queue worker (Rubika/Bale/Drive/SSH) |
| `main.py` | Spawns both |
| `queue/` | SQLite DB + JSON logs |
| `web/miniapp/` | Telegram Mini App static files |
| `v2/` | Modular handlers, toolkit, transfer adapters |
| `secrets/<telegram_id>/` | Per-user Drive SA / OAuth tokens |

---

## Credits

Original project creator: **caffeinexz**.
