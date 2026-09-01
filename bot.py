"""
═══════════════════════════════════════════════════════════════
  HJ ULP EXTRACTOR BOT — PRO EDITION v4.0 · Obsidian
═══════════════════════════════════════════════════════════════
  • Motor de búsqueda paralelo con mmap ultra-rápido
  • Descarga de archivos hasta 4GB con streaming + progreso
  • Sistema de roles: FREE / VIP / SELLER / ADMIN
  • Interfaz premium con diseño Obsidian
  • Sistema multi-idioma (ES / EN / PT)
  • Base de datos SQLite thread-safe con WAL + caché de usuarios
  • Auto-limpieza de archivos expirados
  • Búsqueda gratis para nuevos usuarios (1 búsqueda)
  • /updateBot: actualización remota desde Telegram
  • Pago automático multi-cripto (NOWPayments + IPN)
  • Shutdown elegante (SIGTERM/SIGINT) sin perder datos
═══════════════════════════════════════════════════════════════
"""

import asyncio
import signal

from config import config
from logger_setup import logger
from handlers import register_handlers
from download import (
    _auto_dl_worker, realtime_listener, mover_y_limpiar_archivos
)

# ═════════════════════════════════════════════════════════════
# INICIALIZACION
# ═════════════════════════════════════════════════════════════

from telethon import TelegramClient, events

# Crear clientes
bot_client = TelegramClient(
    config.BOT_SESSION, config.API_ID, config.API_HASH,
    connection_retries=15, retry_delay=3,
    auto_reconnect=True, timeout=60,
    flood_sleep_threshold=600
)

userbot_client = TelegramClient(
    config.USER_SESSION, config.API_ID, config.API_HASH,
    connection_retries=15, retry_delay=3,
    auto_reconnect=True, timeout=120,
    flood_sleep_threshold=600,
    request_retries=5
)


def _print_banner():
    """Banner de arranque elegante en consola."""
    v = config.VERSION
    logger.info("╔══════════════════════════════════════════════╗")
    logger.info("║   ✦ HJ ULP PRO — Obsidian Edition ✦          ║")
    logger.info(f"║   Versión {v} — Professional                  ║")
    logger.info("╚══════════════════════════════════════════════╝")


async def main():
    """Punto de entrada principal del bot."""
    import time as _time
    import state

    _print_banner()
    logger.info(f"Iniciando HJ ULP PRO v{config.VERSION}...")

    # Iniciar clientes
    await bot_client.start(bot_token=config.BOT_TOKEN)
    await userbot_client.start()

    # Asignar referencias globales (DESPUES de start, ANTES de handlers)
    state.bot = bot_client
    state.userbot = userbot_client
    state.START_TIME = _time.time()

    # Inicializar cola de auto-descarga
    state.auto_dl_queue = asyncio.Queue()

    # Cargar grupos permitidos desde la base de datos
    from database import db as _db
    state.allowed_groups = set(_db.get_allowed_groups())
    logger.info(f"Grupos permitidos cargados: {len(state.allowed_groups)}")

    # Registrar handlers
    register_handlers(bot_client)

    # Registrar listener de archivos en el userbot
    userbot_client.add_event_handler(
        realtime_listener,
        events.NewMessage(func=lambda e: e.document is not None)
    )

    # Iniciar worker de auto-descarga
    state.auto_dl_task = asyncio.create_task(_auto_dl_worker())

    # Iniciar limpieza periodica
    async def cleanup_loop():
        while True:
            try:
                await mover_y_limpiar_archivos()
                cleaned = _db.cleanup_expired_vips()
                if cleaned > 0:
                    logger.info(f"Limpieza VIP: {cleaned} usuarios expirados removidos")
            except Exception as e:
                logger.error(f"Error en limpieza: {e}")
            await asyncio.sleep(3600)  # Cada hora

    state.cleanup_task = asyncio.create_task(cleanup_loop())

    # Iniciar polling de pagos NOWPayments (fallback)
    from nowpayments import payment_polling_loop
    state.payment_polling_task = asyncio.create_task(payment_polling_loop())
    logger.info("NOWPayments payment polling iniciado (fallback)")

    # Iniciar servidor webhook IPN para auto-delivery
    try:
        from webhook_server import start_webhook_server
        state.webhook_runner = await start_webhook_server(config.NOWPAYMENTS_WEBHOOK_PORT)
    except Exception as e:
        logger.warning(f"Webhook IPN no pudo iniciar: {e}")

    # Info del bot
    me = await bot_client.get_me()
    user_me = await userbot_client.get_me()
    logger.info(f"Bot: @{me.username} (ID: {me.id})")
    logger.info(f"Userbot: {user_me.first_name} (ID: {user_me.id})")
    logger.info(f"HJ ULP PRO v{config.VERSION} — ACTIVO ✓")

    # ── Shutdown elegante (SIGTERM/SIGINT) ──────────────────
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _request_stop():
        logger.info("Señal de apagado recibida — cerrando ordenadamente...")
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _request_stop)
        except NotImplementedError:
            pass  # Windows

    disconnected = asyncio.ensure_future(bot_client.run_until_disconnected())
    stop_task = asyncio.ensure_future(stop_event.wait())

    done, pending = await asyncio.wait(
        {disconnected, stop_task}, return_when=asyncio.FIRST_COMPLETED
    )

    # ── Limpieza ordenada ───────────────────────────────────
    logger.info("Desconectando clientes...")
    for task in (disconnected, stop_task):
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass

    for attr in ("auto_dl_task", "cleanup_task", "payment_polling_task"):
        task = getattr(state, attr, None)
        if task:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

    runner = getattr(state, "webhook_runner", None)
    if runner:
        try:
            await runner.cleanup()
        except Exception:
            pass

    try:
        await userbot_client.disconnect()
    except Exception:
        pass
    try:
        await bot_client.disconnect()
    except Exception:
        pass

    try:
        from database import db
        db.close()
    except Exception:
        pass

    logger.info(f"HJ ULP PRO v{config.VERSION} — apagado correctamente ✓")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot detenido por usuario")
    except SystemExit:
        logger.info("Bot reiniciado via /updateBot")
    except Exception as e:
        logger.critical(f"Error fatal: {e}")
        import traceback
        traceback.print_exc()
