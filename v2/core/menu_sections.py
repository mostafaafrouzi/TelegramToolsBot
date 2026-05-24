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
    TOOLKIT_TEXT = "toolkit_text"
    TOOLKIT_GEN = "toolkit_gen"
    TOOLKIT_CONV = "toolkit_conv"
    BALE = "bale"
    DRIVE = "drive"
    SSH = "ssh"
    SETTINGS = "settings"
    LINK_DIRECT = "link_direct"
    ADMIN = "admin"
