import asyncio
import json
from functools import partial
import os
import re
import shutil
import time
import pyzipper
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.errors import MessageNotModified
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from rubpy import Client as RubikaClient
from rubpy.crypto import Crypto
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from queue_db import QueueDB
from user_entitlements import (
    DISABLE_USAGE_LIMITS,
    add_bonus_month_mb,
    can_enqueue,
    effective_toolkit_daily_limit,
    estimate_task_bytes,
    effective_max_file_bytes,
    get_usage_snapshot,
    parallel_job_count,
    set_user_tier,
)
from v2.core import menu_engine
from v2.core.direct_mode import load_direct_mode_target, save_direct_mode_target
from v2.core.menu_sections import MenuSection
from v2.handlers.reply_routes import ReplyRouteDeps, dispatch_reply_keyboard_route
from v2.handlers.rubika_wizard import RubikaWizardDeps, dispatch_rubika_connect_wizard
from v2.handlers.provider_connect_wizards import (
    ProviderConnectWizardDeps,
    dispatch_provider_connect_wizard,
    handle_bale_connect,
    handle_bale_disconnect,
    handle_drive_connect,
    handle_drive_disconnect,
    save_drive_sa_from_downloaded_file,
)
from v2.handlers.zip_batch_wizard import ZipBatchWizardDeps, dispatch_zip_batch_wizard
from v2.handlers.zip_password_prompt import ZipPasswordPromptDeps, handle_zip_password_text
from v2.handlers.direct_mode_text import DirectModeTextDeps, handle_direct_mode_plain_text
from v2.handlers.direct_url_hint import DirectUrlHintDeps, handle_direct_url_sendlink_hint
from v2.handlers.basic_commands import BasicCommandDeps, handle_help, handle_lang, handle_log_help, handle_menu, handle_start, handle_version
from v2.billing import maybe_grant_plan_after_paid, run_reconcile
from v2.handlers.admin_commands import (
    AdminCommandDeps,
    handle_admin_bonus,
    handle_admin_panel,
    handle_admin_payment_lookup,
    handle_admin_payment_status,
    handle_admin_reconcile_billing,
    handle_admin_tier,
    handle_cleanup_downloads,
)
from v2.handlers.plan_commands import PlanCommandDeps, handle_plan, handle_purchase, handle_usage
from v2.handlers.queue_commands import QueueCommandDeps, handle_clear_queue, handle_queue_manage, handle_send_link, handle_send_text
from v2.handlers.safemode_command import SafeModeCommandDeps, handle_safemode
from v2.handlers.delete_command import DeleteCommandDeps, handle_delete_one
from v2.handlers.callback_routes import CallbackRouteDeps, dispatch_callback_route
from v2.handlers.batch_commands import BatchCommandDeps, handle_done_batch, handle_new_batch
from v2.handlers.text_entry import TextEntryDeps, handle_text_entry
from v2.handlers.media_handler import MediaHandlerDeps, handle_media_message
from v2.handlers.session_settings_commands import (
    SessionSettingsCommandDeps,
    handle_netstatus,
    handle_rubika_connect,
    handle_rubika_status,
)
from v2.handlers.direct_send_commands import DirectSendCommandDeps, handle_direct_mode
from v2.handlers.link_direct_commands import LinkDirectCommandDeps, handle_show_link_direct_menu
from v2.handlers.link_direct_handler import (
    LinkDirectHandlerDeps,
    handle_link_dest_callback,
    handle_link_direct_for_direct_mode,
    handle_link_direct_text,
)
from v2.transfer.user_credentials import load_bale_credentials, load_drive_credentials
from v2.handlers.toolkit_commands import (
    ToolkitCommandDeps,
    handle_b64_decode,
    handle_b64_encode,
    handle_dns_lookup,
    handle_md5,
    handle_my_ip,
    handle_sha256,
    handle_tcp_ping,
)
from v2.handlers.toolkit_menu_commands import (
    ToolkitMenuDeps,
    handle_show_toolkit_crypto_menu,
    handle_show_toolkit_menu,
    handle_show_toolkit_network_menu,
)
from v2.handlers.transfer_hub_commands import (
    TransferHubDeps,
    handle_bale_set_chat,
    handle_bale_status,
    handle_drive_status,
    handle_show_bale_menu,
    handle_show_drive_menu,
    handle_show_files_menu as handle_show_files_menu_hub,
    handle_show_rubika_menu as handle_show_rubika_menu_hub,
    handle_show_ssh_menu,
    handle_show_transfer_menu,
    handle_ssh_add,
    handle_ssh_list,
)
from v2.bot.client_factory import build_bot_client
from v2.bot.register_handlers import register_handlers

load_dotenv()

# v2: logical keyboard section for analytics / future routing (stored in user_states.json)
MENU_SECTION_KEY = "menu_section"

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "").strip()
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
APP_VERSION = os.getenv("APP_BUILD_VERSION", "telegramtorubika-dev")

BASE_DIR = Path(__file__).resolve().parent
DOWNLOAD_DIR = BASE_DIR / "downloads"
QUEUE_DIR = BASE_DIR / "queue"
STATUS_FILE = QUEUE_DIR / "status.jsonl"
SETTINGS_FILE = QUEUE_DIR / "settings.json"
USERS_FILE = QUEUE_DIR / "users.json"
USER_STATES_FILE = QUEUE_DIR / "user_states.json"
BATCH_FILE = QUEUE_DIR / "batch_sessions.json"
NETWORK_FILE = QUEUE_DIR / "network.json"
FAILED_FILE = QUEUE_DIR / "failed.jsonl"
BOT_LOG_FILE = QUEUE_DIR / "bot_events.jsonl"
WORKER_EVENTS_FILE = QUEUE_DIR / "worker_events.jsonl"
KNOWN_CHATS_FILE = QUEUE_DIR / "known_chats.json"
BROADCAST_STATE_FILE = QUEUE_DIR / "broadcast_state.json"
PROCESSING_FILE = QUEUE_DIR / "processing.json"
DISABLE_UPDATE_BROADCAST = os.getenv("DISABLE_UPDATE_BROADCAST", "").strip().lower() in (
    "1",
    "true",
    "yes",
)

# When true, get_state/get_batch read SQLite mirrors first; JSON is fallback.
# Writes remain dual (JSON + mirror). See docs/v2/09-implementation-roadmap.md.
V2_EPHEMERAL_READ_PRIMARY_SQLITE = (os.getenv("V2_EPHEMERAL_READ_PRIMARY_SQLITE") or "").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
    "sqlite",
)

BILLING_STUB_CHECKOUT = (os.getenv("BILLING_STUB_CHECKOUT") or "").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
BILLING_RECONCILE_ENABLE = (os.getenv("BILLING_RECONCILE_ENABLE") or "").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
try:
    BILLING_RECONCILE_INTERVAL_SEC = max(60, int((os.getenv("BILLING_RECONCILE_INTERVAL_SEC") or "600").strip()))
except ValueError:
    BILLING_RECONCILE_INTERVAL_SEC = 600
try:
    BILLING_RECONCILE_PENDING_MAX_AGE_SEC = max(300, int((os.getenv("BILLING_RECONCILE_PENDING_MAX_AGE_SEC") or "86400").strip()))
except ValueError:
    BILLING_RECONCILE_PENDING_MAX_AGE_SEC = 86400

def _env_flag_on(name: str, *, default_when_unset: bool = False) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default_when_unset
    return raw in ("1", "true", "yes", "on")


# Phase 4 toolkit: default ON when unset (see installer merge_env_defaults).
TOOLKIT_NETWORK_LIGHT = _env_flag_on("TOOLKIT_NETWORK_LIGHT", default_when_unset=True)
TOOLKIT_UTILITY_LIGHT = _env_flag_on("TOOLKIT_UTILITY_LIGHT", default_when_unset=True)


def max_file_bytes() -> Optional[int]:
    """If set, reject queued uploads larger than this (from MAX_FILE_MB in .env). 0 or empty = no limit."""
    raw = (os.getenv("MAX_FILE_MB") or "").strip()
    if not raw or raw == "0":
        return None
    try:
        mb = int(raw)
        if mb <= 0:
            return None
        return mb * 1024 * 1024
    except ValueError:
        return None


