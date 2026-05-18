"""
═══════════════════════════════════════════════════════════════
  HJ ULP EXTRACTOR BOT — Global State Module
═══════════════════════════════════════════════════════════════
"""

import asyncio
from typing import Dict, List, Any, Set, Optional
from cachetools import LRUCache

from config import config

# Grupos permitidos
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

# Task de limpieza
cleanup_task: Optional[asyncio.Task] = None

# Referencia a clientes Telegram (se asignan en bot.py)
bot = None
userbot = None
