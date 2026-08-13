"""
═══════════════════════════════════════════════════════════════
  HJ ULP EXTRACTOR BOT — Config Module
═══════════════════════════════════════════════════════════════
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List

from dotenv import load_dotenv
load_dotenv()


@dataclass
class Config:
    API_ID: int = 33426502
    API_HASH: str = "54a521a10855ddd24314433372190f97"
    BOT_TOKEN: str = field(default_factory=lambda: os.getenv("BOT_TOKEN", ""))
    USER_SESSION: str = "user_session"
    BOT_SESSION: str = "bot_session"

    ADMIN_IDS: List[int] = field(default_factory=lambda: [7656500542])

    BOT_USERNAME: str = "UlpHJBot"
    SELLER_USERNAMES: List[str] = field(default_factory=lambda: ["@hjofc20"])

    DB_FILE: Path = Path("SystemData/hj_bot.db")
    DIR_DOWNLOADS: Path = Path("HJDescargas")
    DIR_ARCHIVE: Path = Path("Archivo_Historico")
    DIR_CACHE: Path = Path("Cache_Resultados")
    DIR_LOCALES: Path = Path("locales")
    DIR_TEMP: Path = Path("Temp_Parts")

    MAX_WORKERS: int = min(os.cpu_count() or 8, 16)

    # Límites de descarga
    MAX_DOWNLOAD_SIZE_MB: int = 4096  # 4GB máximo
    DOWNLOAD_CHUNK_SIZE: int = 1024 * 1024  # 1MB chunks
    DOWNLOAD_TIMEOUT: int = 3600  # 1 hora timeout
    MAX_CONCURRENT_DOWNLOADS: int = 1  # 1 a la vez para evitar FloodWait
    DOWNLOAD_PROGRESS_INTERVAL: int = 3  # Actualizar progreso cada 3 segundos
    DOWNLOAD_DELAY_BETWEEN: int = 10  # Segundos entre descargas
    DOWNLOAD_THROTTLE: float = 0.008  # Throttle mínimo (0.008s entre chunks = ~125MB/s max teórico)
    DOWNLOAD_PART_SIZE_KB: int = 512  # 512KB por request (mejor equilibrio velocidad/FloodWait)

    # Búsqueda
    SEARCH_CACHE_SIZE: int = 200
    SEARCH_MAX_RESULTS: int = 500000
    SEARCH_RESULT_PREVIEW_LINES: int = 15

    # Auto-limpieza
    ARCHIVE_AFTER_HOURS: int = 24
    DELETE_AFTER_HOURS: int = 120

    # Git repo para /updateBot
    GIT_REPO_URL: str = "https://github.com/HacheJotaDev/BotUlp.git"

    # NOWPayments
    NOWPAYMENTS_API_KEY: str = "N9BWS3V-AP94BH7-HA7QH4R-RZ7TKS7"
    NOWPAYMENTS_IPN_KEY: str = "Q0qTZTAZwPPx9V6IqLT2pMptqRLFbE9P"
    NOWPAYMENTS_IPN_URL: str = os.getenv(
        "NOWPAYMENTS_IPN_URL",
        "http://47.57.242.119:9090/ipn"
    )
    NOWPAYMENTS_WEBHOOK_PORT: int = int(os.getenv("NOWPAYMENTS_WEBHOOK_PORT", "9090"))

    def __post_init__(self):
        if not self.BOT_TOKEN:
            raise ValueError(
                "BOT_TOKEN no está configurado. "
                "Crea un archivo .env con: BOT_TOKEN=tu_token_aqui"
            )

        for d in [self.DIR_DOWNLOADS, self.DIR_ARCHIVE, self.DIR_CACHE,
                  self.DB_FILE.parent, self.DIR_LOCALES, self.DIR_TEMP]:
            d.mkdir(parents=True, exist_ok=True)


config = Config()
