"""Logical menu sections for reply-keyboard routing (see docs/v2/03-menu-spec.md)."""

from enum import Enum


class MenuSection(str, Enum):
    MAIN = "main"
    PLAN = "plan"
    TRANSFER = "transfer"
    FILES = "files"
    RUBIKA = "rubika"
    TOOLKIT = "toolkit"
    BALE = "bale"
    DRIVE = "drive"
    SSH = "ssh"
    SETTINGS = "settings"
    ADMIN = "admin"
