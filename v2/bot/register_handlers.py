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
    "admin_stats",
    "admin_service_status",
    "admin_tail_logs",
    "admin_job_help",
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
    "world_markets",
    "world_gold",
    "world_usd",
    "world_eur",
    "world_gbp",
    "world_jpy",
    "world_majors",
    "world_quake",
    "world_time",
    "world_age",
    "world_rss",
    "world_rss_list",
    "feeds",
    "password",
    "revdns",
    "urlexpand",
    "timestamp",
    "lorem",
    "calc_percent",
    "calc_loan",
    "calc_deposit",
    "calc_rial",
    "calc_words",
    "calc_unit",
    "calc_base",
    "calc_binary",
    "calc_fuel",
    "calc_plate",
    "calc_nid",
    "calc_datediff",
    "calc_dateconv",
    "calc_random",
    "calc_mean",
    "calc_power",
    "calc_sqrt",
    "calc_fact",
    "calc_prime",
    "calc_ielts",
    "calc_cig",
    "calc_rect",
    "calc_square",
    "calc_case",
    "calc_wordcount",
    "calc_bmi",
    "calc_compound",
    "calc_log",
    "calc_pct_error",
    "calc_linear",
    "calc_quadratic",
    "calc_add_days",
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
    mh(tb.world_markets_handler, priv & cmd("world_markets"))
    mh(tb.world_gold_handler, priv & cmd("world_gold"))
    mh(tb.world_usd_handler, priv & cmd("world_usd"))
    mh(tb.world_eur_handler, priv & cmd("world_eur"))
    mh(tb.world_gbp_handler, priv & cmd("world_gbp"))
    mh(tb.world_jpy_handler, priv & cmd("world_jpy"))
    mh(tb.world_majors_handler, priv & cmd("world_majors"))
    mh(tb.world_quake_handler, priv & cmd("world_quake"))
    mh(tb.world_time_handler, priv & cmd("world_time"))
    mh(tb.world_age_handler, priv & cmd("world_age"))
    mh(tb.world_rss_handler, priv & cmd("world_rss"))
    mh(tb.world_rss_list_handler, priv & cmd("world_rss_list"))
    mh(tb.show_feed_menu_handler, priv & cmd("feeds"))
    mh(tb.feed_add_handler, priv & cmd("feed_add"))
    mh(tb.feed_help_handler, priv & cmd("feed_help"))
    mh(tb.plan_compare_handler, priv & cmd("plan_compare"))
    mh(tb.password_handler, priv & cmd("password"))
    mh(tb.reverse_dns_handler, priv & cmd("revdns"))
    mh(tb.url_expand_handler, priv & cmd("urlexpand"))
    mh(tb.timestamp_handler, priv & cmd("timestamp"))
    mh(tb.lorem_handler, priv & cmd("lorem"))
    mh(tb.calc_percent_handler, priv & cmd("calc_percent"))
    mh(tb.calc_loan_handler, priv & cmd("calc_loan"))
    mh(tb.calc_deposit_handler, priv & cmd("calc_deposit"))
    mh(tb.calc_rial_handler, priv & cmd("calc_rial"))
    mh(tb.calc_words_handler, priv & cmd("calc_words"))
    mh(tb.calc_unit_handler, priv & cmd("calc_unit"))
    mh(tb.calc_base_handler, priv & cmd("calc_base"))
    mh(tb.calc_binary_handler, priv & cmd("calc_binary"))
    mh(tb.calc_fuel_handler, priv & cmd("calc_fuel"))
    mh(tb.calc_plate_handler, priv & cmd("calc_plate"))
    mh(tb.calc_nid_handler, priv & cmd("calc_nid"))
    mh(tb.calc_datediff_handler, priv & cmd("calc_datediff"))
    mh(tb.calc_dateconv_handler, priv & cmd("calc_dateconv"))
    mh(tb.calc_random_handler, priv & cmd("calc_random"))
    mh(tb.calc_mean_handler, priv & cmd("calc_mean"))
    mh(tb.calc_power_handler, priv & cmd("calc_power"))
    mh(tb.calc_sqrt_handler, priv & cmd("calc_sqrt"))
    mh(tb.calc_fact_handler, priv & cmd("calc_fact"))
    mh(tb.calc_prime_handler, priv & cmd("calc_prime"))
    mh(tb.calc_ielts_handler, priv & cmd("calc_ielts"))
    mh(tb.calc_cig_handler, priv & cmd("calc_cig"))
    mh(tb.calc_rect_handler, priv & cmd("calc_rect"))
    mh(tb.calc_square_handler, priv & cmd("calc_square"))
    mh(tb.calc_case_handler, priv & cmd("calc_case"))
    mh(tb.calc_wordcount_handler, priv & cmd("calc_wordcount"))
    mh(tb.calc_bmi_handler, priv & cmd("calc_bmi"))
    mh(tb.calc_compound_handler, priv & cmd("calc_compound"))
    mh(tb.calc_log_handler, priv & cmd("calc_log"))
    mh(tb.calc_pct_error_handler, priv & cmd("calc_pct_error"))
    mh(tb.calc_linear_handler, priv & cmd("calc_linear"))
    mh(tb.calc_quadratic_handler, priv & cmd("calc_quadratic"))
    mh(tb.calc_add_days_handler, priv & cmd("calc_add_days"))
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
    mh(tb.admin_stats_handler, priv & cmd("admin_stats"))
    mh(tb.admin_service_status_handler, priv & cmd("admin_service_status"))
    mh(tb.admin_tail_logs_handler, priv & cmd("admin_tail_logs"))
    mh(tb.admin_job_help_handler, priv & cmd("admin_job_help"))
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
