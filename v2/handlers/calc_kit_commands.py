"""Kitset-inspired calculator commands and wizards (independent local math)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable, Optional

from pyrogram.types import Message

from v2.core.menu_sections import MenuSection
from v2.toolkit import calc_kit_light as ck
from v2.toolkit.calendar_light import convert_date, date_diff
from v2.toolkit.iran_info_light import national_id_city, plate_lookup
from v2.toolkit.text_utils_light import payload_after_command

TranslateFn = Callable[..., str]
QuotaTryFn = Callable[[int], tuple[bool, str]]
QuotaCommitFn = Callable[[int], None]


@dataclass(frozen=True)
class CalcKitDeps:
    tr: TranslateFn
    set_menu_section: Callable[[int, MenuSection], None]
    set_state_preserving_menu: Callable[[int, dict], None]
    clear_state: Callable[[int], None]
    get_state: Callable[[int], dict]
    toolkit_quota_try: QuotaTryFn
    toolkit_quota_commit: QuotaCommitFn
    toolkit_utility_light_enabled: bool = True


def _parse_floats(parts: list[str]) -> Optional[list[float]]:
    out: list[float] = []
    for p in parts:
        n = ck._parse_num(p)
        if n is None:
            return None
        out.append(n)
    return out


async def _quota(deps: CalcKitDeps, uid: int, message: Message) -> bool:
    ok, msg = deps.toolkit_quota_try(uid)
    if ok:
        return True
    await message.reply_text(msg or deps.tr(uid, "toolkit_quota_exceeded"), parse_mode=None)
    return False


async def _reply_calc(deps: CalcKitDeps, message: Message, ok: bool, body: str) -> None:
    uid = message.from_user.id
    if ok:
        deps.toolkit_quota_commit(uid)
    await message.reply_text(body if ok else deps.tr(uid, "calc_error", detail=body), parse_mode=None)


def _start_wizard(deps: CalcKitDeps, uid: int, step: str) -> None:
    deps.set_menu_section(uid, MenuSection.TOOLKIT)
    deps.set_state_preserving_menu(uid, {"step": step})


async def start_calc_tool(deps: CalcKitDeps, message: Message, tool: str) -> None:
    uid = message.from_user.id
    if not deps.toolkit_utility_light_enabled:
        await message.reply_text(deps.tr(uid, "toolkit_utility_disabled"), parse_mode=None)
        return
    hints = {
        "percent": "calc_hint_percent",
        "loan": "calc_hint_loan",
        "deposit": "calc_hint_deposit",
        "rial": "calc_hint_rial",
        "words": "calc_hint_words",
        "unit": "calc_hint_unit",
        "base": "calc_hint_base",
        "binary": "calc_hint_binary",
        "fuel": "calc_hint_fuel",
        "plate": "calc_hint_plate",
        "nid": "calc_hint_nid",
        "datediff": "calc_hint_datediff",
        "dateconv": "calc_hint_dateconv",
        "random": "calc_hint_random",
        "mean": "calc_hint_mean",
        "power": "calc_hint_power",
        "sqrt": "calc_hint_sqrt",
        "fact": "calc_hint_fact",
        "prime": "calc_hint_prime",
        "ielts": "calc_hint_ielts",
        "cig": "calc_hint_cig",
        "rect": "calc_hint_rect",
        "square": "calc_hint_square",
        "case": "calc_hint_case",
        "wordcount": "calc_hint_wordcount",
    }
    key = hints.get(tool, "calc_hint_percent")
    _start_wizard(deps, uid, f"await_calc_{tool}")
    await message.reply_text(deps.tr(uid, key), parse_mode=None)


async def run_calc_command(deps: CalcKitDeps, message: Message, tool: str) -> None:
    """Slash/command entry: use args if present, else wizard."""
    uid = message.from_user.id
    if not deps.toolkit_utility_light_enabled:
        await message.reply_text(deps.tr(uid, "toolkit_utility_disabled"), parse_mode=None)
        return
    payload = payload_after_command(message.text or "").strip()
    if not payload:
        await start_calc_tool(deps, message, tool)
        return
    if not await _quota(deps, uid, message):
        return
    ok, body = await asyncio.to_thread(_eval_calc, tool, payload)
    await _reply_calc(deps, message, ok, body)


def _eval_calc(tool: str, payload: str) -> tuple[bool, str]:
    parts = ck.parse_calc_args(payload)
    t = (tool or "").lower()
    if t == "percent":
        if len(parts) >= 3 and parts[0] in ("of", "inc", "dec", "chg", "change"):
            mode = parts[0]
            nums = _parse_floats(parts[1:])
            if not nums or len(nums) < 2:
                return False, "usage"
            if mode == "of":
                return ck.apply_percent(nums[0], nums[1], mode="of")
            if mode == "inc":
                return ck.apply_percent(nums[0], nums[1], mode="inc")
            if mode == "dec":
                return ck.apply_percent(nums[0], nums[1], mode="dec")
            return ck.percent_change(nums[0], nums[1])
        nums = _parse_floats(parts)
        if not nums or len(nums) < 2:
            return False, "دو عدد بفرست: جزء کل"
        return ck.percent_of(nums[0], nums[1])
    if t == "loan":
        nums = _parse_floats(parts)
        if not nums or len(nums) < 3:
            return False, "اصل نرخ_سالانه ماه"
        return ck.loan_emi(nums[0], nums[1], int(nums[2]))
    if t == "deposit":
        nums = _parse_floats(parts)
        if not nums or len(nums) < 3:
            return False, "اصل نرخ_سالانه ماه"
        return ck.deposit_interest(nums[0], nums[1], int(nums[2]))
    if t == "rial":
        nums = _parse_floats(parts[:1])
        if not nums:
            return False, "عدد + toman|rial"
        dest = parts[1] if len(parts) > 1 else "toman"
        return ck.rial_toman(nums[0], to=dest)
    if t == "words":
        n = ck._parse_num(parts[0]) if parts else None
        if n is None:
            return False, "یک عدد صحیح بفرست"
        return ck.number_to_persian_words(int(n))
    if t == "unit":
        if len(parts) < 4:
            return False, "نوع مقدار از به"
        amount = ck._parse_num(parts[1])
        if amount is None:
            return False, "مقدار نامعتبر"
        return ck.convert_unit(parts[0], amount, parts[2], parts[3])
    if t == "base":
        if len(parts) < 3:
            return False, "مقدار مبنا_از مبنا_به"
        try:
            return ck.base_convert(parts[0], int(parts[1]), int(parts[2]))
        except ValueError:
            return False, "مبنا نامعتبر"
    if t == "binary":
        if len(parts) < 2:
            return False, "to|from متن"
        return ck.binary_text(parts[0], " ".join(parts[1:]))
    if t == "fuel":
        nums = _parse_floats(parts)
        if not nums or len(nums) < 3:
            return False, "مسافت مصرف_در_۱۰۰ قیمت_لیتر"
        return ck.fuel_cost(nums[0], nums[1], nums[2])
    if t == "plate":
        return plate_lookup(parts[0] if parts else payload)
    if t == "nid":
        return national_id_city(parts[0] if parts else payload)
    if t == "datediff":
        if len(parts) < 2:
            return False, "تاریخ1 تاریخ2"
        return date_diff(parts[0], parts[1], lang="fa")
    if t == "dateconv":
        return convert_date(parts[0] if parts else payload, lang="fa")
    if t == "random":
        nums = _parse_floats(parts)
        if not nums or len(nums) < 3:
            return False, "تعداد حداقل حداکثر"
        return ck.random_numbers(int(nums[0]), nums[1], nums[2])
    if t == "mean":
        nums = _parse_floats(parts)
        if nums is None:
            return False, "اعداد را با فاصله بفرست"
        return ck.math_mean(nums)
    if t == "power":
        nums = _parse_floats(parts)
        if not nums or len(nums) < 2:
            return False, "پایه توان"
        return ck.math_power(nums[0], nums[1])
    if t == "sqrt":
        nums = _parse_floats(parts)
        if not nums:
            return False, "یک عدد بفرست"
        return ck.math_sqrt(nums[0])
    if t == "fact":
        nums = _parse_floats(parts)
        if not nums:
            return False, "یک عدد صحیح بفرست"
        return ck.math_factorial(int(nums[0]))
    if t == "prime":
        nums = _parse_floats(parts)
        if not nums:
            return False, "یک عدد صحیح بفرست"
        return ck.is_prime(int(nums[0]))
    if t == "ielts":
        nums = _parse_floats(parts)
        if not nums or len(nums) < 4:
            return False, "L R W S"
        return ck.ielts_overall(nums[0], nums[1], nums[2], nums[3])
    if t == "cig":
        nums = _parse_floats(parts)
        if not nums or len(nums) < 2:
            return False, "نخ_روزانه قیمت_پاکت"
        pack = int(nums[2]) if len(nums) > 2 else 20
        days = int(nums[3]) if len(nums) > 3 else 365
        return ck.cigarette_cost(nums[0], nums[1], pack_size=pack, days=days)
    if t == "rect":
        nums = _parse_floats(parts)
        if not nums or len(nums) < 2:
            return False, "عرض طول"
        return ck.rect_metrics(nums[0], nums[1])
    if t == "square":
        nums = _parse_floats(parts)
        if not nums:
            return False, "ضلع"
        return ck.square_metrics(nums[0])
    if t == "case":
        if len(parts) < 2:
            return False, "upper|lower|title متن"
        return ck.english_case(" ".join(parts[1:]), parts[0])
    if t == "wordcount":
        return ck.word_count(payload)
    return False, "unknown_tool"


async def dispatch_calc_wizard(
    deps: CalcKitDeps,
    message: Message,
    user_id: int,
    text: str,
) -> bool:
    state = deps.get_state(user_id)
    step = str(state.get("step") or "")
    if not step.startswith("await_calc_"):
        return False
    tool = step[len("await_calc_") :]
    payload = (text or "").strip()
    if not payload:
        await start_calc_tool(deps, message, tool)
        return True
    if not await _quota(deps, user_id, message):
        deps.clear_state(user_id)
        return True
    ok, body = await asyncio.to_thread(_eval_calc, tool, payload)
    deps.clear_state(user_id)
    await _reply_calc(deps, message, ok, body)
    return True
