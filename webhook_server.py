"""
═══════════════════════════════════════════════════════════════
  HJ ULP EXTRACTOR BOT — NOWPayments IPN Webhook Server
═══════════════════════════════════════════════════════════════
  • Recibe callbacks de NOWPayments cuando se confirma un pago
  • Verifica firma HMAC-SHA512
  • Entrega VIP automaticamente
  • Corre en puerto 9090 junto al bot
═══════════════════════════════════════════════════════════════
"""

import hmac
import hashlib
import json
from aiohttp import web

from config import config
from logger_setup import logger
from database import db
from nowpayments import parse_order_id, SUCCESS_STATUSES, FAIL_STATUSES


# ── Verificacion de firma IPN ──────────────────────────────

def verify_ipn_signature(payload_bytes: bytes, signature: str) -> bool:
    """Verificar firma HMAC-SHA512 del IPN callback.

    NOWPayments envia la firma en header 'x-nowpayments-sig'.
    Se calcula como HMAC-SHA512 del body crudo usando el IPN secret.
    """
    secret = config.NOWPAYMENTS_IPN_KEY
    if not secret or not signature:
        return False
    expected = hmac.new(
        secret.encode(),
        payload_bytes,
        hashlib.sha512
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


# ── IPN Handler ────────────────────────────────────────────

async def handle_ipn(request: web.Request) -> web.Response:
    """Manejar callback IPN de NOWPayments."""
    try:
        payload_bytes = await request.read()
        signature = request.headers.get("x-nowpayments-sig", "")

        # Verificar firma
        if not verify_ipn_signature(payload_bytes, signature):
            logger.warning("IPN: firma invalida (signature mismatch)")
            return web.json_response({"error": "invalid signature"}, status=400)

        if not payload_bytes:
            logger.warning("IPN: body vacio")
            return web.json_response({"error": "empty body"}, status=400)

        data = json.loads(payload_bytes)
        payment_status = data.get("payment_status", "").lower()
        order_id = data.get("order_id", "")
        invoice_id = str(data.get("invoice_id", ""))
        payment_id = str(data.get("payment_id", ""))
        ipn_type = data.get("ipn_type", "")

        logger.info(
            f"IPN recibido: type={ipn_type} status={payment_status} "
            f"order={order_id} invoice={invoice_id} payment={payment_id}"
        )

        # Extraer user_id y days del order_id
        user_id, days = parse_order_id(order_id)
        if not user_id or not days:
            logger.error(f"IPN: no se pudo parsear order_id: {order_id}")
            return web.json_response({"status": "ok"})

        # Pago confirmado: entregar VIP
        if payment_status in SUCCESS_STATUSES:
            import state
            from nowpayments import _deliver_vip

            record_id = invoice_id or payment_id
            await _deliver_vip(state, user_id, days, record_id, "es", "IPN")

        # Pago fallido/expirado: actualizar estado
        elif payment_status in FAIL_STATUSES:
            record_id = invoice_id or payment_id
            if record_id:
                db.update_payment_status(record_id, payment_status)
                logger.info(f"IPN: payment {record_id} marcado como {payment_status}")

        return web.json_response({"status": "ok"})

    except json.JSONDecodeError as e:
        logger.error(f"IPN: JSON invalido: {e}")
        return web.json_response({"error": "invalid json"}, status=400)
    except Exception as e:
        logger.error(f"IPN error: {e}", exc_info=True)
        return web.json_response({"status": "error"}, status=500)


# ── Health check ───────────────────────────────────────────

async def handle_health(request: web.Request) -> web.Response:
    """Endpoint de health check."""
    return web.json_response({"status": "ok", "service": "hj-ulp-ipn"})


# ── Iniciar servidor ───────────────────────────────────────

async def start_webhook_server(port: int = 9090) -> web.AppRunner:
    """Iniciar el servidor webhook IPN. Retorna el runner para cleanup."""
    app = web.Application()
    app.router.add_post("/ipn", handle_ipn)
    app.router.add_get("/health", handle_health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"IPN Webhook server en puerto {port} (ipn_callback_url activo)")
    return runner