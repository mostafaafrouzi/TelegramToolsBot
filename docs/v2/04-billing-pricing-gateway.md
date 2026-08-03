# Billing, Pricing, and Gateway Contract (v2)

## 1) Package Matrix (implemented)

| Tier | Transfer day/mo MB | Max file MB | Parallel | Toolkit/day | World/day | Feed max | Push |
|---|---:|---:|---:|---:|---:|---:|---|
| guest | 100 / 500 | 50 | 1 | 15 | 10 | 5 | no |
| free | 500 / 5000 | 500 | 2 | 40 | 30 | 20 | yes |
| pro | 5000 / 50000 | 2048 | 5 | ∞ | ∞ | 50 | yes |
| star | 15000 / 120000 | 2048 | 8 | ∞ | ∞ | 100 | yes |

Notes:
- `0` in code for toolkit/world daily means unlimited.
- Source of truth: [`user_entitlements.py`](../../user_entitlements.py) `TIER_LIMITS`.
- Env overrides: `WORLD_FEED_LIMIT_*`, `TOOLKIT_DAILY_LIMIT_PER_USER`, `MAX_FILE_MB`, `DISABLE_USAGE_LIMITS`.
- Online checkout SKU today: 30-day **pro** via Zarinpal (`/purchase`).
- **star** is admin-granted (`/admin_tier` or `tools/grant_plan.py`).

## 2) Quota Dimensions
- Transfer bytes day/month (`usage_ledger`)
- `max_parallel_tasks` / `max_file_mb`
- Toolkit daily hits (`v2_toolkit_daily`)
- World/FX daily hits (`v2_world_daily`)
- Feed count + push allow flag

Enforcement points:
- Pre-queue gating for transfers (`can_enqueue`)
- Toolkit/world pre-flight + commit-after-success
- Feed add / push toggle plan checks

## 3) Pricing Model (current product)
- Monthly Pro via Zarinpal amount `ZARINPAL_PLAN_AMOUNT_IRR`.
- Star / custom grants via admin tools.
- Future: yearly discount, seat packs, credit packs (not coded yet).

## 4) Gateway Abstraction
Interface:
- `create_payment_intent(user_id, amount, currency, metadata)`
- `verify_callback(headers, payload) -> verified_event`
- `fetch_payment_status(authority_or_ref)`
- `refund_payment(payment_id, amount)`

Provider adapters:
- `v2/billing/zarinpal.py` (live)
- Stub gateway for local/dev (`BILLING_STUB_CHECKOUT`)

## 5) Webhook Contract
- Signature / callback verification on Mini App path `/billing/zarinpal/callback`
- Lifecycle: `initiated` -> `pending` -> (`paid` | `failed` | `expired` | `refunded`)
- Never activate subscription before verified callback / reconcile

## 6) Reconciliation Jobs
- Optional reconcile loop for pending intents
- Admin `/admin_reconcile_billing`

## 7) Access and Entitlement Rules
- Paid tiers `pro`/`star` honor `expires_at` (downgrade to free when expired)
- Guest is restrictive demo tier
- Free is default for new users

## 8) Fraud Controls
- Limit rapid payment attempts (gateway layer)
- Admin override for abuse

## 9) Required Admin Tools
- `/admin_tier`, `/admin_bonus`, payment lookup/status, reconcile
- CLI: `tools/grant_plan.py`
