"""Per-Telegram-user provider credentials (not shared server .env secrets)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from queue_db import QueueDB


@dataclass(frozen=True)
class BaleCredentials:
    bot_token: Optional[str]
    chat_id: Optional[str]

    @property
    def ready(self) -> bool:
        return bool(self.bot_token and self.chat_id)


@dataclass(frozen=True)
class DriveCredentials:
    service_account_path: Optional[Path]
    oauth_token_path: Optional[Path]
    folder_id: Optional[str]

    @property
    def ready(self) -> bool:
        if not self.folder_id:
            return False
        if self.oauth_token_path and self.oauth_token_path.is_file():
            return True
        return bool(self.service_account_path and self.service_account_path.is_file())

    @property
    def auth_mode(self) -> str:
        if self.oauth_token_path and self.oauth_token_path.is_file():
            return "oauth"
        if self.service_account_path and self.service_account_path.is_file():
            return "service_account"
        return "none"


def user_secrets_dir(base_dir: Path, telegram_user_id: int) -> Path:
    return base_dir / "secrets" / str(int(telegram_user_id))


def default_drive_sa_path(base_dir: Path, telegram_user_id: int) -> Path:
    return user_secrets_dir(base_dir, telegram_user_id) / "google-drive-sa.json"


def default_drive_oauth_path(base_dir: Path, telegram_user_id: int) -> Path:
    return user_secrets_dir(base_dir, telegram_user_id) / "drive-oauth-token.json"


def load_bale_credentials(queue: QueueDB, telegram_user_id: int) -> BaleCredentials:
    token, chat = queue.get_bale_credentials(int(telegram_user_id))
    return BaleCredentials(bot_token=token, chat_id=chat)


def load_drive_credentials(queue: QueueDB, base_dir: Path, telegram_user_id: int) -> DriveCredentials:
    folder = queue.get_drive_folder_id(int(telegram_user_id))
    rel = queue.get_drive_sa_path(int(telegram_user_id))
    path: Optional[Path] = None
    if rel:
        p = base_dir / rel
        if p.is_file():
            path = p
    if path is None:
        fallback = default_drive_sa_path(base_dir, telegram_user_id)
        if fallback.is_file():
            path = fallback
    oauth_rel = queue.get_drive_oauth_path(int(telegram_user_id))
    oauth_path: Optional[Path] = None
    if oauth_rel:
        op = base_dir / oauth_rel
        if op.is_file():
            oauth_path = op
    if oauth_path is None:
        fallback_oauth = default_drive_oauth_path(base_dir, telegram_user_id)
        if fallback_oauth.is_file():
            oauth_path = fallback_oauth
    return DriveCredentials(
        service_account_path=path,
        oauth_token_path=oauth_path,
        folder_id=folder,
    )