def max_file_mb_display() -> str:
    b = max_file_bytes()
    if b is None:
        return "∞"
    return str(b // (1024 * 1024))


def effective_max_mb_display(user_id: int) -> str:
    b = effective_max_file_bytes(user_id)
    if b is None:
        return "∞"
    return f"{b / (1024 * 1024):.0f}"


def fmt_mb_bytes(n: int) -> str:
    return f"{n / (1024 * 1024):.1f}"


def quota_fail_text(user_id: int, code: str, detail: dict) -> str:
    if code == "quota_parallel":
        return tr(
            user_id,
            "quota_parallel_msg",
            cur=detail.get("parallel", 0),
            maxp=detail.get("max_parallel", 0),
        )
    if code == "quota_day":
        return tr(
            user_id,
            "quota_day_msg",
            need=detail.get("need_mb", "?"),
            left=f'{detail.get("remain_day_mb", 0):.1f}',
        )
    if code == "quota_month":
        return tr(
            user_id,
            "quota_month_msg",
            need=detail.get("need_mb", "?"),
            left=f'{detail.get("remain_month_mb", 0):.1f}',
        )
    if code == "quota_file_cap":
        return tr(
            user_id,
            "quota_file_cap_msg",
            max_mb=detail.get("max_mb", 0),
            need_mb=detail.get("need_mb", "?"),
        )
    return tr(user_id, "quota_unknown")


ADMIN_IDS = {
    int(x.strip())
    for x in (os.getenv("ADMIN_IDS", "").split(",") if os.getenv("ADMIN_IDS") else [])
    if x.strip().isdigit()
}

DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
QUEUE_DIR.mkdir(parents=True, exist_ok=True)

if not API_ID or not API_HASH or not BOT_TOKEN:
    raise RuntimeError("Please set API_ID, API_HASH and BOT_TOKEN in .env")

app = build_bot_client(
    "tel2rub",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

I18N = {
    "fa": {
        "welcome": (
            "سلام 💙\n\n"
            "🏠 **منوی اصلی** — دو بخش جدا:\n"
            "📁 انتقال فایل (روبیکا، بله، درایو، SSH)\n"
            "🧰 ابزارها (شبکه، هش، Base64)\n\n"
            "برای روبیکا یک‌بار `/rubika_connect` بزن.\n"
            "`/menu` منوی اصلی · `/lang` زبان"
        ),
        "menu_intro": (
            "🏠 منوی اصلی\n\n"
            "📁 **انتقال** — ارسال و انتقال فایل\n"
            "🧰 **ابزارها** — مستقل از انتقال\n"
            "📋 **حساب** — پلن و صف\n"
            "⚙️ **تنظیمات** — حالت مستقیم و شبکه\n\n"
            "در هر زیرمنو «🏠 منوی اصلی» یا «◀️» برای برگشت."
        ),
        "unknown_input_hint": (
            "این پیام با منوی فعلی قابل پردازش نیست.\n"
            "از دکمه‌های زیر استفاده کن یا `/help` را بفرست."
        ),
        "plan_menu_opened": (
            "📋 حساب و پلن\n"
            "پلن، مصرف، خرید و مدیریت صف."
        ),
        "pick_lang": "زبان را انتخاب کن:",
        "lang_saved": "زبان ذخیره شد.",
        "transfer_menu_title": "📁 انتقال فایل\nمقصد را انتخاب کن — هر سرویس منوی خودش را دارد.",
        "toolkit_menu_title": "🧰 ابزارها\nمستقل از انتقال — دسته را انتخاب کن.",
        "toolkit_network_menu_title": "🌐 ابزار شبکه\nبعد از انتخاب، دستور + مقدار را بفرست (مثلاً `/dns google.com`).",
        "toolkit_crypto_menu_title": "🔐 هش و Base64\nمثلاً `/md5 متن` یا `/b64e سلام`",
        "rubika_menu_title": "💬 روبیکا\nاتصال و وضعیت حساب خودت.",
        "bale_menu_title": "📨 بله\nربات و مقصد خودت — `/bale_connect`",
        "drive_menu_title": "☁️ گوگل درایو\n`/drive_connect` سپس ارسال فایل.",
        "ssh_menu_title": "🖥 سرور SSH\nلیست سرورهای خودت. آپلود: `/ssh_put id مسیر`",
        "files_menu_title": "📦 فایل، ZIP و صف\nروبیکا باید متصل باشد.",
        "settings_menu_title": "📤 ارسال مستقیم\nفقط یک مقصد فعال — قبل از فعال‌سازی اتصال همان مقصد را برقرار کن.",
        "direct_send_menu_title": "📤 ارسال مستقیم",
        "admin_menu_title": "🛡 پنل ادمین",
        "admin_denied": "دسترسی ادمین ندارید.",
        "no_worker_events": "فایل لاگ worker هنوز ساخته نشده.",
        "no_recent_jobs": "برای این چت رویداد task_done/task_failed اخیری ثبت نشده.",
        "recent_jobs_title": "آخرین کارها (worker):",
        "btn_main_transfer": "📁 انتقال فایل",
        "btn_main_toolkit": "🧰 ابزارها",
        "btn_main_settings": "📤 ارسال مستقیم",
        "btn_main_link_direct": "🔗 لینک / ویدیو",
        "btn_main_help": "❓ راهنما",
        "btn_main_plan_section": "📋 حساب و پلن",
        "btn_main_admin": "🛡 پنل ادمین",
        "btn_back_main": "🏠 منوی اصلی",
        "btn_back_transfer": "◀️ انتقال",
        "btn_back_toolkit": "◀️ ابزارها",
        "btn_transfer_rubika": "💬 روبیکا",
        "btn_transfer_bale": "📨 بله",
        "btn_transfer_drive": "☁️ درایو",
        "btn_transfer_ssh": "🖥 SSH",
        "btn_transfer_files": "📦 فایل و ZIP",
        "btn_rub_connect": "🔗 اتصال",
        "btn_rub_status": "✅ وضعیت",
        "btn_zip_start": "📥 شروع ZIP",
        "btn_zip_end": "✅ پایان ZIP",
        "btn_send_content": "✉️ متن / لینک",
        "btn_queue": "📋 صف",
        "btn_clear_all": "🗑 پاکسازی",
        "btn_toolkit_network": "🌐 شبکه و IP",
        "btn_toolkit_crypto": "🔐 هش و Base64",
        "btn_tool_dns": "🔍 DNS",
        "btn_tool_myip": "📍 IP من",
        "btn_tool_ping": "📡 Ping",
        "btn_tool_md5": "#️⃣ MD5",
        "btn_tool_sha256": "🔒 SHA256",
        "btn_tool_b64e": "📤 B64 encode",
        "btn_tool_b64d": "📥 B64 decode",
        "btn_plan_plan": "📊 پلن",
        "btn_plan_usage": "📈 مصرف",
        "btn_plan_buy": "💳 خرید",
        "btn_direct_rubika_on": "🚀 مستقیم روبیکا",
        "btn_direct_bale_on": "📨 مستقیم بله",
        "btn_direct_drive_on": "☁️ مستقیم درایو",
        "btn_direct_rubika_off": "⏸ غیرفعال مستقیم روبیکا",
        "btn_direct_bale_off": "⏸ غیرفعال مستقیم بله",
        "btn_direct_drive_off": "⏸ غیرفعال مستقیم درایو",
        "btn_netstatus": "📶 وضعیت شبکه",
        "btn_ssh_list": "📋 لیست سرور",
        "btn_ssh_add_help": "➕ افزودن سرور",
        "btn_drive_download_help": "⬇️ دانلود درایو",
        "btn_admin_panel": "🛡 پنل",
        "btn_inline_refresh": "بروزرسانی",
        "btn_inline_pending": "نمایش Pending",
        "btn_inline_failed": "نمایش Failed",
        "btn_inline_clear": "پاکسازی صف من",
        "btn_inline_recent": "آخرین کارها",
        "btn_inline_faildetail": "جزئیات خطا",
        "queue_kb_refresh": "بروزرسانی شد",
        "queue_kb_cleared": "صف پاک شد",
        "directmode_usage": (
            "ارسال مستقیم (یک مقصد):\n"
            "`/directmode rubika on` · `/directmode bale on` · `/directmode drive on`\n"
            "خاموش: `/directmode rubika off` (یا bale/drive)\n"
            "قدیمی: `/directmode on` = روبیکا"
        ),
        "direct_on_rubika": "ارسال مستقیم به روبیکا فعال شد.",
        "direct_on_bale": "ارسال مستقیم به بله فعال شد.",
        "direct_on_drive": "ارسال مستقیم به Google Drive فعال شد.",
        "direct_off": "ارسال مستقیم غیرفعال شد.",
        "direct_off_wrong_target": "مقصد فعال `{active}` است — ابتدا همان را خاموش کن.",
        "direct_url_only_for_bale_drive": "در مستقیم بله/درایو فقط لینک/ویدیو پشتیبانی می‌شود.",
        "link_menu_opened": (
            "🔗 دانلود لینک / ویدیو\n"
            "یک لینک HTTP(S) یا یوتیوب بفرست.\n"
            "ابتدا اطلاعات فایل نمایش داده می‌شود؛ بعد مقصد را انتخاب کن.\n"
            "تا مقصد و اتصال تأیید نشود، دانلود روی سرور شروع نمی‌شود."
        ),
        "link_send_url": "لطفاً یک لینک معتبر (http/https یا یوتیوب) بفرست.",
        "link_probing": "در حال بررسی لینک (بدون دانلود)…",
        "link_probe_summary": "📎 `{title}`\nنوع: {link_type}\nحجم تقریبی: {size}",
        "link_size_unknown": "نامشخص",
        "link_type_direct": "لینک مستقیم",
        "link_type_youtube": "یوتیوب",
        "link_type_magnet": "تورنت",
        "link_pick_dest": "مقصد را انتخاب کن:",
        "link_dest_rubika": "روبیکا",
        "link_dest_bale": "بله",
        "link_dest_drive": "Google Drive",
        "link_dest_cancel": "لغو",
        "link_need_rubika": "روبیکا متصل نیست. `/rubika_connect`",
        "bale_file_too_large": "حجم فایل برای بله زیاد است. سقف بله `{max_mb}` MB است؛ این فایل ~{size_mb} MB است.",
        "link_probe_unsupported": "این لینک قابل دانلود نیست. ({detail})",
        "link_ytdlp_missing": "یوتیوب نیاز به `yt-dlp` روی سرور دارد.",
        "link_magnet_unsupported": "لینک magnet هنوز پشتیبانی نمی‌شود.",
        "link_session_expired": "انتخاب منقضی شد — لینک را دوباره بفرست.",
        "link_cancelled": "لغو شد.",
        "link_downloading": "در حال دانلود روی سرور…",
        "link_download_failed": "دانلود ناموفق: {error}",
        "link_download_done_queue": "دانلود شد؛ در صف ارسال…",
        "newbatch_ok": (
            "جلسه فایل ZIP فعال شد.\n"
            "فایل‌ها را ارسال کن. بعد از اتمام، «پایان فایل ZIP» یا `/done` را بزن."
        ),
        "prompt_sendtext": "متن را ارسال کن.",
        "prompt_sendlink": "لینک را ارسال کن.",
        "queue_panel": (
            "مدیریت صف:\n\n"
            "- در انتظار در صف SQLite: `{pending}`\n"
            "- هم‌اکنون در حال پردازش (worker): `{processing}`\n"
            "- کل خطاها (global): `{failed}`\n"
            "- حذف‌شده‌ها: `{deleted}`\n"
            "- لغوشده‌ها: `{cancelled}`\n\n"
            "اگر آپلود گیر کرد ولی اینجا `۰` بود، یعنی کار از صف بیرون آمده و worker مشغول است.\n\n"
            "برای پاکسازی صف از دکمهٔ «پاکسازی صف من» استفاده کن."
        ),
        "queue_processing_none": "`—`",
        "queue_processing_detail": "`{job_id}` نوع `{task_type}` — `{file}` (~{size})",
        "bale_not_connected": "بله متصل نیست. `/bale_connect` — ربات بله خودت را بساز و توکن را وارد کن.",
        "bale_ask_token": (
            "توکن ربات بله خودت را بفرست (از @botfather در بله).\n"
            "این توکن فقط برای حساب تلگرام تو ذخیره می‌شود."
        ),
        "bale_token_invalid": "توکن بله نامعتبر است: {detail}",
        "bale_token_ok": "ربات بله تأیید شد (@{bot}).\nحالا `chat_id` مقصد را بفرست (گروه/کاربر در بله).",
        "bale_chat_id_empty": "chat_id خالی است. دوباره بفرست.",
        "bale_connected_ok": "بله متصل شد ✅ مقصد: `{chat_id}`",
        "bale_already_connected": "بله قبلاً متصل است. برای اتصال مجدد `/bale_disconnect` سپس `/bale_connect`.",
        "bale_disconnected": "اتصال بله قطع شد.",
        "btn_bale_connect": "🔗 اتصال",
        "btn_bale_status": "✅ وضعیت",
        "btn_bale_disconnect": "❌ قطع",
        "bale_status_no_chat": "توکن OK ({detail}). chat_id نداری — در ویزارد `/bale_connect` ادامه بده.",
        "bale_status_ok": "بله: chat_id=`{chat_id}` — {detail}",
        "bale_set_chat_usage": "استفاده: `/bale_set_chat <bale_chat_id>` (بعد از `/bale_connect`)",
        "bale_set_chat_saved": "مقصد بله ذخیره شد: `{chat_id}`",
        "drive_not_connected": (
            "گوگل درایو متصل نیست. `/drive_connect` — فایل JSON سرویس‌اکانت خودت را آپلود کن."
        ),
        "drive_ask_sa_json": (
            "فایل JSON سرویس‌اکانت Google (Drive API) را به‌صورت **سند** بفرست.\n"
            "پوشه Drive را با ایمیل سرویس‌اکانت Share کن."
        ),
        "drive_ask_folder_id": "شناسه پوشه Drive (folder ID از URL) را بفرست:",
        "drive_folder_empty": "folder_id خالی است.",
        "drive_sa_missing_retry": "فایل سرویس‌اکانت پیدا نشد. دوباره `/drive_connect`.",
        "drive_connected_ok": "درایو متصل شد ✅ folder=`{folder_id}`",
        "drive_disconnected": "اتصال درایو قطع شد.",
        "btn_drive_connect": "🔗 اتصال",
        "btn_drive_status": "✅ وضعیت",
        "btn_drive_disconnect": "❌ قطع",
        "drive_sa_need_document": "JSON را به‌صورت فایل (document) بفرست، نه متن.",
        "drive_sa_need_json": "نام فایل باید `.json` باشد.",
        "drive_sa_invalid": "JSON نامعتبر: {error}",
        "drive_status_line": "Drive configured: {ok}\n{detail}",
        "ssh_list_empty": "هیچ سرور SSH ثبت نشده. `/ssh_add label host port user`",
        "ssh_list_title": "سرورهای SSH:",
        "ssh_list_row": "`#{id}` {label} — `{ssh_user}@{host}:{port}`",
        "ssh_add_usage": "استفاده: `/ssh_add <label> <host> <port> <user> [password]`",
        "ssh_add_ok": "سرور `{label}` ({host}:{port}) ذخیره شد.",
        "ssh_put_usage": "استفاده: `/ssh_put <server_id> <remote_path>` سپس فایل را بفرست",
        "ssh_put_await_file": "مسیر روی سرور ثبت شد. حالا فایل را در تلگرام بفرست.",
        "ssh_server_not_found": "سرور SSH پیدا نشد.",
        "ssh_auth_missing": "برای این سرور رمز یا کلید SSH ثبت نشده. دوباره با `/ssh_add` و رمز اضافه کن.",
        "bale_active_hint": "پس از `/bale_connect`، همین‌جا فایل بفرست تا با ربات بله خودت ارسال شود (~۲۰ مگ).",
        "drive_active_hint": "پس از `/drive_connect`، فایل بفرست تا در Drive خودت آپلود شود. دانلود: `/drive_download <id>`",
        "drive_download_usage": "استفاده: `/drive_download <google_drive_file_id>`",
        "ssh_get_usage": "استفاده: `/ssh_get <server_id> <remote_path>`",
        "help_short": (
            "راهنمای سریع:\n\n"
            "🏠 منو: `/menu` — 📁 انتقال جدا از 🧰 ابزارها\n\n"
            "📁 انتقال:\n"
            "- روبیکا `/rubika_connect` · بله `/bale_connect` · درایو `/drive_connect`\n"
            "- SSH `/ssh_list` · ZIP `/newbatch` `/done`\n\n"
            "🧰 ابزارها (منوی مستقل):\n"
            "- `/dns host` · `/myip` · `/ping host:port` · `/md5 text` · `/sha256` · `/b64e` `/b64d`\n\n"
            "📤 ارسال مستقیم: `/directmode rubika|bale|drive on|off` · 🔗 لینک: منوی «لینک / ویدیو»\n\n"
            "عیب‌یابی:\n"
            "- وضعیت شبکه: `/netstatus`\n"
            "- پنل ادمین: `/admin`\n"
            "- حذف یک job: `/del <job_id>`\n\n"
            "برای راهنمای تحلیل لاگ: `/loghelp`\n"
            "• مصرف و سهمیه: `/usage` — پلن و خرید: `/plan` — راهنمای خرید: `/purchase`"
        ),
        "loghelp_body": (
            "راهنمای تحلیل لاگ job:\n\n"
            "1) ابتدا `job_id` را از پیام Queued بردار.\n"
            "2) در bot logs دنبال `task_queued` با همان `job_id` بگرد.\n"
            "3) در worker logs باید به‌ترتیب ببینی:\n"
            "   `task_started` -> (`task_done` یا `task_failed`).\n"
            "4) اگر `task_requeued` دیدی، مشکل شبکه/دسترسی بوده و job جدید ساخته شده.\n"
            "5) برای اتصال روبیکا، eventهای `rubika_connect_ok` یا `rubika_connect_failed` را چک کن.\n\n"
            "مسیر لاگ‌ها:\n"
            "- `/opt/tele2rub/queue/bot_events.jsonl`\n"
            "- `/opt/tele2rub/queue/worker_events.jsonl`\n"
            "- `/tmp/tele2rub-installer.jsonl`"
        ),
        "rubika_not_connected": "روبیکا متصل نیست. از `/rubika_connect` استفاده کن.",
        "rubika_checking": "در حال بررسی وضعیت واقعی اتصال روبیکا ...",
        "rubika_ok": (
            "اتصال روبیکا فعال و معتبر است ✅\n"
            "session: `{session}`\n"
            "جزئیات: `{details}`"
        ),
        "rubika_invalid_session": (
            "اتصال ذخیره‌شده معتبر نیست ❌\n"
            "session: `{session}`\n"
            "خطا: `{details}`\n\n"
            "لطفاً دوباره از دکمه «اتصال روبیکا» استفاده کن."
        ),
        "rubika_already_connected": (
            "اکانت روبیکا از قبل متصل است.\n"
            "session: `{session}`\n\n"
            "برای اتصال مجدد، شماره جدید را ارسال کن."
        ),
        "rubika_ask_phone": (
            "شماره روبیکا را با پیش‌شماره کشور ارسال کن.\n"
            "مثال: `98912xxxxxxx`"
        ),
        "rubika_passkey_needed": "این شماره نیاز به PassKey دارد. PassKey روبیکا را ارسال کن.",
        "rubika_code_sent": "کد ارسال شد. کد تایید روبیکا را بفرست.",
        "rubika_send_code_error": "خطا در ارسال کد روبیکا: {error}",
        "rubika_connected_ok": "روبیکا با موفقیت متصل شد ✅",
        "rubika_bad_code": "کد تایید نامعتبر یا خطای ورود: {error}",
        "version_line": "telegramtorubika `{version}`",
        "update_notice": (
            "ربات به‌روز شد ✅\n"
            "نسخه: `{version}`\n"
            "`/menu` منوی اصلی · `/lang` زبان"
        ),
        "prompt_quick_message": (
            "پیام بعدی‌ات را بفرست (متن خالی، فقط لینک، یا متن همراه لینک).\n"
            "بدون تأیید اضافه در صف روبیکا قرار می‌گیرد."
        ),
        "empty_message": "پیام خالی است.",
        "text_queueing": "در حال قرار دادن در صف ...",
        "text_queued": (
            "در صف قرار گرفت ✅\n"
            "Job: `{job_id}`\n"
            "جایگاه تقریبی در صف شما: `{qpos}`\n\n"
            "برای جزئیات «مدیریت صف» را بزن."
        ),
        "sendtext_usage": "فرمت: `/sendtext متن`",
        "sendlink_usage": "فرمت: `/sendlink <url>`",
        "invalid_link": "در این متن لینک http(s) معتبر پیدا نشد.",
        "safemode_usage": "از `/safemode on` یا `/safemode off` استفاده کن.",
        "safemode_on": (
            "Safe Mode فعال شد.\n\n"
            "رمزی که می‌خواهی روی ZIP باشد را بفرست.\n"
            "از این به بعد فایل‌ها قبل از روبیکا با این رمز ZIP می‌شوند."
        ),
        "safemode_off": "Safe Mode غیرفعال شد.\n\nاز این به بعد فایل‌ها به‌صورت عادی ارسال می‌شوند.",
        "safemode_bad": "دستور نامعتبر. `/safemode on` یا `/safemode off`",
        "queue_empty": "صف خالی است.",
        "queue_cleared_all": "تمام موارد در صف پاک شد.",
        "removed_from_queue": "این مورد از صف حذف شد.",
        "done_no_batch": "جلسه فایل ZIP فعالی پیدا نشد یا فایل ندارد.",
        "zip_name_prompt": "نام فایل ZIP را ارسال کن (بدون پسوند).",
        "part_mb_prompt": "سایز هر پارت (MB) را بفرست. مثال: 1900",
        "part_mb_invalid": "عدد معتبر بفرست. مثال: 1900",
        "part_mb_min": "حداقل سایز پارت 50MB است.",
        "zip_no_files": "فایلی برای ساخت ZIP پیدا نشد.",
        "zip_large_warn": (
            "⚠️ حجم فایل ZIP بزرگ است. تلگرام ممکن است ارسال فایل را رد کند؛ "
            "فایل روی سرور آماده است و می‌تواند به روبیکا ارسال شود."
        ),
        "zip_ready_caption": (
            "فایل ZIP آماده شد ✅\n"
            "تعداد فایل‌ها: `{n}`\n"
            "حجم کل ورودی: `{insize}`\n"
            "حجم ZIP: `{zsize}`"
        ),
        "zip_ready_no_doc": (
            "فایل ZIP آماده شد ✅\n"
            "تعداد فایل‌ها: `{n}`\n"
            "حجم کل ورودی: `{insize}`\n"
            "حجم ZIP: `{zsize}`\n"
            "(ارسال فایل در تلگرام ناموفق؛ روی سرور آماده است)"
        ),
        "zip_queue_summary": "ZIP آماده شد: `{name}`\nآیا به روبیکا ارسال شود؟",
        "password_empty": "رمز نمی‌تواند خالی باشد.",
        "password_saved_zip": (
            "رمز ذخیره شد.\n\n"
            "از این به بعد فایل‌ها قبل از روبیکا به‌صورت ZIP رمزدار آماده می‌شوند."
        ),
        "net_status": (
            "وضعیت شبکه: `{mode}`\n"
            "دلیل: `{reason}`\n"
            "آخرین بروزرسانی: `{updated}`"
        ),
        "admin_panel": (
            "پنل ادمین:\n\n"
            "Queue total: `{qt}`\n"
            "Cancelled jobs: `{cancelled}`\n"
            "Deleted jobs: `{deleted}`\n"
            "Failed jobs: `{failed}`\n"
            "Network mode: `{net_mode}`\n"
            "Reason: `{net_reason}`"
        ),
        "eta_unknown": "نامشخص",
        "download_progress_line": (
            "📥 در حال دریافت از تلگرام\n\n"
            "فایل: `{file_name}`\n"
            "حجم: `{total}`\n"
            "پیشرفت: `{percent:.1f}%`\n"
            "`{bar}`\n"
            "سرعت: `{speed}/s`\n"
            "زمان باقی‌مانده: `{eta}`"
        ),
        "media_need_rubika": "ابتدا روبیکا را متصل کن: `/rubika_connect`",
        "media_bad_type": "فایل قابل پردازش نیست.",
        "media_download_status": "فایل دریافت شد.\n\nوضعیت: آماده‌سازی برای دانلود از تلگرام...",
        "media_zip_added": (
            "✅ فایل به جلسه ZIP اضافه شد.\n"
            "تعداد فایل‌های فعلی: `{n}`\n"
            "حجم خام تقریبی: ~`{raw_mb}` مگابایت\n\n"
            "فایل بیشتر بفرست یا «پایان فایل ZIP» را بزن."
        ),
        "media_file_ready": (
            "فایل آماده است: `{name}` ({size})\n"
            "در انتظار تأیید ارسال به روبیکا..."
        ),
        "media_error": "خطا: {error}",
        "file_prepared_summary": "فایل آماده شد: `{name}`",
        "queued_processing": "Queued for processing...",
        "confirm_send_suffix": "به روبیکا همین حالا ارسال شود؟",
        "failed_detail_title": "آخرین خطاهای ثبت‌شده برای نشست شما:",
        "confirm_cancelled": "ارسال لغو شد.",
        "cleanup_done": "پاکسازی `downloads/`: {n} فایل، حدود {mb} MB آزاد شد.",
        "direct_need_rubika": "برای حالت مستقیم اول `/rubika_connect` بزن.",
        "file_too_large": "فایل از سقف مجاز بزرگ‌تر است (حداکثر ~`{max_mb}` مگابایت با توجه به پلن و `MAX_FILE_MB`). حجم این فایل: ~`{size_mb}` مگابایت.",
        "admin_max_file": "`MAX_FILE_MB` (سقف آپلود env): `{mb}` (`0` یا خالی = بدون سقف env)",
        "admin_plan_note": "سهمیه پلن‌ها در SQLite (`user_entitlements`) — `/usage` برای کاربران.",
        "admin_clear_prefs_hint": "پاک کردن ردیف mirror prefs در SQLite: `/admin_clear_prefs <telegram_user_id>`",
        "admin_clear_state_mirrors_hint": "پاک mirror ویزارد/بچ در SQLite (JSON را عوض نمی‌کند): `/admin_clear_state_mirrors <telegram_user_id>`",
        "admin_payment_lookup_hint": "لیست آخرین پرداخت‌های SQLite (`v2_payments`): `/admin_payment_lookup <telegram_user_id> [limit]`",
        "admin_payment_lookup_empty": "هیچ ردیف پرداختی برای این کاربر نیست.",
        "admin_payment_lookup_title": "پرداخت‌ها (جدیدترین اول):\n",
        "admin_payment_status_hint": "به‌روزرسانی وضعیت یک ردیف: `/admin_payment_status <payment_id> <status> [ref_id]`",
        "admin_reconcile_billing_hint": "انقضای ردیف‌های قدیمی pending/initiated: `/admin_reconcile_billing`",
        "admin_reconcile_billing_result": "Reconcile: منقضی‌شده `{expired}`، اسکن‌شده `{scanned}`.",
        "purchase_stub_started": (
            "💳 خرید تست (`BILLING_STUB_CHECKOUT`)\n\n"
            "ردیف `v2_payments` ساخته شد.\n"
            "• payment_id: `{payment_id}`\n"
            "• authority: `{authority}`\n\n"
            "برای اعمال پلن پرو بعد از پرداخت موفق، وضعیت را `paid` کنید:\n"
            "وب‌هوک `POST …/v2_payment_event` یا `/admin_payment_status <id> paid`."
        ),
        "toolkit_network_disabled": "ابزارهای شبکه با env (`TOOLKIT_NETWORK_LIGHT`) خاموش است.",
        "toolkit_utility_disabled": "ابزارهای متنی با env (`TOOLKIT_UTILITY_LIGHT`) خاموش است.",
        "toolkit_quota_exceeded": (
            "سهمیهٔ روزانهٔ ابزار تمام شد ({used}/{limit}). فردا دوباره امتحان کنید."
        ),
        "toolkit_dns_usage": "استفاده: `/dns <hostname>` — مثال: `/dns example.com`",
        "toolkit_dns_result": "`{host}`:\n{ips}",
        "toolkit_dns_error": "DNS برای `{host}`:\n{error}",
        "toolkit_myip_result": "IP خروجی سرور (اینترنت):\n`{ip}`",
        "toolkit_myip_error": "خطا در گرفتن IP:\n{error}",
        "toolkit_ping_usage": "استفاده: `/ping <host> [port]` — پیش‌فرض پورت 443 (TCP). مثال: `/ping example.com 80`",
        "toolkit_ping_result": "TCP `{host}:{port}` ≈ `{ms}` ms",
        "toolkit_ping_error": "`{host}:{port}` — {error}",
        "toolkit_md5_usage": "استفاده: `/md5 <متن>` — MD5 روی UTF-8",
        "toolkit_md5_result": "`{digest}`",
        "toolkit_sha256_usage": "استفاده: `/sha256 <متن>`",
        "toolkit_sha256_result": "`{digest}`",
        "toolkit_b64e_usage": "استفاده: `/b64e <متن>` — Base64 استاندارد",
        "toolkit_b64e_result": "`{data}`",
        "toolkit_b64d_usage": "استفاده: `/b64d <رشته Base64>`",
        "toolkit_b64d_result": "{data}",
        "toolkit_b64d_error": "decode ناموفق: {error}",
        "toolkit_input_truncated": "(ورودی به سقف ۱۲۰۰۰ نویسه بریده شد.)",
        "quota_parallel_msg": "سقف کارهای همزمان در صف پر است (`{cur}` / `{maxp}`). بعد از اتمام یکی دوباره تلاش کن.",
        "quota_day_msg": "سقف حجم روزانه پر است. این کار ~{need} MB است؛ حدود `{left}` MB امروز باقی مانده.",
        "quota_month_msg": "سقف حجم ماهانه پر است. این کار ~{need} MB است؛ حدود `{left}` MB این ماه باقی مانده.",
        "quota_file_cap_msg": "حجم این کار از سقف هر فایل بیشتر است (حداکثر `{max_mb}` MB، این فایل ~{need_mb} MB).",
        "quota_unknown": "سقف مجاز پر است. `/usage` را بزن یا با ادمین تماس بگیر.",
        "usage_panel": (
            "مصرف و محدودیت:\n"
            "• پلن: `{tier}`\n"
            "• امروز: ~{day_used} / {day_cap} MB\n"
            "• این ماه: ~{month_used} / {month_cap} MB\n"
            "• حداکثر هر فایل: `{max_file}` MB\n"
            "• همزمان در صف/پردازش: `{parallel}` / `{max_parallel}`\n\n"
            "موفقیت ارسال به روبیکا به مصرف اضافه می‌شود."
        ),
        "usage_disabled_hint": "سهمیه‌گذاری با `DISABLE_USAGE_LIMITS` خاموش است (فقط محدودیت env در صورت تنظیم).",
        "batch_raw_hint": "جمع حجم خام فعلی: ~`{raw_mb}` MB ({n} فایل). بعد از ZIP ممکن است کمی فرق کند.",
        "direct_url_use_sendlink": "برای لینک از دکمه یا دستور `/sendlink` استفاده کن.",
        "direct_url_use_link_menu": "برای دانلود لینک/ویدیو از منوی اصلی «🔗 لینک / ویدیو» استفاده کن.",
        "purchase_info_body": (
            "💳 خرید / ارتقای پلن\n\n"
            "درگاه پرداخت خودکار هنوز وصل نیست. فعلاً:\n"
            "• از ادمین بخواه پلن را با `/admin_tier` یا `/admin_bonus` برایت تنظیم کند؛ یا\n"
            "• اسکریپت `tools/grant_plan.py` روی سرور؛ یا\n"
            "• `tools/payment_webhook_stub.py` با کلید `PAYMENT_WEBHOOK_SECRET`.\n\n"
            "بعد از پرداخت واقعی، درگاه را به همین webhook وصل کن."
        ),
        "rubika_update_hint": (
            "اگر بعد از به‌روزرسانی سرور روبیکا «قطع» شد: یک‌بار `/rubika_connect` بزن. "
            "فایل‌های session از rsync پاک نمی‌شوند؛ خطای 502 از سرورهای روبیکا هم رایج است."
        ),
    },
    "en": {
        "welcome": (
            "Hi 💙\n\n"
            "🏠 **Main menu** — two separate areas:\n"
            "📁 File transfer (Rubika, Bale, Drive, SSH)\n"
            "🧰 Tools (network, hash, Base64)\n\n"
            "Link Rubika once: `/rubika_connect`\n"
            "`/menu` main menu · `/lang` language"
        ),
        "menu_intro": (
            "🏠 Main menu\n\n"
            "📁 **Transfer** — send & move files\n"
            "🧰 **Tools** — independent utilities\n"
            "📋 **Account** — plan & queue\n"
            "⚙️ **Settings** — direct mode & network\n\n"
            "Use «🏠 Main menu» or «◀️» to go back."
        ),
        "unknown_input_hint": (
            "I could not handle this message in the current menu.\n"
            "Use the buttons below or send `/help`."
        ),
        "plan_menu_opened": (
            "📋 Account & plan\n"
            "Plan, usage, purchase, and queue."
        ),
        "pick_lang": "Choose language:",
        "lang_saved": "Language saved.",
        "transfer_menu_title": "📁 File transfer\nPick a destination — each has its own submenu.",
        "toolkit_menu_title": "🧰 Tools\nSeparate from transfer — pick a category.",
        "toolkit_network_menu_title": "🌐 Network tools\nThen send command + value (e.g. `/dns google.com`).",
        "toolkit_crypto_menu_title": "🔐 Hash & Base64\ne.g. `/md5 text` or `/b64e hello`",
        "rubika_menu_title": "💬 Rubika\nConnect and check your account.",
        "bale_menu_title": "📨 Bale\nYour bot & destination — `/bale_connect`",
        "drive_menu_title": "☁️ Google Drive\n`/drive_connect` then send files.",
        "ssh_menu_title": "🖥 SSH servers\nYour servers. Upload: `/ssh_put id path`",
        "files_menu_title": "📦 Files, ZIP & queue\nRubika must be linked.",
        "settings_menu_title": "📤 Direct send\nOnly one destination at a time — connect it before enabling.",
        "direct_send_menu_title": "📤 Direct send",
        "admin_menu_title": "🛡 Admin",
        "admin_denied": "You are not an admin.",
        "no_worker_events": "Worker log file not found yet.",
        "no_recent_jobs": "No recent task_done/task_failed for this chat.",
        "recent_jobs_title": "Recent jobs (worker):",
        "btn_main_transfer": "📁 File transfer",
        "btn_main_toolkit": "🧰 Tools",
        "btn_main_settings": "📤 Direct send",
        "btn_main_link_direct": "🔗 Link / video",
        "btn_main_help": "❓ Help",
        "btn_main_plan_section": "📋 Account & plan",
        "btn_main_admin": "🛡 Admin",
        "btn_back_main": "🏠 Main menu",
        "btn_back_transfer": "◀️ Transfer",
        "btn_back_toolkit": "◀️ Tools",
        "btn_transfer_rubika": "💬 Rubika",
        "btn_transfer_bale": "📨 Bale",
        "btn_transfer_drive": "☁️ Drive",
        "btn_transfer_ssh": "🖥 SSH",
        "btn_transfer_files": "📦 Files & ZIP",
        "btn_rub_connect": "🔗 Connect",
        "btn_rub_status": "✅ Status",
        "btn_zip_start": "📥 Start ZIP",
        "btn_zip_end": "✅ End ZIP",
        "btn_send_content": "✉️ Text / link",
        "btn_queue": "📋 Queue",
        "btn_clear_all": "🗑 Clear all",
        "btn_toolkit_network": "🌐 Network & IP",
        "btn_toolkit_crypto": "🔐 Hash & Base64",
        "btn_tool_dns": "🔍 DNS",
        "btn_tool_myip": "📍 My IP",
        "btn_tool_ping": "📡 Ping",
        "btn_tool_md5": "#️⃣ MD5",
        "btn_tool_sha256": "🔒 SHA256",
        "btn_tool_b64e": "📤 B64 encode",
        "btn_tool_b64d": "📥 B64 decode",
        "btn_plan_plan": "📊 Plan",
        "btn_plan_usage": "📈 Usage",
        "btn_plan_buy": "💳 Purchase",
        "btn_direct_rubika_on": "🚀 Direct Rubika",
        "btn_direct_bale_on": "📨 Direct Bale",
        "btn_direct_drive_on": "☁️ Direct Drive",
        "btn_direct_rubika_off": "⏸ Off direct Rubika",
        "btn_direct_bale_off": "⏸ Off direct Bale",
        "btn_direct_drive_off": "⏸ Off direct Drive",
        "btn_netstatus": "📶 Network",
        "btn_ssh_list": "📋 Server list",
        "btn_ssh_add_help": "➕ Add server",
        "btn_drive_download_help": "⬇️ Drive download",
        "btn_admin_panel": "🛡 Panel",
        "btn_inline_refresh": "Refresh",
        "btn_inline_pending": "Pending",
        "btn_inline_failed": "Failed",
        "btn_inline_clear": "Clear my queue",
        "btn_inline_recent": "Recent jobs",
        "btn_inline_faildetail": "Error details",
        "queue_kb_refresh": "Refreshed",
        "queue_kb_cleared": "Queue cleared",
        "directmode_usage": (
            "Direct send (one target):\n"
            "`/directmode rubika on` · `/directmode bale on` · `/directmode drive on`\n"
            "Off: `/directmode rubika off` (or bale/drive)\n"
            "Legacy: `/directmode on` = Rubika"
        ),
        "direct_on_rubika": "Direct send to Rubika enabled.",
        "direct_on_bale": "Direct send to Bale enabled.",
        "direct_on_drive": "Direct send to Google Drive enabled.",
        "direct_off": "Direct send disabled.",
        "direct_off_wrong_target": "Active target is `{active}` — turn that off first.",
        "direct_url_only_for_bale_drive": "Bale/Drive direct mode supports links/videos only.",
        "link_menu_opened": (
            "🔗 Link / video download\n"
            "Send an HTTP(S) or YouTube link.\n"
            "Metadata first, then pick destination.\n"
            "No server download until destination is connected."
        ),
        "link_send_url": "Send a valid http/https or YouTube link.",
        "link_probing": "Checking link (no download yet)…",
        "link_probe_summary": "📎 `{title}`\nType: {link_type}\nApprox. size: {size}",
        "link_size_unknown": "unknown",
        "link_type_direct": "direct link",
        "link_type_youtube": "YouTube",
        "link_type_magnet": "torrent",
        "link_pick_dest": "Choose destination:",
        "link_dest_rubika": "Rubika",
        "link_dest_bale": "Bale",
        "link_dest_drive": "Google Drive",
        "link_dest_cancel": "Cancel",
        "link_need_rubika": "Rubika not connected. `/rubika_connect`",
        "bale_file_too_large": "This file is too large for Bale. Bale limit is `{max_mb}` MB; yours is ~{size_mb} MB.",
        "link_probe_unsupported": "Cannot download this link. ({detail})",
        "link_ytdlp_missing": "YouTube needs `yt-dlp` on the server.",
        "link_magnet_unsupported": "Magnet links are not supported yet.",
        "link_session_expired": "Selection expired — send the link again.",
        "link_cancelled": "Cancelled.",
        "link_downloading": "Downloading on server…",
        "link_download_failed": "Download failed: {error}",
        "link_download_done_queue": "Downloaded; queuing upload…",
        "newbatch_ok": (
            "ZIP batch started.\n"
            "Send files, then tap «End ZIP» or `/done`."
        ),
        "prompt_sendtext": "Send the text.",
        "prompt_sendlink": "Send the link.",
        "queue_panel": (
            "Queue:\n\n"
            "- Pending in SQLite (your session): `{pending}`\n"
            "- Currently processing (worker): `{processing}`\n"
            "- Failed (global): `{failed}`\n"
            "- Deleted: `{deleted}`\n"
            "- Cancelled: `{cancelled}`\n\n"
            "If upload looks stuck but Pending is `0`, the job left the queue and the worker is busy.\n\n"
            "Use «Clear my queue» to wipe your pending tasks."
        ),
        "queue_processing_none": "`—`",
        "queue_processing_detail": "`{job_id}` type `{task_type}` — `{file}` (~{size})",
        "bale_not_connected": "Bale is not linked. Use `/bale_connect` with your own Bale bot token.",
        "bale_ask_token": "Send your Bale bot token (from Bale @botfather). Stored only for your Telegram account.",
        "bale_token_invalid": "Invalid Bale token: {detail}",
        "bale_token_ok": "Bale bot verified (@{bot}). Send the destination `chat_id`.",
        "bale_chat_id_empty": "chat_id is empty.",
        "bale_connected_ok": "Bale linked ✅ destination: `{chat_id}`",
        "bale_already_connected": "Bale already linked. `/bale_disconnect` then `/bale_connect` to replace.",
        "bale_disconnected": "Bale disconnected.",
        "btn_bale_connect": "🔗 Connect",
        "btn_bale_status": "✅ Status",
        "btn_bale_disconnect": "❌ Disconnect",
        "bale_status_no_chat": "Token OK ({detail}). Missing chat_id — continue `/bale_connect`.",
        "bale_status_ok": "Bale: chat_id=`{chat_id}` — {detail}",
        "bale_set_chat_usage": "Usage: `/bale_set_chat <bale_chat_id>` (after `/bale_connect`)",
        "bale_set_chat_saved": "Bale destination saved: `{chat_id}`",
        "drive_not_connected": "Google Drive not linked. Use `/drive_connect` and upload your service-account JSON.",
        "drive_ask_sa_json": "Send your Google service-account JSON as a **document** file.",
        "drive_ask_folder_id": "Send the Drive folder ID (from the folder URL):",
        "drive_folder_empty": "folder_id is empty.",
        "drive_sa_missing_retry": "Service account file missing. Run `/drive_connect` again.",
        "drive_connected_ok": "Drive linked ✅ folder=`{folder_id}`",
        "drive_disconnected": "Drive disconnected.",
        "btn_drive_connect": "🔗 Connect",
        "btn_drive_status": "✅ Status",
        "btn_drive_disconnect": "❌ Disconnect",
        "drive_sa_need_document": "Send the JSON as a document file, not plain text.",
        "drive_sa_need_json": "File name must end with `.json`.",
        "drive_sa_invalid": "Invalid JSON: {error}",
        "drive_status_line": "Drive configured: {ok}\n{detail}",
        "ssh_list_empty": "No SSH servers. Use `/ssh_add label host port user`",
        "ssh_list_title": "SSH servers:",
        "ssh_list_row": "`#{id}` {label} — `{ssh_user}@{host}:{port}`",
        "ssh_add_usage": "Usage: `/ssh_add <label> <host> <port> <user> [password]`",
        "ssh_add_ok": "Saved server `{label}` ({host}:{port}).",
        "ssh_put_usage": "Usage: `/ssh_put <server_id> <remote_path>` then send the file",
        "ssh_put_await_file": "Remote path saved. Send the file in Telegram now.",
        "ssh_server_not_found": "SSH server not found.",
        "ssh_auth_missing": "No password/key for this server. Re-add with `/ssh_add` and password.",
        "bale_active_hint": "After `/bale_connect`, send a file here to upload via your Bale bot (~20 MB max).",
        "drive_active_hint": "After `/drive_connect`, send a file to upload to your Drive. Download: `/drive_download <id>`",
        "drive_download_usage": "Usage: `/drive_download <google_drive_file_id>`",
        "ssh_get_usage": "Usage: `/ssh_get <server_id> <remote_path>`",
        "help_short": (
            "Quick help:\n\n"
            "🏠 `/menu` — 📁 Transfer and 🧰 Tools are separate\n\n"
            "📁 Transfer:\n"
            "- Rubika `/rubika_connect` · Bale `/bale_connect` · Drive `/drive_connect`\n"
            "- SSH `/ssh_list` · ZIP `/newbatch` `/done`\n\n"
            "🧰 Tools (own menu):\n"
            "- `/dns host` · `/myip` · `/ping host:port` · `/md5 text` · `/sha256` · `/b64e` `/b64d`\n\n"
            "📤 Direct send: `/directmode rubika|bale|drive on|off` · 🔗 links: Link / video menu\n\n"
            "Troubleshooting:\n"
            "- Network: `/netstatus`\n"
            "- Admin: `/admin`\n"
            "- Remove one job: `/del <job_id>`\n\n"
            "Log analysis: `/loghelp`\n"
            "Usage & limits: `/usage` — plan bundle: `/plan` — purchase info: `/purchase`"
        ),
        "loghelp_body": (
            "Job log analysis:\n\n"
            "1) Copy `job_id` from the Queued message.\n"
            "2) In bot logs, find `task_queued` with that `job_id`.\n"
            "3) In worker logs you should see:\n"
            "   `task_started` -> (`task_done` or `task_failed`).\n"
            "4) If you see `task_requeued`, network/access failed and a new job was created.\n"
            "5) For Rubika login, check `rubika_connect_ok` / `rubika_connect_failed`.\n\n"
            "Log paths:\n"
            "- `/opt/tele2rub/queue/bot_events.jsonl`\n"
            "- `/opt/tele2rub/queue/worker_events.jsonl`\n"
            "- `/tmp/tele2rub-installer.jsonl`"
        ),
        "rubika_not_connected": "Rubika is not linked. Use `/rubika_connect`.",
        "rubika_checking": "Checking live Rubika session...",
        "rubika_ok": (
            "Rubika session is valid ✅\n"
            "session: `{session}`\n"
            "details: `{details}`"
        ),
        "rubika_invalid_session": (
            "Saved session is not valid ❌\n"
            "session: `{session}`\n"
            "error: `{details}`\n\n"
            "Use «Connect Rubika» again."
        ),
        "rubika_already_connected": (
            "Rubika is already linked.\n"
            "session: `{session}`\n\n"
            "To reconnect, send a new phone number."
        ),
        "rubika_ask_phone": (
            "Send your Rubika phone with country code.\n"
            "Example: `98912xxxxxxx`"
        ),
        "rubika_passkey_needed": "This number needs a PassKey. Send your Rubika PassKey.",
        "rubika_code_sent": "Code sent. Send the Rubika verification code.",
        "rubika_send_code_error": "Error sending Rubika code: {error}",
        "rubika_connected_ok": "Rubika linked successfully ✅",
        "rubika_bad_code": "Invalid code or sign-in error: {error}",
        "version_line": "telegramtorubika `{version}`",
        "update_notice": (
            "Bot updated ✅\n"
            "Version: `{version}`\n"
            "`/menu` main menu · `/lang` language"
        ),
        "prompt_quick_message": (
            "Send your next message (plain text, a link, or both).\n"
            "It is queued for Rubika without an extra confirmation step."
        ),
        "empty_message": "Message is empty.",
        "text_queueing": "Queueing...",
        "text_queued": (
            "Queued ✅\n"
            "Job: `{job_id}`\n"
            "Approx. position in your queue: `{qpos}`\n\n"
            "Use «Queue» for details."
        ),
        "sendtext_usage": "Format: `/sendtext ...`",
        "sendlink_usage": "Format: `/sendlink <url>`",
        "invalid_link": "No valid http(s) link found in that text.",
        "safemode_usage": "Use `/safemode on` or `/safemode off`.",
        "safemode_on": (
            "Safe Mode enabled.\n\n"
            "Send the password you want on ZIP files.\n"
            "Files will be ZIP-encrypted before Rubika."
        ),
        "safemode_off": "Safe Mode disabled.\n\nFiles will upload normally.",
        "safemode_bad": "Invalid command. Use `/safemode on` or `/safemode off`.",
        "queue_empty": "Your queue is empty.",
        "queue_cleared_all": "All your queued tasks were removed.",
        "removed_from_queue": "Removed from queue.",
        "done_no_batch": "No active ZIP batch or no files collected.",
        "zip_name_prompt": "Send the ZIP base name (no extension).",
        "part_mb_prompt": "Part size in MB, e.g. `1900`",
        "part_mb_invalid": "Send a valid number, e.g. `1900`",
        "part_mb_min": "Minimum part size is 50 MB.",
        "zip_no_files": "No files left to build the ZIP.",
        "zip_large_warn": (
            "⚠️ ZIP is large; Telegram may refuse sending the file. "
            "It is still on the server and can go to Rubika."
        ),
        "zip_ready_caption": (
            "ZIP ready ✅\n"
            "Files: `{n}`\n"
            "Input size: `{insize}`\n"
            "ZIP size: `{zsize}`"
        ),
        "zip_ready_no_doc": (
            "ZIP ready ✅\n"
            "Files: `{n}`\n"
            "Input size: `{insize}`\n"
            "ZIP size: `{zsize}`\n"
            "(Telegram upload failed; file is on the server)"
        ),
        "zip_queue_summary": "ZIP ready: `{name}`\nSend to Rubika?",
        "password_empty": "Password cannot be empty.",
        "password_saved_zip": (
            "Password saved.\n\n"
            "Files will be prepared as passworded ZIP before Rubika."
        ),
        "net_status": (
            "Network: `{mode}`\n"
            "Reason: `{reason}`\n"
            "Updated: `{updated}`"
        ),
        "admin_panel": (
            "Admin panel:\n\n"
            "Queue total: `{qt}`\n"
            "Cancelled jobs: `{cancelled}`\n"
            "Deleted jobs: `{deleted}`\n"
            "Failed jobs: `{failed}`\n"
            "Network mode: `{net_mode}`\n"
            "Reason: `{net_reason}`"
        ),
        "eta_unknown": "unknown",
        "download_progress_line": (
            "📥 Downloading from Telegram\n\n"
            "File: `{file_name}`\n"
            "Size: `{total}`\n"
            "Progress: `{percent:.1f}%`\n"
            "`{bar}`\n"
            "Speed: `{speed}/s`\n"
            "ETA: `{eta}`"
        ),
        "media_need_rubika": "Link Rubika first: `/rubika_connect`",
        "media_bad_type": "Unsupported media type.",
        "media_download_status": "Received.\n\nPreparing download from Telegram...",
        "media_zip_added": (
            "✅ Added to ZIP batch.\n"
            "Files in batch: `{n}`\n"
            "Approx. raw total: ~`{raw_mb}` MB\n\n"
            "Send more or tap «End ZIP»."
        ),
        "media_file_ready": (
            "File ready: `{name}` ({size})\n"
            "Waiting for confirmation to send to Rubika..."
        ),
        "media_error": "Error: {error}",
        "file_prepared_summary": "File prepared: `{name}`",
        "queued_processing": "Queued for processing...",
        "confirm_send_suffix": "Send to Rubika now?",
        "failed_detail_title": "Recent failures for your Rubika session:",
        "confirm_cancelled": "Send cancelled.",
        "cleanup_done": "Cleaned `downloads/`: {n} files, ~{mb} MB freed.",
        "direct_need_rubika": "Link Rubika first: `/rubika_connect`",
        "file_too_large": "File exceeds the limit (max ~`{max_mb}` MB from plan + `MAX_FILE_MB`). This file is ~`{size_mb}` MB.",
        "admin_max_file": "`MAX_FILE_MB` (env cap): `{mb}` (`0` or empty = no env cap)",
        "admin_plan_note": "Per-user plans live in SQLite (`user_entitlements`). Users: `/usage`.",
        "admin_clear_prefs_hint": "Clear cached `v2_user_prefs` row: `/admin_clear_prefs <telegram_user_id>`",
        "admin_clear_state_mirrors_hint": "Clear wizard/batch SQLite mirrors only (not JSON files): `/admin_clear_state_mirrors <telegram_user_id>`",
        "admin_payment_lookup_hint": "Recent `v2_payments` rows: `/admin_payment_lookup <telegram_user_id> [limit]`",
        "admin_payment_lookup_empty": "No payment rows for this user.",
        "admin_payment_lookup_title": "Payments (newest first):\n",
        "admin_payment_status_hint": "Set one payment row status: `/admin_payment_status <payment_id> <status> [ref_id]`",
        "admin_reconcile_billing_hint": "Expire stale pending/initiated payments: `/admin_reconcile_billing`",
        "admin_reconcile_billing_result": "Reconcile: expired `{expired}`, scanned `{scanned}`.",
        "purchase_stub_started": (
            "💳 Test checkout (`BILLING_STUB_CHECKOUT`)\n\n"
            "Created `v2_payments` row.\n"
            "• payment_id: `{payment_id}`\n"
            "• authority: `{authority}`\n\n"
            "To grant Pro after success, set status to `paid`:\n"
            "`POST …/v2_payment_event` or `/admin_payment_status <id> paid`."
        ),
        "toolkit_network_disabled": "Network toolkit is off (set `TOOLKIT_NETWORK_LIGHT`).",
        "toolkit_utility_disabled": "Text/encoding toolkit is off (set `TOOLKIT_UTILITY_LIGHT`).",
        "toolkit_quota_exceeded": "Daily toolkit quota reached ({used}/{limit}). Try again tomorrow.",
        "toolkit_dns_usage": "Usage: `/dns <hostname>` — e.g. `/dns example.com`",
        "toolkit_dns_result": "`{host}`:\n{ips}",
        "toolkit_dns_error": "DNS error for `{host}`:\n{error}",
        "toolkit_myip_result": "Server egress IP:\n`{ip}`",
        "toolkit_myip_error": "Could not fetch IP:\n{error}",
        "toolkit_ping_usage": "Usage: `/ping <host> [port]` — default port 443 (TCP). E.g. `/ping example.com 80`",
        "toolkit_ping_result": "TCP `{host}:{port}` ~ `{ms}` ms",
        "toolkit_ping_error": "`{host}:{port}` — {error}",
        "toolkit_md5_usage": "Usage: `/md5 <text>` — MD5 (UTF-8)",
        "toolkit_md5_result": "`{digest}`",
        "toolkit_sha256_usage": "Usage: `/sha256 <text>`",
        "toolkit_sha256_result": "`{digest}`",
        "toolkit_b64e_usage": "Usage: `/b64e <text>` — standard Base64",
        "toolkit_b64e_result": "`{data}`",
        "toolkit_b64d_usage": "Usage: `/b64d <base64 string>`",
        "toolkit_b64d_result": "{data}",
        "toolkit_b64d_error": "Decode failed: {error}",
        "toolkit_input_truncated": "(Input truncated to 12000 characters.)",
        "quota_parallel_msg": "Too many jobs at once for your plan (`{cur}` / `{maxp}`). Wait for one to finish.",
        "quota_day_msg": "Daily data limit reached. This job ~{need} MB; ~{left} MB left today.",
        "quota_month_msg": "Monthly data limit reached. This job ~{need} MB; ~{left} MB left this month.",
        "quota_file_cap_msg": "This file exceeds the per-file cap (`{max_mb}` MB max; yours ~{need_mb} MB).",
        "quota_unknown": "Quota blocked. Try `/usage` or contact admin.",
        "usage_panel": (
            "Usage & limits:\n"
            "• Tier: `{tier}`\n"
            "• Today: ~{day_used} / {day_cap} MB\n"
            "• This month: ~{month_used} / {month_cap} MB\n"
            "• Max per file: `{max_file}` MB\n"
            "• Parallel jobs: `{parallel}` / `{max_parallel}`\n\n"
            "Usage increments when Rubika upload succeeds."
        ),
        "usage_disabled_hint": "Quotas are off (`DISABLE_USAGE_LIMITS`). Only optional env caps apply.",
        "batch_raw_hint": "Current raw total ~`{raw_mb}` MB ({n} files). ZIP size may differ slightly.",
        "direct_url_use_sendlink": "For links use the button or `/sendlink`.",
        "direct_url_use_link_menu": "For link/video download use main menu «🔗 Link / video».",
        "purchase_info_body": (
            "💳 Plans / purchase\n\n"
            "Automatic checkout is not wired yet. For now:\n"
            "• Ask an admin to run `/admin_tier` or `/admin_bonus`; or\n"
            "• Use `tools/grant_plan.py` on the server; or\n"
            "• `tools/payment_webhook_stub.py` + `PAYMENT_WEBHOOK_SECRET`.\n\n"
            "Connect your real PSP to that webhook when ready."
        ),
        "rubika_update_hint": (
            "If Rubika breaks after a server update: run `/rubika_connect` once. "
            "Session files are excluded from rsync; 502s from Rubika edges are common."
        ),
    },
}


def get_lang(user_id: int) -> str:
    users = load_users()
    lang = users.get(get_user_key(user_id), {}).get("lang")
    if lang in ("fa", "en"):
        return lang
    try:
        db_lang = queue.get_lang(user_id)
    except Exception as e:
        log_event("v2_user_prefs_lang_read_failed", user_id=user_id, error=str(e))
        return "fa"
    if db_lang in ("fa", "en"):
        return db_lang
    return "fa"


def set_lang(user_id: int, lang: str):
    if lang not in ("fa", "en"):
        lang = "fa"
    users = load_users()
    key = get_user_key(user_id)
    item = users.get(key, {})
    item["lang"] = lang
    users[key] = item
    save_users(users)
    try:
        queue.upsert_lang(user_id, lang)
    except Exception as e:
        log_event("v2_user_prefs_lang_upsert_failed", user_id=user_id, error=str(e))


def tr(user_id: int, key: str, **kwargs) -> str:
    lang = get_lang(user_id)
    text = I18N.get(lang, I18N["fa"]).get(key) or I18N["fa"].get(key) or key
    try:
        return text.format(**kwargs)
    except Exception:
        return text


def remember_chat(chat_id: int):
    data = load_json(KNOWN_CHATS_FILE, {"ids": []})
    ids = data.get("ids", [])
    if chat_id not in ids:
        ids.append(chat_id)
        data["ids"] = ids
        save_json(KNOWN_CHATS_FILE, data)


def recent_jobs_summary(user_id: int, limit: int = 10) -> str:
    path = WORKER_EVENTS_FILE
    if not path.exists():
        return tr(user_id, "no_worker_events")
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.readlines()
    except Exception:
        return tr(user_id, "no_worker_events")
    interested = []
    for line in reversed(raw[-8000:]):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if row.get("chat_id") != user_id:
            continue
        ev = row.get("event")
        if ev not in ("task_done", "task_failed", "task_requeued"):
            continue
        interested.append(row)
        if len(interested) >= limit:
            break
    if not interested:
        return tr(user_id, "no_recent_jobs")
    lines = []
    for row in interested:
        ev = row.get("event")
        jid = row.get("job_id", "?")
        dur = row.get("duration_ms")
        err = (row.get("error") or "")[:120]
        if ev == "task_done":
            suf = f" {dur}ms" if dur is not None else ""
            lines.append(f"✅ `{jid}` done{suf}")
        elif ev == "task_failed":
            lines.append(f"❌ `{jid}` failed: `{err}`")
        else:
            lines.append(f"🔄 `{jid}` requeued")
    return "\n".join(lines)


def dir_bytes(path: Path) -> int:
    total = 0
    if not path.exists():
        return 0
    try:
        for f in path.rglob("*"):
            if f.is_file():
                try:
                    total += f.stat().st_size
                except OSError:
                    pass
    except OSError:
        pass
    return total


def admin_disk_report_text() -> str:
    du = shutil.disk_usage(BASE_DIR)
    dl = dir_bytes(DOWNLOAD_DIR)
    qz = dir_bytes(QUEUE_DIR)
    return (
        f"💾 Storage\n"
        f"- Free / total: `{pretty_size(float(du.free))}` / `{pretty_size(float(du.total))}`\n"
        f"- `{DOWNLOAD_DIR.name}/`: `{pretty_size(float(dl))}`\n"
        f"- `{QUEUE_DIR.name}/`: `{pretty_size(float(qz))}`"
    )


def recent_failed_detail_text(session: Optional[str], limit: int = 8) -> str:
    if not session or not FAILED_FILE.exists():
        return "—"
    rows = []
    try:
        with open(FAILED_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                task = row.get("task") or {}
                if task.get("rubika_session") != session:
                    continue
                jid = task.get("job_id", "?")
                fn = task.get("file_name") or ""
                if not fn and task.get("path"):
                    fn = Path(str(task.get("path"))).name
                if not fn:
                    fn = task.get("type", "?")
                err = (row.get("error") or "")[:900]
                rows.append(f"`{jid}` `{fn}`\n`{err}`")
                if len(rows) >= limit:
                    break
    except Exception:
        return "—"
    return "\n\n".join(rows) if rows else "—"


def build_main_menu(user_id: int) -> ReplyKeyboardMarkup:
    return menu_engine.build_main_menu(user_id, tr, user_id in ADMIN_IDS)


def build_plan_menu(user_id: int) -> ReplyKeyboardMarkup:
    return menu_engine.build_plan_menu(user_id, tr)


def build_transfer_menu(user_id: int) -> ReplyKeyboardMarkup:
    return menu_engine.build_transfer_menu(user_id, tr)


def build_toolkit_menu(user_id: int) -> ReplyKeyboardMarkup:
    return menu_engine.build_toolkit_menu(user_id, tr)


def build_toolkit_network_menu(user_id: int) -> ReplyKeyboardMarkup:
    return menu_engine.build_toolkit_network_menu(user_id, tr)


def build_toolkit_crypto_menu(user_id: int) -> ReplyKeyboardMarkup:
    return menu_engine.build_toolkit_crypto_menu(user_id, tr)


def build_bale_menu(user_id: int) -> ReplyKeyboardMarkup:
    return menu_engine.build_bale_menu(user_id, tr)


def build_drive_menu(user_id: int) -> ReplyKeyboardMarkup:
    return menu_engine.build_drive_menu(user_id, tr)


def build_ssh_menu(user_id: int) -> ReplyKeyboardMarkup:
    return menu_engine.build_ssh_menu(user_id, tr)


def build_rubika_menu(user_id: int) -> ReplyKeyboardMarkup:
    return menu_engine.build_rubika_menu(user_id, tr)


def build_files_menu(user_id: int) -> ReplyKeyboardMarkup:
    return menu_engine.build_files_menu(user_id, tr)


def build_link_direct_menu(user_id: int) -> ReplyKeyboardMarkup:
    return menu_engine.build_link_direct_menu(user_id, tr)


def build_settings_menu(user_id: int) -> ReplyKeyboardMarkup:
    return menu_engine.build_settings_menu(user_id, tr, get_direct_mode_target(user_id))


def build_admin_menu(user_id: int) -> ReplyKeyboardMarkup:
    return menu_engine.build_admin_menu(user_id, tr)


def safe_filename(name: Optional[str]) -> str:
    name = (name or "file.bin").strip()
    name = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "_", name)
    name = name.rstrip(". ")
    return name[:200] or "file.bin"


def split_name(filename: str) -> tuple[str, str]:
    path = Path(filename)
    return path.stem, path.suffix


def get_media(message: Message):
    media_types = [
        ("document", message.document),
        ("video", message.video),
        ("audio", message.audio),
        ("voice", message.voice),
        ("photo", message.photo),
        ("animation", message.animation),
        ("video_note", message.video_note),
        ("sticker", message.sticker),
    ]

    for media_type, media in media_types:
        if media:
            return media_type, media

    return None, None


def build_download_filename(message: Message, media_type: str, media) -> str:
    original_name = getattr(media, "file_name", None)

    if not original_name:
        file_unique_id = getattr(media, "file_unique_id", None) or "file"

        default_extensions = {
            "document": ".bin",
            "video": ".mp4",
            "audio": ".mp3",
            "voice": ".ogg",
            "photo": ".jpg",
            "animation": ".mp4",
            "video_note": ".mp4",
            "sticker": ".webp",
        }

        original_name = f"{file_unique_id}{default_extensions.get(media_type, '.bin')}"

    original_name = safe_filename(original_name)
    stem, suffix = split_name(original_name)

    unique_name = f"{stem}_{message.id}{suffix or '.bin'}"
    return safe_filename(unique_name)


def make_bundle_zip_local(file_paths: list[Path], zip_name: str, password: str = "") -> Path:
    zip_base = safe_filename(zip_name or f"bundle_{int(time.time())}")
    zip_path = DOWNLOAD_DIR / f"{zip_base}.zip"
    if zip_path.exists():
        zip_path = DOWNLOAD_DIR / f"{zip_base}_{int(time.time())}.zip"
    if password:
        with pyzipper.AESZipFile(
            zip_path,
            "w",
            compression=pyzipper.ZIP_STORED,
            encryption=pyzipper.WZ_AES,
        ) as zip_file:
            zip_file.setpassword(password.encode("utf-8"))
            for file_path in file_paths:
                zip_file.write(file_path, arcname=file_path.name)
    else:
        with pyzipper.AESZipFile(zip_path, "w", compression=pyzipper.ZIP_STORED) as zip_file:
            for file_path in file_paths:
                zip_file.write(file_path, arcname=file_path.name)
    return zip_path

waiting_for_zip_password = False


def load_json(path: Path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def save_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def log_event(event: str, **kwargs):
    payload = {
        "ts": int(time.time()),
        "event": event,
        **kwargs,
    }
    try:
        with open(BOT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass


def load_users() -> dict:
    return load_json(USERS_FILE, {})


def save_users(data: dict):
    save_json(USERS_FILE, data)


def get_user_key(user_id: int) -> str:
    return str(user_id)


def get_user_session(user_id: int) -> Optional[str]:
    users = load_users()
    item = users.get(get_user_key(user_id), {})
    if item.get("connected"):
        return item.get("session")
    try:
        db_sess = queue.get_rubika_session(user_id)
    except Exception as e:
        log_event("v2_user_prefs_rubika_session_read_failed", user_id=user_id, error=str(e))
        return None
    if db_sess:
        return db_sess
    return None


def _persist_rubika_session_prefs(user_id: int, session_name: str) -> None:
    try:
        queue.upsert_rubika_session(user_id, session_name)
    except Exception as e:
        log_event("v2_user_prefs_rubika_session_upsert_failed", user_id=user_id, error=str(e))


def check_rubika_session_sync(session_name: str) -> tuple[bool, str]:
    client = RubikaClient(name=session_name)
    try:
        client.start()
        me = client.get_me()
        phone = getattr(getattr(me, "user", None), "phone", "")
        guid = getattr(getattr(me, "user", None), "user_guid", "")
        return True, f"phone={phone or 'unknown'} guid={guid or 'unknown'}"
    except Exception as e:
        return False, str(e)
    finally:
        try:
            client.disconnect()
        except Exception:
            pass


def get_direct_mode_target(user_id: int) -> Optional[str]:
    return load_direct_mode_target(
        user_id,
        load_users=load_users,
        get_user_key=get_user_key,
        queue=queue,
    )


def set_direct_mode_target(user_id: int, target: Optional[str]) -> None:
    save_direct_mode_target(
        user_id,
        target,  # type: ignore[arg-type]
        load_users=load_users,
        save_users=save_users,
        get_user_key=get_user_key,
        queue=queue,
    )


def is_direct_mode(user_id: int) -> bool:
    return get_direct_mode_target(user_id) is not None


def set_direct_mode(user_id: int, enabled: bool):
    """Legacy bool API: True → rubika, False → off."""
    set_direct_mode_target(user_id, "rubika" if enabled else None)


def load_user_states() -> dict:
    return load_json(USER_STATES_FILE, {})


def save_user_states(data: dict):
    save_json(USER_STATES_FILE, data)


def load_batch_sessions() -> dict:
    return load_json(BATCH_FILE, {})


def save_batch_sessions(data: dict):
    save_json(BATCH_FILE, data)


def get_state(user_id: int) -> dict:
    key = get_user_key(user_id)
    s: dict = {}
    if V2_EPHEMERAL_READ_PRIMARY_SQLITE:
        try:
            mirrored = queue.get_user_state_mirror(user_id)
            if mirrored:
                s = dict(mirrored)
        except Exception as e:
            log_event("v2_user_state_mirror_read_failed", user_id=user_id, error=str(e))
        if not s:
            states = load_user_states()
            if key in states:
                raw = states[key]
                s = dict(raw) if isinstance(raw, dict) else {}
    else:
        states = load_user_states()
        if key in states:
            raw = states[key]
            s = dict(raw) if isinstance(raw, dict) else {}
        else:
            try:
                mirrored = queue.get_user_state_mirror(user_id)
                if mirrored:
                    s = dict(mirrored)
            except Exception as e:
                log_event("v2_user_state_mirror_read_failed", user_id=user_id, error=str(e))
    if MENU_SECTION_KEY in s:
        return s
    try:
        sec = queue.get_menu_section(user_id)
    except Exception as e:
        log_event("v2_user_prefs_read_failed", user_id=user_id, error=str(e))
        return s
    if not sec:
        return s
    out = dict(s)
    out[MENU_SECTION_KEY] = sec
    return out


def get_effective_menu_section(user_id: int) -> Optional[str]:
    """Read menu section from the dual-written state with SQLite fallback."""
    section = get_state(user_id).get(MENU_SECTION_KEY)
    if section:
        return str(section)
    try:
        return queue.get_menu_section(user_id)
    except Exception as e:
        log_event("v2_user_prefs_read_failed", user_id=user_id, error=str(e))
        return None


def set_state(user_id: int, data: dict):
    states = load_user_states()
    states[get_user_key(user_id)] = data
    save_user_states(states)
    try:
        queue.upsert_user_state_mirror(user_id, data)
    except Exception as e:
        log_event("v2_user_state_mirror_upsert_failed", user_id=user_id, error=str(e))


def clear_state(user_id: int):
    """Drop wizard keys from ``user_states.json`` only.

    Does **not** delete ``v2_user_prefs`` so mirrors for menu/lang/direct_mode/rubika_session stay intact.
    """
    states = load_user_states()
    states.pop(get_user_key(user_id), None)
    save_user_states(states)
    try:
        queue.delete_user_state_mirror(user_id)
    except Exception as e:
        log_event("v2_user_state_mirror_delete_failed", user_id=user_id, error=str(e))


def merge_user_state(user_id: int, patch: dict) -> None:
    cur = dict(get_state(user_id))
    cur.update(patch)
    set_state(user_id, cur)


def set_menu_section(user_id: int, section: MenuSection) -> None:
    merge_user_state(user_id, {MENU_SECTION_KEY: section.value})
    try:
        queue.upsert_menu_section(user_id, section.value)
    except Exception as e:
        log_event("v2_user_prefs_upsert_failed", user_id=user_id, error=str(e))


def set_state_preserving_menu(user_id: int, new_state: dict) -> None:
    """Replace wizard/session keys but keep MENU_SECTION_KEY if already set."""
    prev = get_state(user_id)
    merged = dict(new_state)
    if MENU_SECTION_KEY in prev:
        merged[MENU_SECTION_KEY] = prev[MENU_SECTION_KEY]
    set_state(user_id, merged)


def get_batch(user_id: int) -> dict:
    key = get_user_key(user_id)
    if V2_EPHEMERAL_READ_PRIMARY_SQLITE:
        try:
            mirrored = queue.get_batch_session_mirror(user_id)
            if mirrored:
                return dict(mirrored)
        except Exception as e:
            log_event("v2_batch_session_mirror_read_failed", user_id=user_id, error=str(e))
        sessions = load_batch_sessions()
        if key in sessions:
            raw = sessions[key]
            return dict(raw) if isinstance(raw, dict) else {}
        return {}
    sessions = load_batch_sessions()
    if key in sessions:
        raw = sessions[key]
        return dict(raw) if isinstance(raw, dict) else {}
    try:
        mirrored = queue.get_batch_session_mirror(user_id)
        return dict(mirrored) if mirrored else {}
    except Exception as e:
        log_event("v2_batch_session_mirror_read_failed", user_id=user_id, error=str(e))
        return {}


def set_batch(user_id: int, data: dict):
    sessions = load_batch_sessions()
    sessions[get_user_key(user_id)] = data
    save_batch_sessions(sessions)
    try:
        queue.upsert_batch_session_mirror(user_id, data)
    except Exception as e:
        log_event("v2_batch_session_mirror_upsert_failed", user_id=user_id, error=str(e))


def clear_batch(user_id: int):
    sessions = load_batch_sessions()
    sessions.pop(get_user_key(user_id), None)
    save_batch_sessions(sessions)
    try:
        queue.delete_batch_session_mirror(user_id)
    except Exception as e:
        log_event("v2_batch_session_mirror_delete_failed", user_id=user_id, error=str(e))


async def rubika_send_code(session_name: str, phone_number: str, pass_key: str = ""):
    client = RubikaClient(name=session_name)
    try:
        if not hasattr(client, "connection"):
            await client.connect()

        phone_number = phone_number.strip().replace(" ", "").replace("-", "").replace("+", "")
        if phone_number.startswith("0"):
            phone_number = f"98{phone_number[1:]}"

        kwargs = {"phone_number": phone_number, "send_type": "SMS"}
        if pass_key:
            kwargs["pass_key"] = pass_key
        result = await client.send_code(**kwargs)
        return result
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


def _deep_find_phone_hash(payload) -> Optional[str]:
    if payload is None:
        return None
    if hasattr(payload, "phone_code_hash"):
        value = getattr(payload, "phone_code_hash", None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    if hasattr(payload, "__dict__"):
        for value in vars(payload).values():
            found = _deep_find_phone_hash(value)
            if found:
                return found
    if isinstance(payload, dict):
        for key in ("phone_code_hash", "phoneCodeHash", "phone_codeHash", "phone_hash"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        for value in payload.values():
            found = _deep_find_phone_hash(value)
            if found:
                return found
    if isinstance(payload, list):
        for item in payload:
            found = _deep_find_phone_hash(item)
            if found:
                return found
    return None


def _deep_find_status(payload) -> str:
    if payload is None:
        return ""
    if hasattr(payload, "status"):
        value = getattr(payload, "status", "")
        if value:
            return str(value)
    if isinstance(payload, dict):
        if payload.get("status"):
            return str(payload.get("status"))
        for value in payload.values():
            found = _deep_find_status(value)
            if found:
                return found
    if isinstance(payload, list):
        for item in payload:
            found = _deep_find_status(item)
            if found:
                return found
    if hasattr(payload, "__dict__"):
        for value in vars(payload).values():
            found = _deep_find_status(value)
            if found:
                return found
    return ""


async def rubika_sign_in(session_name: str, phone_number: str, phone_code_hash: str, code: str):
    client = RubikaClient(name=session_name)
    try:
        if not hasattr(client, "connection"):
            await client.connect()

        phone_number = phone_number.strip().replace(" ", "").replace("-", "").replace("+", "")
        if phone_number.startswith("0"):
            phone_number = f"98{phone_number[1:]}"

        public_key, private_key = Crypto.create_keys()
        result = await client.sign_in(
            phone_code=str(code).strip(),
            phone_number=phone_number,
            phone_code_hash=phone_code_hash,
            public_key=public_key,
        )
        status = getattr(result, "status", "")
        if str(status).upper() != "OK":
            raise RuntimeError(f"Rubika sign_in failed: {status}")

        auth = Crypto.decrypt_RSA_OAEP(private_key, result.auth)
        client.key = Crypto.passphrase(auth)
        client.auth = auth
        client.decode_auth = Crypto.decode_auth(auth)
        client.private_key = private_key
        client.import_key = pkcs1_15.new(RSA.import_key(client.private_key.encode()))
        client.session.insert(
            auth=client.auth,
            guid=result.user.user_guid,
            user_agent=client.user_agent,
            phone_number=result.user.phone,
            private_key=client.private_key,
        )
        await client.register_device(device_model=session_name)
        await client.get_me()
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass

queue = QueueDB()


def sync_v2_ephemeral_mirrors_from_json() -> None:
    """Copy existing ``user_states.json`` / ``batch_sessions.json`` into SQLite mirrors.

    Runs once per process start so mirrors match on-disk JSON without waiting for
    the next ``set_state`` / ``set_batch`` per user.
    """
    n_state = 0
    n_batch = 0
    try:
        raw_states = load_user_states()
    except Exception as e:
        log_event("v2_state_mirror_backfill_failed", phase="load_user_states", error=str(e))
        raw_states = {}
    for key, value in (raw_states or {}).items():
        if not isinstance(key, str) or not key.isdigit():
            continue
        if not isinstance(value, dict):
            continue
        uid = int(key)
        try:
            queue.upsert_user_state_mirror(uid, value)
            n_state += 1
        except Exception as e:
            log_event(
                "v2_state_mirror_backfill_row_failed",
                user_id=uid,
                kind="user_state",
                error=str(e),
            )
    try:
        raw_batches = load_batch_sessions()
    except Exception as e:
        log_event("v2_state_mirror_backfill_failed", phase="load_batch_sessions", error=str(e))
        raw_batches = {}
    for key, value in (raw_batches or {}).items():
        if not isinstance(key, str) or not key.isdigit():
            continue
        if not isinstance(value, dict):
            continue
        uid = int(key)
        try:
            queue.upsert_batch_session_mirror(uid, value)
            n_batch += 1
        except Exception as e:
            log_event(
                "v2_state_mirror_backfill_row_failed",
                user_id=uid,
                kind="batch_session",
                error=str(e),
            )
    if n_state or n_batch:
        log_event("v2_state_mirror_backfill_done", user_states=n_state, batch_sessions=n_batch)


async def gate_quota(message: Message, user_id: int, task: dict) -> bool:
    """Return True if the user may enqueue this task."""
    task["telegram_user_id"] = user_id
    est = estimate_task_bytes(task)
    ok, code, det = can_enqueue(user_id, est, queue)
    if ok:
        return True
    await message.reply_text(quota_fail_text(user_id, code, det), parse_mode=None)
    log_event("quota_blocked", user_id=user_id, code=code)
    return False


def usage_report_text(user_id: int) -> str:
    if DISABLE_USAGE_LIMITS:
        return tr(user_id, "usage_disabled_hint")
    u = get_usage_snapshot(user_id)
    day_u = u["day_bytes"] / (1024 * 1024)
    month_u = u["month_bytes"] / (1024 * 1024)
    cur_par = parallel_job_count(user_id, queue)
    return tr(
        user_id,
        "usage_panel",
        tier=u["tier"],
        day_used=f"{day_u:.1f}",
        day_cap=u["quota_day_mb"],
        month_used=f"{month_u:.1f}",
        month_cap=u["quota_month_mb"],
        max_file=u["max_file_mb"],
        parallel=cur_par,
        max_parallel=u["max_parallel"],
    )


def mark_deleted(task: dict):
    queue.mark_deleted(task)


def mark_cancelled(task: dict):
    job_id = str(task.get("job_id", "")).strip()
    if job_id:
        queue.cancel_job(job_id)


def cancel_job(job_id: str):
    queue.cancel_job(str(job_id))


def cleanup_task_artifacts(task: dict) -> None:
    """Remove local files for tasks that will not be queued or processed."""
    paths = []
    if isinstance(task, dict):
        if task.get("path"):
            paths.append(task.get("path"))
        paths.extend(task.get("files") or [])
    for raw in paths:
        try:
            p = Path(str(raw))
            if p.exists() and p.is_file():
                p.unlink()
        except Exception:
            pass


def was_deleted(job_id=None, message_id=None) -> bool:
    return queue.was_deleted(job_id=job_id, message_id=message_id)

def load_settings() -> dict:
    try:
        if SETTINGS_FILE.exists():
            return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass

    return {"safe_mode": False, "zip_password": ""}

def save_settings(data: dict):
    SETTINGS_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

def is_direct_url(text: str) -> bool:
    if not text:
        return False

    url = extract_first_url(text)
    if not url:
        return False

    try:
        parsed = urlparse(url)
    except Exception:
        return False

    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def extract_first_url(text: str) -> Optional[str]:
    if not text:
        return None

    match = re.search(r"https?://\S+", text)
    return match.group(0) if match else None


def progress_bar(percent: float, length: int = 12) -> str:
    filled = int(length * percent / 100)
    return "█" * filled + "░" * (length - filled)


def pretty_size(size) -> str:
    size = float(size or 0)
    units = ["B", "KB", "MB", "GB"]

    index = 0
    while size >= 1024 and index < len(units) - 1:
        size /= 1024
        index += 1

    return f"{size:.2f} {units[index]}"


def processing_display_for_queue(user_id: int) -> str:
    """Current worker job for this user (Rubika/Bale/Drive/SSH)."""
    if not PROCESSING_FILE.exists():
        return tr(user_id, "queue_processing_none")
    try:
        data = json.loads(PROCESSING_FILE.read_text(encoding="utf-8"))
    except Exception:
        return tr(user_id, "queue_processing_none")
    session = get_user_session(user_id)
    task_uid = data.get("telegram_user_id")
    matches_user = False
    try:
        matches_user = int(task_uid or 0) == int(user_id)
    except (TypeError, ValueError):
        matches_user = False
    if not matches_user and (not session or data.get("rubika_session") != session):
        return tr(user_id, "queue_processing_none")
    jid = str(data.get("job_id", "?"))
    typ = str(data.get("type", "?"))
    fn = ""
    if data.get("file_name"):
        fn = str(data["file_name"])
    elif data.get("path"):
        fn = Path(str(data["path"])).name
    sz = data.get("file_size")
    sz_txt = pretty_size(sz) if sz else "?"
    return tr(
        user_id,
        "queue_processing_detail",
        job_id=jid,
        task_type=typ,
        file=fn or "—",
        size=sz_txt,
    )


def eta_text(seconds, user_id: int = 0) -> str:
    if not seconds or seconds <= 0:
        return tr(user_id, "eta_unknown") if user_id else "نامشخص"

    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60

    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


async def download_progress(current, total, status_message, file_name, started_at, state):
    now = time.time()

    if now - state.get("last_update", 0) < 3 and current < total:
        return

    state["last_update"] = now

    percent = current * 100 / total if total else 0
    elapsed = max(now - started_at, 1)
    speed = current / elapsed
    eta = (total - current) / speed if speed else None
    uid = int(state.get("user_id") or 0)

    text = tr(
        uid,
        "download_progress_line",
        file_name=file_name,
        total=pretty_size(total),
        percent=percent,
        bar=progress_bar(percent),
        speed=pretty_size(speed),
        eta=eta_text(eta, uid),
    )

    try:
        await status_message.edit_text(text, parse_mode=None)
    except MessageNotModified:
        pass
    except Exception:
        pass

async def status_watcher():
    pos = 0
    while True:
        await asyncio.sleep(1)
        if not STATUS_FILE.exists():
            continue
        try:
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                f.seek(pos)
                lines = f.readlines()
                pos = f.tell()
            for line in lines:
                if not line.strip():
                    continue
                data = json.loads(line)
                chat_id = data.get("chat_id")
                msg_id = data.get("message_id")
                text = data.get("text", "")
                percent = data.get("percent")
                if not chat_id or not msg_id:
                    continue
                if percent is not None:
                    text += f"\n\n`{progress_bar(float(percent))}` `{float(percent):.1f}%`"
                try:
                    await app.edit_message_text(chat_id, msg_id, text, parse_mode=None)
                except MessageNotModified:
                    pass
                except Exception:
                    pass
        except Exception:
            pass


async def maybe_broadcast_update():
    """Notify known private chats once per APP_VERSION (disable with DISABLE_UPDATE_BROADCAST=1)."""
    await asyncio.sleep(2)
    if DISABLE_UPDATE_BROADCAST:
        return
    state = load_json(BROADCAST_STATE_FILE, {})
    if state.get("last_broadcast_version") == APP_VERSION:
        return
    data = load_json(KNOWN_CHATS_FILE, {"ids": []})
    ids = list(dict.fromkeys(data.get("ids", [])))
    for cid in ids:
        try:
            uid = int(cid)
            await app.send_message(
                uid,
                tr(uid, "update_notice", version=APP_VERSION),
                reply_markup=build_main_menu(uid),
            )
        except Exception:
            log_event("update_broadcast_skip", chat_id=cid)
        await asyncio.sleep(0.06)
    state["last_broadcast_version"] = APP_VERSION
    save_json(BROADCAST_STATE_FILE, state)
    log_event("update_broadcast_done", version=APP_VERSION, chats=len(ids))


async def payment_reconcile_loop():
    """Periodic stale-payment expiry when ``BILLING_RECONCILE_ENABLE`` is set."""
    await asyncio.sleep(90)
    while True:
        await asyncio.sleep(BILLING_RECONCILE_INTERVAL_SEC)
        if not BILLING_RECONCILE_ENABLE:
            continue
        try:
            stats = run_reconcile(queue, pending_max_age_sec=BILLING_RECONCILE_PENDING_MAX_AGE_SEC)
            if stats.get("expired", 0):
                log_event("billing_reconcile_tick", **stats)
        except Exception as e:
            log_event("billing_reconcile_error", error=str(e))


def _create_stub_purchase_checkout(user_id: int) -> tuple[int, str]:
    from v2.billing import StubPaymentGateway

    gw = StubPaymentGateway(queue)
    r = gw.create_payment_intent(
        user_id,
        0,
        currency="IRR",
        metadata={"grant_tier": "pro", "grant_days": 30, "stub_checkout": True},
    )
    return r.payment_id, (r.authority or "")


BASIC_COMMAND_DEPS = BasicCommandDeps(
    tr=tr,
    remember_chat=remember_chat,
    set_menu_section=set_menu_section,
    build_main_menu=build_main_menu,
    app_version=APP_VERSION,
)

SESSION_SETTINGS_COMMAND_DEPS = SessionSettingsCommandDeps(
    tr=tr,
    get_user_session=get_user_session,
    check_rubika_session_sync=check_rubika_session_sync,
    set_menu_section=set_menu_section,
    set_state_preserving_menu=set_state_preserving_menu,
    log_event=log_event,
    build_settings_menu=build_settings_menu,
    build_main_menu=build_main_menu,
    load_network_snapshot=partial(
        load_json,
        NETWORK_FILE,
        {"mode": "unknown", "reason": "", "updated_at": 0},
    ),
)

DIRECT_SEND_COMMAND_DEPS = DirectSendCommandDeps(
    tr=tr,
    set_menu_section=set_menu_section,
    get_direct_mode_target=get_direct_mode_target,
    set_direct_mode_target=set_direct_mode_target,
    get_user_session=get_user_session,
    get_bale_ready=lambda uid: load_bale_credentials(queue, uid).ready,
    get_drive_ready=lambda uid: load_drive_credentials(queue, BASE_DIR, uid).ready,
    build_settings_menu=build_settings_menu,
    build_main_menu=build_main_menu,
)

LINK_DIRECT_COMMAND_DEPS = LinkDirectCommandDeps(
    tr=tr,
    set_menu_section=set_menu_section,
    build_link_direct_menu=build_link_direct_menu,
)

PLAN_COMMAND_DEPS = PlanCommandDeps(
    tr=tr,
    set_menu_section=set_menu_section,
    usage_report_text=usage_report_text,
    stub_checkout_enabled=BILLING_STUB_CHECKOUT,
    create_stub_checkout=_create_stub_purchase_checkout,
)


def _toolkit_quota_try(uid: int) -> tuple[bool, str]:
    """Pre-flight quota check (does not consume). Handlers call ``_toolkit_quota_commit`` after success."""
    lim = effective_toolkit_daily_limit(uid)
    if lim <= 0:
        return True, ""
    cur = queue.toolkit_daily_get_count(uid)
    if cur >= lim:
        return False, tr(
            uid,
            "toolkit_quota_exceeded",
            used=cur,
            limit=lim,
        )
    return True, ""


def _toolkit_quota_commit(uid: int) -> None:
    """Count one successful toolkit invocation (atomic; skips if already at cap)."""
    lim = effective_toolkit_daily_limit(uid)
    if lim <= 0:
        return
    queue.toolkit_daily_increment_if_under_cap(uid, daily_limit=lim)


TOOLKIT_COMMAND_DEPS = ToolkitCommandDeps(
    tr=tr,
    set_menu_section=set_menu_section,
    toolkit_network_light_enabled=TOOLKIT_NETWORK_LIGHT,
    toolkit_utility_light_enabled=TOOLKIT_UTILITY_LIGHT,
    toolkit_quota_try=_toolkit_quota_try,
    toolkit_quota_commit=_toolkit_quota_commit,
)

TOOLKIT_MENU_DEPS = ToolkitMenuDeps(
    tr=tr,
    set_menu_section=set_menu_section,
    build_toolkit_menu=build_toolkit_menu,
    build_toolkit_network_menu=build_toolkit_network_menu,
    build_toolkit_crypto_menu=build_toolkit_crypto_menu,
)

TRANSFER_HUB_DEPS = TransferHubDeps(
    tr=tr,
    base_dir=BASE_DIR,
    queue=queue,
    set_menu_section=set_menu_section,
    build_transfer_menu=build_transfer_menu,
    build_rubika_menu=build_rubika_menu,
    build_files_menu=build_files_menu,
    build_bale_menu=build_bale_menu,
    build_drive_menu=build_drive_menu,
    build_ssh_menu=build_ssh_menu,
    get_bale_credentials=queue.get_bale_credentials,
    set_bale_chat_id=queue.upsert_bale_chat_id,
    list_ssh_servers=queue.list_ssh_servers,
    get_ssh_server=queue.get_ssh_server,
    ssh_add_server=queue.add_ssh_server,
)

PROVIDER_CONNECT_DEPS = ProviderConnectWizardDeps(
    tr=tr,
    base_dir=BASE_DIR,
    set_menu_section=set_menu_section,
    set_state_preserving_menu=set_state_preserving_menu,
    clear_state=clear_state,
    get_bale_credentials=queue.get_bale_credentials,
    upsert_bale_bot_token=queue.upsert_bale_bot_token,
    upsert_bale_chat_id=queue.upsert_bale_chat_id,
    clear_bale_credentials=queue.clear_bale_credentials,
    upsert_drive_folder_id=queue.upsert_drive_folder_id,
    upsert_drive_sa_path=queue.upsert_drive_sa_path,
    clear_drive_credentials=queue.clear_drive_credentials,
    log_event=log_event,
)


async def show_transfer_menu_handler(client: Client, message: Message):
    await handle_show_transfer_menu(TRANSFER_HUB_DEPS, client, message)


async def show_toolkit_menu_handler(client: Client, message: Message):
    await handle_show_toolkit_menu(TOOLKIT_MENU_DEPS, client, message)


async def show_toolkit_network_menu_handler(client: Client, message: Message):
    await handle_show_toolkit_network_menu(TOOLKIT_MENU_DEPS, client, message)


async def show_toolkit_crypto_menu_handler(client: Client, message: Message):
    await handle_show_toolkit_crypto_menu(TOOLKIT_MENU_DEPS, client, message)


async def show_rubika_menu_handler(client: Client, message: Message):
    await handle_show_rubika_menu_hub(TRANSFER_HUB_DEPS, client, message)


async def show_bale_menu_handler(client: Client, message: Message):
    await handle_show_bale_menu(TRANSFER_HUB_DEPS, client, message)


async def show_drive_menu_handler(client: Client, message: Message):
    await handle_show_drive_menu(TRANSFER_HUB_DEPS, client, message)


async def show_ssh_menu_handler(client: Client, message: Message):
    await handle_show_ssh_menu(TRANSFER_HUB_DEPS, client, message)


async def show_files_menu_handler(client: Client, message: Message):
    await handle_show_files_menu_hub(TRANSFER_HUB_DEPS, client, message)


async def bale_status_handler(client: Client, message: Message):
    await handle_bale_status(TRANSFER_HUB_DEPS, client, message)


async def bale_set_chat_handler(client: Client, message: Message):
    await handle_bale_set_chat(TRANSFER_HUB_DEPS, client, message)


async def bale_connect_handler(client: Client, message: Message):
    await handle_bale_connect(PROVIDER_CONNECT_DEPS, client, message)


async def bale_disconnect_handler(client: Client, message: Message):
    await handle_bale_disconnect(PROVIDER_CONNECT_DEPS, client, message)


async def drive_connect_handler(client: Client, message: Message):
    await handle_drive_connect(PROVIDER_CONNECT_DEPS, client, message)


async def drive_disconnect_handler(client: Client, message: Message):
    await handle_drive_disconnect(PROVIDER_CONNECT_DEPS, client, message)


async def drive_status_handler(client: Client, message: Message):
    await handle_drive_status(TRANSFER_HUB_DEPS, client, message)


async def ssh_list_handler(client: Client, message: Message):
    await handle_ssh_list(TRANSFER_HUB_DEPS, client, message)


async def ssh_add_handler(client: Client, message: Message):
    await handle_ssh_add(TRANSFER_HUB_DEPS, client, message)


async def ssh_put_handler(client: Client, message: Message):
    from v2.handlers.transfer_hub_commands import handle_ssh_put_command

    await handle_ssh_put_command(
        TRANSFER_HUB_DEPS,
        client,
        message,
        set_state_preserving_menu=set_state_preserving_menu,
    )


async def drive_download_handler(client: Client, message: Message):
    from v2.handlers.transfer_hub_commands import handle_drive_download_command

    await handle_drive_download_command(
        TRANSFER_HUB_DEPS,
        client,
        message,
        push_task_direct=push_task_direct,
    )


async def ssh_get_handler(client: Client, message: Message):
    from v2.handlers.transfer_hub_commands import handle_ssh_get_command

    await handle_ssh_get_command(
        TRANSFER_HUB_DEPS,
        client,
        message,
        push_task_direct=push_task_direct,
    )


async def start_handler(client: Client, message: Message):
    await handle_start(BASIC_COMMAND_DEPS, client, message)


async def menu_handler(client: Client, message: Message):
    await handle_menu(BASIC_COMMAND_DEPS, client, message)


async def lang_handler(client: Client, message: Message):
    await handle_lang(BASIC_COMMAND_DEPS, client, message)


async def help_handler(client: Client, message: Message):
    await handle_help(BASIC_COMMAND_DEPS, client, message)


async def log_help_handler(client: Client, message: Message):
    await handle_log_help(BASIC_COMMAND_DEPS, client, message)


async def version_handler(client: Client, message: Message):
    await handle_version(BASIC_COMMAND_DEPS, client, message)


async def rubika_status_handler(client: Client, message: Message):
    await handle_rubika_status(SESSION_SETTINGS_COMMAND_DEPS, client, message)


async def rubika_connect_handler(client: Client, message: Message):
    await handle_rubika_connect(SESSION_SETTINGS_COMMAND_DEPS, client, message)


async def direct_mode_handler(client: Client, message: Message):
    await handle_direct_mode(DIRECT_SEND_COMMAND_DEPS, client, message)


async def show_link_direct_menu_handler(client: Client, message: Message):
    await handle_show_link_direct_menu(LINK_DIRECT_COMMAND_DEPS, client, message)


async def netstatus_handler(client: Client, message: Message):
    await handle_netstatus(SESSION_SETTINGS_COMMAND_DEPS, client, message)


def failed_count() -> int:
    if not FAILED_FILE.exists():
        return 0
    try:
        with open(FAILED_FILE, "r", encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())
    except Exception:
        return 0


def _run_admin_cleanup_downloads() -> tuple[int, int]:
    n = 0
    freed = 0
    for p in DOWNLOAD_DIR.glob("*"):
        try:
            if p.is_file():
                freed += p.stat().st_size
                p.unlink()
                n += 1
        except OSError:
            pass
    return n, freed


ADMIN_COMMAND_DEPS = AdminCommandDeps(
    admin_ids=frozenset(ADMIN_IDS),
    tr=tr,
    set_menu_section=set_menu_section,
    build_admin_menu=build_admin_menu,
    load_network_snapshot=SESSION_SETTINGS_COMMAND_DEPS.load_network_snapshot,
    queue_count=queue.queue_count,
    queue_cancelled_count=queue.cancelled_count,
    queue_deleted_count=queue.deleted_count,
    failed_count=failed_count,
    max_file_mb_display=max_file_mb_display,
    admin_disk_report_text=admin_disk_report_text,
    set_user_tier=set_user_tier,
    add_bonus_month_mb=add_bonus_month_mb,
    run_admin_cleanup_downloads=_run_admin_cleanup_downloads,
    list_v2_payments_for_user=lambda uid, lim: queue.list_v2_payments_for_user(uid, limit=lim),
    get_v2_payment_by_id=queue.get_v2_payment_by_id,
    update_v2_payment_status=lambda pid, st, ref: queue.update_v2_payment_status(
        pid, st, ref_id=ref
    ),
    maybe_grant_after_paid=lambda pid: maybe_grant_plan_after_paid(queue, pid),
    run_billing_reconcile=lambda: run_reconcile(
        queue,
        pending_max_age_sec=BILLING_RECONCILE_PENDING_MAX_AGE_SEC,
    ),
    log_event=log_event,
)

QUEUE_COMMAND_DEPS = QueueCommandDeps(
    tr=tr,
    set_menu_section=set_menu_section,
    enqueue_rubika_text_message=lambda message, text: enqueue_rubika_text_message(message, text),
    extract_first_url=extract_first_url,
    get_user_session=get_user_session,
    queue_count_by_session=queue.queue_count_by_session,
    queue_count_for_user=queue.count_tasks_for_user,
    processing_display_for_queue=processing_display_for_queue,
    failed_count=failed_count,
    queue_deleted_count=queue.deleted_count,
    queue_cancelled_count=queue.cancelled_count,
    queue_all_tasks=queue.all_tasks,
    queue_remove_tasks_by_session=queue.remove_tasks_by_session,
    queue_remove_tasks_by_user=queue.remove_tasks_by_user,
    mark_deleted=mark_deleted,
)

DELETE_COMMAND_DEPS = DeleteCommandDeps(
    queue_all_tasks=queue.all_tasks,
    queue_remove_task=queue.remove_task,
    was_deleted=was_deleted,
    cancel_job=cancel_job,
    mark_deleted=mark_deleted,
)

BATCH_COMMAND_DEPS = BatchCommandDeps(
    tr=tr,
    set_batch=set_batch,
    get_batch=get_batch,
    set_menu_section=set_menu_section,
    build_files_menu=build_files_menu,
    set_state_preserving_menu=set_state_preserving_menu,
)


async def enqueue_rubika_text_message(message: Message, text_body: str) -> None:
    user_id = message.from_user.id
    session_name = get_user_session(user_id)
    if not session_name:
        await message.reply_text(tr(user_id, "rubika_not_connected"))
        return
    text_body = (text_body or "").strip()
    if not text_body:
        await message.reply_text(tr(user_id, "empty_message"))
        return
    task = {
        "type": "text_message",
        "text": text_body,
        "rubika_session": session_name,
    }
    if not await gate_quota(message, user_id, task):
        return
    status = await message.reply_text(tr(user_id, "text_queueing"))
    task["chat_id"] = message.chat.id
    task["status_message_id"] = status.id
    pushed = queue.push_task(task)
    qpos = queue.queue_count_by_session(session_name)
    log_event(
        "task_queued",
        user_id=user_id,
        job_id=pushed.get("job_id"),
        task_type="text_message",
        direct_mode=is_direct_mode(user_id),
    )
    try:
        await status.edit_text(
            tr(user_id, "text_queued", job_id=pushed["job_id"], qpos=qpos),
            parse_mode=None,
        )
    except MessageNotModified:
        pass


async def queue_or_confirm(
    message: Message,
    task: dict,
    summary: str,
    status_message: Optional[Message] = None,
):
    user_id = message.from_user.id
    task["telegram_user_id"] = user_id
    if get_direct_mode_target(user_id):
        if not await gate_quota(message, user_id, task):
            cleanup_task_artifacts(task)
            return
        anchor = status_message
        if anchor:
            task["chat_id"] = message.chat.id
            task["status_message_id"] = anchor.id
            try:
                await anchor.edit_text(tr(user_id, "text_queueing"), parse_mode=None)
            except Exception:
                pass
            pushed = queue.push_task(task)
            qpos = queue.count_tasks_for_user(user_id)
            log_event(
                "task_queued",
                user_id=user_id,
                job_id=pushed.get("job_id"),
                task_type=task.get("type"),
                direct_mode=True,
            )
            try:
                await anchor.edit_text(
                    tr(user_id, "text_queued", job_id=pushed["job_id"], qpos=qpos),
                    parse_mode=None,
                )
            except MessageNotModified:
                pass
            return

        status = await message.reply_text(tr(user_id, "queued_processing"))
        task["chat_id"] = message.chat.id
        task["status_message_id"] = status.id
        pushed = queue.push_task(task)
        qpos = queue.count_tasks_for_user(user_id)
        log_event(
            "task_queued",
            user_id=user_id,
            job_id=pushed.get("job_id"),
            task_type=task.get("type"),
            direct_mode=True,
        )
        try:
            await status.edit_text(
                tr(user_id, "text_queued", job_id=pushed["job_id"], qpos=qpos),
                parse_mode=None,
            )
        except MessageNotModified:
            pass
        return

    set_state_preserving_menu(
        user_id,
        {
            "step": "await_send_confirm",
            "pending_task": task,
            "pending_summary": summary,
            "confirm_target_msg_id": status_message.id if status_message else None,
        },
    )
    suffix = tr(user_id, "confirm_send_suffix")
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Confirm Send", callback_data="confirm_send")],
            [InlineKeyboardButton("Cancel", callback_data="cancel_send")],
        ]
    )
    body = f"{summary}\n\n{suffix}"
    if status_message:
        try:
            await status_message.edit_text(body, reply_markup=kb, parse_mode=None)
        except Exception:
            await message.reply_text(body, reply_markup=kb)
    else:
        await message.reply_text(body, reply_markup=kb)
    log_event(
        "task_confirm_requested",
        user_id=user_id,
        task_type=task.get("type"),
    )


async def push_task_direct(
    message: Message,
    task: dict,
    status_message: Optional[Message] = None,
) -> None:
    """Queue non-Rubika transfer tasks immediately (Bale, Drive, SSH)."""
    user_id = message.from_user.id
    task["telegram_user_id"] = user_id
    task["chat_id"] = message.chat.id
    if not await gate_quota(message, user_id, task):
        cleanup_task_artifacts(task)
        return
    anchor = status_message
    if not anchor:
        anchor = await message.reply_text(tr(user_id, "text_queueing"), parse_mode=None)
    task["status_message_id"] = anchor.id
    pushed = queue.push_task(task)
    qpos = queue.count_tasks_for_user(user_id)
    log_event(
        "task_queued",
        user_id=user_id,
        job_id=pushed.get("job_id"),
        task_type=task.get("type"),
        direct_mode=True,
    )
    try:
        await anchor.edit_text(
            tr(user_id, "text_queued", job_id=pushed["job_id"], qpos=qpos),
            parse_mode=None,
        )
    except MessageNotModified:
        pass
    st = get_state(user_id)
    if st.get("step") == "await_ssh_put_file":
        clear_state(user_id)


async def safe_delete_user_message(message: Message):
    try:
        await message.delete()
    except Exception:
        pass


async def edit_wizard(chat_id: int, wizard_message_id: int, text: str):
    try:
        await app.edit_message_text(chat_id=chat_id, message_id=wizard_message_id, text=text)
    except Exception:
        pass


async def admin_handler(client: Client, message: Message):
    await handle_admin_panel(ADMIN_COMMAND_DEPS, client, message)


async def usage_handler(client: Client, message: Message):
    await handle_usage(PLAN_COMMAND_DEPS, client, message)


async def plan_handler(client: Client, message: Message):
    await handle_plan(PLAN_COMMAND_DEPS, client, message)


async def purchase_handler(client: Client, message: Message):
    await handle_purchase(PLAN_COMMAND_DEPS, client, message)


async def dns_lookup_handler(client: Client, message: Message):
    await handle_dns_lookup(TOOLKIT_COMMAND_DEPS, client, message)


async def my_ip_handler(client: Client, message: Message):
    await handle_my_ip(TOOLKIT_COMMAND_DEPS, client, message)


async def tcp_ping_handler(client: Client, message: Message):
    await handle_tcp_ping(TOOLKIT_COMMAND_DEPS, client, message)


async def md5_handler(client: Client, message: Message):
    await handle_md5(TOOLKIT_COMMAND_DEPS, client, message)


async def sha256_handler(client: Client, message: Message):
    await handle_sha256(TOOLKIT_COMMAND_DEPS, client, message)


async def b64_encode_handler(client: Client, message: Message):
    await handle_b64_encode(TOOLKIT_COMMAND_DEPS, client, message)


async def b64_decode_handler(client: Client, message: Message):
    await handle_b64_decode(TOOLKIT_COMMAND_DEPS, client, message)


async def admin_tier_handler(client: Client, message: Message):
    await handle_admin_tier(ADMIN_COMMAND_DEPS, client, message)


async def admin_bonus_handler(client: Client, message: Message):
    await handle_admin_bonus(ADMIN_COMMAND_DEPS, client, message)


async def cleanup_downloads_handler(client: Client, message: Message):
    await handle_cleanup_downloads(ADMIN_COMMAND_DEPS, client, message)


async def admin_payment_lookup_handler(client: Client, message: Message):
    await handle_admin_payment_lookup(ADMIN_COMMAND_DEPS, client, message)


async def admin_payment_status_handler(client: Client, message: Message):
    await handle_admin_payment_status(ADMIN_COMMAND_DEPS, client, message)


async def admin_reconcile_billing_handler(client: Client, message: Message):
    await handle_admin_reconcile_billing(ADMIN_COMMAND_DEPS, client, message)


async def admin_clear_prefs_handler(client: Client, message: Message):
    uid = message.from_user.id
    if uid not in ADMIN_IDS:
        await message.reply_text(tr(uid, "admin_denied"))
        return
    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.reply_text(
            "Usage: `/admin_clear_prefs <telegram_user_id>`",
            parse_mode=None,
        )
        return
    try:
        target = int(parts[1].strip())
    except ValueError:
        await message.reply_text("Invalid user id.", parse_mode=None)
        return
    try:
        queue.delete_v2_user_prefs(target)
    except Exception as e:
        log_event("admin_clear_prefs_failed", admin_id=uid, target=target, error=str(e))
        await message.reply_text(f"DB error: {e}", parse_mode=None)
        return
    log_event("admin_clear_prefs_ok", admin_id=uid, target=target)
    await message.reply_text(f"OK: cleared v2_user_prefs for `{target}`", parse_mode=None)


async def admin_clear_state_mirrors_handler(client: Client, message: Message):
    uid = message.from_user.id
    if uid not in ADMIN_IDS:
        await message.reply_text(tr(uid, "admin_denied"))
        return
    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.reply_text(
            "Usage: `/admin_clear_state_mirrors <telegram_user_id>`",
            parse_mode=None,
        )
        return
    try:
        target = int(parts[1].strip())
    except ValueError:
        await message.reply_text("Invalid user id.", parse_mode=None)
        return
    try:
        queue.delete_user_state_mirror(target)
        queue.delete_batch_session_mirror(target)
    except Exception as e:
        log_event("admin_clear_state_mirrors_failed", admin_id=uid, target=target, error=str(e))
        await message.reply_text(f"DB error: {e}", parse_mode=None)
        return
    log_event("admin_clear_state_mirrors_ok", admin_id=uid, target=target)
    await message.reply_text(
        f"OK: cleared `v2_user_state_mirror` + `v2_batch_session_mirror` for `{target}` (JSON unchanged).",
        parse_mode=None,
    )


async def safemode_handler(client: Client, message: Message):
    await handle_safemode(SAFEMODE_COMMAND_DEPS, client, message)


async def clear_queue_handler(client: Client, message: Message, acting_user_id: Optional[int] = None):
    await handle_clear_queue(QUEUE_COMMAND_DEPS, client, message, acting_user_id=acting_user_id)

async def new_batch_handler(client: Client, message: Message):
    await handle_new_batch(BATCH_COMMAND_DEPS, client, message)


async def done_batch_handler(client: Client, message: Message):
    await handle_done_batch(BATCH_COMMAND_DEPS, client, message)


async def callback_handler(client: Client, callback_query):
    handled = await dispatch_callback_route(client, callback_query, CALLBACK_ROUTE_DEPS)
    if handled:
        return
    await callback_query.answer("این گزینه منقضی شده یا معتبر نیست.", show_alert=True)


async def send_text_handler(client: Client, message: Message):
    await handle_send_text(QUEUE_COMMAND_DEPS, client, message)


async def send_link_handler(client: Client, message: Message):
    await handle_send_link(QUEUE_COMMAND_DEPS, client, message)


async def queue_manage_handler(
    client: Client,
    message: Message,
    edit_existing: bool = False,
    target_user_id: Optional[int] = None,
):
    await handle_queue_manage(
        QUEUE_COMMAND_DEPS,
        client,
        message,
        edit_existing=edit_existing,
        target_user_id=target_user_id,
    )


async def delete_one_handler(client: Client, message: Message):
    await handle_delete_one(DELETE_COMMAND_DEPS, client, message)


def _zip_password_waiting() -> bool:
    global waiting_for_zip_password
    return waiting_for_zip_password


def _set_zip_password_waiting(v: bool) -> None:
    global waiting_for_zip_password
    waiting_for_zip_password = v


REPLY_ROUTE_DEPS = ReplyRouteDeps(
    admin_ids=frozenset(ADMIN_IDS),
    tr=tr,
    set_menu_section=set_menu_section,
    set_state_preserving_menu=set_state_preserving_menu,
    menu_handler=menu_handler,
    help_handler=help_handler,
    log_help_handler=log_help_handler,
    rubika_connect_handler=rubika_connect_handler,
    rubika_status_handler=rubika_status_handler,
    bale_status_handler=bale_status_handler,
    bale_connect_handler=bale_connect_handler,
    bale_disconnect_handler=bale_disconnect_handler,
    drive_status_handler=drive_status_handler,
    drive_connect_handler=drive_connect_handler,
    drive_disconnect_handler=drive_disconnect_handler,
    ssh_list_handler=ssh_list_handler,
    new_batch_handler=new_batch_handler,
    done_batch_handler=done_batch_handler,
    clear_queue_handler=clear_queue_handler,
    queue_manage_handler=queue_manage_handler,
    netstatus_handler=netstatus_handler,
    admin_handler=admin_handler,
    version_handler=version_handler,
    direct_mode_handler=direct_mode_handler,
    plan_handler=plan_handler,
    usage_handler=usage_handler,
    purchase_handler=purchase_handler,
    show_transfer_menu_handler=show_transfer_menu_handler,
    show_toolkit_menu_handler=show_toolkit_menu_handler,
    show_toolkit_network_menu_handler=show_toolkit_network_menu_handler,
    show_toolkit_crypto_menu_handler=show_toolkit_crypto_menu_handler,
    show_rubika_menu_handler=show_rubika_menu_handler,
    show_bale_menu_handler=show_bale_menu_handler,
    show_drive_menu_handler=show_drive_menu_handler,
    show_ssh_menu_handler=show_ssh_menu_handler,
    show_files_menu_handler=show_files_menu_handler,
    show_link_direct_menu_handler=show_link_direct_menu_handler,
    dns_lookup_handler=dns_lookup_handler,
    my_ip_handler=my_ip_handler,
    tcp_ping_handler=tcp_ping_handler,
    md5_handler=md5_handler,
    sha256_handler=sha256_handler,
    b64_encode_handler=b64_encode_handler,
    b64_decode_handler=b64_decode_handler,
    build_plan_menu=build_plan_menu,
    build_transfer_menu=build_transfer_menu,
    build_toolkit_menu=build_toolkit_menu,
    build_rubika_menu=build_rubika_menu,
    build_files_menu=build_files_menu,
    build_settings_menu=build_settings_menu,
    build_admin_menu=build_admin_menu,
)

async def _save_drive_sa_file(user_id: int, local_path: Path) -> tuple[bool, str]:
    return await save_drive_sa_from_downloaded_file(PROVIDER_CONNECT_DEPS, user_id, local_path)


RUBIKA_WIZARD_DEPS = RubikaWizardDeps(
    tr=tr,
    set_state_preserving_menu=set_state_preserving_menu,
    clear_state=clear_state,
    get_user_key=get_user_key,
    load_users=load_users,
    save_users=save_users,
    log_event=log_event,
    persist_rubika_session=_persist_rubika_session_prefs,
    rubika_send_code=rubika_send_code,
    rubika_sign_in=rubika_sign_in,
    deep_find_phone_hash=_deep_find_phone_hash,
    deep_find_status=_deep_find_status,
)

ZIP_BATCH_WIZARD_DEPS = ZipBatchWizardDeps(
    tr=tr,
    safe_filename=safe_filename,
    safe_delete_user_message=safe_delete_user_message,
    edit_wizard=edit_wizard,
    set_state_preserving_menu=set_state_preserving_menu,
    clear_state=clear_state,
    clear_batch=clear_batch,
    load_settings=load_settings,
    make_bundle_zip_local=make_bundle_zip_local,
    effective_max_file_bytes=effective_max_file_bytes,
    effective_max_mb_display=effective_max_mb_display,
    fmt_mb_bytes=fmt_mb_bytes,
    gate_quota=gate_quota,
    get_user_session=get_user_session,
    pretty_size=pretty_size,
    queue_or_confirm=queue_or_confirm,
)

ZIP_PASSWORD_DEPS = ZipPasswordPromptDeps(
    get_waiting_for_password=_zip_password_waiting,
    set_waiting_for_password=_set_zip_password_waiting,
    tr=tr,
    load_settings=load_settings,
    save_settings=save_settings,
)

SAFEMODE_COMMAND_DEPS = SafeModeCommandDeps(
    tr=tr,
    load_settings=load_settings,
    save_settings=save_settings,
    set_waiting_for_zip_password=_set_zip_password_waiting,
)

LINK_DIRECT_HANDLER_DEPS = LinkDirectHandlerDeps(
    tr=tr,
    base_dir=BASE_DIR,
    download_dir=DOWNLOAD_DIR,
    queue=queue,
    extract_first_url=extract_first_url,
    get_menu_section=get_effective_menu_section,
    get_state=get_state,
    set_state_preserving_menu=set_state_preserving_menu,
    get_user_session=get_user_session,
    load_settings=load_settings,
    effective_max_file_bytes=effective_max_file_bytes,
    effective_max_mb_display=effective_max_mb_display,
    fmt_mb_bytes=fmt_mb_bytes,
    pretty_size=pretty_size,
    gate_quota=gate_quota,
    queue_or_confirm=queue_or_confirm,
    push_task_direct=push_task_direct,
    log_event=log_event,
)


async def _link_dest_callback_route(client: Client, callback_query, dest: str) -> bool:
    return await handle_link_dest_callback(LINK_DIRECT_HANDLER_DEPS, client, callback_query, dest)


CALLBACK_ROUTE_DEPS = CallbackRouteDeps(
    tr=tr,
    get_state=get_state,
    set_lang=set_lang,
    set_menu_section_main=lambda user_id: set_menu_section(user_id, MenuSection.MAIN),
    build_main_menu=build_main_menu,
    queue_manage_handler=queue_manage_handler,
    clear_queue_handler=clear_queue_handler,
    get_user_session=get_user_session,
    queue_count_by_session=queue.queue_count_by_session,
    count_tasks_for_user=queue.count_tasks_for_user,
    failed_count=failed_count,
    recent_failed_detail_text=recent_failed_detail_text,
    recent_jobs_summary=recent_jobs_summary,
    gate_quota=gate_quota,
    queue_push_task=queue.push_task,
    clear_state=clear_state,
    cleanup_task_artifacts=cleanup_task_artifacts,
    log_event=log_event,
    handle_link_dest_callback=_link_dest_callback_route,
)


DIRECT_MODE_TEXT_DEPS = DirectModeTextDeps(
    tr=tr,
    get_direct_mode_target=get_direct_mode_target,
    get_user_session=get_user_session,
    extract_first_url=extract_first_url,
    gate_quota=gate_quota,
    push_task=queue.push_task,
    queue_count_by_session=queue.queue_count_by_session,
    handle_link_direct_for_direct_mode=lambda msg, uid, url, dest: handle_link_direct_for_direct_mode(
        LINK_DIRECT_HANDLER_DEPS, msg, uid, url, dest
    ),
    log_event=log_event,
)

DIRECT_URL_HINT_DEPS = DirectUrlHintDeps(
    tr=tr,
    extract_first_url=extract_first_url,
    is_direct_url=is_direct_url,
)

TEXT_ENTRY_DEPS = TextEntryDeps(
    tr=tr,
    get_state=get_state,
    set_menu_section=set_menu_section,
    build_plan_menu=build_plan_menu,
    build_main_menu=build_main_menu,
    resolve_reply_button_route=menu_engine.resolve_reply_button_route,
    dispatch_reply_keyboard_route=dispatch_reply_keyboard_route,
    reply_route_deps=REPLY_ROUTE_DEPS,
    clear_state=clear_state,
    enqueue_rubika_text_message=enqueue_rubika_text_message,
    dispatch_rubika_connect_wizard=dispatch_rubika_connect_wizard,
    rubika_wizard_deps=RUBIKA_WIZARD_DEPS,
    dispatch_provider_connect_wizard=dispatch_provider_connect_wizard,
    provider_connect_wizard_deps=PROVIDER_CONNECT_DEPS,
    dispatch_zip_batch_wizard=dispatch_zip_batch_wizard,
    zip_batch_wizard_deps=ZIP_BATCH_WIZARD_DEPS,
    handle_zip_password_text=handle_zip_password_text,
    zip_password_deps=ZIP_PASSWORD_DEPS,
    handle_direct_mode_plain_text=handle_direct_mode_plain_text,
    direct_mode_text_deps=DIRECT_MODE_TEXT_DEPS,
    handle_direct_url_sendlink_hint=handle_direct_url_sendlink_hint,
    direct_url_hint_deps=DIRECT_URL_HINT_DEPS,
    handle_link_direct_text=handle_link_direct_text,
    link_direct_deps=LINK_DIRECT_HANDLER_DEPS,
)

MEDIA_HANDLER_DEPS = MediaHandlerDeps(
    tr=tr,
    base_dir=BASE_DIR,
    queue=queue,
    get_user_session=get_user_session,
    get_menu_section=get_effective_menu_section,
    get_bale_credentials=queue.get_bale_credentials,
    get_state=get_state,
    set_state_preserving_menu=set_state_preserving_menu,
    save_drive_sa_file=_save_drive_sa_file,
    get_ssh_server=queue.get_ssh_server,
    get_media=get_media,
    build_download_filename=build_download_filename,
    download_dir=DOWNLOAD_DIR,
    download_progress=download_progress,
    effective_max_file_bytes=effective_max_file_bytes,
    effective_max_mb_display=effective_max_mb_display,
    fmt_mb_bytes=fmt_mb_bytes,
    load_settings=load_settings,
    get_batch=get_batch,
    set_batch=set_batch,
    pretty_size=pretty_size,
    queue_or_confirm=queue_or_confirm,
    push_task_direct=push_task_direct,
    log_event=log_event,
)


async def text_handler(client: Client, message: Message):
    await handle_text_entry(TEXT_ENTRY_DEPS, client, message)

    
async def media_handler(client: Client, message: Message):
    await handle_media_message(MEDIA_HANDLER_DEPS, client, message)


register_handlers(app)


def clear_old_status():
    try:
        if STATUS_FILE.exists():
            STATUS_FILE.unlink()
    except Exception:
        pass

if __name__ == "__main__":
    from v2.bot.startup import run_bot

    run_bot()
