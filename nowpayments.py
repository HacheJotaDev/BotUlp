"""
═══════════════════════════════════════════════════════════════
  HJ ULP EXTRACTOR BOT — NOWPayments Integration Module v2
═══════════════════════════════════════════════════════════════
  • Usa POST /v1/payment (NO /v1/invoice)
  • El payment_id retornado es el mismo que usa GET /v1/payment/{id}
  • Polling cada 25s con GET /v1/payment/{payment_id}
  • Entrega automatica VIP al confirmar pago
  • Soporte USDT (Arbitrum One / ERC20)
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

# Moneda de pago
PAY_CURRENCY = "USDTERC20"

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
#  CREAR PAGO (POST /v1/payment)
# ═════════════════════════════════════════════════════════════

async def create_payment(user_id: int, days: int, lang: str = 'es') -> Optional[Dict]:
    """Crear un pago via POST /v1/payment.

    Retorna dict con:
      - id (payment_id)
      - pay_address (direccion de deposito)
      - pay_amount (monto en cripto)
      - price_amount (monto en USD)
      - order_id

    El payment_id retornado se usa directamente con GET /v1/payment/{id}.
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
        "pay_currency": PAY_CURRENCY,
        "order_id": order_id,
        "order_description": f"HJ ULP VIP - {plan['label']}",
        "ipn_callback_url": "https://google.com"
    }

    data = await _api_post("/payment", payload)
    if not data or "id" not in data:
        logger.error(f"Error creando payment para {user_id}: {data}")
        return None

    payment_id = str(data["id"])
    pay_address = data.get("pay_address", "")
    pay_amount = data.get("pay_amount", 0)

    logger.info(
        f"Payment creado: id={payment_id} | user={user_id} | {plan['label']} | "
        f"${price_usd} -> {pay_amount} {PAY_CURRENCY} | addr={pay_address[:20]}..."
    )

    # Guardar en DB
    try:
        db.create_payment(
            user_id=user_id,
            invoice_id=payment_id,
            order_id=order_id,
            days=days,
            amount_usd=price_usd,
            status="pending",
            lang=lang
        )
        logger.info(f"Payment {payment_id} guardado en DB")
    except Exception as db_err:
        logger.error(f"CRITICO: Payment {payment_id} NO se guardo en DB: {db_err}")

    return data


# ═════════════════════════════════════════════════════════════
#  VERIFICAR ESTADO (GET /v1/payment/{id})
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
#  POLLING LOOP — verifica pagos pendientes cada 25s
# ═════════════════════════════════════════════════════════════

POLLING_INTERVAL = 25  # segundos
ORDER_EXPIRY_MINUTES = 120


async def payment_polling_loop():
    """Bucle principal que verifica pagos pendientes."""
    logger.info(f"NOWPayments polling iniciado (cada {POLLING_INTERVAL}s)")
    await asyncio.sleep(10)  # Esperar a que el bot este listo

    while True:
        try:
            await _check_pending_payments()
        except Exception as e:
            logger.error(f"Error en payment polling: {e}")
        await asyncio.sleep(POLLING_INTERVAL)


async def _check_pending_payments():
    """Verificar todos los pagos pendientes y entregar VIP a los confirmados."""
    import state

    pending = db.get_pending_payments()
    if not pending:
        return

    logger.info(f"Payment polling: {len(pending)} pagos pendientes")
    now = datetime.now(timezone.utc)

    async def _process_one(payment: dict):
        payment_id = payment["invoice_id"]  # invoice_id columna guarda el payment_id
        user_id = payment["user_id"]
        days = payment["days"]
        lang = payment.get("lang", "es")

        # 1) Consultar estado a NOWPayments
        try:
            status = await get_payment_status(payment_id)
        except Exception as e:
            logger.error(f"Error consultando payment {payment_id}: {e}")
            return

        if not status:
            return  # Error de red, reintentar en proximo ciclo

        if status == "not_found":
            logger.warning(f"Payment {payment_id} not found en API")
            return

        logger.info(f"Payment {payment_id} | user={user_id} | status={status}")

        # 2) Estado exitoso: entregar VIP
        if status in SUCCESS_STATUSES:
            try:
                db.set_role(user_id, "VIP", days)
                db.update_payment_status(payment_id, "delivered")

                logger.info(
                    f"VIP ENTREGADO via polling: user={user_id} | {days}d | "
                    f"payment={payment_id} | status={status}"
                )

                # Notificar al usuario
                try:
                    from ui import UI, Keyboards
                    from roles import get_user_role

                    role = get_user_role(user_id)
                    await state.bot.send_message(
                        user_id,
                        UI.text("pay_success", lang, days),
                        buttons=Keyboards.main(role, lang, False),
                        parse_mode='md'
                    )
                    logger.info(f"Notificacion de pago enviada a {user_id}")
                except Exception as e:
                    logger.error(f"Error notificando pago a {user_id}: {e}")

            except Exception as e:
                logger.error(f"ERROR CRITICO entregando VIP user={user_id} payment={payment_id}: {e}")

        # 3) Estados intermedios: verificar expiracion
        elif status in WAITING_STATUSES:
            try:
                created_str = payment.get("created_at", "")
                if created_str:
                    created = datetime.fromisoformat(created_str)
                    if created.tzinfo is None:
                        created = created.replace(tzinfo=timezone.utc)
                    elapsed_min = (now - created).total_seconds() / 60
                    if elapsed_min > ORDER_EXPIRY_MINUTES:
                        db.update_payment_status(payment_id, "expired")
                        logger.info(
                            f"Payment {payment_id} expirada: {elapsed_min:.0f}min "
                            f"(status={status}) user={user_id}"
                        )
            except Exception as e:
                logger.warning(f"Error verificando expiracion de {payment_id}: {e}")

        # 4) Estados fallidos
        elif status in FAIL_STATUSES:
            db.update_payment_status(payment_id, status)
            logger.info(f"Payment {payment_id} marcada como {status}")

        else:
            logger.warning(f"Payment {payment_id}: status desconocido '{status}'")

    # Ejecutar todas las consultas en paralelo
    results = await asyncio.gather(*[_process_one(p) for p in pending], return_exceptions=True)

    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Error inesperado en polling (payment #{i}): {result}")
