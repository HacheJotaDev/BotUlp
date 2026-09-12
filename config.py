"""
═══════════════════════════════════════════════════════════════
  HJ ULP EXTRACTOR BOT — Config Module v4.0
═══════════════════════════════════════════════════════════════
  • Todos los secretos se leen desde el archivo .env
  • Valores por defecto solo como fallback de compatibilidad
  • Configuracion centralizada y tipada (dataclass)
  • IP del VPS auto-detectada (no hace falta tocarla al migrar)
═══════════════════════════════════════════════════════════════
"""

import os
import socket
import urllib.request
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


# ═════════════════════════════════════════════════════════════
#  AUTO-DETECCION DE IP PUBLICA DEL VPS
# ═════════════════════════════════════════════════════════════
#  Si NOWPAYMENTS_IPN_URL esta vacia, es "auto" o contiene el
#  placeholder "TU_IP", se detecta la IP publica automaticamente
#  al arrancar el bot. Ideal si cambias de VPS seguido.
# ═════════════════════════════════════════════════════════════

_PUBLIC_IP_CACHE: str = ""


def _is_valid_ipv4(ip: str) -> bool:
    """Validacion basica de una IPv4 publica."""
    if not ip or ip.startswith("<") or ip.startswith("{"):
        return False
    parts = ip.split(".")
    if len(parts) != 4:
        return False
    try:
        return all(0 <= int(p) <= 255 for p in parts)
    except ValueError:
        return False


def _detect_public_ip(timeout: int = 5) -> str:
    """Detectar la IP publica del VPS.

    Orden de intentos:
      1. Servicios externos (ipify, ifconfig.me, ipinfo.io, amazonaws)
         -> devuelven la IP tal como la ve Internet (la buena para webhooks)
      2. Socket UDP hacia 8.8.8.8 -> IP de salida local
         (en la mayoria de VPS coincide con la publica)

    El resultado se cachea en _PUBLIC_IP_CACHE para no repetir consultas.
    """
    global _PUBLIC_IP_CACHE
    if _PUBLIC_IP_CACHE:
        return _PUBLIC_IP_CACHE

    # --- Metodo 1: servicios externos ---------------------------------
    services = [
        "https://api.ipify.org?format=text",
        "https://ifconfig.me/ip",
        "https://ipinfo.io/ip",
        "https://checkip.amazonaws.com",
        "https://icanhazip.com",
    ]
    for url in services:
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "curl/8.0"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                ip = resp.read().decode("utf-8", errors="ignore").strip()
                if _is_valid_ipv4(ip):
                    _PUBLIC_IP_CACHE = ip
                    print(f"[config] IP publica detectada via {url}: {ip}")
                    return ip
        except Exception:
            continue

    # --- Metodo 2: socket UDP (IP de salida) --------------------------
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(timeout)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if _is_valid_ipv4(ip):
            _PUBLIC_IP_CACHE = ip
            print(f"[config] IP de salida detectada via socket: {ip}")
            return ip
    except Exception:
        pass

    print("[config] WARNING: no se pudo detectar la IP publica del VPS")
    return ""


def _resolve_ipn_url() -> str:
    """Resolver NOWPAYMENTS_IPN_URL con auto-deteccion de IP.

    Reglas:
      - Si NOWPAYMENTS_IPN_URL esta vacia, es 'auto' o contiene
        'TU_IP'  -> se arma con la IP detectada + puerto + /ipn
      - En cualquier otro caso -> se usa el valor del .env tal cual
        (por si queres forzar una URL, dominio o proxy)
    """
    raw = os.getenv("NOWPAYMENTS_IPN_URL", "").strip()

    # El usuario puso una URL completa -> respetarla
    if raw and raw.lower() != "auto" and "TU_IP" not in raw.upper():
        return raw

    # Auto-detectar la IP publica
    port = int(os.getenv("NOWPAYMENTS_WEBHOOK_PORT", "9090"))
    ip = _detect_public_ip()
    if ip:
        return f"http://{ip}:{port}/ipn"

    # Fallback final: devolver lo que haya (o localhost)
    return raw or f"http://127.0.0.1:{port}/ipn"


@dataclass
class Config:
    # ── Version ──────────────────────────────────────────────
    VERSION: str = "4.2.9"

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

    # ── Base de datos (PostgreSQL) ───────────────────────────
    #  URL completa: postgresql://user:pass@host/db?sslmode=require
    #  Compatible con Neon, Supabase, Railway, Render, etc.
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://neondb_owner:npg_yeLUO1TV8Qdl@ep-damp-bar-ay8m8k1e-pooler.c-5.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
    )

    # ── Directorios ──────────────────────────────────────────
    # (Solo para archivos locales: descargas, caché de resultados, etc.)
    # La base de datos ahora es PostgreSQL (ver DATABASE_URL).
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
    # ⚡ AUTO-IP: poner "auto" (o dejar vacío) en el .env para detectar la IP
    #    del VPS automáticamente. O escribe la URL completa para forzarla.
    NOWPAYMENTS_IPN_URL: str = field(default_factory=_resolve_ipn_url)
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

        # Mostrar la IPN URL resuelta al arrancar (sale en pm2 logs)
        print(f"[config] NOWPAYMENTS_IPN_URL = {self.NOWPAYMENTS_IPN_URL}")

    @property
    def PM2_NAMES(self) -> List[str]:
        return [n.strip() for n in self.PM2_NAME.split(",") if n.strip()]


config = Config()
