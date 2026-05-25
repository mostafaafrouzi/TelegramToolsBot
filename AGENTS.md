# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

This is **TelegramToRubika (tele2rub)** — a Python Telegram bot that transfers files from Telegram to Rubika (and optionally Bale, Google Drive, SSH). See `README.md` for full feature list.

### Development setup

- **Runtime:** Python 3.12 (system default). No Node.js required.
- **Package manager:** pip with `requirements.txt` (no lockfile).
- **Virtual environment:** `python3 -m venv venv` at repo root, then `pip install -r requirements.txt`.
- **System deps needed for build:** `python3.12-venv`, `python3.12-dev`, `build-essential` (for `tgcrypto` C extension).
- **Configuration:** Copy `.env.example` to `.env` and set credentials. The bot requires `API_ID`, `API_HASH`, and `BOT_TOKEN` (Telegram API credentials) to start — without them `telebot.py` raises `RuntimeError`.

### Running the app

- **Combined mode:** `python main.py` — spawns both `telebot.py` (Telegram bot) and `rub.py` (Rubika worker) as subprocesses.
- **Split mode:** Run `python telebot.py` and `python rub.py` separately.
- The bot connects to Telegram via Pyrogram MTProto; the worker processes the upload queue to Rubika.

### Testing

- **Existing tests:** `python -m v2.transfer.test_link_direct` (smoke tests, no pytest required).
- **Lint:** `python -m pyflakes *.py` or `python -m py_compile <file>` for syntax checks. There are a few pre-existing pyflakes warnings (unused imports in `telebot.py`) — these are cosmetic, not errors.
- **No pytest/unittest suite** is present; the codebase uses manual smoke tests.

### Gotchas

- SQLite database at `queue/queue.sqlite3` is auto-created on first import of `queue_db`. No migrations needed.
- The `rub.py` worker module loads cleanly without Telegram credentials; only `telebot.py` requires `API_ID`/`API_HASH`/`BOT_TOKEN` at import time.
- `tgcrypto==1.2.5` needs C compilation headers (`python3.12-dev`). If pip install fails with "Python.h not found", install `python3.12-dev`.
- The `.env` file is gitignored. Always create it from `.env.example` for local/dev use.
