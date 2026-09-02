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

# Estado temporal de usuarios (para conversaciones)
temp_state: Dict[int, dict] = {}

# Control de busquedas por usuario (cola anti-superposicion)
active_searches: Set[int] = set()  # UIDs con busqueda en curso
search_queue: Dict[int, list] = {}  # UID -> lista de busquedas encoladas

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
