"""
═══════════════════════════════════════════════════════════════
  HJ ULP EXTRACTOR BOT — Notificaciones de Venta VIP v4.3.1
═══════════════════════════════════════════════════════════════
  Mensaje privado elegante a los ADMINISTRADORES configurados
  (config.ADMIN_IDS) cada vez que una venta VIP real se confirma
  y la membresía queda efectivamente activada.

  CUÁNDO SE NOTIFICA (y cuándo NO):
  • SÍ — pago verificado vía NOWPayments (IPN webhook, polling de
    fallback o verificación manual «Ya pagué») con entrega del VIP
    ya ejecutada. La venta existe: estado 'delivered' en la DB.
  • NO — activaciones gratuitas o manuales: promo 100 %, canje de
    keys, /vip de administrador, /keygen. Nunca se presentan como
    ventas cobradas.
  • NO — doble confirmación del proveedor: la idempotencia vive en
    nowpayments._deliver_vip (claim atómico en la DB por invoice_id);
    el notifier solo se invoca desde el lado ganador del claim.

  DATOS 100 % REALES (nada se inventa):
  • Cliente: entidad Telegram viva (nombre, @username o «Sin
    username», ID). Fallback honesto si Telegram no responde.
  • Membresía: días y vencimiento LEÍDOS de la DB DESPUÉS de la
    activación (reflejan la renovación real).
  • Pago: importe y moneda del registro de la DB; monto cripto
    efectivamente pagado solo si viene verificado en el IPN.
  • Método: NOWPayments (único proveedor integrado).
  • Transacción: invoice_id interno (no sensible).

  PRIVACIDAD: sin tokens, claves API, datos de tarjeta ni secretos
  de pasarela. Estas notificaciones NUNCA se registran en el
  sistema de limpieza (auto_clean) — son registro contable.
═══════════════════════════════════════════════════════════════
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional

from config import config
from logger_setup import logger

# Emojis del diseño — todos con ID premium registrado (86 catálogo v4.2.32).
# Verificado: 💎 ✅ 👤 👑 💰 🎉 📅 🆔 🪙 🔗 ⚡ 📊 🔥 🚀 🌟 ⏳
_PLAN_EMOJIS = {1: "⚡", 3: "📊", 7: "🔥", 15: "🚀", 30: "💎"}

# Fuentes que representan una venta COBRADA real (NOWPayments).
# "promo-100" (regalo), canjes y /vip manual quedan fuera por diseño.
PAID_SOURCES = ("IPN", "polling", "manual-check")

# Reintentos de entrega controlados: 2 intentos por admin, sin duplicar
# la venta (la idempotencia ya quedó garantizada ANTES de notificar).
_DELIVERY_ATTEMPTS = 2
_RETRY_DELAY = 5.0


def _fmt_dt_utc(iso_str: str) -> str:
    """'2026-11-07T15:30:00+00:00' → '07/11/2026 15:30 UTC' (o '—')."""
    try:
        dt = datetime.fromisoformat(str(iso_str))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.strftime("%d/%m/%Y %H:%M") + " UTC"
    except (TypeError, ValueError):
        return "—"


def _fmt_amount(v) -> str:
    """$10 · $10.50 — sin ceros falsos, con 2 decimales si hace falta."""
    try:
        s = f"{float(v):.2f}"
        return s[:-3] if s.endswith(".00") else s
    except (TypeError, ValueError):
        return "—"


def build_sale_notification(
    user_id: int,
    days: int,
    amount_usd: float,
    record_id: str,
    expiry_iso: Optional[str],
    activation_iso: Optional[str] = None,
    first_name: Optional[str] = None,
    username: Optional[str] = None,
    paid_crypto: Optional[str] = None,
    paid_crypto_currency: Optional[str] = None,
    order_id: Optional[str] = None,
) -> str:
    """Construir la tarjeta de venta VIP (contenido íntegro y verificable).

    Todos los campos son opcionales-resilientes: lo que no se pudo
    verificar se muestra como «—» o «Sin username», jamás inventado.
    """
    plan_emoji = _PLAN_EMOJIS.get(days, "💎")
    dias_txt = f"{days} día" if days == 1 else f"{days} días"
    activacion = _fmt_dt_utc(activation_iso) if activation_iso else "—"
    vencimiento = _fmt_dt_utc(expiry_iso) if expiry_iso else "—"

    nombre = (first_name or "").strip() or "No disponible"
    usuario = f"@{username.lstrip('@')}" if username else "Sin username"

    # Bloque de pago — moneda USD del invoice (price_currency real);
    # el monto cripto SOLO si el IPN lo trajo verificado.
    pago_lineas = [
        f"├─ 💲 Importe: **${_fmt_amount(amount_usd)} USD**",
    ]
    if paid_crypto and paid_crypto_currency:
        try:
            crypto_txt = f"{float(paid_crypto):g} {paid_crypto_currency}"
        except (TypeError, ValueError):
            crypto_txt = f"{paid_crypto} {paid_crypto_currency}"
        pago_lineas.append(f"├─ 🪙 Pagado (verificado): `{crypto_txt}`")
    pago_lineas.append("├─ 💳 Método: **NOWPayments · Cripto**")
    pago_lineas.append("└─ ✅ Estado: **Confirmado**")

    tx_line = f"🔗 Transacción: `{record_id}`" if record_id else ""

    # Diseño sobrio tipo tarjeta ✦ del sistema UI/UX v4.3.0
    # (separadores ━ solo en cabecera/pie, sin adornos excesivos)
    text = (
        "╭━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╮\n"
        "┃ 💎 HJ BOT · NUEVA VENTA VIP\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯\n"
        "\n"
        "✅ Membresía activada y verificada\n"
        "\n"
        "👤 **CLIENTE**\n"
        f"├─ Nombre: {nombre}\n"
        f"├─ Usuario: {usuario}\n"
        f"└─ 🆔 ID: `{user_id}`\n"
        "\n"
        "👑 **MEMBRESÍA**\n"
        f"├─ Plan: {plan_emoji} VIP · {dias_txt}\n"
        f"├─ 📅 Activación: {activacion}\n"
        f"└─ ⏳ Vence: {vencimiento}\n"
        "\n"
        "💰 **PAGO**\n"
        + "\n".join(pago_lineas) + "\n"
        "\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🎉 Venta registrada correctamente"
    )
    if tx_line:
        text += f"\n{tx_line}"
    if order_id:
        text += f"\n📋 Orden: `{order_id}`"
    return text


async def _resolve_user(user_id: int):
    """Entidad Telegram del cliente (nombre/@username) — best effort.

    Si Telegram no responde (usuario bloqueado, red caída), la venta
    sigue notificándose con ID y placeholders honestos.
    """
    try:
        import state
        if state.bot is None:
            return None, None
        entity = await asyncio.wait_for(state.bot.get_entity(user_id), timeout=6)
        return (
            getattr(entity, "first_name", None),
            getattr(entity, "username", None),
        )
    except Exception:
        return None, None


async def _send_to_admin(admin_id: int, text: str) -> bool:
    """Entregar la notificación a UN administrador.

    Maneja el caso «admin nunca inició chat con el bot» (Telegram
    lo rechaza con Forbidden) sin romper nada: se registra y se
    continúa con los demás admins.
    """
    import state
    if state.bot is None:
        logger.error("VIP_NOTIFIER: state.bot no disponible — notificación no enviada")
        return False

    for attempt in range(1, _DELIVERY_ATTEMPTS + 1):
        try:
            await state.bot.send_message(admin_id, text, parse_mode='md', link_preview=False)
            return True
        except asyncio.CancelledError:
            return False
        except Exception as exc:
            name = type(exc).__name__
            if attempt < _DELIVERY_ATTEMPTS:
                logger.warning(
                    f"VIP_NOTIFIER: reintento {attempt + 1}/{_DELIVERY_ATTEMPTS} "
                    f"para admin {admin_id} ({name}: {str(exc)[:120]})"
                )
                await asyncio.sleep(_RETRY_DELAY)
            else:
                # Admin sin PM iniciado (Forbidden), bloqueado o red caída:
                # la venta YA está procesada — solo queda el registro.
                logger.error(
                    f"VIP_NOTIFIER: no se pudo notificar al admin {admin_id} "
                    f"({name}: {str(exc)[:150]}) — la venta está registrada en DB"
                )
    return False


async def notify_vip_sale(
    user_id: int,
    days: int,
    amount_usd: float,
    record_id: str,
    expiry_iso: Optional[str],
    activation_iso: Optional[str] = None,
    ipn_data: Optional[dict] = None,
    order_id: Optional[str] = None,
) -> int:
    """Notificar una venta VIP real a todos los administradores.

    Se invoca SOLO tras: pago verificado por NOWPayments + claim
    idempotente ganado + membresía activada en DB. Retorna la
    cantidad de administradores notificados.
    """
    first_name, username = await _resolve_user(user_id)

    paid_crypto = None
    paid_crypto_cur = None
    if ipn_data:
        paid_crypto = ipn_data.get("actually_paid") or ipn_data.get("pay_amount")
        paid_crypto_cur = (ipn_data.get("actually_paid_currency")
                           or ipn_data.get("pay_currency"))
        order_id = order_id or ipn_data.get("order_id")

    text = build_sale_notification(
        user_id=user_id, days=days, amount_usd=amount_usd,
        record_id=record_id, expiry_iso=expiry_iso,
        activation_iso=activation_iso, first_name=first_name,
        username=username, paid_crypto=paid_crypto,
        paid_crypto_currency=paid_crypto_cur, order_id=order_id,
    )

    delivered = 0
    for admin_id in config.ADMIN_IDS:
        ok = await _send_to_admin(int(admin_id), text)
        delivered += 1 if ok else 0
    logger.info(
        f"VIP_NOTIFIER: venta user={user_id} record={record_id} notificada a "
        f"{delivered}/{len(config.ADMIN_IDS)} admin(s)"
    )
    return delivered


def spawn_vip_sale_notification(**kwargs) -> Optional[asyncio.Task]:
    """Lanzar la notificación como tarea independiente (fire-and-forget).

    La venta ya está procesada: si la notificación falla, se registra
    el problema y NO se re-procesa nada (sin duplicar ventas).
    """
    try:
        return asyncio.create_task(notify_vip_sale(**kwargs))
    except RuntimeError:
        # Sin loop (tests) — ejecución síncrona imposible, se registra
        logger.error("VIP_NOTIFIER: sin event loop — notificación no lanzada")
        return None
