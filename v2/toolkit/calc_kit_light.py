"""Independent calculators inspired by popular Persian toolkit sites (kitset-style)."""

from __future__ import annotations

import math
import random
import re
from typing import Optional

_ONES = (
    "",
    "یک",
    "دو",
    "سه",
    "چهار",
    "پنج",
    "شش",
    "هفت",
    "هشت",
    "نه",
    "ده",
    "یازده",
    "دوازده",
    "سیزده",
    "چهارده",
    "پانزده",
    "شانزده",
    "هفده",
    "هجده",
    "نوزده",
)
_TENS = ("", "", "بیست", "سی", "چهل", "پنجاه", "شصت", "هفتاد", "هشتاد", "نود")
_HUNDREDS = ("", "صد", "دویست", "سیصد", "چهارصد", "پانصد", "ششصد", "هفتصد", "هشتصد", "نهصد")
_SCALES = ("", "هزار", "میلیون", "میلیارد", "تریلیون", "کوآدریلیون", "کوینتیلیون")


def _parse_num(raw: str) -> Optional[float]:
    s = (raw or "").strip().replace(",", "").replace("٬", "").replace("،", "").replace("٫", ".")
    s = s.replace("۰", "0").replace("۱", "1").replace("۲", "2").replace("۳", "3")
    s = s.replace("۴", "4").replace("۵", "5").replace("۶", "6").replace("۷", "7")
    s = s.replace("۸", "8").replace("۹", "9")
    try:
        v = float(s)
    except ValueError:
        return None
    if v != v or v in (float("inf"), float("-inf")):  # NaN / inf
        return None
    return v


def percent_of(part: float, whole: float) -> tuple[bool, str]:
    if whole == 0:
        return False, "مخرج صفر است."
    pct = (part / whole) * 100.0
    return True, f"{part:g} از {whole:g} = {pct:,.4f}٪"


def percent_change(old: float, new: float) -> tuple[bool, str]:
    if old == 0:
        return False, "مقدار اولیه صفر است."
    ch = ((new - old) / old) * 100.0
    direction = "افزایش" if ch >= 0 else "کاهش"
    return True, f"از {old:g} به {new:g}\n{direction}: {abs(ch):,.4f}٪"


def apply_percent(value: float, pct: float, *, mode: str = "of") -> tuple[bool, str]:
    if mode == "inc":
        out = value * (1 + pct / 100.0)
        return True, f"{value:g} + {pct:g}٪ = {out:,.4f}"
    if mode == "dec":
        out = value * (1 - pct / 100.0)
        return True, f"{value:g} − {pct:g}٪ = {out:,.4f}"
    out = value * (pct / 100.0)
    return True, f"{pct:g}٪ از {value:g} = {out:,.4f}"


def loan_emi(principal: float, annual_rate_pct: float, months: int) -> tuple[bool, str]:
    if principal <= 0 or months <= 0:
        return False, "مبلغ و تعداد ماه باید مثبت باشد."
    if annual_rate_pct < 0:
        return False, "نرخ نمی‌تواند منفی باشد."
    r = (annual_rate_pct / 100.0) / 12.0
    if r == 0:
        emi = principal / months
        total = principal
    else:
        emi = principal * r * ((1 + r) ** months) / (((1 + r) ** months) - 1)
        total = emi * months
    interest = total - principal
    return True, (
        "محاسبه اقساط وام\n"
        f"اصل: {principal:,.0f}\n"
        f"نرخ سالانه: {annual_rate_pct:g}٪\n"
        f"مدت: {months} ماه\n"
        f"قسط ماهانه: {emi:,.0f}\n"
        f"کل پرداختی: {total:,.0f}\n"
        f"سود تقریبی: {interest:,.0f}"
    )


def deposit_interest(principal: float, annual_rate_pct: float, months: int) -> tuple[bool, str]:
    if principal <= 0 or months <= 0:
        return False, "مبلغ و مدت باید مثبت باشد."
    if annual_rate_pct < 0:
        return False, "نرخ نمی‌تواند منفی باشد."
    interest = principal * (annual_rate_pct / 100.0) * (months / 12.0)
    return True, (
        "سود سپرده (ساده)\n"
        f"اصل: {principal:,.0f}\n"
        f"نرخ سالانه: {annual_rate_pct:g}٪\n"
        f"مدت: {months} ماه\n"
        f"سود: {interest:,.0f}\n"
        f"جمع: {principal + interest:,.0f}"
    )


def rial_toman(amount: float, *, to: str) -> tuple[bool, str]:
    t = (to or "").lower()
    if t in ("toman", "irt", "tmn", "تومان"):
        return True, f"{amount:,.0f} ریال = {amount / 10.0:,.1f} تومان"
    if t in ("rial", "irr", "ریال"):
        return True, f"{amount:,.0f} تومان = {amount * 10.0:,.0f} ریال"
    return False, "مقصد را rial یا toman بفرست."


