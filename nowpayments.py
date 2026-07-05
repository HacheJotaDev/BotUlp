"""
═══════════════════════════════════════════════════════════════
  HJ ULP EXTRACTOR BOT — NOWPayments Integration Module
═══════════════════════════════════════════════════════════════
  • Creacion de pagos via API REST
  • Polling de estado (sin webhooks)
  • Entrega automatica VIP al confirmar pago
  • Soporte USDT (Arbitrum One)
═══════════════════════════════════════════════════════════════
"""

import asyncio
import aiohttp
from datetime import datetime, timezone
from typing import Optional, Dict, Any

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


# ═════════════════════════════════════════════════════════════
#  FUNCIONES API
# ═════════════════════════════════════════════════════════════

async def _api_get(endpoint: str, params: dict = None) -> Optional[Dict]:
    """GET request a la API de NOWPayments."""
    url = f"{NP_API_BASE}{endpoint}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=NP_HEADERS, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    text = await resp.text()
                    logger.error(f"NOWPayments GET {endpoint} error {resp.status}: {text[:200]}")
    except Exception as e:
        logger.error(f"NOWPayments GET {endpoint} exception: {e}")
    return None


async def _api_post(endpoint: str, payload: dict) -> Optional[Dict]:
    """POST request a la API de NOWPayments."""
    url = f"{NP_API_BASE}{endpoint}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=NP_HEADERS, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status in (200, 201):
                    return await resp.json()
                else:
                    text = await resp.text()
                    logger.error(f"NOWPayments POST {endpoint} error {resp.status}: {text[:200]}")
    except Exception as e:
        logger.error(f"NOWPayments POST {endpoint} exception: {e}")
    return None


async def get_np_status() -> bool:
    """Verificar que la API key es valida y la API esta operativa."""
    data = await _api_get("/status")
    return data is not None


async def get_minimum_price() -> float:
    """Obtener el monto minimo para USDT en Arbitrum."""
    data = await _api_get("/min-amount", {"currency_from": "USD", "currency_to": "USDTERC20"})
    if data and "minimum_amount" in data:
        try:
            return float(data["minimum_amount"])
        except (ValueError, TypeError):
            pass
    return 5.0  # fallback


async def get_estimated_price(usd_amount: float) -> float:
    """Estimar cuantos USDT se necesitan por el monto USD."""
    data = await _api_get("/estimate", {
        "amount": usd_amount,
        "currency_from": "USD",
        "currency_to": "USDTERC20"
    })
    if data and "estimated_amount" in data:
        try:
            return float(data["estimated_amount"])
        except (ValueError, TypeError):
            pass
    return usd_amount  # fallback 1:1


async def create_invoice(user_id: int, days: int, lang: str = 'es') -> Optional[Dict]:
    """Crear una factura de pago NOWPayments.

    Retorna dict con invoice info o None si falla.
    """
    plan = VIP_PLANS.get(days)
    if not plan:
        logger.error(f"Plan invalido: {days} dias")
        return None

    price_usd = plan["price"]
    order_id = f"HJ-{user_id}-{days}d-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    payload = {
        "price_amount": price_usd,
        "price_currency": "USD",
        "order_id": order_id,
        "order_description": f"HJ ULP VIP - {plan['label']}",
        "ipn_callback_url": "",
        "success_url": "",
        "cancel_url": "",
        " purchaser_email": "",
    }

    data = await _api_post("/invoice", payload)
    if not data or "id" not in data:
        logger.error(f"Error creando invoice para {user_id}: {data}")
        return None

    # Guardar en DB
    db.create_payment(
        user_id=user_id,
        invoice_id=str(data["id"]),
        order_id=order_id,
        days=days,
        amount_usd=price_usd,
        status="pending",
        lang=lang
    )

    logger.info(f"Invoice creada: {data['id']} | user={user_id} | {plan['label']} | ${price_usd}")
    return data


async def get_invoice_status(invoice_id: str) -> Optional[str]:
    """Obtener estado de una invoice. Retorna el status string o None."""
    data = await _api_get(f"/invoice/{invoice_id}")
    if data and "status" in data:
        return data["status"]
    return None


# ═════════════════════════════════════════════════════════════
#  POLLING LOOP
# ═════════════════════════════════════════════════════════════

async def payment_polling_loop():
    """Bucle principal que verifica pagos pendientes cada 30 segundos."""
    logger.info("NOWPayments polling iniciado (cada 30s)")

    await asyncio.sleep(10)  # Esperar a que el bot este listo

    while True:
        try:
            await _check_pending_payments()
        except Exception as e:
            logger.error(f"Error en payment polling: {e}")
        await asyncio.sleep(30)


async def _check_pending_payments():
    """Verificar todos los pagos pendientes y entregar VIP a los confirmados."""
    import state

    pending = db.get_pending_payments()
    if not pending:
        return

    for payment in pending:
        invoice_id = payment["invoice_id"]
        user_id = payment["user_id"]
        days = payment["days"]
        lang = payment.get("lang", "es")
        order_id = payment["order_id"]

        status = await get_invoice_status(invoice_id)
        if not status:
            continue

        logger.info(f"Payment {invoice_id} status: {status} (user={user_id})")

        if status == "paid" or status == "confirmed" or status == "finished":
            # Entregar VIP
            db.set_role(user_id, "VIP", days)
            db.update_payment_status(invoice_id, "delivered")

            logger.info(f"VIP ENTREGADO: user={user_id} | {days} dias | invoice={invoice_id}")

            # Notificar al usuario
            try:
                from ui import UI, Keyboards
                from roles import get_user_role

                role = get_user_role(user_id)
                await state.bot.send_message(
                    user_id,
                    UI.text("payment_success", lang, days),
                    buttons=Keyboards.main(role, lang, False),
                    parse_mode='md'
                )
            except Exception as e:
                logger.error(f"Error notificando pago a {user_id}: {e}")

        elif status == "expired" or status == "failed" or status == "refunded":
            db.update_payment_status(invoice_id, status)
            logger.info(f"Payment {invoice_id} marcado como {status}")