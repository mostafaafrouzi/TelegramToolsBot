"""Process entry: start client, background tasks, idle loop.

Uses lazy import of ``telebot`` so ``register_handlers(app)`` runs after handler
functions are defined (see ``v2.bot.register_handlers``).
"""

from __future__ import annotations

from pyrogram import idle


def run_bot() -> None:
    import telebot as tb

    tb.sync_v2_ephemeral_mirrors_from_json()
    tb.sync_v2_provider_credentials_from_users_json()
    if getattr(tb, "V2_EPHEMERAL_READ_PRIMARY_SQLITE", False):
        tb.log_event("v2_ephemeral_read_mode", primary="sqlite")
    tb.clear_old_status()
    tb.app.start()
    tb.app.loop.create_task(tb.status_watcher())
    tb.app.loop.create_task(tb.maybe_broadcast_update())
    tb.app.loop.create_task(tb.payment_reconcile_loop())
    tb.app.loop.create_task(tb.rss_poll_loop())
    serve_local = getattr(tb, "MINIAPP_SERVE_LOCAL", False)
    miniapp_url = (getattr(tb, "MINIAPP_BASE_URL", None) or "").strip()
    if serve_local or miniapp_url:
        from v2.toolkit.drive_oauth_light import oauth_configured
        from v2.web.miniapp_http import start_miniapp_server

        web_root = tb.BASE_DIR / "web"
        oauth_cb = tb.google_oauth_http_callback if oauth_configured() else None
        start_miniapp_server(web_root, port=tb.MINIAPP_PORT, google_oauth_callback=oauth_cb)
    idle()
    tb.app.stop()