def word_count(text: str) -> tuple[bool, str]:
    words = re.findall(r"\S+", text or "")
    chars = len(text or "")
    chars_no_space = len(re.sub(r"\s+", "", text or ""))
    return True, (
        "شمارش متن\n"
        f"کلمه: {len(words)}\n"
        f"کاراکتر (با فاصله): {chars}\n"
        f"کاراکتر (بدون فاصله): {chars_no_space}"
    )


def _three_digits_fa(n: int) -> str:
    if n == 0:
        return ""
    if n < 20:
        return _ONES[n]
    if n < 100:
        a, b = divmod(n, 10)
        return _TENS[a] if b == 0 else f"{_TENS[a]} و {_ONES[b]}"
    a, b = divmod(n, 100)
    rest = _three_digits_fa(b)
    return _HUNDREDS[a] if not rest else f"{_HUNDREDS[a]} و {rest}"


def number_to_persian_words(n: int) -> tuple[bool, str]:
    if n < 0:
        ok, body = number_to_persian_words(-n)
        return ok, ("منفی " + body) if ok else body
    if n == 0:
        return True, "صفر"
    parts = []
    scale = 0
    while n > 0 and scale < len(_SCALES):
        n, rem = divmod(n, 1000)
        if rem:
            chunk = _three_digits_fa(rem)
            if _SCALES[scale]:
                chunk = f"{chunk} {_SCALES[scale]}".strip()
            parts.append(chunk)
        scale += 1
    return True, " و ".join(reversed(parts))


_UNIT_TABLES: dict[str, dict[str, float]] = {
    "temp": {},  # special
    "length": {"m": 1.0, "km": 1000.0, "cm": 0.01, "mm": 0.001, "mi": 1609.344, "ft": 0.3048, "in": 0.0254},
    "weight": {"kg": 1.0, "g": 0.001, "mg": 1e-6, "lb": 0.45359237, "oz": 0.028349523125},
    "volume": {"l": 1.0, "ml": 0.001, "m3": 1000.0, "gal": 3.785411784},
    "speed": {"mps": 1.0, "kph": 1 / 3.6, "mph": 0.44704},
    "data": {"b": 1.0, "kb": 1024.0, "mb": 1024**2, "gb": 1024**3, "tb": 1024**4},
    "area": {"m2": 1.0, "km2": 1e6, "cm2": 1e-4, "ha": 10000.0, "acre": 4046.8564224, "ft2": 0.09290304},
}


def convert_unit(kind: str, amount: float, frm: str, to: str) -> tuple[bool, str]:
    k = (kind or "").lower().strip()
    f = (frm or "").lower().strip()
    t = (to or "").lower().strip()
    if k in ("temp", "temperature", "دما"):
        # normalize to C
        if f in ("c", "celsius"):
            c = amount
        elif f in ("f", "fahrenheit"):
            c = (amount - 32) * 5 / 9
        elif f in ("k", "kelvin"):
            c = amount - 273.15
        else:
            return False, "واحد دما: C / F / K"
        if t in ("c", "celsius"):
            out = c
        elif t in ("f", "fahrenheit"):
            out = c * 9 / 5 + 32
        elif t in ("k", "kelvin"):
            out = c + 273.15
        else:
            return False, "واحد دما: C / F / K"
        return True, f"{amount:g} {f.upper()} = {out:,.4f} {t.upper()}"
    table = _UNIT_TABLES.get(k)
    if not table:
        return False, "نوع: length|weight|volume|speed|data|temp|area"
    if f not in table or t not in table:
        return False, f"واحدهای {k}: {', '.join(sorted(table))}"
    base = amount * table[f]
    out = base / table[t]
    return True, f"{amount:g} {f} = {out:,.6g} {t}"


def base_convert(value: str, base_from: int, base_to: int) -> tuple[bool, str]:
    try:
        n = int(value.strip(), base_from)
    except ValueError:
        return False, "عدد/مبنا نامعتبر است."
    if not (2 <= base_to <= 36):
        return False, "مبنا باید بین ۲ تا ۳۶ باشد."
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    if n == 0:
        return True, "0"
    neg = n < 0
    n = abs(n)
    out = []
    while n:
        n, r = divmod(n, base_to)
        out.append(digits[r])
    s = "".join(reversed(out))
    return True, ("-" if neg else "") + s


