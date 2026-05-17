"""
═══════════════════════════════════════════════════════════════
  HJ & GHOST ULP EXTRACTOR BOT — PRO EDITION v2.0
═══════════════════════════════════════════════════════════════
  • Motor de búsqueda paralelo con mmap ultra-rápido
  • Descarga de archivos hasta 4GB con streaming + progreso
  • Sistema de roles: FREE / VIP / SELLER / ADMIN
  • Interfaz elegante con animaciones fluidas
  • Sistema multi-idioma (ES / EN / PT)
  • Base de datos SQLite thread-safe con WAL mode
  • Auto-limpieza de archivos expirados
═══════════════════════════════════════════════════════════════
"""

import os
import re
import sys
import sqlite3
import asyncio
import logging
import time
import mmap
import random
import string
import json
import hashlib
import traceback
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, Set, Tuple, Callable
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from cachetools import LRUCache
from collections import defaultdict

from telethon import TelegramClient, events, Button, utils
from telethon.tl.types import DocumentAttributeFilename, DocumentAttributeVideo
from telethon.errors import (
    MessageNotModifiedError, UserIsBlockedError,
    InputUserDeactivatedError, FloodWaitError,
    ChatWriteForbiddenError, UserBannedInChannelError,
    TimedOutError, FileReferenceExpiredError
)

# ═════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ═════════════════════════════════════════════════════════════

@dataclass
class Config:
    API_ID: int = 33426502
    API_HASH: str = "54a521a10855ddd24314433372190f97"
    BOT_TOKEN: str = "8994978352:AAFZG5qY47aprhtSdZjugnkX7TKnzZAhj8w"
    USER_SESSION: str = "user_session"
    BOT_SESSION: str = "bot_session"

    ADMIN_IDS: List[int] = field(default_factory=lambda: [5947916142, 6142451295])

    BOT_USERNAME: str = "UlpHJBot"
    SELLER_USERNAMES: List[str] = field(default_factory=lambda: ["@hjofc20", "@Ghosthat_Real1"])

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
    DOWNLOAD_TIMEOUT: int = 3600  # 1 hora timeout para descargas grandes
    MAX_CONCURRENT_DOWNLOADS: int = 1  # 1 a la vez para evitar FloodWait
    DOWNLOAD_PROGRESS_INTERVAL: int = 5  # Actualizar progreso cada 5 segundos
    DOWNLOAD_DELAY_BETWEEN: int = 10  # Segundos entre descargas para evitar flood

    # Búsqueda
    SEARCH_CACHE_SIZE: int = 200
    SEARCH_MAX_RESULTS: int = 500000
    SEARCH_RESULT_PREVIEW_LINES: int = 15

    # Auto-limpieza
    ARCHIVE_AFTER_HOURS: int = 24
    DELETE_AFTER_HOURS: int = 72

    def __post_init__(self):
        for d in [self.DIR_DOWNLOADS, self.DIR_ARCHIVE, self.DIR_CACHE,
                  self.DB_FILE.parent, self.DIR_LOCALES, self.DIR_TEMP]:
            d.mkdir(parents=True, exist_ok=True)

config = Config()

# ═════════════════════════════════════════════════════════════
# LOGGING PROFESIONAL
# ═════════════════════════════════════════════════════════════

class ColoredFormatter(logging.Formatter):
    """Formatter con colores para consola."""
    COLORS = {
        'DEBUG': '\033[36m', 'INFO': '\033[32m', 'WARNING': '\033[33m',
        'ERROR': '\033[31m', 'CRITICAL': '\033[35m'
    }
    RESET = '\033[0m'

    def format(self, record):
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)

