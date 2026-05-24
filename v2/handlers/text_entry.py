"""Primary text-message pipeline extracted from telebot."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional

from pyrogram.types import Message

from v2.core.menu_sections import MenuSection

TranslateFn = Callable[..., str]
ResolveRouteFn = Callable[[str], Optional[str]]
AsyncRouteFn = Callable[..., Awaitable[bool]]
AsyncWizardFn = Callable[..., Awaitable[bool]]


@dataclass(frozen=True)
class TextEntryDeps:
    tr: TranslateFn
    get_state: Callable[[int], dict]
    set_menu_section: Callable[[int, MenuSection], None]
    build_plan_menu: Callable[[int], Any]
    resolve_reply_button_route: Callable[..., Optional[str]]
    dispatch_reply_keyboard_route: AsyncRouteFn
    reply_route_deps: Any
    clear_state: Callable[[int], None]
    enqueue_rubika_text_message: Callable[[Message, str], Awaitable[None]]
    dispatch_rubika_connect_wizard: AsyncWizardFn
    rubika_wizard_deps: Any
    dispatch_provider_connect_wizard: AsyncWizardFn
    provider_connect_wizard_deps: Any
    dispatch_zip_batch_wizard: AsyncWizardFn
    zip_batch_wizard_deps: Any
    handle_zip_password_text: AsyncWizardFn
    zip_password_deps: Any
    handle_direct_mode_plain_text: AsyncWizardFn
    direct_mode_text_deps: Any
    handle_direct_url_sendlink_hint: AsyncWizardFn
    direct_url_hint_deps: Any
    handle_link_direct_text: AsyncWizardFn
    link_direct_deps: Any
    build_main_menu: Callable[[int], Any]


async def handle_text_entry(deps: TextEntryDeps, client: Any, message: Message) -> None:
    text = message.text or ""
    user_id = message.from_user.id
    state = deps.get_state(user_id)

    mapped = deps.resolve_reply_button_route(text, user_id, deps.tr)
    if await deps.dispatch_reply_keyboard_route(client, message, user_id, mapped, deps.reply_route_deps):
        return

    if state.get("step") == "await_quick_message":
        deps.clear_state(user_id)
        await deps.enqueue_rubika_text_message(message, text)
        return

    if await deps.dispatch_rubika_connect_wizard(
        message,
        user_id,
        state,
        text,
        deps.rubika_wizard_deps,
    ):
        return

    if await deps.dispatch_provider_connect_wizard(
        message,
        user_id,
        state,
        text,
        deps.provider_connect_wizard_deps,
    ):
        return

    if await deps.dispatch_zip_batch_wizard(
        message,
        user_id,
        state,
        text,
        deps.zip_batch_wizard_deps,
    ):
        return

    if await deps.handle_zip_password_text(message, user_id, text, deps.zip_password_deps):
        return

    if await deps.handle_link_direct_text(deps.link_direct_deps, client, message, user_id, text):
        return

    if await deps.handle_direct_mode_plain_text(message, user_id, text, deps.direct_mode_text_deps):
        return

    if await deps.handle_direct_url_sendlink_hint(message, user_id, text, deps.direct_url_hint_deps):
        return

    await message.reply_text(
        deps.tr(user_id, "text_unhandled_hint"),
        reply_markup=deps.build_main_menu(user_id),
        parse_mode=None,
    )