def binary_text(mode: str, payload: str) -> tuple[bool, str]:
    m = (mode or "").lower()
    if m in ("to", "encode", "bin"):
        data = (payload or "").encode("utf-8")
        bits = " ".join(format(b, "08b") for b in data)
        return True, bits or "(empty)"
    if m in ("from", "decode", "text"):
        parts = payload.replace(" ", "")
        if len(parts) % 8 != 0 or not re.fullmatch(r"[01]+", parts or ""):
            return False, "بایت‌های ۸بیتی ۰/۱ بفرست."
        try:
            data = bytes(int(parts[i : i + 8], 2) for i in range(0, len(parts), 8))
            return True, data.decode("utf-8")
        except Exception:
            return False, "رشته باینری به UTF-8 معتبر نیست."
    return False, "mode: to|from"


def fuel_cost(distance_km: float, consumption_l_per_100: float, price_per_liter: float) -> tuple[bool, str]:
    if distance_km <= 0 or consumption_l_per_100 <= 0 or price_per_liter <= 0:
        return False, "مقادیر باید مثبت باشند."
    liters = distance_km * consumption_l_per_100 / 100.0
    cost = liters * price_per_liter
    return True, (
        "مصرف بنزین\n"
        f"مسافت: {distance_km:g} km\n"
        f"مصرف: {consumption_l_per_100:g} L/100km\n"
        f"لیتر لازم: {liters:,.2f}\n"
        f"هزینه: {cost:,.0f}"
    )


def parse_calc_args(text: str) -> list[str]:
    return [p for p in re.split(r"\s+", (text or "").strip()) if p]


def random_numbers(count: int, lo: float, hi: float, *, integer: bool = True) -> tuple[bool, str]:
    if count <= 0 or count > 50:
        return False, "تعداد باید ۱ تا ۵۰ باشد."
    if hi < lo:
        lo, hi = hi, lo
    vals = []
    for _ in range(count):
        if integer:
            a, b = math.ceil(lo), math.floor(hi)
            if a > b:
                return False, "بازه صحیح معتبری وجود ندارد."
            vals.append(str(random.randint(a, b)))
        else:
            vals.append(f"{random.uniform(lo, hi):.4f}")
    return True, "اعداد تصادفی:\n" + ", ".join(vals)


def math_mean(nums: list[float]) -> tuple[bool, str]:
    if not nums:
        return False, "حداقل یک عدد بفرست."
    m = sum(nums) / len(nums)
    return True, f"میانگین {len(nums)} عدد = {m:,.6g}"


def math_power(base: float, exp: float) -> tuple[bool, str]:
    if base == 0 and exp < 0:
        return False, "صفر به توان منفی تعریف نشده است."
    try:
        out = base**exp
    except (OverflowError, ZeroDivisionError):
        return False, "نتیجه تعریف‌نشده یا خیلی بزرگ است."
    if isinstance(out, complex):
        return False, "نتیجه مختلط است؛ پایه و توان را عوض کن."
    if out != out or out in (float("inf"), float("-inf")):
        return False, "نتیجه نامعتبر است."
    return True, f"{base:g} ^ {exp:g} = {out:,.6g}"


def math_sqrt(n: float) -> tuple[bool, str]:
    if n < 0:
        return False, "جذر عدد منفی تعریف نشده."
    return True, f"√{n:g} = {math.sqrt(n):,.6g}"


def math_factorial(n: int) -> tuple[bool, str]:
    if n < 0 or n > 200:
        return False, "n باید ۰ تا ۲۰۰ باشد."
    return True, f"{n}! = {math.factorial(n)}"


def is_prime(n: int) -> tuple[bool, str]:
    if n <= 1:
        return True, f"{n} اول نیست."
    if n <= 3:
        return True, f"{n} عدد اول است."
    if n % 2 == 0 or n % 3 == 0:
        return True, f"{n} اول نیست."
    i = 5
    while i * i <= n:
        if n % i == 0 or n % (i + 2) == 0:
            return True, f"{n} اول نیست."
        i += 6
    return True, f"{n} عدد اول است."


def ielts_overall(listening: float, reading: float, writing: float, speaking: float) -> tuple[bool, str]:
    scores = [listening, reading, writing, speaking]
    for s in scores:
        if s < 0 or s > 9 or abs(s * 2 - round(s * 2)) > 1e-9:
            return False, "نمرات باید ۰ تا ۹ و با گام ۰٫۵ باشند."
    avg = sum(scores) / 4.0
    # IELTS rounding: .25→.5, .75→next whole
    frac = avg - math.floor(avg)
    if frac < 0.25:
        band = float(math.floor(avg))
    elif frac < 0.75:
        band = math.floor(avg) + 0.5
    else:
        band = float(math.floor(avg) + 1)
    return True, (
        "نمره IELTS (تقریبی)\n"
        f"Listening: {listening:g}\nReading: {reading:g}\n"
        f"Writing: {writing:g}\nSpeaking: {speaking:g}\n"
        f"میانگین: {avg:.2f}\nOverall Band: {band:g}"
    )