logging.basicConfig(
    format='%(asctime)s │ %(levelname)-8s │ %(message)s',
    datefmt='%H:%M:%S',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot_activity.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
# Aplicar colores al handler de consola
for handler in logging.getLogger().handlers:
    if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
        handler.setFormatter(ColoredFormatter(
            '%(asctime)s │ %(levelname)-8s │ %(message)s', datefmt='%H:%M:%S'
        ))

logger = logging.getLogger("HJ_PRO")
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# ═════════════════════════════════════════════════════════════
# SISTEMA DE IDIOMAS
# ═════════════════════════════════════════════════════════════

class LocaleManager:
    """Gestor de idiomas con soporte de fallback a español."""

    def __init__(self, locales_dir: Path):
        self.locales_dir = locales_dir
        self.translations: Dict[str, Dict[str, str]] = {}
        self.default_lang = 'es'
        self._load_translations()

    def _load_translations(self):
        # Español base integrado
        self.translations['es'] = {
            "welcome": (
                "╔══════════════════════════════════╗\n"
                "║     ☾  HJ & GHOST ULP PRO  ☽    ║\n"
                "╚══════════════════════════════════╝\n\n"
                "▸ Búsqueda ultra-rápida (paralela)\n"
                "▸ Bases actualizadas 24/7\n"
                "▸ Privacidad & anonimato total\n"
                "▸ Descargas hasta 4GB sin límites\n\n"
                "┌──────────────────────────────────┐\n"
                "│  Comandos: /start │ /url          │\n"
                "└──────────────────────────────────┘\n\n"
                "🌟 Soporte:\n"
                "  ✦ @hjofc20\n"
                "  ✦ @Ghosthat_Real1\n\n"
                "👤 **Rol:** `{}` │ 📊 **Búsquedas:** `{}`"
            ),
            "buy_vip_info": (
                "╔══════════════════════════════════╗\n"
                "║      💰 COMPRAR VIP ACCESS 💰     ║\n"
                "╚══════════════════════════════════╝\n\n"
                "💲 **PRECIOS:**\n"
                "  ⟡ 1 día  »  6$\n"
                "  ⟡ 3 días »  10$\n"
                "  ⟡ 7 días »  25$\n"
                "  ⟡ 30 días » 100$\n\n"
                "📬 **CONTACTO:**\n{}"
            ),
            "file_management": (
                "╔══════════════════════════════════╗\n"
                "║    📂 GESTIÓN DE ARCHIVOS        ║\n"
                "╚══════════════════════════════════╝\n\n"
                "📊 **Base de Datos:**\n"
                "  📁 Total: `{}` archivos\n"
                "  ⚡ Últimas 24h: `{}`\n"
                "  🗄️ Histórico: `{}`\n\n"
                "🔄 **Descargas:**\n"
                "  ♻️ Auto-Download: `{}`\n"
                "  📝 En cola: `{}` archivos\n"
                "  ⬇️ Activos: `{}` descargas"
            ),
            "no_results": "❌ **SIN RESULTADOS**\n\nNo se encontraron datos para `{}`.",
            "search_step_time": "🔍 **Dominio:** `{}`\n\n⏳ Selecciona el rango de tiempo:",
            "loading": "⚙️ **Procesando...**",
            "access_denied": "🚫 **ACCESO DENEGADO**\n\nSolo usuarios VIP pueden realizar búsquedas.",
            "ask_domain": "🔍 **NUEVA BÚSQUEDA**\n\nEscribe el dominio a buscar:",
            "language_selected": "🌐 Idioma actualizado correctamente.",
            "select_language": "🌐 **SELECT LANGUAGE / IDIOMA / IDIOMA**\n\nChoose your preferred language:",
            "my_account": (
                "╔══════════════════════════════════╗\n"
                "║       👤 MI CUENTA               ║\n"
                "╚══════════════════════════════════╝\n\n"
                "🆔 ID: `{}`\n"
                "🎖 Rango: `{}`\n"
                "📅 Expira: `{}`\n"
                "📊 Búsquedas: `{}`"
            ),
            "search_completed": (
                "╔══════════════════════════════════╗\n"
                "║     ✅ BÚSQUEDA COMPLETADA       ║\n"
                "╚══════════════════════════════════╝\n\n"
                "🔍 Dominio: `{}`\n"
                "📑 Tipo: `{}`\n"
                "📊 Resultados: `{}`\n"
                "⏱️ Tiempo: `{:.1f}s`"
            ),
            "download_progress": "📥 Descargando: `{}`\n\n📊 Progreso: `{}`\n⚡ Velocidad: `{}`\n⏱️ ETA: `{}`",
            "redeem_success": "🎉 **¡Felicidades!**\n\nTu cuenta VIP ha sido activada exitosamente.",
            "key_generated": (
                "✅ **KEY GENERADA EXITOSAMENTE**\n\n"
                "🔑 Código:\n`{}`\n\n"
                "🔗 Link de canje:\n{}\n\n"
                "📅 Días: {}"
            ),
            "admin_panel": (
                "╔══════════════════════════════════╗\n"
                "║       🔐 PANEL ADMIN             ║\n"
                "╚══════════════════════════════════╝\n\n"
                "👑 VIPs: `{}`\n"
                "💼 Sellers: `{}`\n"
                "🔍 Búsquedas: `{}`\n"
                "👥 Total usuarios: `{}`"
            ),
            "stats_global": (
                "╔══════════════════════════════════╗\n"
                "║      📊 ESTADÍSTICAS GLOBALES    ║\n"
                "╚══════════════════════════════════╝\n\n"
                "👑 Usuarios VIP: `{}`\n"
                "💼 Sellers: `{}`\n"
                "🔍 Búsquedas Totales: `{}`\n"
                "👥 Total Usuarios: `{}`"
            ),
            "broadcast_done": "✅ **Broadcast Finalizado**\n\n📬 Enviados: `{}`\n🚫 Fallidos: `{}`",
        }

        # Cargar archivos de locale externos
        for lang_file in self.locales_dir.glob('*.json'):
            lang_code = lang_file.stem
            try:
                with open(lang_file, 'r', encoding='utf-8') as f:
                    self.translations[lang_code] = json.load(f)
                logger.info(f"Locale cargado: {lang_code}")
            except Exception as e:
                logger.error(f"Error cargando locale {lang_file}: {e}")

    def get(self, key: str, lang: str = 'es', *args) -> str:
        msg_dict = self.translations.get(lang, {})
        text = msg_dict.get(key)
        if text is None:
            if lang == 'es':
                return self.translations.get('es', {}).get(key, key)
            return self.get(key, 'es', *args)
        try:
            return text.format(*args) if args else text
        except (IndexError, KeyError):
            return text

locale_manager = LocaleManager(config.DIR_LOCALES)

# ═════════════════════════════════════════════════════════════
# BASE DE DATOS THREAD-SAFE CON WAL
# ═════════════════════════════════════════════════════════════

class Database:
    """Base de datos SQLite con WAL mode para máximo rendimiento concurrente."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._lock = asyncio.Lock()
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        # Activar WAL mode para mejor rendimiento concurrente
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
        self.conn.execute("PRAGMA temp_store=MEMORY")
        self._init_schema()

    def _init_schema(self):
        c = self.conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            role TEXT DEFAULT 'FREE',
            vip_expiry TEXT,
            search_count INTEGER DEFAULT 0,
            language TEXT DEFAULT 'es',
            first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
            last_active TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS keys (
            key_code TEXT PRIMARY KEY,
            days INTEGER,
            created_by INTEGER,
            used_by INTEGER,
            is_used INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS download_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            file_size INTEGER DEFAULT 0,
            chat_id INTEGER,
            downloaded_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")

        # Migraciones
        c.execute("PRAGMA table_info(users)")
        columns = [info[1] for info in c.fetchall()]

        migrations = [
            ('language', "ALTER TABLE users ADD COLUMN language TEXT DEFAULT 'es'"),
            ('first_seen', "ALTER TABLE users ADD COLUMN first_seen TEXT DEFAULT CURRENT_TIMESTAMP"),
            ('last_active', "ALTER TABLE users ADD COLUMN last_active TEXT DEFAULT CURRENT_TIMESTAMP"),
        ]
        for col_name, alter_sql in migrations:
            if col_name not in columns:
                logger.info(f"Migrando DB: añadiendo columna '{col_name}'...")
                try:
                    c.execute(alter_sql)
                    self.conn.commit()
                    logger.info(f"Columna '{col_name}' añadida correctamente.")
                except Exception as e:
                    logger.error(f"Error migrando DB: {e}")

        self.conn.commit()

    def get_user(self, uid: int) -> dict:
        c = self.conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id = ?", (uid,))
        row = c.fetchone()
        if not row:
            now = datetime.now(timezone.utc).isoformat()
            c.execute(
                "INSERT INTO users (user_id, first_seen, last_active) VALUES (?, ?, ?)",
                (uid, now, now)
            )
            self.conn.commit()
            return {
                'user_id': uid, 'role': 'FREE', 'vip_expiry': None,
                'search_count': 0, 'language': 'es',
                'first_seen': now, 'last_active': now
            }
        # Actualizar last_active
        try:
            c.execute(
                "UPDATE users SET last_active = ? WHERE user_id = ?",
                (datetime.now(timezone.utc).isoformat(), uid)
            )
            self.conn.commit()
        except Exception:
            pass
        return dict(row)

    def set_language(self, uid: int, lang: str):
        c = self.conn.cursor()
        c.execute("UPDATE users SET language = ? WHERE user_id = ?", (lang, uid))
        self.conn.commit()

    def set_role(self, uid: int, role: str, days: int = 0):
        expiry = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat() if role == 'VIP' else None
        c = self.conn.cursor()
        c.execute(
            "INSERT INTO users (user_id, role, vip_expiry) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET role=excluded.role, vip_expiry=excluded.vip_expiry",
            (uid, role, expiry)
        )
        self.conn.commit()

    def remove_vip(self, uid: int):
        c = self.conn.cursor()
        c.execute("UPDATE users SET role='FREE', vip_expiry=NULL WHERE user_id=?", (uid,))
        self.conn.commit()

    def gen_key(self, creator: int, days: int) -> str:
        code = f"HJ-{''.join(random.choices(string.ascii_uppercase + string.digits, k=12))}"
        c = self.conn.cursor()
        c.execute(
            "INSERT INTO keys (key_code, days, created_by) VALUES (?, ?, ?)",
            (code, days, creator)
        )
        self.conn.commit()
        return code

    def redeem(self, uid: int, code: str) -> bool:
        c = self.conn.cursor()
        c.execute("SELECT days FROM keys WHERE key_code = ? AND is_used = 0", (code,))
        row = c.fetchone()
        if not row:
            return False
        days = row['days']
        expiry = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
        c.execute("UPDATE keys SET is_used = 1, used_by = ? WHERE key_code = ?", (uid, code))
        c.execute(
            "INSERT INTO users (user_id, role, vip_expiry) VALUES (?, 'VIP', ?) "
            "ON CONFLICT(user_id) DO UPDATE SET role='VIP', vip_expiry=excluded.vip_expiry",
            (uid, expiry)
        )
        self.conn.commit()
        return True

    def add_search(self, uid: int):
        c = self.conn.cursor()
        c.execute("UPDATE users SET search_count = search_count + 1 WHERE user_id = ?", (uid,))
        self.conn.commit()

    def get_stats(self) -> dict:
        c = self.conn.cursor()
        c.execute("SELECT COUNT(*) FROM users WHERE role='VIP'")
        vips = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM users WHERE role='SELLER'")
        sellers = c.fetchone()[0]
        c.execute("SELECT SUM(search_count) FROM users")
        total_searches = c.fetchone()[0] or 0
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
        return {
            'vips': vips, 'sellers': sellers,
            'searches': total_searches, 'total_users': total_users
        }

    def list_vips(self) -> List[dict]:
        c = self.conn.cursor()
        c.execute("SELECT user_id, vip_expiry, search_count FROM users WHERE role='VIP' OR role='SELLER'")
        return [dict(r) for r in c.fetchall()]

    def list_sellers(self) -> List[int]:
        c = self.conn.cursor()
        c.execute("SELECT user_id FROM users WHERE role='SELLER'")
        return [r['user_id'] for r in c.fetchall()]

    def get_all_users(self) -> List[int]:
        c = self.conn.cursor()
        c.execute("SELECT user_id FROM users")
        return [row[0] for row in c.fetchall()]

    def log_download(self, filename: str, file_size: int, chat_id: int):
        c = self.conn.cursor()
        c.execute(
            "INSERT INTO download_log (filename, file_size, chat_id) VALUES (?, ?, ?)",
            (filename, file_size, chat_id)
        )
        self.conn.commit()

db = Database(config.DB_FILE)

# ═════════════════════════════════════════════════════════════
# ESTADO GLOBAL
# ═════════════════════════════════════════════════════════════

allowed_groups: Set[int] = set()
search_memory_cache = LRUCache(maxsize=config.SEARCH_CACHE_SIZE)
auto_download_enabled: bool = False
pending_downloads: List[Dict[str, Any]] = []
active_downloads: Dict[str, Dict[str, Any]] = {}  # filename -> {task, start_time, size}
download_semaphore: Optional[asyncio.Semaphore] = None
auto_dl_queue: asyncio.Queue = None  # Cola secuencial para auto-descarga
auto_dl_worker_running: bool = False
temp_state: Dict[int, dict] = {}
cleanup_task: Optional[asyncio.Task] = None

# ═════════════════════════════════════════════════════════════
# ROLES Y PERMISOS
# ═════════════════════════════════════════════════════════════

class UserRole(Enum):
    ADMIN = "ADMIN"
    SELLER = "SELLER"
    VIP = "VIP"
    FREE = "FREE"

class SearchMode(Enum):
    ULP = "ULP"
    MAIL = "MAIL:PASS"
    USERPASS = "USER:PASS"

def get_user_role(uid: int) -> UserRole:
    if uid in config.ADMIN_IDS:
        return UserRole.ADMIN
    user = db.get_user(uid)
    role_str = user.get('role', 'FREE')
    if role_str == 'SELLER':
        return UserRole.SELLER
    if role_str == 'VIP':
        exp = user.get('vip_expiry')
        if exp:
            try:
                if datetime.now(timezone.utc) < datetime.fromisoformat(exp):
                    return UserRole.VIP
            except Exception:
                pass
    return UserRole.FREE

def normalizar_url(url: str) -> str:
    url = url.strip().lower()
    for prefix in ['https://', 'http://', 'www.']:
        if url.startswith(prefix):
            url = url[len(prefix):]
    return url.split('/')[0].split('?')[0].split(':')[0]

# ═════════════════════════════════════════════════════════════
# MOTOR DE BÚSQUEDA ULTRA-RÁPIDO
# ═════════════════════════════════════════════════════════════

executor = ThreadPoolExecutor(
    max_workers=config.MAX_WORKERS,
    thread_name_prefix="search_worker"
)

# Regex pre-compilado para máximo rendimiento
_EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

def _search_file(path: Path, kw: str, modo: SearchMode) -> List[str]:
    """Búsqueda en archivo con mmap - máxima velocidad."""
    res_set = set()
    enc_kw = kw.lower().encode()
    kw_lower = kw.lower()

    try:
        file_size = path.stat().st_size
        if file_size == 0:
            return []

        with open(path, 'rb') as f:
            # mmap para archivos grandes (acceso directo a memoria)
            with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                # Para archivos muy grandes, usar find() para saltar directamente
                pos = 0
                mm_size = mm.size()

                while pos < mm_size:
                    # Buscar la keyword directamente en bytes
                    found = mm.find(enc_kw, pos)
                    if found == -1:
                        break

                    # Retroceder al inicio de la línea
                    line_start = mm.rfind(b'\n', max(0, found - 4096), found)
                    if line_start == -1:
                        line_start = 0
                    else:
                        line_start += 1

                    # Avanzar al final de la línea
                    line_end = mm.find(b'\n', found)
                    if line_end == -1:
                        line_end = mm_size
                    else:
                        line_end += 1  # Include the newline

                    # Leer la línea completa
                    line_data = mm[line_start:line_end].strip()
                    if not line_data:
                        pos = line_end
                        continue

                    try:
                        decoded = line_data.decode('utf-8', 'ignore').strip()
                        if not decoded or kw_lower not in decoded.lower():
                            pos = line_end
                            continue

                        if modo == SearchMode.ULP:
                            res_set.add(decoded)

                        elif modo in (SearchMode.MAIL, SearchMode.USERPASS):
                            clean_line = decoded.replace("|", ":").replace(";", ":")
                            parts = [p.strip() for p in clean_line.split(":") if p.strip()]

                            user = ""
                            password = ""

                            if len(parts) >= 3:
                                user = parts[-2]
                                password = parts[-1]
                            elif len(parts) == 2:
                                user = parts[0]
                                password = parts[1]
                            else:
                                pos = line_end
                                continue

                            if not user or not password:
                                pos = line_end
                                continue

                            if modo == SearchMode.MAIL:
                                if _EMAIL_RE.match(user):
                                    res_set.add(f"{user}:{password}")
                            elif modo == SearchMode.USERPASS:
                                if "@" not in user:
                                    res_set.add(f"{user}:{password}")

                    except Exception:
                        pass

                    # Mover posición después de esta línea
                    pos = line_end

    except Exception:
        pass

    return list(res_set)

async def search_engine(kw: str, time_opt: str, modo: SearchMode) -> Optional[Path]:
    """Motor de búsqueda paralelo con caché inteligente."""
    # Verificar caché
    cache_key = f"{kw}:{time_opt}:{modo.value}"
    if cache_key in search_memory_cache:
        cached_path = search_memory_cache[cache_key]
        if cached_path and cached_path.exists():
            logger.info(f"Cache HIT: {cache_key}")
            return cached_path

    loop = asyncio.get_event_loop()
    dirs = []
    if time_opt in ['24h', 'all']:
        dirs.append(config.DIR_DOWNLOADS)
    if time_opt in ['old', 'all']:
        dirs.append(config.DIR_ARCHIVE)

    files = [f for d in dirs for f in d.glob('*.txt') if f.stat().st_size > 0]
    if not files:
        return None

    # Búsqueda paralela en todos los archivos
    tasks = [
        loop.run_in_executor(executor, _search_file, f, kw, modo)
        for f in files
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Unificar resultados eliminando duplicados
    final = set()
    for r in results:
        if isinstance(r, list):
            final.update(r)

    if not final:
        return None

    # Limitar resultados para evitar archivos enormes
    if len(final) > config.SEARCH_MAX_RESULTS:
        logger.warning(f"Resultados truncados: {len(final)} -> {config.SEARCH_MAX_RESULTS}")
        final = set(list(final)[:config.SEARCH_MAX_RESULTS])

    out = config.DIR_CACHE / f"result_{int(time.time())}_{kw[:20]}.txt"
    with open(out, 'w', encoding='utf-8', buffering=1024*64) as f:
        f.write('\n'.join(final))

    # Guardar en caché
    search_memory_cache[cache_key] = out

    return out

# ═════════════════════════════════════════════════════════════
# SISTEMA DE DESCARGA ULTRA-ESTABLE (Hasta 4GB)
# ═════════════════════════════════════════════════════════════

def _format_size(size_bytes: int) -> str:
    """Formatear bytes a formato legible."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"

def _format_time(seconds: float) -> str:
    """Formatear segundos a formato legible."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds//60:.0f}m {seconds%60:.0f}s"
    else:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        return f"{h:.0f}h {m:.0f}m"

def get_file_counts() -> Dict[str, int]:
    count_24h = len(list(config.DIR_DOWNLOADS.glob('*.txt')))
    count_old = len(list(config.DIR_ARCHIVE.glob('*.txt')))
    return {'total': count_24h + count_old, '24h': count_24h, 'old': count_old}

async def mover_y_limpiar_archivos():
    """Auto-limpieza de archivos expirados."""
    ahora = time.time()
    segundos_archive = config.ARCHIVE_AFTER_HOURS * 3600
    segundos_delete = config.DELETE_AFTER_HOURS * 3600

    moved = 0
    deleted = 0

    for f in config.DIR_DOWNLOADS.glob('*.txt'):
        try:
            if (ahora - f.stat().st_mtime) > segundos_archive:
                dest = config.DIR_ARCHIVE / f.name
                if dest.exists():
                    dest.unlink()
                f.rename(dest)
                moved += 1
        except Exception:
            pass

    for f in config.DIR_ARCHIVE.glob('*.txt'):
        try:
            if (ahora - f.stat().st_mtime) > segundos_delete:
                f.unlink()
                deleted += 1
        except Exception:
            pass

    # Limpiar archivos temporales
    for f in config.DIR_TEMP.glob('*'):
        try:
            if (ahora - f.stat().st_mtime) > 3600:  # 1 hora
                f.unlink()
                deleted += 1
        except Exception:
            pass

    # Limpiar caché viejo
    for f in config.DIR_CACHE.glob('*.txt'):
        try:
            if (ahora - f.stat().st_mtime) > 86400:  # 24 horas
                f.unlink()
        except Exception:
            pass

    if moved or deleted:
        logger.info(f"Limpieza: {moved} archivados, {deleted} eliminados")

async def _download_with_progress(
    event_or_msg,
    filename: str,
    dest_path: Path,
    progress_callback: Optional[Callable] = None
) -> bool:
    """
    Descarga archivos de Telegram con soporte para archivos grandes (hasta 4GB).
    Usa descarga en streaming con callback de progreso.
    """
    try:
        file_size = 0
        if hasattr(event_or_msg, 'document') and event_or_msg.document:
            file_size = event_or_msg.document.size or 0

        logger.info(f"Descarga iniciada: {filename} ({_format_size(file_size)})")

        # Crear archivo temporal primero
        temp_path = dest_path.with_suffix('.tmp')

        start_time = time.time()
        last_update = [start_time]
        downloaded = [0]

        def progress(current, total):
            downloaded[0] = current
            now = time.time()
            # Actualizar progreso cada N segundos
            if progress_callback and (now - last_update[0]) >= config.DOWNLOAD_PROGRESS_INTERVAL:
                last_update[0] = now
                elapsed = now - start_time
                if elapsed > 0 and current > 0:
                    speed = current / elapsed
                    if speed > 0:
                        eta = (total - current) / speed
                    else:
                        eta = 0
                    pct = (current / total * 100) if total > 0 else 0
                    try:
                        asyncio.get_event_loop().call_soon_threadsafe(
                            lambda: asyncio.create_task(
                                progress_callback(current, total, speed, eta, pct)
                            )
                        )
                    except Exception:
                        pass

        # Descargar con Telethon (soporta streaming nativo)
        await event_or_msg.download_media(
            file=str(temp_path),
            progress_callback=progress if file_size > 10 * 1024 * 1024 else None  # Solo progreso si > 10MB
        )

        # Verificar descarga
        if temp_path.exists() and temp_path.stat().st_size > 0:
            # Mover de temp a destino final
            if dest_path.exists():
                dest_path.unlink()
            temp_path.rename(dest_path)

            elapsed = time.time() - start_time
            final_size = dest_path.stat().st_size
            speed = final_size / elapsed if elapsed > 0 else 0

            logger.info(
                f"Descarga completada: {filename} "
                f"({_format_size(final_size)}) en {_format_time(elapsed)} "
                f"({_format_size(speed)}/s)"
            )

            # Log en base de datos
            chat_id = getattr(event_or_msg, 'chat_id', 0)
            db.log_download(filename, final_size, chat_id)

            return True
        else:
            logger.warning(f"Descarga vacía: {filename}")
            if temp_path.exists():
                temp_path.unlink()
            return False

    except FloodWaitError as e:
        logger.warning(f"FloodWait en descarga {filename}: {e.seconds}s")
        await asyncio.sleep(e.seconds + 1)
        return False
    except TimedOutError:
        logger.error(f"Timeout en descarga: {filename}")
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass
        return False
    except Exception as e:
        logger.error(f"Error en descarga {filename}: {e}")
        if dest_path.with_suffix('.tmp').exists():
            try:
                dest_path.with_suffix('.tmp').unlink()
            except Exception:
                pass
        return False
    finally:
        # Limpiar estado de descarga
        if filename in active_downloads:
            active_downloads.pop(filename, None)

async def _download_large_file_task(event, filename: str, dest_path: Path):
    """Task de descarga con semáforo para control de concurrencia."""
    global download_semaphore
    if download_semaphore is None:
        download_semaphore = asyncio.Semaphore(config.MAX_CONCURRENT_DOWNLOADS)

    async with download_semaphore:
        active_downloads[filename] = {
            'start_time': time.time(),
            'size': 0,
            'status': 'downloading'
        }
        success = await _download_with_progress(event, filename, dest_path)
        if not success and filename in active_downloads:
            active_downloads[filename]['status'] = 'failed'
        # Delay entre descargas para evitar FloodWait
        if success:
            logger.info(f"Esperando {config.DOWNLOAD_DELAY_BETWEEN}s antes de siguiente descarga...")
            await asyncio.sleep(config.DOWNLOAD_DELAY_BETWEEN)

async def _auto_dl_worker():
    """Worker que procesa la cola de auto-descarga SECUENCIALMENTE (1 a la vez)."""
    global auto_dl_queue, auto_dl_worker_running
    auto_dl_worker_running = True
    logger.info("Auto-DL Worker iniciado (modo secuencial)")
    
    while True:
        try:
            # Esperar siguiente item de la cola
            item = await auto_dl_queue.get()
            if item is None:  # Señal de parada
                break
            
            event = item['event']
            filename = item['filename']
            dest_path = item['dest_path']
            file_size = item['size']
            
            # Verificar si ya existe
            if dest_path.exists() and dest_path.stat().st_size > 0:
                auto_dl_queue.task_done()
                continue
            
            logger.info(f"Auto-DL: Descargando {filename} ({_format_size(file_size)})")
            active_downloads[filename] = {
                'start_time': time.time(),
                'size': file_size,
                'status': 'downloading'
            }
            
            success = await _download_with_progress(event, filename, dest_path)
            
            if not success and filename in active_downloads:
                active_downloads[filename]['status'] = 'failed'
            
            # Delay entre descargas para EVITAR FloodWait
            logger.info(f"Auto-DL: Esperando {config.DOWNLOAD_DELAY_BETWEEN}s...")
            await asyncio.sleep(config.DOWNLOAD_DELAY_BETWEEN)
            
            auto_dl_queue.task_done()
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error en auto-dl worker: {e}")
            await asyncio.sleep(5)
    
    auto_dl_worker_running = False
    logger.info("Auto-DL Worker detenido")

async def realtime_listener(event):
    """Escucha automática de archivos en canales/grupos."""
    global pending_downloads, auto_download_enabled

    try:
        if not event.document:
            return

        filename = None
        for attr in event.document.attributes:
            if isinstance(attr, DocumentAttributeFilename):
                filename = attr.file_name

        if not filename or not filename.lower().endswith('.txt'):
            return

        # Verificar tamaño
        file_size = event.document.size or 0
        if file_size > config.MAX_DOWNLOAD_SIZE_MB * 1024 * 1024:
            logger.warning(f"Archivo demasiado grande: {filename} ({_format_size(file_size)})")
            return

        text_content = event.message.message or ""
        text_lower = text_content.lower()
        filename_lower = filename.lower()

        keywords = ["ulp", "url:log:pass", "url:pass", "combo", "database", "leak", "combo", "db"]
        if not any(k in filename_lower for k in keywords):
            if not any(k in text_lower for k in keywords):
                return

        dest_path = config.DIR_DOWNLOADS / filename

        if dest_path.exists() and dest_path.stat().st_size > 0:
            return

        if filename in active_downloads:
            return

        if auto_download_enabled:
            # Encolar en vez de lanzar directamente (evita FloodWait)
            if auto_dl_queue is not None:
                await auto_dl_queue.put({
                    'event': event,
                    'filename': filename,
                    'dest_path': dest_path,
                    'size': file_size
                })
                queue_size = auto_dl_queue.qsize()
                logger.info(f"Auto-DL: Encolado {filename} (cola: {queue_size})")
            else:
                # Fallback si no hay cola
                active_downloads[filename] = {
                    'start_time': time.time(),
                    'size': file_size,
                    'status': 'starting'
                }
                asyncio.create_task(_download_large_file_task(event, filename, dest_path))
        else:
            if not any(p['msg_id'] == event.id for p in pending_downloads):
                try:
                    chat = await event.get_chat()
                    chat_name = getattr(chat, 'title', f"Chat {event.chat_id}")
                except Exception:
                    chat_name = "Unknown"
                pending_downloads.append({
                    'chat_id': event.chat_id,
                    'msg_id': event.id,
                    'filename': filename,
                    'chat_name': chat_name,
                    'size': file_size
                })
                logger.info(f"Pendiente detectado: {filename} ({_format_size(file_size)})")

    except Exception as e:
        logger.error(f"Error en listener: {e}")

async def process_pending_downloads(status_msg=None):
    """Procesar descargas pendientes con progreso en tiempo real."""
    global pending_downloads

    if not pending_downloads:
        if status_msg:
            await status_msg.edit("No hay archivos pendientes.")
        return

    total = len(pending_downloads)
    stats = {'new': 0, 'existing': 0, 'errors': 0}
    start_time = time.time()

    if status_msg:
        await status_msg.edit(f"**Descargando {total} archivos pendientes...**")

    to_download = list(pending_downloads)
    pending_downloads = []

    for idx, item in enumerate(to_download, 1):
        try:
            msg = await userbot.get_messages(item['chat_id'], ids=item['msg_id'])
            if not msg or not msg.document:
                stats['errors'] += 1
                continue

            dest_path = config.DIR_DOWNLOADS / item['filename']

            if dest_path.exists() and dest_path.stat().st_size > 0:
                stats['existing'] += 1
                continue

            if status_msg:
                try:
                    fname_short = item['filename'][:35]
                    await status_msg.edit(
                        f"📥 **Descargando ({idx}/{total})**\n\n"
                        f"📄 `{fname_short}`\n"
                        f"📊 Tamaño: `{_format_size(item.get('size', 0))}`\n\n"
                        f"✅ Nuevos: `{stats['new']}` │ 💾 Existentes: `{stats['existing']}` │ ❌ Errores: `{stats['errors']}`"
                    )
                except MessageNotModifiedError:
                    pass
                except Exception:
                    pass

            success = await _download_with_progress(msg, item['filename'], dest_path)
            if success:
                stats['new'] += 1
            else:
                stats['errors'] += 1

            # Pequeña pausa entre descargas para no saturar
            await asyncio.sleep(0.3)

        except Exception as e:
            logger.error(f"Error descargando pendiente: {e}")
            stats['errors'] += 1

    elapsed = time.time() - start_time

    if status_msg:
        report = (
            "✅ **DESCARGA COMPLETADA**\n\n"
            f"📥 Nuevos: `{stats['new']}`\n"
            f"💾 Existentes: `{stats['existing']}`\n"
            f"❌ Errores: `{stats['errors']}`\n"
            f"⏱️ Tiempo: `{_format_time(elapsed)}`"
        )
        try:
            await status_msg.edit(report, buttons=Keyboards.back("adm_files"), parse_mode='md')
        except Exception:
            pass

# ═════════════════════════════════════════════════════════════
# INTERFAZ DE USUARIO ELEGANTE
# ═════════════════════════════════════════════════════════════

class UI:
    @staticmethod
    def text(key: str, lang: str = 'es', *args) -> str:
        localized = locale_manager.get(key, lang, *args)
        if localized:
            try:
                return localized.format(*args) if args else localized
            except (IndexError, KeyError):
                return localized

        # Fallback al diccionario base de español
        return locale_manager.get(key, 'es', *args) or key

class Keyboards:
    @staticmethod
    def main(role: UserRole, lang: str = 'es'):
        lang_btn = [Button.inline("🌐 Idioma / Language", b"ch_lang")]

        if role == UserRole.FREE:
            return [
                [Button.inline("💰 COMPRAR VIP", b"buy_vip_info")],
                [Button.inline("👤 Mi Cuenta", b"my_account")],
                lang_btn
            ]
        elif role == UserRole.VIP:
            return [
                [Button.inline("🔍 NUEVA BÚSQUEDA", b"search_init")],
                [Button.inline("👤 Mi Cuenta", b"my_account")],
                lang_btn
            ]
        elif role == UserRole.SELLER:
            return [
                [Button.inline("🔍 NUEVA BÚSQUEDA", b"search_init")],
                [Button.inline("🔑 GENERAR KEY", b"seller_genkey")],
                [Button.inline("👤 Mi Cuenta", b"my_account")]
            ]
        elif role == UserRole.ADMIN:
            return [
                [Button.inline("🔍 NUEVA BÚSQUEDA", b"search_init")],
                [Button.inline("🔐 PANEL ADMIN", b"admin_enter")],
                [Button.inline("📂 GESTIÓN ARCHIVOS", b"adm_files")],
                [Button.inline("👤 Mi Cuenta", b"my_account")]
            ]
        return []

    @staticmethod
    def time():
        return [
            [Button.inline("⚡ Últimas 24h", b"time_24h")],
            [Button.inline("🗂 24h + Antiguos", b"time_all")],
            [Button.inline("📅 Solo Antiguos", b"time_old")],
            [Button.inline("❌ Cancelar", b"back_main")]
        ]

    @staticmethod
    def formats():
        return [
            [Button.inline("📄 ULP (Completo)", b"fmt_ulp")],
            [Button.inline("📧 MAIL:PASS", b"fmt_mail")],
            [Button.inline("👤 USER:PASS", b"fmt_user")],
            [Button.inline("❌ Cancelar", b"back_main")]
        ]

    @staticmethod
    def no_results(kw: str):
        return [
            [Button.inline("⚠️ REPORTAR URL", b"report_url")],
            [Button.inline("🔙 Volver", b"back_main")]
        ]

    @staticmethod
    def admin():
        return [
            [Button.inline("👑 Ver VIPs", b"adm_vips"),
             Button.inline("💼 Sellers", b"adm_sellers")],
            [Button.inline("🔑 Generar Key", b"adm_genkey")],
            [Button.inline("📊 Stats", b"adm_stats")],
            [Button.inline("📂 Gestión Archivos", b"adm_files")],
            [Button.inline("🔙 Volver", b"back_main")]
        ]

    @staticmethod
    def gen_key():
        return [
            [Button.inline("1 Día", b"gen_1"),
             Button.inline("3 Días", b"gen_3"),
             Button.inline("7 Días", b"gen_7")],
            [Button.inline("30 Días", b"gen_30")],
            [Button.inline("🔙 Volver", b"back_main")]
        ]

    @staticmethod
    def files_control(auto_dl: bool, pending_count: int, active_count: int):
        if auto_dl:
            btn_auto = Button.inline("✅ Auto-DL ON", b"toggle_auto_off")
        else:
            btn_auto = Button.inline("❌ Auto-DL OFF", b"toggle_auto_on")

        return [
            [btn_auto],
            [Button.inline(f"📥 Descargar Pendientes ({pending_count})", b"dl_all")],
            [Button.inline("🗑 Vaciar Pendientes", b"clear_pending")],
            [Button.inline("🔄 Refrescar", b"refresh_files")],
            [Button.inline("🔙 Volver", b"admin_enter")]
        ]

    @staticmethod
    def language_selection():
        return [
            [Button.inline("🇪🇸 Español", b"set_lang_es")],
            [Button.inline("🇬🇧 English", b"set_lang_en")],
            [Button.inline("🇧🇷 Português", b"set_lang_pt")],
            [Button.inline("🔙 Volver", b"back_main")]
        ]

    @staticmethod
    def back(data: str = "back_main"):
        return [[Button.inline("🔙 Volver", data.encode())]]

# ═════════════════════════════════════════════════════════════
# CLIENTES TELEGRAM
# ═════════════════════════════════════════════════════════════

bot = TelegramClient(
    config.BOT_SESSION, config.API_ID, config.API_HASH,
    connection_retries=15, retry_delay=3,
    auto_reconnect=True, timeout=60
)
userbot = TelegramClient(
    config.USER_SESSION, config.API_ID, config.API_HASH,
    connection_retries=15, retry_delay=3,
    auto_reconnect=True, timeout=120
)

# ═════════════════════════════════════════════════════════════
# ANIMACIONES DE CARGA
# ═════════════════════════════════════════════════════════════

LOADING_FRAMES = [
    "⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"
]

SEARCH_FRAMES = [
    "🔍 ━━━━━━━━━━",
    "🔍 ━━━━━━━━━━",
    "🔍 ━━━━━━━━━━",
    "🔍 ━━━━━━━━━━",
    "🔍 ━━━━━━━━━━",
    "🔍 ━━━━━━━━━━",
]

async def animate_loading(msg, search_task: asyncio.Task, kw: str):
    """Animación de carga elegante durante la búsqueda."""
    i = 0
    while not search_task.done():
        frame = LOADING_FRAMES[i % len(LOADING_FRAMES)]
        elapsed = time.time()
        try:
            await msg.edit(
                f"⚙️ **Buscando** `{kw}`...\n\n"
                f"{frame} Procesando bases de datos\n"
                f"⏱️ Transcurrido: `{i * 0.6:.0f}s`",
                parse_mode='md'
            )
        except MessageNotModifiedError:
            pass
        except Exception:
            pass
        i += 1
        await asyncio.sleep(0.6)

# ═════════════════════════════════════════════════════════════
# HANDLERS DE COMANDOS
# ═════════════════════════════════════════════════════════════

@bot.on(events.NewMessage(pattern="/start"))
async def start(e):
    uid = e.sender_id
    user = db.get_user(uid)
    lang = user.get('language', 'es')
    role = get_user_role(uid)

    # Verificar si es link de referral/key
    args = e.message.message.split()
    if len(args) > 1:
        code = args[1]
        if db.redeem(uid, code):
            role = get_user_role(uid)
            await e.reply(
                locale_manager.get("redeem_success", lang),
                buttons=Keyboards.main(role, lang),
                parse_mode='md'
            )
            return

    await e.reply(
        UI.text("welcome", lang, role.value, user['search_count']),
        buttons=Keyboards.main(role, lang),
        parse_mode='md'
    )

@bot.on(events.NewMessage(pattern=r"/vip (\d+)"))
async def cmd_vip_perm(e):
    if get_user_role(e.sender_id) != UserRole.ADMIN:
        return
    uid = int(e.pattern_match.group(1))
    db.set_role(uid, 'VIP', days=36500)
    await e.reply(f"✅ Usuario `{uid}` ahora es **VIP Permanente**.", parse_mode='md')

@bot.on(events.NewMessage(pattern=r"/seller (\d+)"))
async def cmd_seller(e):
    if get_user_role(e.sender_id) != UserRole.ADMIN:
        return
    uid = int(e.pattern_match.group(1))
    db.set_role(uid, 'SELLER')
    await e.reply(f"✅ Usuario `{uid}` promovido a **SELLER**.", parse_mode='md')

@bot.on(events.NewMessage(pattern=r"/unseller (\d+)"))
async def cmd_unseller(e):
    if get_user_role(e.sender_id) != UserRole.ADMIN:
        return
    uid = int(e.pattern_match.group(1))
    db.set_role(uid, 'FREE')
    await e.reply(f"❌ Usuario `{uid}` removido de **SELLER**.", parse_mode='md')

@bot.on(events.NewMessage(pattern=r"/unvip (\d+)"))
async def cmd_unvip(e):
    if get_user_role(e.sender_id) != UserRole.ADMIN:
        return
    uid = int(e.pattern_match.group(1))
    db.remove_vip(uid)
    await e.reply(f"🗑 Usuario `{uid}` eliminado de VIP.", parse_mode='md')

@bot.on(events.NewMessage(pattern=r"/gp"))
async def cmd_gp(e):
    if get_user_role(e.sender_id) != UserRole.ADMIN:
        return
    if not e.is_group:
        return
    allowed_groups.add(e.chat_id)
    await e.reply("✅ Grupo añadido a la lista permitida.")

@bot.on(events.NewMessage(pattern=r"/ungp"))
async def cmd_ungp(e):
    if get_user_role(e.sender_id) != UserRole.ADMIN:
        return
    if not e.is_group:
        return
    if e.chat_id in allowed_groups:
        allowed_groups.discard(e.chat_id)
        await e.reply("🗑 Grupo eliminado de la lista permitida.")

@bot.on(events.NewMessage(pattern=r"/url (.+)"))
async def cmd_url(e):
    uid = e.sender_id
    user = db.get_user(uid)
    lang = user.get('language', 'es')
    role = get_user_role(uid)
    if role == UserRole.FREE:
        return await e.reply(
            UI.text("access_denied", lang),
            buttons=Keyboards.back(),
            parse_mode='md'
        )
    kw = normalizar_url(e.pattern_match.group(1))
    temp_state[uid] = {'kw': kw}
    await e.reply(
        UI.text("search_step_time", lang, kw),
        buttons=Keyboards.time(),
        parse_mode='md'
    )

# --- BROADCAST ---

async def _broadcast(sender_id: int, targets: list, msg_text: str, status_msg, label: str):
    """Ejecutar broadcast con manejo de errores robusto."""
    total = len(targets)
    if total == 0:
        await status_msg.edit(f"No hay usuarios para broadcast.")
        return

    sent = 0
    errors = 0

    for idx, target in enumerate(targets):
        uid = target if isinstance(target, int) else target['user_id']
        try:
            await bot.send_message(uid, msg_text, parse_mode='md')
            sent += 1
            # Rate limiting inteligente
            await asyncio.sleep(0.05)

            # Actualizar progreso cada 50 mensajes
            if sent % 50 == 0:
                try:
                    await status_msg.edit(
                        f"📣 **{label}**\n\n"
                        f"✅ Enviados: `{sent}/{total}`\n"
                        f"❌ Errores: `{errors}`"
                    )
                except Exception:
                    pass
        except FloodWaitError as fw:
            logger.warning(f"FloodWait: {fw.seconds}s en broadcast")
            await asyncio.sleep(fw.seconds + 1)
            # Reintentar
            try:
                await bot.send_message(uid, msg_text, parse_mode='md')
                sent += 1
            except Exception:
                errors += 1
        except (UserIsBlockedError, InputUserDeactivatedError):
            errors += 1
        except Exception:
            errors += 1
            await asyncio.sleep(0.5)

    await status_msg.edit(
        f"✅ **{label} Finalizado**\n\n"
        f"📬 Enviados: `{sent}`\n"
        f"🚫 Fallidos: `{errors}`"
    )

@bot.on(events.NewMessage(pattern=r"/bc (.+)"))
async def cmd_bc(e):
    if get_user_role(e.sender_id) != UserRole.ADMIN:
        return
    msg_text = e.pattern_match.group(1)
    users = db.get_all_users()
    status = await e.reply(
        f"📣 **Broadcast Global Iniciado**\n\n👥 Total: `{len(users)}`\n⚡ Enviando..."
    )
    await _broadcast(e.sender_id, users, msg_text, status, "Broadcast Global")

@bot.on(events.NewMessage(pattern=r"/bcvip (.+)"))
async def cmd_bcvip(e):
    if get_user_role(e.sender_id) != UserRole.ADMIN:
        return
    msg_text = e.pattern_match.group(1)
    vips_data = db.list_vips()
    status = await e.reply(
        f"👑 **Broadcast VIP Iniciado**\n\n👥 Total VIPs: `{len(vips_data)}`\n⚡ Enviando..."
    )
    await _broadcast(e.sender_id, vips_data, msg_text, status, "Broadcast VIP")

# --- CONVERSATION HANDLER ---

@bot.on(events.NewMessage)
async def handle_conversation(e):
    if not e.is_private:
        return
    uid = e.sender_id
    if uid in temp_state and temp_state[uid].get('step') == 'WAITING_KEYWORD':
        user = db.get_user(uid)
        lang = user.get('language', 'es')
        kw = normalizar_url(e.text)
        temp_state[uid] = {'kw': kw}
        await e.reply(
            UI.text("search_step_time", lang, kw),
            buttons=Keyboards.time(),
            parse_mode='md'
        )

# ═════════════════════════════════════════════════════════════
# CALLBACKS - TODOS LOS BOTONES FUNCIONALES
# ═════════════════════════════════════════════════════════════

@bot.on(events.CallbackQuery)
async def callbacks(e):
    global auto_download_enabled, pending_downloads

    uid = e.sender_id
    user = db.get_user(uid)
    lang = user.get('language', 'es')
    role = get_user_role(uid)
    data = e.data.decode()

    try:
        # ─── VOLVER AL MENÚ PRINCIPAL ───
        if data == "back_main":
            await e.edit(
                UI.text("welcome", lang, role.value, user['search_count']),
                buttons=Keyboards.main(role, lang),
                parse_mode='md'
            )

        # ─── MI CUENTA ───
        elif data == "my_account":
            exp = user['vip_expiry'][:10] if user['vip_expiry'] else "N/A"
            await e.edit(
                UI.text("my_account", lang, uid, role.value, exp, user['search_count']),
                buttons=Keyboards.back(),
                parse_mode='md'
            )

        # ─── COMPRAR VIP ───
        elif data == "buy_vip_info":
            contacts = "\n".join(config.SELLER_USERNAMES)
            await e.edit(
                UI.text("buy_vip_info", lang, contacts),
                buttons=Keyboards.back(),
                parse_mode='md'
            )

        # ─── IDIOMA ───
        elif data == "ch_lang":
            await e.edit(
                UI.text("select_language", lang),
                buttons=Keyboards.language_selection(),
                parse_mode='md'
            )

        elif data.startswith("set_lang_"):
            parts = data.split("_")
            new_lang = parts[2] if len(parts) >= 3 else 'es'
            db.set_language(uid, new_lang)
            await e.answer(UI.text("language_selected", new_lang), alert=True)
            user = db.get_user(uid)
            await e.edit(
                UI.text("welcome", new_lang, role.value, user['search_count']),
                buttons=Keyboards.main(role, new_lang),
                parse_mode='md'
            )

        # ─── GESTIÓN DE ARCHIVOS ───
        elif data in ("adm_files", "refresh_files"):
            if role != UserRole.ADMIN:
                return await e.answer("Acceso denegado.", alert=True)
            counts = get_file_counts()
            auto_status = "ON" if auto_download_enabled else "OFF"
            queue_count = auto_dl_queue.qsize() if auto_dl_queue else 0
            total_pending = len(pending_downloads) + queue_count
            await e.edit(
                UI.text("file_management", lang,
                        counts['total'], counts['24h'], counts['old'],
                        auto_status, total_pending, len(active_downloads)),
                buttons=Keyboards.files_control(
                    auto_download_enabled, total_pending, len(active_downloads)
                ),
                parse_mode='md'
            )

        elif data == "toggle_auto_on":
            if role != UserRole.ADMIN:
                return await e.answer("Acceso denegado.", alert=True)
            auto_download_enabled = True
            await e.answer("Auto-Descarga ACTIVADA (secuencial)", alert=True)
            counts = get_file_counts()
            queue_count = auto_dl_queue.qsize() if auto_dl_queue else 0
            total_pending = len(pending_downloads) + queue_count
            await e.edit(
                UI.text("file_management", lang,
                        counts['total'], counts['24h'], counts['old'],
                        "ON", total_pending, len(active_downloads)),
                buttons=Keyboards.files_control(
                    True, total_pending, len(active_downloads)
                ),
                parse_mode='md'
            )

        elif data == "toggle_auto_off":
            if role != UserRole.ADMIN:
                return await e.answer("Acceso denegado.", alert=True)
            auto_download_enabled = False
            await e.answer("Auto-Descarga DESACTIVADA", alert=True)
            counts = get_file_counts()
            queue_count = auto_dl_queue.qsize() if auto_dl_queue else 0
            total_pending = len(pending_downloads) + queue_count
            await e.edit(
                UI.text("file_management", lang,
                        counts['total'], counts['24h'], counts['old'],
                        "OFF", total_pending, len(active_downloads)),
                buttons=Keyboards.files_control(
                    False, total_pending, len(active_downloads)
                ),
                parse_mode='md'
            )

        elif data == "dl_all":
            if role != UserRole.ADMIN:
                return await e.answer("Acceso denegado.", alert=True)
            if not pending_downloads:
                return await e.answer("No hay archivos pendientes.", alert=True)
            msg = await e.edit("📥 **Procesando descargas pendientes...**", buttons=None)
            asyncio.create_task(process_pending_downloads(msg))

        elif data == "clear_pending":
            if role != UserRole.ADMIN:
                return await e.answer("Acceso denegado.", alert=True)
            count = len(pending_downloads)
            pending_downloads.clear()
            await e.edit(
                f"🗑 **{count} archivos pendientes eliminados.**",
                buttons=Keyboards.back("adm_files")
            )

        # ─── BÚSQUEDA ───
        elif data == "search_init":
            if role == UserRole.FREE:
                return await e.answer("Necesitas VIP para buscar.", alert=True)
            temp_state[uid] = {'step': 'WAITING_KEYWORD'}
            await e.edit(
                UI.text("ask_domain", lang),
                buttons=Keyboards.back(),
                parse_mode='md'
            )

        elif data.startswith("time_"):
            t_opt = data.split("_")[1]
            if uid in temp_state and temp_state[uid].get('kw'):
                temp_state[uid]['time'] = t_opt
                await e.edit(
                    "📄 **Formato de salida:**",
                    buttons=Keyboards.formats()
                )
            else:
                await e.answer("Usa 'Nueva Búsqueda' primero.", alert=True)

        elif data.startswith("fmt_"):
            if uid not in temp_state or not temp_state[uid].get('kw'):
                return await e.answer("Sesión expirada. Inicia nueva búsqueda.", alert=True)

            kw = temp_state[uid]['kw']
            t_opt = temp_state[uid].get('time', '24h')

            modo = SearchMode.ULP
            tipo_texto = "ULP"
            if data == "fmt_mail":
                modo = SearchMode.MAIL
                tipo_texto = "MAIL:PASS"
            elif data == "fmt_user":
                modo = SearchMode.USERPASS
                tipo_texto = "USER:PASS"

            # Animación de carga elegante
            msg = await e.edit(
                f"⚙️ **Buscando** `{kw}`...\n\n⠋ Procesando",
                buttons=None,
                parse_mode='md'
            )

            start_time = time.time()
            search_task = asyncio.create_task(search_engine(kw, t_opt, modo))

            # Animar mientras busca
            await animate_loading(msg, search_task, kw)

            result_file = await search_task
            elapsed = time.time() - start_time

            if result_file:
                db.add_search(uid)
                # Contar líneas eficientemente
                count = 0
                with open(result_file, 'rb') as f:
                    for _ in f:
                        count += 1

                # Generar preview
                preview_lines = []
                with open(result_file, 'r', encoding='utf-8') as f:
                    for i, line in enumerate(f):
                        if i >= config.SEARCH_RESULT_PREVIEW_LINES:
                            break
                        preview_lines.append(line.strip())

                # Limpiar temp_state
                if uid in temp_state:
                    del temp_state[uid]

                await e.delete()

                # Enviar preview + archivo
                preview_text = '\n'.join(preview_lines)
                if len(preview_text) > 3000:
                    preview_text = preview_text[:3000] + "..."

                caption = (
                    f"✅ **BÚSQUEDA COMPLETADA**\n\n"
                    f"🔍 Dominio: `{kw}`\n"
                    f"📑 Tipo: `{tipo_texto}`\n"
                    f"📊 Resultados: `{count}`\n"
                    f"⏱️ Tiempo: `{elapsed:.1f}s`"
                )

                await bot.send_file(
                    uid, result_file,
                    caption=caption,
                    parse_mode='md'
                )

                # Limpiar archivo de resultado
                try:
                    os.remove(result_file)
                except Exception:
                    pass
            else:
                await e.edit(
                    UI.text("no_results", lang, kw),
                    buttons=Keyboards.no_results(kw),
                    parse_mode='md'
                )

        # ─── REPORTAR URL ───
        elif data == "report_url":
            kw = temp_state.get(uid, {}).get('kw', 'Desconocido')
            for admin_id in config.ADMIN_IDS:
                try:
                    await bot.send_message(
                        admin_id,
                        f"⚠️ **REPORTE DE URL**\n\n👤 Usuario: `{uid}`\n🔍 URL: `{kw}`"
                    )
                except Exception:
                    pass
            await e.answer("Reporte enviado correctamente.", alert=True)

        # ─── PANEL ADMIN ───
        elif data == "admin_enter":
            if role != UserRole.ADMIN:
                return await e.answer("Acceso denegado.", alert=True)
            stats = db.get_stats()
            await e.edit(
                UI.text("admin_panel", lang,
                        stats['vips'], stats['sellers'],
                        stats['searches'], stats['total_users']),
                buttons=Keyboards.admin(),
                parse_mode='md'
            )

        elif data == "adm_stats":
            if role != UserRole.ADMIN:
                return await e.answer("Acceso denegado.", alert=True)
            stats = db.get_stats()
            await e.edit(
                UI.text("stats_global", lang,
                        stats['vips'], stats['sellers'],
                        stats['searches'], stats['total_users']),
                buttons=Keyboards.back("admin_enter"),
                parse_mode='md'
            )

        elif data == "adm_sellers":
            if role != UserRole.ADMIN:
                return await e.answer("Acceso denegado.", alert=True)
            sellers = db.list_sellers()
            if not sellers:
                text = "💼 **SELLERS**\n\nNo hay sellers registrados."
            else:
                lines = [f"👤 ID: `{s}`" for s in sellers]
                text = "💼 **SELLERS**\n\n" + "\n".join(lines)
            await e.edit(text, buttons=Keyboards.back("admin_enter"), parse_mode='md')

        elif data == "adm_genkey":
            if role not in (UserRole.ADMIN, UserRole.SELLER):
                return await e.answer("Acceso denegado.", alert=True)
            await e.edit("🔑 **Generador de Keys**", buttons=Keyboards.gen_key())

        elif data == "seller_genkey":
            if role not in (UserRole.ADMIN, UserRole.SELLER):
                return await e.answer("Acceso denegado.", alert=True)
            await e.edit("🔑 **Generador de Keys**", buttons=Keyboards.gen_key())

        elif data.startswith("gen_"):
            days = int(data.split("_")[1])
            code = db.gen_key(uid, days)
            link = f"https://t.me/{config.BOT_USERNAME}?start={code}"

            back_data = "admin_enter" if role == UserRole.ADMIN else "back_main"
            await e.edit(
                UI.text("key_generated", lang, code, link, days),
                buttons=Keyboards.back(back_data),
                parse_mode='md'
            )

        elif data == "adm_vips":
            if role != UserRole.ADMIN:
                return await e.answer("Acceso denegado.", alert=True)
            vips = db.list_vips()
            if not vips:
                text = "👑 **VIPs**\n\nNo hay usuarios VIP."
            else:
                lines = []
                for v in vips[:30]:  # Limitar a 30 para no romper el mensaje
                    exp = v['vip_expiry'][:10] if v['vip_expiry'] else 'N/A'
                    lines.append(f"👤 `{v['user_id']}` │ 📅 {exp} │ 🔍 {v['search_count']}")
                text = "👑 **VIPs**\n\n" + "\n".join(lines)
                if len(vips) > 30:
                    text += f"\n\n...y {len(vips) - 30} más"
            await e.edit(text, buttons=Keyboards.back("admin_enter"), parse_mode='md')

        else:
            # Botón desconocido
            await e.answer("Opción no reconocida.", alert=False)

    except MessageNotModifiedError:
        pass
    except FloodWaitError as fw:
        logger.warning(f"FloodWait en callback: {fw.seconds}s")
        await asyncio.sleep(fw.seconds + 1)
    except Exception as ex:
        logger.error(f"Error callback '{data}': {ex}")
        try:
            await e.answer("Error interno. Intenta de nuevo.", alert=True)
        except Exception:
            pass

# ═════════════════════════════════════════════════════════════
# AUTO-LIMPIEZA EN SEGUNDO PLANO
# ═════════════════════════════════════════════════════════════

async def periodic_cleanup():
    """Ejecutar limpieza cada hora."""
    while True:
        try:
            await asyncio.sleep(3600)  # Cada hora
            await mover_y_limpiar_archivos()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error en limpieza periódica: {e}")

# ═════════════════════════════════════════════════════════════
# INICIO DEL BOT
# ═════════════════════════════════════════════════════════════

async def main():
    global cleanup_task, auto_dl_queue

    logger.info("Iniciando HJ & GHOST ULP PRO v2.0...")

    # Iniciar clientes
    await bot.start(bot_token=config.BOT_TOKEN)
    await userbot.start()

    # Inicializar cola de auto-descarga secuencial
    auto_dl_queue = asyncio.Queue()
    asyncio.create_task(_auto_dl_worker())
    logger.info("Auto-DL Worker (cola secuencial) iniciado")

    # Registrar listener de archivos
    userbot.add_event_handler(realtime_listener, events.NewMessage)
    logger.info("Escucha automática de archivos ACTIVADA")

    # Limpieza inicial
    await mover_y_limpiar_archivos()

    # Iniciar limpieza periódica
    cleanup_task = asyncio.create_task(periodic_cleanup())

    # Stats
    stats = db.get_stats()
    logger.info(
        f"Sistema operativo │ 👥 {stats['total_users']} usuarios │ "
        f"👑 {stats['vips']} VIPs │ 💼 {stats['sellers']} Sellers"
    )

    # Mantener bot corriendo
    await bot.run_until_disconnected()

async def shutdown():
    """Apagado limpio."""
    global auto_dl_queue
    logger.info("Apagando sistema...")
    if cleanup_task:
        cleanup_task.cancel()
    # Detener auto-dl worker
    if auto_dl_queue is not None:
        await auto_dl_queue.put(None)  # Señal de parada
    # Cancelar descargas activas
    for filename, info in list(active_downloads.items()):
        logger.info(f"Cancelando descarga: {filename}")
    await bot.disconnect()
    await userbot.disconnect()
    executor.shutdown(wait=False)
    logger.info("Sistema apagado correctamente.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupción de teclado. Apagando...")
        try:
            asyncio.run(shutdown())
        except Exception:
            pass
    except Exception as e:
        logger.critical(f"Error fatal: {e}")
        logger.critical(traceback.format_exc())
