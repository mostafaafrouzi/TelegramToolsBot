"""Central Pyrogram handler registration (replaces @app.on_message / @app.on_callback_query).

Import ``telebot`` only inside ``register_handlers`` so the module finishes loading
before handlers are resolved (avoids circular import).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyrogram import filters
from pyrogram.handlers import CallbackQueryHandler, MessageHandler

if TYPE_CHECKING:
    from pyrogram import Client

# Commands handled by dedicated handlers; must stay aligned with ``text_handler`` logic in telebot.
_TEXT_EXCLUDED_COMMANDS = [
    "start",
    "menu",
    "lang",
    "help",
    "loghelp",
    "version",
    "rubika_status",
    "rubika_connect",
    "directmode",
    "netstatus",
    "admin",
    "safemode",
    "del",
    "delall",
    "newbatch",
    "done",
    "sendtext",
    "sendlink",
    "queue",
    "usage",
    "plan",
    "purchase",
    "dns",
    "myip",
    "ping",
    "ipinfo",
    "whois",
    "myid",
    "gsearch",
    "gisearch",
    "md5",
    "sha256",
    "b64e",
    "b64d",
    "bale_status",
    "bale_connect",
    "bale_disconnect",
    "bale_set_chat",
    "drive_status",
    "drive_connect",
    "drive_disconnect",
    "ssh_list",
    "ssh_add",
    "ssh_put",
    "ssh_ls",
    "ssh_del",
    "drive_download",
    "drive_ls",
    "ssh_get",
    "cf_connect",
    "cf_status",
    "cf_zones",
    "cf_dns",
    "cf_disconnect",
    "admin_users_list",
    "admin_tier",
    "admin_bonus",
    "admin_clear_prefs",
    "admin_clear_state_mirrors",
    "admin_payment_lookup",
    "admin_payment_status",
    "admin_reconcile_billing",
    "cleanup_downloads",
    "imenu",
    "httpheaders",
    "webstatus",
    "portcheck",
    "subnet",
    "blacklist",
    "sslcheck",
    "world_weather",
    "world_calendar",
    "world_currency",
    "world_quake",
    "world_rss",
    "world_rss_list",
    "feeds",
    "password",
    "revdns",
    "urlexpand",
    "timestamp",
    "lorem",
]

_MEDIA_FILTER = filters.private & (
    filters.document
    | filters.video
    | filters.audio
    | filters.voice
    | filters.photo
    | filters.animation
    | filters.video_note
    | filters.sticker
)


def register_handlers(app: Client, *, group: int = 0) -> None:
    import telebot as tb

    priv = filters.private
    cmd = filters.command

    def mh(callback, flt):
        app.add_handler(MessageHandler(callback, flt), group)

    mh(tb.start_handler, priv & cmd("start"))
    mh(tb.menu_handler, priv & cmd("menu"))
    mh(tb.lang_handler, priv & cmd("lang"))
    mh(tb.help_handler, priv & cmd("help"))
    mh(tb.log_help_handler, priv & cmd("loghelp"))
    mh(tb.version_handler, priv & cmd("version"))
    mh(tb.imenu_handler, priv & cmd("imenu"))
    mh(tb.http_headers_handler, priv & cmd("httpheaders"))
    mh(tb.website_status_handler, priv & cmd("webstatus"))
    mh(tb.port_check_handler, priv & cmd("portcheck"))
    mh(tb.subnet_calc_handler, priv & cmd("subnet"))
    mh(tb.blacklist_check_handler, priv & cmd("blacklist"))
    mh(tb.ssl_check_handler, priv & cmd("sslcheck"))
    mh(tb.world_weather_handler, priv & cmd("world_weather"))
    mh(tb.world_calendar_handler, priv & cmd("world_calendar"))
    mh(tb.world_currency_handler, priv & cmd("world_currency"))
    mh(tb.world_quake_handler, priv & cmd("world_quake"))
    mh(tb.world_rss_handler, priv & cmd("world_rss"))
    mh(tb.world_rss_list_handler, priv & cmd("world_rss_list"))
    mh(tb.show_feed_menu_handler, priv & cmd("feeds"))
    mh(tb.password_handler, priv & cmd("password"))
    mh(tb.reverse_dns_handler, priv & cmd("revdns"))
    mh(tb.url_expand_handler, priv & cmd("urlexpand"))
    mh(tb.timestamp_handler, priv & cmd("timestamp"))
    mh(tb.lorem_handler, priv & cmd("lorem"))
    mh(tb.rubika_status_handler, priv & cmd("rubika_status"))
    mh(tb.rubika_connect_handler, priv & cmd("rubika_connect"))
    mh(tb.direct_mode_handler, priv & cmd("directmode"))
    mh(tb.netstatus_handler, priv & cmd("netstatus"))
    mh(tb.admin_handler, priv & cmd("admin"))
    mh(tb.usage_handler, priv & cmd("usage"))
    mh(tb.plan_handler, priv & cmd("plan"))
    mh(tb.purchase_handler, priv & cmd("purchase"))
    mh(tb.dns_lookup_handler, priv & cmd("dns"))
    mh(tb.my_ip_handler, priv & cmd("myip"))
    mh(tb.my_ip_handler, priv & cmd("miniapp"))
    mh(tb.tcp_ping_handler, priv & cmd("ping"))
    mh(tb.ipinfo_handler, priv & cmd("ipinfo"))
    mh(tb.whois_handler, priv & cmd("whois"))
    mh(tb.my_id_handler, priv & cmd("myid"))
    mh(tb.google_search_handler, priv & cmd("gsearch"))
    mh(tb.google_image_search_handler, priv & cmd("gisearch"))
    mh(tb.md5_handler, priv & cmd("md5"))
    mh(tb.sha256_handler, priv & cmd("sha256"))
    mh(tb.b64_encode_handler, priv & cmd("b64e"))
    mh(tb.b64_decode_handler, priv & cmd("b64d"))
    mh(tb.bale_status_handler, priv & cmd("bale_status"))
    mh(tb.bale_connect_handler, priv & cmd("bale_connect"))
    mh(tb.bale_disconnect_handler, priv & cmd("bale_disconnect"))
    mh(tb.bale_set_chat_handler, priv & cmd("bale_set_chat"))
    mh(tb.drive_status_handler, priv & cmd("drive_status"))
    mh(tb.drive_connect_handler, priv & cmd("drive_connect"))
    mh(tb.drive_disconnect_handler, priv & cmd("drive_disconnect"))
    mh(tb.ssh_list_handler, priv & cmd("ssh_list"))
    mh(tb.ssh_add_handler, priv & cmd("ssh_add"))
    mh(tb.ssh_put_handler, priv & cmd("ssh_put"))
    mh(tb.ssh_ls_handler, priv & cmd("ssh_ls"))
    mh(tb.ssh_del_handler, priv & cmd("ssh_del"))
    mh(tb.drive_download_handler, priv & cmd("drive_download"))
    mh(tb.drive_ls_handler, priv & cmd("drive_ls"))
    mh(tb.ssh_get_handler, priv & cmd("ssh_get"))
    mh(tb.cf_connect_handler, priv & cmd("cf_connect"))
    mh(tb.cf_status_handler, priv & cmd("cf_status"))
    mh(tb.cf_zones_handler, priv & cmd("cf_zones"))
    mh(tb.cf_dns_handler, priv & cmd("cf_dns"))
    mh(tb.cf_disconnect_handler, priv & cmd("cf_disconnect"))
    mh(tb.admin_users_list_handler, priv & cmd("admin_users_list"))
    mh(tb.admin_tier_handler, priv & cmd("admin_tier"))
    mh(tb.admin_bonus_handler, priv & cmd("admin_bonus"))
    mh(tb.admin_clear_prefs_handler, priv & cmd("admin_clear_prefs"))
    mh(tb.admin_clear_state_mirrors_handler, priv & cmd("admin_clear_state_mirrors"))
    mh(tb.admin_payment_lookup_handler, priv & cmd("admin_payment_lookup"))
    mh(tb.admin_payment_status_handler, priv & cmd("admin_payment_status"))
    mh(tb.admin_reconcile_billing_handler, priv & cmd("admin_reconcile_billing"))
    mh(tb.cleanup_downloads_handler, priv & cmd("cleanup_downloads"))
    mh(tb.safemode_handler, priv & cmd("safemode"))
    mh(tb.clear_queue_handler, priv & cmd("delall"))
    mh(tb.new_batch_handler, priv & cmd("newbatch"))
    mh(tb.done_batch_handler, priv & cmd("done"))
    mh(tb.send_text_handler, priv & cmd("sendtext"))
    mh(tb.send_link_handler, priv & cmd("sendlink"))
    mh(tb.queue_manage_handler, priv & cmd("queue"))
    mh(tb.delete_one_handler, priv & cmd("del"))
    mh(
        tb.text_handler,
        priv & filters.text & ~cmd(_TEXT_EXCLUDED_COMMANDS),
    )
    mh(tb.media_handler, _MEDIA_FILTER)

    app.add_handler(CallbackQueryHandler(tb.callback_handler), group)
