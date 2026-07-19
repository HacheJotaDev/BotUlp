"""
═══════════════════════════════════════════════════════════════
  HJ ULP EXTRACTOR BOT — Logging Module
═══════════════════════════════════════════════════════════════
"""

import sys
import logging


class ColoredFormatter(logging.Formatter):
    """Formatter con colores para consola."""
    COLORS = {
        'DEBUG': '\033[36m', 'INFO': '\033[32m', 'WARNING': '\033[33m',
        'ERROR': '\033[31m', 'CRITICAL': '\033[35m'
    }
    RESET = '\033[0m'

    def format(self, record):
        # FIX: try/finally para garantizar restauracion del levelname original
        levelname = record.levelname
        color = self.COLORS.get(levelname, self.RESET)
        record.levelname = f"{color}{levelname}{self.RESET}"
        try:
            result = super().format(record)
        finally:
            record.levelname = levelname  # Siempre restaurar
        return result


def setup_logging():
    """Configurar logging profesional con colores y archivo."""
    logging.basicConfig(
        format='%(asctime)s │ %(levelname)-8s │ %(message)s',
        datefmt='%H:%M:%S',
        level=logging.INFO,
        handlers=[
            logging.FileHandler('bot_activity.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    for handler in logging.getLogger().handlers:
        if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
            handler.setFormatter(ColoredFormatter(
                '%(asctime)s │ %(levelname)-8s │ %(message)s', datefmt='%H:%M:%S'
            ))

    # Silenciar logs ruidosos de Telethon
    logging.getLogger('telethon').setLevel(logging.ERROR)

    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')

    return logging.getLogger("HJ_PRO")


# Initialize on import
logger = setup_logging()