"""Interactive SSH server registration and ops wizards (Telegram-friendly)."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from v2.core.menu_sections import MenuSection
from v2.transfer.ssh_client import sftp_list

TranslateFn = Callable[..., str]

_SSH_ADD_STEPS = frozenset(
    {
        "await_ssh_add_label",
        "await_ssh_add_host",
        "await_ssh_add_port",
        "await_ssh_add_user",
        "await_ssh_add_auth",
        "await_ssh_add_password",
        "await_ssh_add_key_paste",
        "await_ssh_add_key_file",
    }
)

_SSH_OP_STEPS = frozenset({"await_ssh_op_path"})
_SSH_WIZARD_STEPS = _SSH_ADD_STEPS | _SSH_OP_STEPS
_SSH_OPS = frozenset({"ls", "put", "get", "del"})


@dataclass(frozen=True)
class SshWizardDeps:
    tr: TranslateFn
    base_dir: Path
    get_state: Callable[[int], dict]
    set_menu_section: Callable[[int, MenuSection], None]
    set_state_preserving_menu: Callable[..., None]
    clear_state: Callable[[int], None]
    ssh_add_server: Callable[..., tuple[bool, str]]
    build_ssh_menu: Callable[[int], Any]
    list_ssh_servers: Callable[[int], list[dict]]
    get_ssh_server: Callable[[int, int], Optional[dict]]
    ssh_delete_server: Callable[[int, int], bool]
    push_task_direct: Callable[..., Any]
    safe_delete_user_message: Callable[[Message], Any] | None = None


def _ssh_keys_dir(base_dir: Path) -> Path:
    d = base_dir / "queue" / "ssh_keys"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_user_ssh_key(base_dir: Path, user_id: int, content: str) -> tuple[bool, str]:
    """Persist private key text; return (ok, path_or_error)."""
    text = (content or "").strip()
    if not text:
        return False, "empty key"
    if "PRIVATE KEY" not in text and not text.startswith("-----"):
        return False, "not a PEM private key"
    path = _ssh_keys_dir(base_dir) / f"{user_id}_{int(time.time())}.pem"
    try:
        path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
        os.chmod(path, 0o600)
    except OSError as e:
        return False, str(e)
    return True, str(path)


async def start_ssh_add_wizard(deps: SshWizardDeps, message: Message) -> None:
    uid = message.from_user.id
    deps.set_menu_section(uid, MenuSection.SSH)
    deps.set_state_preserving_menu(uid, {"step": "await_ssh_add_label"})
    await message.reply_text(deps.tr(uid, "ssh_wizard_ask_label"), parse_mode=None)


async def start_ssh_op_wizard(deps: SshWizardDeps, message: Message, op: str) -> None:
    uid = message.from_user.id
    op = (op or "").strip().lower()
    if op not in _SSH_OPS:
        return
    deps.set_menu_section(uid, MenuSection.SSH)
    rows = deps.list_ssh_servers(uid)
    if not rows:
        await message.reply_text(deps.tr(uid, "ssh_list_empty"), parse_mode=None)
        return
    buttons = []
    for r in rows[:20]:
        sid = int(r["id"])
        label = f"#{sid} {r.get('label') or r.get('host')}"
        buttons.append([InlineKeyboardButton(label[:60], callback_data=f"sshop:{op}:{sid}")])
    await message.reply_text(
        deps.tr(uid, "ssh_op_pick_server", op=op),
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=None,
    )


async def finish_ssh_add_from_state(
    deps: SshWizardDeps,
    message: Message,
    user_id: int,
    state: dict,
    *,
    ssh_secret: str = "",
    ssh_key_path: str = "",
) -> None:
    label = str(state.get("ssh_w_label") or "").strip()
    host = str(state.get("ssh_w_host") or "").strip()
    port = int(state.get("ssh_w_port") or 22)
    ssh_user = str(state.get("ssh_w_user") or "").strip()
    ok, msg = deps.ssh_add_server(
        user_id,
        label,
        host,
        port,
        ssh_user,
        ssh_secret=ssh_secret,
        ssh_key_path=ssh_key_path,
    )
    if ssh_secret and deps.safe_delete_user_message:
        try:
            await deps.safe_delete_user_message(message)
        except Exception:
            pass
    deps.clear_state(user_id)
    deps.set_menu_section(user_id, MenuSection.SSH)
    if not ok:
        await message.reply_text(msg, parse_mode=None)
        return
    await message.reply_text(
        deps.tr(user_id, "ssh_add_ok", label=label, host=host, port=port),
        reply_markup=deps.build_ssh_menu(user_id),
        parse_mode=None,
    )


async def complete_ssh_key_file_upload(
    deps: SshWizardDeps,
    message: Message,
    user_id: int,
    key_content: str,
) -> bool:
    state = deps.get_state(user_id)
    if state.get("step") != "await_ssh_add_key_file":
        return False
    ok, path_or_err = save_user_ssh_key(deps.base_dir, user_id, key_content)
    if not ok:
        await message.reply_text(deps.tr(user_id, "ssh_wizard_key_invalid", error=path_or_err), parse_mode=None)
        return True
    await finish_ssh_add_from_state(deps, message, user_id, state, ssh_key_path=path_or_err)
    return True


async def handle_ssh_op_callback(
    deps: SshWizardDeps,
    client: Any,
    callback_query: Any,
    op: str,
    server_id: int,
) -> bool:
    uid = callback_query.from_user.id
    op = (op or "").strip().lower()
    if op not in _SSH_OPS:
        return False
    srv = deps.get_ssh_server(uid, server_id)
    if not srv:
        await callback_query.answer(deps.tr(uid, "ssh_server_not_found"), show_alert=True)
        return True

    if op == "del":
        await callback_query.answer()
        if deps.ssh_delete_server(uid, server_id):
            await callback_query.message.reply_text(
                deps.tr(uid, "ssh_del_ok", id=server_id),
                reply_markup=deps.build_ssh_menu(uid),
                parse_mode=None,
            )
        else:
            await callback_query.message.reply_text(deps.tr(uid, "ssh_server_not_found"), parse_mode=None)
        return True

    if not srv.get("ssh_secret") and not srv.get("ssh_key_path"):
        await callback_query.answer(deps.tr(uid, "ssh_auth_missing"), show_alert=True)
        return True

    await callback_query.answer()
    deps.set_state_preserving_menu(
        uid,
        {"step": "await_ssh_op_path", "ssh_op": op, "ssh_server_id": server_id},
    )
    await callback_query.message.reply_text(deps.tr(uid, "ssh_op_ask_path", op=op), parse_mode=None)
    return True


async def _run_ssh_op_path(
    deps: SshWizardDeps,
    message: Message,
    user_id: int,
    state: dict,
    remote_path: str,
) -> None:
    op = str(state.get("ssh_op") or "")
    server_id = int(state.get("ssh_server_id") or 0)
    srv = deps.get_ssh_server(user_id, server_id)
    if not srv:
        deps.clear_state(user_id)
        await message.reply_text(deps.tr(user_id, "ssh_server_not_found"), parse_mode=None)
        return
    path = remote_path.strip() or "."

    if op == "ls":
        ok, detail = sftp_list(
            srv.get("host", ""),
            int(srv.get("port") or 22),
            srv.get("ssh_user", ""),
            path,
            password=srv.get("ssh_secret"),
            key_filename=srv.get("ssh_key_path"),
        )
        deps.clear_state(user_id)
        await message.reply_text(
            deps.tr(user_id, "ssh_ls_result", path=path, detail=detail)
            if ok
            else deps.tr(user_id, "ssh_ls_error", error=detail),
            parse_mode=None,
        )
        return

    if op == "put":
        deps.set_state_preserving_menu(
            user_id,
            {"step": "await_ssh_put_file", "ssh_server_id": server_id, "ssh_remote_path": path},
        )
        await message.reply_text(deps.tr(user_id, "ssh_put_await_file"), parse_mode=None)
        return

    if op == "get":
        task = {
            "type": "ssh_get",
            "remote_path": path,
            "telegram_user_id": user_id,
            "chat_id": message.chat.id,
            "ssh_server": {
                "host": srv["host"],
                "port": srv["port"],
                "ssh_user": srv["ssh_user"],
                "ssh_secret": srv.get("ssh_secret"),
                "ssh_key_path": srv.get("ssh_key_path"),
            },
        }
        deps.clear_state(user_id)
        await deps.push_task_direct(message, task)
        return

    deps.clear_state(user_id)
    await message.reply_text(deps.tr(user_id, "ssh_op_ask_path", op=op), parse_mode=None)


async def dispatch_ssh_wizard(
    deps: SshWizardDeps,
    message: Message,
    user_id: int,
    state: dict,
    text: str,
) -> bool:
    step = state.get("step")
    if step not in _SSH_WIZARD_STEPS:
        return False

    raw = (text or "").strip()

    if step == "await_ssh_op_path":
        if not raw:
            await message.reply_text(
                deps.tr(user_id, "ssh_op_ask_path", op=str(state.get("ssh_op") or "")),
                parse_mode=None,
            )
            return True
        await _run_ssh_op_path(deps, message, user_id, state, raw)
        return True

    if step == "await_ssh_add_label":
        if not raw:
            await message.reply_text(deps.tr(user_id, "ssh_wizard_ask_label"), parse_mode=None)
            return True
        deps.set_state_preserving_menu(
            user_id,
            {**state, "step": "await_ssh_add_host", "ssh_w_label": raw[:64]},
        )
        await message.reply_text(deps.tr(user_id, "ssh_wizard_ask_host"), parse_mode=None)
        return True

    if step == "await_ssh_add_host":
        if not raw:
            await message.reply_text(deps.tr(user_id, "ssh_wizard_ask_host"), parse_mode=None)
            return True
        deps.set_state_preserving_menu(
            user_id,
            {**state, "step": "await_ssh_add_port", "ssh_w_host": raw[:255]},
        )
        await message.reply_text(deps.tr(user_id, "ssh_wizard_ask_port"), parse_mode=None)
        return True

    if step == "await_ssh_add_port":
        try:
            port = int(raw or "22")
        except ValueError:
            await message.reply_text(deps.tr(user_id, "ssh_wizard_bad_port"), parse_mode=None)
            return True
        if port < 1 or port > 65535:
            await message.reply_text(deps.tr(user_id, "ssh_wizard_bad_port"), parse_mode=None)
            return True
        deps.set_state_preserving_menu(
            user_id,
            {**state, "step": "await_ssh_add_user", "ssh_w_port": port},
        )
        await message.reply_text(deps.tr(user_id, "ssh_wizard_ask_user"), parse_mode=None)
        return True

    if step == "await_ssh_add_user":
        if not raw:
            await message.reply_text(deps.tr(user_id, "ssh_wizard_ask_user"), parse_mode=None)
            return True
        deps.set_state_preserving_menu(
            user_id,
            {**state, "step": "await_ssh_add_auth", "ssh_w_user": raw[:64]},
        )
        await message.reply_text(deps.tr(user_id, "ssh_wizard_ask_auth"), parse_mode=None)
        return True

    if step == "await_ssh_add_auth":
        choice = raw.lower()
        if choice in ("key", "کلید", "2", "k"):
            deps.set_state_preserving_menu(user_id, {**state, "step": "await_ssh_add_key_paste"})
            await message.reply_text(deps.tr(user_id, "ssh_wizard_ask_key_paste"), parse_mode=None)
            return True
        if choice in ("file", "فایل", "3", "upload"):
            deps.set_state_preserving_menu(user_id, {**state, "step": "await_ssh_add_key_file"})
            await message.reply_text(deps.tr(user_id, "ssh_wizard_ask_key_file"), parse_mode=None)
            return True
        if choice in ("password", "رمز", "1", "pass", "pwd"):
            deps.set_state_preserving_menu(user_id, {**state, "step": "await_ssh_add_password"})
            await message.reply_text(deps.tr(user_id, "ssh_wizard_ask_password"), parse_mode=None)
            return True
        if raw:
            await finish_ssh_add_from_state(deps, message, user_id, state, ssh_secret=raw)
            return True
        await message.reply_text(deps.tr(user_id, "ssh_wizard_ask_auth"), parse_mode=None)
        return True

    if step == "await_ssh_add_password":
        if not raw:
            await message.reply_text(deps.tr(user_id, "ssh_wizard_ask_password"), parse_mode=None)
            return True
        await finish_ssh_add_from_state(deps, message, user_id, state, ssh_secret=raw)
        return True

    if step == "await_ssh_add_key_paste":
        if not raw:
            await message.reply_text(deps.tr(user_id, "ssh_wizard_ask_key_paste"), parse_mode=None)
            return True
        ok, path_or_err = save_user_ssh_key(deps.base_dir, user_id, raw)
        if not ok:
            await message.reply_text(deps.tr(user_id, "ssh_wizard_key_invalid", error=path_or_err), parse_mode=None)
            return True
        await finish_ssh_add_from_state(deps, message, user_id, state, ssh_key_path=path_or_err)
        return True

    if step == "await_ssh_add_key_file":
        await message.reply_text(deps.tr(user_id, "ssh_wizard_ask_key_file"), parse_mode=None)
        return True

    return False
