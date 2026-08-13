"""
═══════════════════════════════════════════════════════════════
  HJ ULP EXTRACTOR BOT — NOWPayments Integration Module
═══════════════════════════════════════════════════════════════
  • Creacion de pagos via API REST
  • Polling de estado (sin webhooks)
  • Entrega automatica VIP al confirmar pago
  • Soporte USDT (Arbitrum One)
  • FIX: multiples campos de status + logging completo
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

# Status que indican pago exitoso
SUCCESS_STATUSES = ("paid", "confirmed", "finished", "partially_paid")

# Status que indican que hay que esperar
WAITING_STATUSES = ("waiting", "confirming", "sending", "pending")

# Status que indican fallo
FAIL_STATUSES = ("expired", "failed", "refunded", "reverted")


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
                    logger.error(f"NOWPayments GET {endpoint} error {resp.status}: {text[:300]}")
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
                    logger.error(f"NOWPayments POST {endpoint} error {resp.status}: {text[:300]}")
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

    invoice_id = str(data["id"])

    # Guardar en DB
    db.create_payment(
        user_id=user_id,
        invoice_id=invoice_id,
        order_id=order_id,
        days=days,
        amount_usd=price_usd,
        status="pending",
        lang=lang
    )

    logger.info(f"Invoice creada: id={invoice_id} | user={user_id} | {plan['label']} | ${price_usd}")
    return data


async def get_invoice_status(invoice_id: str) -> Optional[str]:
    """Obtener estado de una invoice.

    Retorna el status string, 'not_found' si 404, o None si error de red.

    FIX: Ahora revisa multiples campos posibles del response
    (status, payment_status, invoice_status) porque NOWPayments
    cambia el formato segun el tipo de pago (crypto2crypto, etc.)
    """
    url = f"{NP_API_BASE}/invoice/{invoice_id}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=NP_HEADERS, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()

                    # Log completo para debuggear
                    logger.debug(f"NOWPayments invoice {invoice_id} response: {str(data)[:500]}")

                    # Intentar multiples campos donde puede estar el status
                    status = None
                    for field in ("status", "payment_status", "invoice_status", "state"):
                        val = data.get(field)
                        if val and isinstance(val, str) and val.strip():
                            status = val.strip().lower()
                            break

                    if status:
                        logger.info(f"Invoice {invoice_id}: status='{status}' (field used: {field})")
                        return status
                    else:
                        # No se encontro ningun campo de status conocido
                        logger.error(
                            f"Invoice {invoice_id}: NO status field found in response! "
                            f"Keys: {list(data.keys())} | Full: {str(data)[:500]}"
                        )
                        return None

                elif resp.status == 404:
                    logger.warning(f"Invoice {invoice_id} no encontrada (404)")
                    return "not_found"
                else:
                    text = await resp.text()
                    logger.error(f"NOWPayments invoice {invoice_id} error {resp.status}: {text[:300]}")
    except Exception as e:
        logger.error(f"NOWPayments invoice {invoice_id} exception: {e}")
    return None


async def get_invoice_full(invoice_id: str) -> Optional[Dict]:
    """Obtener todos los datos de una invoice (para admin/debug)."""
    url = f"{NP_API_BASE}/invoice/{invoice_id}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=NP_HEADERS, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return await resp.json()
                elif resp.status == 404:
                    return {"error": "not_found"}
                else:
                    text = await resp.text()
                    return {"error": f"http_{resp.status}", "detail": text[:200]}
    except Exception as e:
        return {"error": "exception", "detail": str(e)[:200]}


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


# Tiempo maximo antes de expirar una orden que sigue pendiente en NOWPayments.
ORDER_EXPIRY_MINUTES = 120


async def _check_pending_payments():
    """Verificar todos los pagos pendientes y entregar VIP a los confirmados."""
    import state

    pending = db.get_pending_payments()
    if not pending:
        return

    logger.info(f"Payment polling: {len(pending)} pagos pendientes")
    now = datetime.now(timezone.utc)

    async def _process_one(payment: dict):
        invoice_id = payment["invoice_id"]
        user_id = payment["user_id"]
        days = payment["days"]
        lang = payment.get("lang", "es")

        # ── 1) Consultar estado a NOWPayments ──
        try:
            status = await get_invoice_status(invoice_id)
        except Exception as e:
            logger.error(f"Error consultando invoice {invoice_id}: {e}")
            return

        if not status or status == "not_found":
            if status == "not_found":
                db.update_payment_status(invoice_id, "expired")
                logger.info(f"Payment {invoice_id} marcada expired (404 not found)")
            return

        logger.info(f"Payment {invoice_id} | user={user_id} | np_status={status}")

        # ── 2) Estado exitoso: entregar VIP sin importar el tiempo ──
        if status in SUCCESS_STATUSES:
            try:
                if status == "partially_paid":
                    logger.warning(
                        f"VIP entregado por partially_paid: user={user_id} | {days}d | "
                        f"invoice={invoice_id}"
                    )

                db.set_role(user_id, "VIP", days)
                db.update_payment_status(invoice_id, "delivered")

                logger.info(
                    f"VIP ENTREGADO: user={user_id} | {days}d | "
                    f"invoice={invoice_id} | np_status={status}"
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
                logger.error(f"ERROR CRITICO entregando VIP user={user_id} invoice={invoice_id}: {e}")

        # ── 3) Estados intermedios: esperar siguiente ciclo ──
        elif status in WAITING_STATUSES:
            try:
                created_str = payment.get("created_at", "")
                if created_str:
                    created = datetime.fromisoformat(created_str)
                    if created.tzinfo is None:
                        created = created.replace(tzinfo=timezone.utc)
                    elapsed_min = (now - created).total_seconds() / 60
                    if elapsed_min > ORDER_EXPIRY_MINUTES:
                        db.update_payment_status(invoice_id, "expired")
                        logger.info(
                            f"Payment {invoice_id} expirada: {elapsed_min:.0f}min sin resolver "
                            f"(np_status={status}) user={user_id}"
                        )
            except Exception as e:
                logger.warning(f"Error verificando expiracion de {invoice_id}: {e}")

        # ── 4) Estados fallidos: marcar y salir ──
        elif status in FAIL_STATUSES:
            try:
                db.update_payment_status(invoice_id, status)
                logger.info(f"Payment {invoice_id} marcada como {status}")
            except Exception as e:
                logger.error(f"Error actualizando estado de {invoice_id}: {e}")

        else:
            # Status desconocido - logear para debug
            logger.warning(f"Payment {invoice_id}: status desconocido '{status}' para user={user_id}")

    # Ejecutar todas las consultas en paralelo
    results = await asyncio.gather(*[_process_one(p) for p in pending], return_exceptions=True)

    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Error inesperado en payment polling (payment #{i}): {result}")


def _parse_order_id(order_id: str) -> tuple:
    """Extraer user_id y dias del order_id formato HJ-{uid}-{days}d-..."""
    import re
    m = re.match(r'^HJ-(\d+)-(\d+)d-', order_id or '')
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None


async def manual_check_and_deliver(invoice_id: str) -> dict:
    """Verificar manualmente una invoice y entregar VIP si esta pagada.

    Usado por el admin via /fixpay.
    Soporta:
      - Buscar por invoice_id en DB
      - Buscar por order_id en DB
      - Si no esta en DB, consultar NOWPayments API directamente,
        extraer user_id del order_id y entregar VIP
    Retorna dict con resultado de la operacion.
    """
    import re
    from database import db as _db

    # ── 1) Buscar en DB por invoice_id ──
    with _db._lock:
        c = _db.conn.cursor()
        c.execute("SELECT * FROM payments WHERE invoice_id = ?", (invoice_id,))
        row = c.fetchone()

    # ── 2) Si no encontro, buscar por order_id ──
    if not row:
        with _db._lock:
            c = _db.conn.cursor()
            c.execute("SELECT * FROM payments WHERE order_id = ?", (invoice_id,))
            row = c.fetchone()

    # ── 3) Si esta en DB, procesar normalmente ──
    if row:
        payment = dict(row)
        user_id = payment["user_id"]
        days = payment["days"]
        current_status = payment["status"]
        actual_invoice_id = payment["invoice_id"]

        # Si ya fue entregada, no hacer nada
        if current_status == "delivered":
            return {"info": f"Invoice {actual_invoice_id} ya fue entregada a user {user_id}"}

        # Consultar NOWPayments con el invoice_id real
        np_data = await get_invoice_full(actual_invoice_id)
        if not np_data:
            return {"error": f"No se pudo consultar la API de NOWPayments"}
        if "error" in np_data:
            return {"error": f"Error de API: {np_data['error']} - {np_data.get('detail', '')}"}

        np_status = _extract_np_status(np_data)
        if not np_status:
            return {"error": f"No se pudo determinar el status", "api_response": {k: str(v)[:100] for k, v in np_data.items()}}

        if np_status in SUCCESS_STATUSES:
            return await _deliver_vip(_db, user_id, days, actual_invoice_id, payment.get("lang", "es"), np_status)
        elif np_status in WAITING_STATUSES:
            return {"info": f"Pago pendiente (status: {np_status}). Esperar.", "np_status": np_status}
        elif np_status in FAIL_STATUSES:
            _db.update_payment_status(actual_invoice_id, np_status)
            return {"info": f"Pago fallo (status: {np_status}).", "np_status": np_status}
        else:
            return {"warning": f"Status desconocido: {np_status}", "api_response": {k: str(v)[:100] for k, v in np_data.items()}}

    # ── 4) NO esta en DB: consultar NOWPayments directamente ──
    logger.warning(f"fixpay: {invoice_id} no encontrada en DB, consultando API directamente...")

    np_data = await get_invoice_full(invoice_id)
    if not np_data:
        return {"error": f"No se pudo consultar NOWPayments para {invoice_id}"}
    if "error" in np_data:
        return {"error": f"Error de API: {np_data['error']} - {np_data.get('detail', '')}"}

    np_status = _extract_np_status(np_data)
    if not np_status:
        return {"error": f"No se pudo determinar el status", "api_response": {k: str(v)[:100] for k, v in np_data.items()}}

    # Extraer order_id del response de NOWPayments
    np_order_id = np_data.get("order_id", "")
    np_amount = np_data.get("price_amount", 0)

    # Intentar extraer user_id y dias del order_id
    user_id, days = _parse_order_id(np_order_id)

    # Fallback: buscar user_id en la descripcion si no hay order_id
    if not user_id:
        # Tambien buscar en descripcion: "HJ ULP VIP - X Dias"
        desc = np_data.get("order_description", "")
        m = re.search(r'(\d+)\s*(?:Dia|Dias|Day|Days)', desc, re.IGNORECASE)
        if m:
            days = int(m.group(1))

    if not user_id or not days:
        return {
            "error": f"No se pudo extraer user_id/dias del order_id '{np_order_id}'. "
                   f"Usa /vip <user_id> manualmente.",
            "api_response": {
                "order_id": np_order_id,
                "status": np_status,
                "price_amount": np_amount
            }
        }

    if np_status not in SUCCESS_STATUSES:
        return {"info": f"Pago NO completado (status: {np_status}). No se entrega VIP.", "np_status": np_status}

    # Registrar en DB y entregar
    _db.create_payment(
        user_id=user_id,
        invoice_id=invoice_id,
        order_id=np_order_id,
        days=days,
        amount_usd=float(np_amount) if np_amount else 0,
        status="delivered",
        lang="es"
    )

    return await _deliver_vip(_db, user_id, days, invoice_id, "es", np_status)


def _extract_np_status(np_data: dict) -> str:
    """Extraer status del response de NOWPayments, revisando multiples campos."""
    for field in ("status", "payment_status", "invoice_status", "state"):
        val = np_data.get(field)
        if val and isinstance(val, str) and val.strip():
            return val.strip().lower()
    return ""


async def _deliver_vip(_db, user_id: int, days: int, invoice_id: str, lang: str, np_status: str) -> dict:
    """Entregar VIP, actualizar DB y notificar al usuario."""
    try:
        _db.set_role(user_id, "VIP", days)
        _db.update_payment_status(invoice_id, "delivered")

        import state
        from ui import UI, Keyboards
        from roles import get_user_role

        role = get_user_role(user_id)
        try:
            await state.bot.send_message(
                user_id,
                UI.text("pay_success", lang, days),
                buttons=Keyboards.main(role, lang, False),
                parse_mode='md'
            )
            logger.info(f"Notificacion de pago enviada a {user_id}")
        except Exception as e:
            logger.error(f"Error notificando pago a {user_id}: {e}")

        return {
            "success": True,
            "user_id": user_id,
            "days": days,
            "np_status": np_status,
            "message": f"VIP ({days}d) entregado a user {user_id} | invoice {invoice_id} | status: {np_status}"
        }
    except Exception as e:
        return {"error": f"Error entregando VIP: {e}"}
