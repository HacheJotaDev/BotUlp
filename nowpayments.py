"""
═══════════════════════════════════════════════════════════════
  HJ ULP EXTRACTOR BOT — NOWPayments Integration Module v3
═══════════════════════════════════════════════════════════════
  • Usa POST /v1/invoice → genera link multi-crypto
  • IPN webhook para auto-delivery instantaneo
  • Polling GET /v1/payment/{id} como fallback
  • Soporte multi-crypto (USDT, BTC, ETH, etc.)
═══════════════════════════════════════════════════════════════
"""

import asyncio
import aiohttp
from datetime import datetime, timezone
from typing import Optional, Dict

from config import config
from logger_setup import logger
from database import db

# ── Precios VIP (USD) ──────────────────────────────────────
VIP_PLANS = {
    1: {"price": 6.0, "label": "1 Dia"},
    3: {"price": 10.0, "label": "3 Dias"},
    7: {"price": 25.0, "label": "7 Dias"},
    30: {"price": 100.0, "label": "30 Dias"},
}

# ── Configuracion API ──────────────────────────────────────
NP_API_BASE = "https://api.nowpayments.io/v1"
NP_HEADERS = {
    "x-api-key": config.NOWPAYMENTS_API_KEY,
    "Content-Type": "application/json",
}

# Status que indican pago exitoso
SUCCESS_STATUSES = ("finished", "confirmed", "paid", "partially_paid")

# Status que indican que hay que esperar
WAITING_STATUSES = ("waiting", "confirming", "sending", "pending")

# Status que indican fallo
FAIL_STATUSES = ("expired", "failed", "refunded", "reverted")


# ═════════════════════════════════════════════════════════════
#  FUNCIONES API BASE
# ═════════════════════════════════════════════════════════════

async def _api_get(endpoint: str, params: dict = None) -> Optional[Dict]:
    """GET request a la API de NOWPayments."""
    url = f"{NP_API_BASE}{endpoint}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=NP_HEADERS, params=params,
                                  timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    text = await resp.text()
                    logger.error(f"NP GET {endpoint} error {resp.status}: {text[:300]}")
    except Exception as e:
        logger.error(f"NP GET {endpoint} exception: {e}")
    return None


async def _api_post(endpoint: str, payload: dict) -> Optional[Dict]:
    """POST request a la API de NOWPayments."""
    url = f"{NP_API_BASE}{endpoint}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=NP_HEADERS, json=payload,
                                   timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status in (200, 201):
                    return await resp.json()
                else:
                    text = await resp.text()
                    logger.error(f"NP POST {endpoint} error {resp.status}: {text[:300]}")
    except Exception as e:
        logger.error(f"NP POST {endpoint} exception: {e}")
    return None


async def get_np_status() -> bool:
    """Verificar que la API key es valida."""
    data = await _api_get("/status")
    return data is not None


# ═════════════════════════════════════════════════════════════
#  CREAR INVOICE (POST /v1/invoice) — multi-crypto link
# ═════════════════════════════════════════════════════════════

async def create_invoice(user_id: int, days: int, lang: str = 'es') -> Optional[Dict]:
    """Crear una invoice via POST /v1/invoice.

    Retorna dict con:
      - invoice_id
      - invoice_url (link multi-crypto)
      - order_id
      - price_amount
      - plan_label

    El usuario paga a traves del invoice_url y elige su cripto.
    La confirmacion llega via IPN webhook.
    """
    plan = VIP_PLANS.get(days)
    if not plan:
        logger.error(f"Plan invalido: {days} dias")
        return None

    price_usd = plan["price"]
    order_id = f"HJ-{user_id}-{days}d-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    payload = {
        "price_amount": price_usd,
        "price_currency": "usd",
        "order_id": order_id,
        "order_description": f"HJ ULP VIP - {plan['label']}",
        "ipn_callback_url": config.NOWPAYMENTS_IPN_URL,
    }

    data = await _api_post("/invoice", payload)
    if not data or "id" not in data or "invoice_url" not in data:
        logger.error(f"Error creando invoice para {user_id}: {data}")
        return None

    invoice_id = str(data["id"])
    invoice_url = data["invoice_url"]

    logger.info(
        f"Invoice creado: id={invoice_id} | user={user_id} | {plan['label']} | "
        f"${price_usd} | url={invoice_url[:50]}..."
    )

    # Guardar en DB (invoice_id en columna invoice_id)
    try:
        db.create_payment(
            user_id=user_id,
            invoice_id=invoice_id,
            order_id=order_id,
            days=days,
            amount_usd=price_usd,
            status="pending",
            lang=lang
        )
        logger.info(f"Invoice {invoice_id} guardado en DB")
    except Exception as db_err:
        logger.error(f"CRITICO: Invoice {invoice_id} NO se guardo en DB: {db_err}")

    return {
        "invoice_id": invoice_id,
        "invoice_url": invoice_url,
        "order_id": order_id,
        "price_amount": price_usd,
        "plan_label": plan["label"],
    }


# ═════════════════════════════════════════════════════════════
#  VERIFICAR ESTADO (GET /v1/payment/{id}) — fallback polling
# ═════════════════════════════════════════════════════════════

