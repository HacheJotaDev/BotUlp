"""
═══════════════════════════════════════════════════════════════
  HJ ULP EXTRACTOR BOT — PRO EDITION v3.5
═══════════════════════════════════════════════════════════════
  • Motor de busqueda paralelo con mmap ultra-rapido
  • Descarga de archivos hasta 4GB con streaming + progreso
  • Sistema de roles: FREE / VIP / SELLER / ADMIN
  • Interfaz elegante con diseno 彡 Style
  • Sistema multi-idioma (ES / EN / PT)
  • Base de datos SQLite thread-safe con WAL mode
  • Auto-limpieza de archivos expirados
  • Busqueda gratis para nuevos usuarios (1 busqueda)
  • /updateBot: actualizacion remota desde Telegram
  • Codigo modular organizado en multiples archivos
═══════════════════════════════════════════════════════════════
"""

import asyncio

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


async def main():
    """Punto de entrada principal del bot."""
    logger.info("Iniciando HJ ULP PRO v3.5...")

    # Iniciar clientes
    await bot_client.start(bot_token=config.BOT_TOKEN)
    await userbot_client.start()

    # Asignar referencias globales (DESPUES de start, ANTES de handlers)
    import state
    state.bot = bot_client
    state.userbot = userbot_client

    # Inicializar cola de auto-descarga
    state.auto_dl_queue = asyncio.Queue()

    # Cargar grupos permitidos desde la base de datos
    import state as _state
    from database import db as _db
    _state.allowed_groups = set(_db.get_allowed_groups())
    logger.info(f"Grupos permitidos cargados: {len(_state.allowed_groups)}")

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

    # Iniciar polling de pagos NOWPayments
    from nowpayments import payment_polling_loop
    state.payment_polling_task = asyncio.create_task(payment_polling_loop())
    logger.info("NOWPayments payment polling iniciado")

    # Info del bot
    me = await bot_client.get_me()
    user_me = await userbot_client.get_me()
    logger.info(f"Bot: @{me.username} (ID: {me.id})")
    logger.info(f"Userbot: {user_me.first_name} (ID: {user_me.id})")
    logger.info("HJ ULP PRO v3.5 — ACTIVO")

    try:
        await bot_client.run_until_disconnected()
    finally:
        logger.info("Desconectando clientes...")
        try:
            await userbot_client.disconnect()
        except Exception:
            pass


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