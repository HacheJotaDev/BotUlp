"""
═══════════════════════════════════════════════════════════════
  HJ ULP EXTRACTOR BOT — PRO EDITION v3.2
═══════════════════════════════════════════════════════════════
  • Motor de búsqueda paralelo con mmap ultra-rápido
  • Descarga de archivos hasta 4GB con streaming + progreso
  • Sistema de roles: FREE / VIP / SELLER / ADMIN
  • Interfaz elegante con diseño 彡 Style
  • Sistema multi-idioma (ES / EN / PT)
  • Base de datos SQLite thread-safe con WAL mode
  • Auto-limpieza de archivos expirados
  • /updateBot: actualización remota desde Telegram
  • Código modular organizado en múltiples archivos
═══════════════════════════════════════════════════════════════
"""

import asyncio
import time

from config import config
from logger_setup import logger
from state import bot as bot_ref, userbot as userbot_ref
from handlers import register_handlers
from download import (
    _auto_dl_worker, realtime_listener, mover_y_limpiar_archivos
)

# ═════════════════════════════════════════════════════════════
# INICIALIZACIÓN
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
    logger.info("Iniciando HJ ULP PRO v3.2...")

    # Iniciar clientes
    await bot_client.start(bot_token=config.BOT_TOKEN)
    await userbot_client.start()

    # Asignar referencias globales
    import state
    state.bot = bot_client
    state.userbot = userbot_client

    # Inicializar cola de auto-descarga
    state.auto_dl_queue = asyncio.Queue()

    # Registrar handlers
    register_handlers(bot_client)

    # Registrar listener de archivos en el userbot
    userbot_client.add_event_handler(
        realtime_listener,
        events.NewMessage(func=lambda e: e.document is not None)
    )

    # Iniciar worker de auto-descarga
    asyncio.create_task(_auto_dl_worker())

    # Iniciar limpieza periódica
    async def cleanup_loop():
        while True:
            try:
                await mover_y_limpiar_archivos()
            except Exception as e:
                logger.error(f"Error en limpieza: {e}")
            await asyncio.sleep(3600)  # Cada hora

    asyncio.create_task(cleanup_loop())

    # Info del bot
    me = await bot_client.get_me()
    user_me = await userbot_client.get_me()
    logger.info(f"Bot: @{me.username} (ID: {me.id})")
    logger.info(f"Userbot: {user_me.first_name} (ID: {user_me.id})")
    logger.info("HJ ULP PRO v3.2 — ACTIVO")

    # Mantener corriendo
    await bot_client.run_until_disconnected()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot detenido por usuario")
    except Exception as e:
        logger.critical(f"Error fatal: {e}")
        import traceback
        traceback.print_exc()
