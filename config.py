"""
═══════════════════════════════════════════════════════════════
  HJ ULP EXTRACTOR BOT — Config Module v4.0
═══════════════════════════════════════════════════════════════
  • Todos los secretos se leen desde el archivo .env
  • Valores por defecto solo como fallback de compatibilidad
  • Configuracion centralizada y tipada (dataclass)
═══════════════════════════════════════════════════════════════
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List

from dotenv import load_dotenv
load_dotenv()


def _env_list(key: str, default: List) -> List:
    """Leer una lista desde variable de entorno: 'id1,id2,id3'."""
    raw = os.getenv(key, "")
    if not raw:
        return default
    items = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            items.append(int(part))
        except ValueError:
            items.append(part.lstrip("@"))
    return items


@dataclass
class Config:
    # ── Version ──────────────────────────────────────────────
    VERSION: str = "4.2.4"

    # ── Telegram ─────────────────────────────────────────────
    API_ID: int = int(os.getenv("API_ID", "33426502"))
    API_HASH: str = os.getenv("API_HASH", "54a521a10855ddd24314433372190f97")
    BOT_TOKEN: str = field(default_factory=lambda: os.getenv("BOT_TOKEN", ""))
    USER_SESSION: str = os.getenv("USER_SESSION", "user_session")
    BOT_SESSION: str = os.getenv("BOT_SESSION", "bot_session")

    ADMIN_IDS: List[int] = field(default_factory=lambda: _env_list("ADMIN_IDS", [7656500542]))

    BOT_USERNAME: str = os.getenv("BOT_USERNAME", "UlpHJBot")
    SELLER_USERNAMES: List[str] = field(default_factory=lambda: _env_list("SELLER_USERNAMES", ["@hjofc20"]))
    SUPPORT_CONTACT: str = os.getenv("SUPPORT_CONTACT", "@hjofc20")

    # ── Directorios ──────────────────────────────────────────
    DB_FILE: Path = Path("SystemData/hj_bot.db")
    DIR_DOWNLOADS: Path = Path("HJDescargas")
    DIR_ARCHIVE: Path = Path("Archivo_Historico")
    DIR_CACHE: Path = Path("Cache_Resultados")
    DIR_LOCALES: Path = Path("locales")
    DIR_TEMP: Path = Path("Temp_Parts")

    # ── Rendimiento ──────────────────────────────────────────
    MAX_WORKERS: int = min(os.cpu_count() or 8, 16)
    USER_CACHE_TTL: int = int(os.getenv("USER_CACHE_TTL", "30"))      # caché de usuarios en RAM (segundos)
    LAST_ACTIVE_INTERVAL: int = 300                                   # throttle de last_active (segundos)

    # ── Descargas ────────────────────────────────────────────
    MAX_DOWNLOAD_SIZE_MB: int = 4096          # 4GB máximo
    DOWNLOAD_CHUNK_SIZE: int = 1024 * 1024    # 1MB chunks
    DOWNLOAD_TIMEOUT: int = 3600              # 1 hora timeout
    MAX_CONCURRENT_DOWNLOADS: int = 1         # 1 a la vez para evitar FloodWait
    DOWNLOAD_PROGRESS_INTERVAL: int = 3       # Actualizar progreso cada 3 segundos
    DOWNLOAD_DELAY_BETWEEN: int = 10          # Segundos entre descargas
    DOWNLOAD_THROTTLE: float = 0.008          # Throttle mínimo (~125MB/s teórico)
    DOWNLOAD_PART_SIZE_KB: int = 512          # 512KB por request

    # ── Búsqueda ─────────────────────────────────────────────
    SEARCH_CACHE_SIZE: int = 200
    SEARCH_MAX_RESULTS: int = 500000
    SEARCH_RESULT_PREVIEW_LINES: int = 15
    SEARCH_ANIM_INTERVAL: float = 1.2         # Intervalo de la animación de búsqueda (suave, anti-FloodWait)

    # ── Auto-limpieza ────────────────────────────────────────
    ARCHIVE_AFTER_HOURS: int = 24
    DELETE_AFTER_HOURS: int = 120

    # ── Git repo para /updateBot ─────────────────────────────
    GIT_REPO_URL: str = "https://github.com/HacheJotaDev/BotUlp.git"
    PM2_NAME: str = os.getenv("PM2_NAME", "botulp,ulp-bot")  # Nombres pm2 a probar (separados por coma)

    # ── NOWPayments ──────────────────────────────────────────
    NOWPAYMENTS_API_KEY: str = os.getenv("NOWPAYMENTS_API_KEY", "N9BWS3V-AP94BH7-HA7QH4R-RZ7TKS7")
    NOWPAYMENTS_IPN_KEY: str = os.getenv("NOWPAYMENTS_IPN_KEY", "Q0qTZTAZwPPx9V6IqLT2pMptqRLFbE9P")
    NOWPAYMENTS_IPN_URL: str = os.getenv("NOWPAYMENTS_IPN_URL", "http://151.241.99.91:9090/ipn")
    NOWPAYMENTS_WEBHOOK_PORT: int = int(os.getenv("NOWPAYMENTS_WEBHOOK_PORT", "9090"))

    def __post_init__(self):
        if not self.BOT_TOKEN:
            raise ValueError(
                "\n═══════════════════════════════════════════\n"
                "  BOT_TOKEN no está configurado.\n"
                "  1) Copia .env.example como .env\n"
                "  2) Escribe: BOT_TOKEN=tu_token_aqui\n"
                "═══════════════════════════════════════════"
            )

        for d in [self.DIR_DOWNLOADS, self.DIR_ARCHIVE, self.DIR_CACHE,
                  self.DB_FILE.parent, self.DIR_LOCALES, self.DIR_TEMP]:
            d.mkdir(parents=True, exist_ok=True)

    @property
    def PM2_NAMES(self) -> List[str]:
        return [n.strip() for n in self.PM2_NAME.split(",") if n.strip()]


config = Config()
