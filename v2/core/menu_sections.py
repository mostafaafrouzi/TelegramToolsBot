"""Logical menu sections for reply-keyboard routing (see docs/v2/03-menu-spec.md)."""

from enum import Enum


class MenuSection(str, Enum):
    MAIN = "main"
    PLAN = "plan"
    TRANSFER = "transfer"
    FILES = "files"
    RUBIKA = "rubika"
    TOOLKIT = "toolkit"
    TOOLKIT_NETWORK = "toolkit_network"
    TOOLKIT_CRYPTO = "toolkit_crypto"
    TOOLKIT_CALC = "toolkit_calc"
    TOOLKIT_CALC_CAT = "toolkit_calc_cat"
    BALE = "bale"
    DRIVE = "drive"
    SSH = "ssh"
    SETTINGS = "settings"
    LINK_DIRECT = "link_direct"
    CLOUDFLARE = "cloudflare"
    WORLD = "world"
    FEED = "feed"
    ADMIN = "admin"
    ADMIN_USERS = "admin_users"
    ADMIN_BILLING = "admin_billing"
    ADMIN_MAINTENANCE = "admin_maintenance"
    ADMIN_BROADCAST = "admin_broadcast"