async def get_payment_status(payment_id: str) -> Optional[str]:
    """Obtener estado de un pago via GET /v1/payment/{id}.

    Retorna:
      - status string (lowercase)
      - 'not_found' si 404
      - None si error de red
    """
    url = f"{NP_API_BASE}/payment/{payment_id}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=NP_HEADERS,
                                  timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    status = _extract_status(data)
                    if status:
                        logger.debug(f"Payment {payment_id}: status='{status}'")
                        return status
                    else:
                        logger.error(
                            f"Payment {payment_id}: sin campo status! "
                            f"Keys: {list(data.keys())}"
                        )
                        return None
                elif resp.status == 404:
                    logger.warning(f"Payment {payment_id}: 404 not found")
                    return "not_found"
                else:
                    text = await resp.text()
                    logger.error(f"Payment {payment_id}: error {resp.status}: {text[:200]}")
                    return None
    except Exception as e:
        logger.error(f"Payment {payment_id}: exception: {e}")
        return None


def _extract_status(data: dict) -> str:
    """Extraer status del response de NOWPayments."""
    for field in ("status", "payment_status"):
        val = data.get(field)
        if val and isinstance(val, str) and val.strip():
            return val.strip().lower()
    return ""


# ═════════════════════════════════════════════════════════════
#  PARSE ORDER_ID — extrae user_id y dias del order_id
# ═════════════════════════════════════════════════════════════

def parse_order_id(order_id: str):
    """Parsear order_id formato: HJ-{user_id}-{days}d-{timestamp}

    Retorna (user_id, days) o (None, None) si no se puede parsear.
    """
    if not order_id or not order_id.startswith("HJ-"):
        return None, None
    parts = order_id.split("-")
    if len(parts) >= 3:
        try:
            user_id = int(parts[1])
            days = int(parts[2].replace("d", ""))
            return user_id, days
        except (ValueError, IndexError):
            return None, None
    return None, None


# ═════════════════════════════════════════════════════════════
#  POLLING LOOP — fallback para pagos legacy cada 30s
# ═════════════════════════════════════════════════════════════

POLLING_INTERVAL = 30  # segundos
ORDER_EXPIRY_MINUTES = 120


async def payment_polling_loop():
    """Bucle de verificacion de pagos pendientes (fallback).

    Los invoices nuevos se confirman via IPN webhook.
    Este polling es fallback para pagos directos o si el webhook falla.
    """
    logger.info(f"NOWPayments polling iniciado (cada {POLLING_INTERVAL}s, fallback)")
    await asyncio.sleep(10)

    while True:
        try:
            await _check_pending_payments()
        except Exception as e:
            logger.error(f"Error en payment polling: {e}")
        await asyncio.sleep(POLLING_INTERVAL)


async def _check_pending_payments():
    """Verificar pagos pendientes via GET /v1/payment/{id}."""
    import state

    pending = db.get_pending_payments()
    if not pending:
        return

    logger.info(f"Payment polling: {len(pending)} pagos pendientes")
    now = datetime.now(timezone.utc)

    async def _process_one(payment: dict):
        record_id = payment["invoice_id"]
        user_id = payment["user_id"]
        days = payment["days"]
        lang = payment.get("lang", "es")

        # Intentar GET /v1/payment/{id} (funciona para pagos directos)
        try:
            status = await get_payment_status(record_id)
        except Exception as e:
            logger.error(f"Error consultando payment {record_id}: {e}")
            return

        if not status:
            return

        if status == "not_found":
            # Es un invoice ID (no payment ID), no se puede consultar por este endpoint
            # Se confirmara via IPN webhook
            return

        logger.info(f"Payment {record_id} | user={user_id} | status={status}")

        if status in SUCCESS_STATUSES:
            await _deliver_vip(state, user_id, days, record_id, lang, "polling")

        elif status in WAITING_STATUSES:
            try:
                created_str = payment.get("created_at", "")
                if created_str:
                    created = datetime.fromisoformat(created_str)
                    if created.tzinfo is None:
                        created = created.replace(tzinfo=timezone.utc)
                    elapsed_min = (now - created).total_seconds() / 60
                    if elapsed_min > ORDER_EXPIRY_MINUTES:
                        db.update_payment_status(record_id, "expired")
                        logger.info(
                            f"Payment {record_id} expirada: {elapsed_min:.0f}min "
                            f"user={user_id}"
                        )
            except Exception as e:
                logger.warning(f"Error verificando expiracion de {record_id}: {e}")

        elif status in FAIL_STATUSES:
            db.update_payment_status(record_id, status)
            logger.info(f"Payment {record_id} marcada como {status}")

        else:
            logger.warning(f"Payment {record_id}: status desconocido '{status}'")

    results = await asyncio.gather(*[_process_one(p) for p in pending], return_exceptions=True)
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Error inesperado en polling (payment #{i}): {result}")


async def _deliver_vip(state_module, user_id: int, days: int, record_id: str,
                     lang: str, source: str = "unknown"):
    """Entregar VIP y notificar al usuario."""
    try:
        db.set_role(user_id, "VIP", days)
        db.update_payment_status(record_id, "delivered")

        logger.info(
            f"VIP ENTREGADO via {source}: user={user_id} | {days}d | record={record_id}"
        )

        # Notificar al usuario
        try:
            from ui import UI, Keyboards
            from roles import get_user_role

            role = get_user_role(user_id)
            await state_module.bot.send_message(
                user_id,
                UI.text("pay_success", lang, days),
                buttons=Keyboards.main(role, lang, False),
                parse_mode='md'
            )
            logger.info(f"Notificacion de pago enviada a {user_id}")
        except Exception as e:
            logger.error(f"Error notificando pago a {user_id}: {e}")

    except Exception as e:
        logger.error(
            f"ERROR CRITICO entregando VIP user={user_id} record={record_id}: {e}"
        )