def cigarette_cost(
    cigarettes_per_day: float,
    price_per_pack: float,
    *,
    pack_size: int = 20,
    days: int = 365,
) -> tuple[bool, str]:
    if cigarettes_per_day <= 0 or price_per_pack <= 0 or pack_size <= 0 or days <= 0:
        return False, "مقادیر باید مثبت باشند."
    packs = cigarettes_per_day * days / pack_size
    cost = packs * price_per_pack
    return True, (
        "هزینه مصرف سیگار\n"
        f"روزانه: {cigarettes_per_day:g} نخ\n"
        f"قیمت پاکت: {price_per_pack:,.0f}\n"
        f"در {days} روز ≈ {packs:,.1f} پاکت\n"
        f"هزینه تقریبی: {cost:,.0f}"
    )


def rect_metrics(w: float, h: float) -> tuple[bool, str]:
    if w <= 0 or h <= 0:
        return False, "ابعاد باید مثبت باشند."
    return True, (
        "مستطیل\n"
        f"محیط: {2 * (w + h):,.6g}\n"
        f"مساحت: {w * h:,.6g}\n"
        f"قطر: {math.hypot(w, h):,.6g}"
    )


def square_metrics(a: float) -> tuple[bool, str]:
    if a <= 0:
        return False, "ضلع باید مثبت باشد."
    return True, (
        "مربع\n"
        f"محیط: {4 * a:,.6g}\n"
        f"مساحت: {a * a:,.6g}\n"
        f"قطر: {a * math.sqrt(2):,.6g}"
    )


def english_case(text: str, mode: str) -> tuple[bool, str]:
    m = (mode or "").lower()
    if m in ("upper", "up", "بزرگ"):
        return True, text.upper()
    if m in ("lower", "low", "کوچک"):
        return True, text.lower()
    if m in ("title", "عنوان"):
        return True, text.title()
    return False, "mode: upper|lower|title"


def bmi(weight_kg: float, height_cm: float) -> tuple[bool, str]:
    if weight_kg <= 0 or height_cm <= 0:
        return False, "وزن و قد باید مثبت باشند."
    h = height_cm / 100.0
    val = weight_kg / (h * h)
    if val < 18.5:
        cat = "کم‌وزن"
    elif val < 25:
        cat = "نرمال"
    elif val < 30:
        cat = "اضافه‌وزن"
    else:
        cat = "چاق"
    return True, f"BMI = {val:.2f}\nوضعیت تقریبی: {cat}\n(صرفاً اطلاع عمومی — جایگزین مشاوره پزشکی نیست)"


def compound_deposit(principal: float, annual_rate_pct: float, months: int) -> tuple[bool, str]:
    if principal <= 0 or months <= 0 or annual_rate_pct < 0:
        return False, "مقادیر نامعتبر است."
    r = annual_rate_pct / 100.0 / 12.0
    total = principal * ((1 + r) ** months)
    interest = total - principal
    return True, (
        "سود سپرده مرکب (ماهانه)\n"
        f"اصل: {principal:,.0f}\n"
        f"نرخ سالانه: {annual_rate_pct:g}٪\n"
        f"مدت: {months} ماه\n"
        f"سود: {interest:,.0f}\n"
        f"جمع: {total:,.0f}"
    )


def percent_error(actual: float, measured: float) -> tuple[bool, str]:
    if actual == 0:
        return False, "مقدار واقعی صفر است."
    err = abs(measured - actual) / abs(actual) * 100.0
    return True, f"خطای نسبی: {err:,.4f}٪"


def math_log(n: float, base: float = 10.0) -> tuple[bool, str]:
    if n <= 0 or base <= 0 or base == 1:
        return False, "برای لگاریتم، عدد و مبنا باید مثبت و مبنا ≠ ۱ باشد."
    return True, f"log_{base:g}({n:g}) = {math.log(n, base):,.6g}"


def linear_eq(a: float, b: float) -> tuple[bool, str]:
    # ax + b = 0
    if a == 0:
        return False, "ضریب a نباید صفر باشد."
    x = -b / a
    return True, f"{a:g}x + {b:g} = 0\nx = {x:,.6g}"


def quadratic_eq(a: float, b: float, c: float) -> tuple[bool, str]:
    if a == 0:
        return linear_eq(b, c)
    disc = b * b - 4 * a * c
    if disc < 0:
        return True, f"دلتا منفی ({disc:g}) — ریشه حقیقی ندارد."
    s = math.sqrt(disc)
    x1 = (-b + s) / (2 * a)
    x2 = (-b - s) / (2 * a)
    return True, f"Δ = {disc:g}\nx₁ = {x1:,.6g}\nx₂ = {x2:,.6g}"
