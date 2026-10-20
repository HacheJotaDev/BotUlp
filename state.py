"""
═══════════════════════════════════════════════════════════════
  HJ ULP EXTRACTOR BOT — Global State Module
═══════════════════════════════════════════════════════════════
"""

import asyncio
from typing import Dict, List, Any, Set, Optional
from cachetools import LRUCache

from config import config

# Grupos permitidos (se cargan desde la DB en bot.py al iniciar)
allowed_groups: Set[int] = set()

# Caché de búsqueda
search_memory_cache = LRUCache(maxsize=config.SEARCH_CACHE_SIZE)

# Auto-download
auto_download_enabled: bool = False
pending_downloads: List[Dict[str, Any]] = []
active_downloads: Dict[str, Dict[str, Any]] = {}
download_semaphore: Optional[asyncio.Semaphore] = None
auto_dl_queue: Optional[asyncio.Queue] = None
auto_dl_worker_running: bool = False

# v4.2.14: Anti-duplicados de descarga — claves "filename|size" ya vistas o
# en curso (fast-path en memoria; la fuente persistente es download_log en DB)
seen_downloads: Set[str] = set()

# Estado temporal de usuarios (para conversaciones)
temp_state: Dict[int, dict] = {}

# Control de busquedas por usuario (cola anti-superposicion)
active_searches: Set[int] = set()  # UIDs con busqueda en curso
search_queue: Dict[int, list] = {}  # UID -> lista de busquedas encoladas

# Control de /hotmailchk en curso (anti-superposición: 1 check por usuario a la vez)
active_hotmail_checks: Set[int] = set()

# v4.2.11: Control de /hotmail (extracción de líneas únicas) en curso
active_hotmail_extracts: Set[int] = set()

# v4.2.16: Control de /imap (extracción mix/mail de líneas únicas) en curso
active_imap_extracts: Set[int] = set()

# v4.2.25: Tokens de cancelación del checker IMAP (/imapchk).
# Un token "imapc_<uid>_<ms>" está presente SOLO cuando el usuario pidió
# cancelar; imap_check_file lo consulta vía cancel_check() y entrega las
# hits parciales. Se limpia con discard al terminar el check.
imap_cancel_requests: Set[str] = set()

# Ultima busqueda ejecutada por usuario (contexto para reintentos y reportes)
last_search: Dict[int, dict] = {}

# Task de limpieza y auto-dl (FIX #15: guardar referencias para cancelación)
cleanup_task: Optional[asyncio.Task] = None
auto_dl_task: Optional[asyncio.Task] = None

# Referencia a clientes Telegram (se asignan en bot.py)
bot = None
userbot = None

# v4.0 — Info de sesión
START_TIME: float = 0.0                 # epoch del arranque (para /ping)
USER_NAMES: Dict[int, str] = {}         # caché de nombres para saludos
