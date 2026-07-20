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
        "price_currency": "usd",
        "order_id": order_id,
        "order_description": f"HJ ULP VIP - {plan['label']}",
        "ipn_callback_url": "https://google.com"
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
    """Obtener estado de una invoice. Retorna el status string, 'not_found' si 404, o None."""
    url = f"{NP_API_BASE}/invoice/{invoice_id}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=NP_HEADERS, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("status")
                elif resp.status == 404:
                    logger.warning(f"Invoice {invoice_id} no encontrada (404) — se descarta")
                    return "not_found"
                else:
                    text = await resp.text()
                    logger.error(f"NOWPayments invoice {invoice_id} error {resp.status}: {text[:200]}")
    except Exception as e:
        logger.error(f"NOWPayments invoice {invoice_id} exception: {e}")
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


# Tiempo maximo antes de expirar una orden pendiente (30 minutos)
ORDER_EXPIRY_MINUTES = 30


async def _check_pending_payments():
    """Verificar todos los pagos pendientes y entregar VIP a los confirmados.

    - Si una orden tiene mas de ORDER_EXPIRY_MINUTES, se marca como expired localmente.
    - Si NOWPayments devuelve 404, se descarta la orden silenciosamente.
    - Cada consulta es independiente (try/except por pago) para no bloquear las demas.
    - Las consultas corren en paralelo con asyncio.gather.
    """
    import state

    pending = db.get_pending_payments()
    if not pending:
        return

    now = datetime.now(timezone.utc)

    async def _process_one(payment: dict):
        invoice_id = payment["invoice_id"]
        user_id = payment["user_id"]
        days = payment["days"]
        lang = payment.get("lang", "es")

        # ── 1) Expiracion por tiempo ──
        try:
            created_str = payment.get("created_at", "")
            if created_str:
                created = datetime.fromisoformat(created_str)
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                if (now - created).total_seconds() > ORDER_EXPIRY_MINUTES * 60:
                    db.update_payment_status(invoice_id, "expired")
                    logger.info(f"Payment {invoice_id} expirada por tiempo (>{ORDER_EXPIRY_MINUTES}min) user={user_id}")
                    return
        except Exception as e:
            logger.warning(f"Error verificando expiracion de {invoice_id}: {e}")

        # ── 2) Consultar estado a NOWPayments ──
        try:
            status = await get_invoice_status(invoice_id)
        except Exception as e:
            logger.error(f"Error consultando invoice {invoice_id}: {e}")
            return

        if not status or status == "not_found":
            # 404 o sin respuesta: descartar silenciosamente
            if status == "not_found":
                db.update_payment_status(invoice_id, "expired")
            return

        logger.info(f"Payment {invoice_id} status: {status} (user={user_id})")

        # Estados intermedios: no hacer nada, esperar siguiente ciclo
        if status in ("waiting", "confirming", "sending"):
            logger.debug(f"Payment {invoice_id} en estado intermedio: {status}, esperando...")
            return

        if status in ("paid", "confirmed", "finished", "partially_paid"):
            # Entregar VIP (partially_paid se incluye porque NOWPayments lo usa
            # cuando el monto crypto difiere ligeramente por conversion/tarifas,
            # pero el equivalente fiat cubre el precio. El cliente ya pago.)
            if status == "partially_paid":
                logger.warning(
                    f"VIP entregado por partially_paid: user={user_id} | {days} dias | "
                    f"invoice={invoice_id} — revisar si el monto fiat cubre el precio"
                )
            db.set_role(user_id, "VIP", days)
            db.update_payment_status(invoice_id, "delivered")

            logger.info(f"VIP ENTREGADO: user={user_id} | {days} dias | invoice={invoice_id} | np_status={status}")

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

        elif status in ("expired", "failed", "refunded"):
            db.update_payment_status(invoice_id, status)
            logger.info(f"Payment {invoice_id} marcado como {status}")

    # Ejecutar todas las consultas en paralelo (no bloqueante)
    await asyncio.gather(*[_process_one(p) for p in pending], return_exceptions=True)