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
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, Set, Union, Tuple
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from cachetools import LRUCache

from telethon import TelegramClient, events, Button
from telethon.tl.types import DocumentAttributeFilename
from telethon.errors import MessageNotModifiedError, UserIsBlockedError, InputUserDeactivatedError

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

@dataclass
class Config:
    API_ID: int = 33426502
    API_HASH: str = "54a521a10855ddd24314433372190f97"
    BOT_TOKEN: str = "8162894918:AAFURqtx8xAUWm-dw8fhJkiO82M2G46bMyY"
    USER_SESSION: str = "user_session"
    BOT_SESSION: str = "bot_session"
    
    ADMIN_IDS: List[int] = field(default_factory=lambda: [5947916142, 6142451295])
    
    BOT_USERNAME: str = "UlpExtractorBot"
    SELLER_USERNAMES: List[str] = field(default_factory=lambda: ["@hjofc20", "@Ghosthat_Real1"])
    
    DB_FILE: Path = Path("SystemData/hj_bot.db")
    DIR_DOWNLOADS: Path = Path("HJDescargas")
    DIR_ARCHIVE: Path = Path("Archivo_Historico")
    DIR_CACHE: Path = Path("Cache_Resultados")
    DIR_LOCALES: Path = Path("locales") 
    
    MAX_WORKERS: int = os.cpu_count() or 8
    
    def __post_init__(self):
        for d in [self.DIR_DOWNLOADS, self.DIR_ARCHIVE, self.DIR_CACHE, self.DB_FILE.parent, self.DIR_LOCALES]:
            d.mkdir(parents=True, exist_ok=True)

config = Config()

# =============================================================================
# LOGGING
# =============================================================================

logging.basicConfig(
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot_activity.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("HJ_SYSTEM")
if sys.platform == 'win32': sys.stdout.reconfigure(encoding='utf-8')

# =============================================================================
# SISTEMA DE IDIOMAS (LOCALES)
# =============================================================================

class LocaleManager:
    def __init__(self, locales_dir: Path):
        self.locales_dir = locales_dir
        self.translations: Dict[str, Dict[str, str]] = {}
        self.default_lang = 'es'
        self._load_translations()

    def _load_translations(self):
        self.translations['es'] = {} 
        
        for lang_file in self.locales_dir.glob('*.json'):
            lang_code = lang_file.stem 
            try:
                with open(lang_file, 'r', encoding='utf-8') as f:
                    self.translations[lang_code] = json.load(f)
                logger.info(f"📖 Idioma cargado: {lang_code}")
            except Exception as e:
                logger.error(f"❌ Error cargando idioma {lang_file}: {e}")

    def get(self, key: str, lang: str = 'es', *args) -> str:
        msg_dict = self.translations.get(lang, {})
        text = msg_dict.get(key)
        
        if text is None:
            if lang == 'es': 
                return self.translations.get('es', {}).get(key, key)
            return self.get(key, 'es', *args)
            
        return text.format(*args) if args else text

locale_manager = LocaleManager(config.DIR_LOCALES)

# =============================================================================
# BASE DE DATOS
# =============================================================================

class Database:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        c = self.conn.cursor()
        # Crear tablas si no existen
        c.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, role TEXT DEFAULT 'FREE', vip_expiry TEXT, search_count INTEGER DEFAULT 0, language TEXT DEFAULT 'es')")
        c.execute("CREATE TABLE IF NOT EXISTS keys (key_code TEXT PRIMARY KEY, days INTEGER, created_by INTEGER, used_by INTEGER, is_used INTEGER DEFAULT 0)")
        
        # --- SOLUCIÓN AL ERROR: MIGRACIÓN DE COLUMNA ---
        # Verificar si la columna 'language' existe en la tabla users
        c.execute("PRAGMA table_info(users)")
        columns = [info[1] for info in c.fetchall()]
        
        if 'language' not in columns:
            logger.info("🔧 Migrando base de datos: añadiendo columna 'language'...")
            try:
                c.execute("ALTER TABLE users ADD COLUMN language TEXT DEFAULT 'es'")
                self.conn.commit()
                logger.info("✅ Columna 'language' añadida correctamente.")
            except Exception as e:
                logger.error(f"❌ Error migrando DB: {e}")
        
        self.conn.commit()

    def get_user(self, uid: int) -> dict:
        c = self.conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id = ?", (uid,))
        row = c.fetchone()
        if not row:
            c.execute("INSERT INTO users (user_id) VALUES (?)", (uid,))
            self.conn.commit()
            return {'user_id': uid, 'role': 'FREE', 'vip_expiry': None, 'search_count': 0, 'language': 'es'}
        return dict(row)

    def set_language(self, uid: int, lang: str):
        c = self.conn.cursor()
        c.execute("UPDATE users SET language = ? WHERE user_id = ?", (lang, uid))
        self.conn.commit()

    def set_role(self, uid: int, role: str, days: int = 0):
        expiry = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat() if role == 'VIP' else None
        c = self.conn.cursor()
        c.execute("INSERT INTO users (user_id, role, vip_expiry) VALUES (?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET role=excluded.role, vip_expiry=excluded.vip_expiry", (uid, role, expiry))
        self.conn.commit()

    def remove_vip(self, uid: int):
        c = self.conn.cursor()
        c.execute("UPDATE users SET role='FREE', vip_expiry=NULL WHERE user_id=?", (uid,))
        self.conn.commit()

    def gen_key(self, creator: int, days: int) -> str:
        code = f"HJ-{''.join(random.choices(string.ascii_uppercase + string.digits, k=10))}"
        c = self.conn.cursor()
        c.execute("INSERT INTO keys (key_code, days, created_by) VALUES (?, ?, ?)", (code, days, creator))
        self.conn.commit()
        return code

    def redeem(self, uid: int, code: str) -> bool:
        c = self.conn.cursor()
        c.execute("SELECT days FROM keys WHERE key_code = ? AND is_used = 0", (code,))
        row = c.fetchone()
        if not row: return False
        days = row['days']
        expiry = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
        c.execute("UPDATE keys SET is_used = 1, used_by = ? WHERE key_code = ?", (uid, code))
        c.execute("INSERT INTO users (user_id, role, vip_expiry) VALUES (?, 'VIP', ?) ON CONFLICT(user_id) DO UPDATE SET role='VIP', vip_expiry=excluded.vip_expiry", (uid, expiry))
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
        return {'vips': vips, 'sellers': sellers, 'searches': total_searches}
    
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

db = Database(config.DB_FILE)

# Estado Global
allowed_groups: Set[int] = set()
search_memory_cache = LRUCache(maxsize=100)
auto_download_enabled = False 
pending_downloads: List[Dict[str, Any]] = []
active_downloads: Set[str] = set()

# =============================================================================
# LÓGICA Y ROLES
# =============================================================================

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
    if uid in config.ADMIN_IDS: return UserRole.ADMIN
    user = db.get_user(uid)
    role_str = user.get('role', 'FREE')
    if role_str == 'SELLER': return UserRole.SELLER
    if role_str == 'VIP':
        exp = user.get('vip_expiry')
        if exp:
            try:
                if datetime.now(timezone.utc) < datetime.fromisoformat(exp): return UserRole.VIP
            except: pass
    return UserRole.FREE

def normalizar_url(url: str) -> str:
    url = url.strip().lower()
    for p in ['https://', 'http://', 'www.']:
        if url.startswith(p): url = url[len(p):]
    return url.split('/')[0].split('?')[0]

# =============================================================================
# MOTOR DE BÚSQUEDA (OPTIMIZADO Y FILTRADO)
# =============================================================================
# =============================================================================
# MOTOR DE BÚSQUEDA (OPTIMIZADO Y FILTRADO)
# =============================================================================

# =============================================================================
# MOTOR DE BÚSQUEDA (MEJORADO Y SIN DUPLICADOS)
# =============================================================================

executor = ThreadPoolExecutor(max_workers=config.MAX_WORKERS)

def _search_file(path: Path, kw: str, modo: SearchMode) -> List[str]:
    # Usamos set para velocidad y eliminación automática de duplicados
    res_set = set()
    enc_kw = kw.lower().encode()
    
    # Regex compilado para validación estricta de email
    email_regex = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    
    try:
        with open(path, 'rb') as f:
            # Lectura con mmap para alta velocidad
            with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                for line in iter(mm.readline, b''):
                    try:
                        # 1. Filtro rápido por palabra clave (bytes) antes de procesar
                        if enc_kw not in line.lower(): continue
                        
                        decoded = line.decode('utf-8', 'ignore').strip()
                        if not decoded: continue

                        if modo == SearchMode.ULP:
                            # ULP: Guardar línea completa tal cual (sin duplicados)
                            res_set.add(decoded)
                            
                        elif modo == SearchMode.MAIL or modo == SearchMode.USERPASS:
                            # --- FILTRO MEJORADO ---
                            
                            # Normalizar separadores
                            clean_line = decoded.replace("|", ":").replace(";", ":")
                            parts = [p.strip() for p in clean_line.split(":") if p.strip()]
                            
                            user = ""
                            password = ""
                            
                            # Detectar formato flexible (URL:USER:PASS o USER:PASS)
                            if len(parts) >= 3:
                                # Formato URL:USER:PASS -> Tomar los dos últimos
                                user = parts[-2]
                                password = parts[-1]
                            elif len(parts) == 2:
                                # Formato USER:PASS directo
                                user = parts[0]
                                password = parts[1]
                            else:
                                continue # Línea con formato incorrecto

                            if not user or not password: continue

                            # --- LÓGICA DE SEPARACIÓN ---
                            
                            if modo == SearchMode.MAIL:
                                # Modo MAIL: Solo aceptar si es un email válido
                                if email_regex.match(user):
                                    res_set.add(f"{user}:{password}")
                                    
                            elif modo == SearchMode.USERPASS:
                                # Modo USER: Solo aceptar si NO es email (para evitar mezclas)
                                if "@" not in user:
                                    res_set.add(f"{user}:{password}")

                    except Exception: 
                        pass
    except Exception: 
        pass
        
    return list(res_set)

async def search_engine(kw: str, time_opt: str, modo: SearchMode) -> Optional[Path]:
    loop = asyncio.get_event_loop()
    dirs = []
    if time_opt in ['24h', 'all']: dirs.append(config.DIR_DOWNLOADS)
    if time_opt in ['old', 'all']: dirs.append(config.DIR_ARCHIVE)
    
    files = [f for d in dirs for f in d.glob('*.txt')]
    if not files: return None

    # Búsqueda paralela
    tasks = [loop.run_in_executor(executor, _search_file, f, kw, modo) for f in files] 
    results = await asyncio.gather(*tasks)
    
    # Unificar resultados y eliminar duplicados globales
    final = set()
    for r in results: 
        final.update(r)
    
    if not final: return None
    
    out = config.DIR_CACHE / f"result_{int(time.time())}.txt"
    with open(out, 'w', encoding='utf-8') as f: f.write('\n'.join(final))
    return out

# =============================================================================
# SISTEMA DE ARCHIVOS Y ESCUCHA AUTOMÁTICA
# =============================================================================

def get_file_counts() -> Dict[str, int]:
    count_24h = len(list(config.DIR_DOWNLOADS.glob('*.txt')))
    count_old = len(list(config.DIR_ARCHIVE.glob('*.txt')))
    return {'total': count_24h + count_old, '24h': count_24h, 'old': count_old}

async def mover_y_limpiar_archivos():
    ahora = time.time()
    segundos_24h = 86400
    segundos_3d = 259200

    for f in config.DIR_DOWNLOADS.glob('*.txt'):
        try:
            if (ahora - f.stat().st_mtime) > segundos_24h:
                dest = config.DIR_ARCHIVE / f.name
                if dest.exists(): dest.unlink()
                f.rename(dest)
        except: pass

    for f in config.DIR_ARCHIVE.glob('*.txt'):
        try:
            if (ahora - f.stat().st_mtime) > segundos_3d:
                f.unlink()
        except: pass

async def _download_large_file_task(event, filename: str, dest_path: Path):
    try:
        logger.info(f"📥 [Stream-DL] Iniciando descarga: {filename}")
        await event.download_media(file=str(dest_path))
        
        if dest_path.exists() and dest_path.stat().st_size > 0:
            logger.info(f"✅ [Stream-DL] Completado: {filename} ({dest_path.stat().st_size / 1024 / 1024:.2f} MB)")
        else:
            logger.warning(f"⚠️ [Stream-DL] Archivo vacío o error: {filename}")
            if dest_path.exists(): dest_path.unlink()
            
    except Exception as e:
        logger.error(f"❌ [Stream-DL] Error en {filename}: {e}")
        if dest_path.exists():
            try: dest_path.unlink()
            except: pass
    finally:
        active_downloads.discard(filename)

async def realtime_listener(event):
    global pending_downloads, auto_download_enabled
    
    try:
        if not event.document: return
        
        filename = None
        for attr in event.document.attributes:
            if isinstance(attr, DocumentAttributeFilename): 
                filename = attr.file_name
        
        if not filename or not filename.lower().endswith('.txt'): return
        
        text_content = event.message.message or ""
        text_lower = text_content.lower()
        filename_lower = filename.lower()
        
        keywords = ["ulp", "url:log:pass", "url:pass", "combo", "database", "leak"]
        if not any(k in filename_lower for k in keywords):
            if not any(k in text_lower for k in keywords):
                return

        dest_path = config.DIR_DOWNLOADS / filename
        
        if dest_path.exists() and dest_path.stat().st_size > 0:
            return
            
        if filename in active_downloads:
            return

        if auto_download_enabled:
            active_downloads.add(filename)
            asyncio.create_task(_download_large_file_task(event, filename, dest_path))
            
        else:
            if not any(p['msg_id'] == event.id for p in pending_downloads):
                chat = await event.get_chat()
                chat_name = getattr(chat, 'title', f"Chat {event.chat_id}")
                pending_downloads.append({
                    'chat_id': event.chat_id,
                    'msg_id': event.id,
                    'filename': filename,
                    'chat_name': chat_name
                })
                logger.info(f"📝 [Pendiente] Detectado: {filename}")
                
    except Exception as e:
        logger.error(f"Error crítico en listener: {e}")

async def process_pending_downloads(status_msg=None):
    global pending_downloads
    if not pending_downloads:
        if status_msg: await status_msg.edit("❌ No hay archivos pendientes.")
        return

    total = len(pending_downloads)
    stats = {'new': 0, 'existing': 0, 'errors': 0}
    start_time = time.time()
    
    if status_msg: await status_msg.edit(f"📥 **Descargando {total} archivos pendientes...**")
    
    to_download = list(pending_downloads)
    pending_downloads = [] 
    
    for item in to_download:
        try:
            msg = await userbot.get_messages(item['chat_id'], ids=item['msg_id'])
            if not msg or not msg.document: continue
            
            dest_path = config.DIR_DOWNLOADS / item['filename']
            
            if dest_path.exists() and dest_path.stat().st_size > 0:
                stats['existing'] += 1
                continue

            if status_msg:
                try: await status_msg.edit(f"📥 ({stats['new']+stats['existing']+1}/{total}):\n`{item['filename'][:40]}`")
                except: pass
            
            await msg.download_media(file=str(dest_path))
            
            if dest_path.exists() and dest_path.stat().st_size > 0:
                stats['new'] += 1
            else:
                stats['errors'] += 1
                
            await asyncio.sleep(0.5)
        except Exception as e:
            logger.error(f"Error descargando pendiente: {e}")
            stats['errors'] += 1

    elapsed = time.time() - start_time
    
    if status_msg:
        report = (
            "✅ **DESCARGA FINALIZADA**\n\n"
            f"📥 Descargados nuevos: `{stats['new']}`\n"
            f"💾 Ya existentes: `{stats['existing']}`\n"
            f"❌ Errores: `{stats['errors']}`\n"
            f"⏱️ Tiempo: `{elapsed:.1f}s`"
        )
        await status_msg.edit(report, buttons=Keyboards.back("adm_files"), parse_mode='md')

# =============================================================================
# INTERFAZ DE USUARIO
# =============================================================================
class UI:
    @staticmethod
    def text(key: str, lang: str = 'es', *args) -> str:
        localized = locale_manager.get(key, lang, *args)
        if localized:
            return localized

        msgs = {
            "welcome":
                "────────────────────────────────\n"
                "          ☾ HJ & GHOST ULP ☽     \n"
                "────────────────────────────────\n\n"
                "✦━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━✦\n"
                "          ✧ CARACTERÍSTICAS ✧\n"
                "✦━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━✦\n"
                "⚡ Búsqueda ultra rápida (paralela)\n"
                "🟢 Bases actualizadas 24/7\n"
                "🛡️ Privacidad & anonimato\n"
                "👑 Búsquedas ilimitadas\n\n"
                "✦━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━✦\n"
                "             ✧ COMANDOS ✧\n"
                "✦━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━✦\n"
                "➤ /start\n"
                "➤ /url\n"
                "✦━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━✦\n"
                "              ✧ SOPORTE ✧\n"
                "✦━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━✦\n"
                "✧ @hjofc20\n"
                "✧ @Ghosthat_Real1\n\n"
                "─────────────────────────────   ⋆｡°✩ DATABASES ✩°｡⋆     \n"
                "────────────────────────────\n\n"
                "⚡ Búsquedas privadas\n"
                "🟢 Bases actualizadas 24/7\n\n"
                "👤 **Tu Rol:** `{}`\n"
                "📊 **Búsquedas:** `{}`",

            "buy_vip_info": 
                "💰 **COMPRAR VIP**\n\n"
                "💲 **PRECIOS:**\n"
                "⟡ 1d » 6$\n"
                "⟡ 3d » 10$\n"
                "⟡ 7d » 25$\n"
                "⟡ 30d » 100$\n\n"
                "📬 **CONTACTO:**\n"
                "{}",

            "file_management": 
                "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "📊 **Estadísticas del Sistema:**\n\n"
                "📁 **Total Archivos:** `{}`\n"
                "⚡ **Últimas 24h:** `{}`\n"
                "🗄️ **Histórico:** `{}`\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "🔄 **Estado Descarga:** \n\n"
                "📡 **Estado:** 🎧 Escucha Activa\n"
                "♻️ **Auto-Descarga:** `{}`\n"
                "📝 **En Cola:** `{}` archivos\n"
                "⬇️ **Descargando:** `{}` activos",
            
            "no_results": "❌ **SIN RESULTADOS**\n\nNo se encontraron datos para `{}`.",
            "search_step_time": "🔍 **Dominio:** `{}`\n\n⏳ Selecciona el rango de tiempo.",
            "loading": "⚙️ **Procesando...**",
            "access_denied": "🚫 **ACCESO DENEGADO**\n\nSolo usuarios VIP pueden buscar.",
            "ask_domain": "🔍 **NUEVA BÚSQUEDA**\n\nEscribe el dominio:",
            
            "language_selected": "🌐 Idioma actualizado correctamente.",
            "select_language": "🌐 **SELECT LANGUAGE / IDIOMA / IDIOMA**\n\nChoose your preferred language:"
        }
        return msgs.get(key, key).format(*args)

class Keyboards:
    @staticmethod
    def main(role: UserRole, lang: str = 'es'):
        lang_btn = [Button.inline(" 🌐 Idioma / Language ", b"ch_lang")]
        
        if role == UserRole.FREE:
            return [
                [Button.inline(" 💰 COMPRAR VIP ", b"buy_vip_info")],
                [Button.inline(" 👤 Mi Cuenta ", b"my_account")],
                lang_btn
            ]
        elif role == UserRole.VIP:
            return [
                [Button.inline(" 🔍 NUEVA BÚSQUEDA ", b"search_init")],
                [Button.inline(" 👤 Mi Cuenta ", b"my_account")],
                lang_btn
            ]
        elif role == UserRole.SELLER:
            return [
                [Button.inline(" 🔍 NUEVA BÚSQUEDA ", b"search_init")],
                [Button.inline(" 🔑 GENERAR KEY ", b"seller_genkey")],
                [Button.inline(" 👤 Mi Cuenta ", b"my_account")]
            ]
        elif role == UserRole.ADMIN:
            return [
                [Button.inline(" 🔍 NUEVA BÚSQUEDA ", b"search_init")],
                [Button.inline(" 🔐 PANEL ADMIN ", b"admin_enter")],
                [Button.inline(" 📂 GESTIÓN ARCHIVOS ", b"adm_files")],
                [Button.inline(" 👤 Mi Cuenta ", b"my_account")]
            ]
        return []

    @staticmethod
    def time():
        return [
            [Button.inline(" ⚡ Últimas 24h ", b"time_24h")],
            [Button.inline(" 🗂️ 24h + Antiguos ", b"time_all")],
            [Button.inline(" 📅 Antiguos ", b"time_old")],
            [Button.inline(" ❌ Cancelar ", b"back_main")]
        ]

    @staticmethod
    def formats():
        return [
            [Button.inline(" 📄 ULP ", b"fmt_ulp")],
            [Button.inline(" 📧 MAIL:PASS ", b"fmt_mail")],
            [Button.inline(" 👤 USER:PASS ", b"fmt_user")],
            [Button.inline(" ❌ Cancelar ", b"back_main")]
        ]
    
    @staticmethod
    def no_results(kw: str):
        return [
            [Button.inline(" ⚠️ REPORTAR URL ", b"report_url")],
            [Button.inline(" 🔙 Volver ", b"back_main")]
        ]

    @staticmethod
    def admin():
        return [
            [Button.inline(" 👑 Ver VIPs ", b"adm_vips"), Button.inline(" 💼 Sellers ", b"adm_sellers")],
            [Button.inline(" 🔑 Generar Key ", b"adm_genkey")],
            [Button.inline(" 📊 Stats ", b"adm_stats")],
            [Button.inline(" 📂 Gestión Archivos ", b"adm_files")],
            [Button.inline(" 🔙 Volver ", b"back_main")]
        ]
    
    @staticmethod
    def gen_key():
        return [
            [Button.inline(" 1 Día ", b"gen_1"), Button.inline(" 7 Días ", b"gen_7")],
            [Button.inline(" 30 Días ", b"gen_30")],
            [Button.inline(" 🔙 Volver ", b"back_main")]
        ]
    
    @staticmethod
    def files_control(auto_dl: bool, pending_count: int, active_count: int):
        if auto_dl:
            btn_auto = Button.inline(" ✅ Auto-Descarga ON ", b"toggle_auto_off")
        else:
            btn_auto = Button.inline(" ❌ Auto-Descarga OFF ", b"toggle_auto_on")

        row1 = [btn_auto]
        row2 = [Button.inline(f" 📥 Descargar Pendientes ({pending_count}) ", b"dl_all")]
        row3 = [Button.inline(" 🗑️ Vaciar Pendientes ", b"clear_pending")]
        row_refresh = [Button.inline(" 🔄 Refrescar ", b"refresh_files")] 
        row_back = [Button.inline(" 🔙 Volver ", b"admin_enter")] 
        
        return [
            row1,
            row2,
            row3,
            row_refresh,
            row_back
        ]
    
    @staticmethod
    def language_selection():
        return [
            [Button.inline(" 🇪🇸 Español ", b"set_lang_es")],
            [Button.inline(" 🇬🇧 English ", b"set_lang_en")],
            [Button.inline(" 🇧🇷 Português ", b"set_lang_pt")],
            [Button.inline(" 🔙 Volver ", b"back_main")]
        ]

    @staticmethod
    def back(data: str = "back_main"):
        return [[Button.inline(" 🔙 Volver ", data.encode())]]

# =============================================================================
# CLIENTES
# =============================================================================

bot = TelegramClient(config.BOT_SESSION, config.API_ID, config.API_HASH)
userbot = TelegramClient(config.USER_SESSION, config.API_ID, config.API_HASH)
temp_state: Dict[int, dict] = {}

# =============================================================================
# HANDLERS
# =============================================================================

@bot.on(events.NewMessage(pattern="/start"))
async def start(e):
    uid = e.sender_id
    user = db.get_user(uid)
    lang = user.get('language', 'es')
    role = get_user_role(uid)
    
    args = e.message.message.split()
    if len(args) > 1:
        code = args[1]
        if db.redeem(uid, code):
            role = get_user_role(uid)
            await e.reply(f"🎉 **¡Felicidades!**\n\nTu cuenta ha sido activada.", buttons=Keyboards.main(role, lang))
            return

    await e.reply(UI.text("welcome", lang, role.value, user['search_count']), buttons=Keyboards.main(role, lang), parse_mode='md')

@bot.on(events.NewMessage(pattern=r"/vip (\d+)"))
async def cmd_vip_perm(e):
    if get_user_role(e.sender_id) != UserRole.ADMIN: return
    uid = int(e.pattern_match.group(1))
    db.set_role(uid, 'VIP', days=36500)
    await e.reply(f"✅ Usuario `{uid}` ahora es **VIP Permanente**.", parse_mode='md')

@bot.on(events.NewMessage(pattern=r"/seller (\d+)"))
async def cmd_seller(e):
    if get_user_role(e.sender_id) != UserRole.ADMIN: return
    uid = int(e.pattern_match.group(1))
    db.set_role(uid, 'SELLER')
    await e.reply(f"✅ Usuario `{uid}` promovido a **SELLER**.", parse_mode='md')

@bot.on(events.NewMessage(pattern=r"/unseller (\d+)"))
async def cmd_unseller(e):
    if get_user_role(e.sender_id) != UserRole.ADMIN: return
    uid = int(e.pattern_match.group(1))
    db.set_role(uid, 'USER')
    await e.reply(f"❌ Usuario `{uid}` removido de **SELLER**.", parse_mode='md')
    
@bot.on(events.NewMessage(pattern=r"/unvip (\d+)"))
async def cmd_unvip(e):
    if get_user_role(e.sender_id) != UserRole.ADMIN: return
    uid = int(e.pattern_match.group(1))
    db.remove_vip(uid)
    await e.reply(f"🗑️ Usuario `{uid}` eliminado de VIP.", parse_mode='md')
    
@bot.on(events.NewMessage(pattern=r"/gp"))
async def cmd_gp(e):
    if get_user_role(e.sender_id) != UserRole.ADMIN: return
    if not e.is_group: return
    allowed_groups.add(e.chat_id)
    await e.reply("✅ Grupo añadido a la lista permitida.")

@bot.on(events.NewMessage(pattern=r"/ungp"))
async def cmd_ungp(e):
    if get_user_role(e.sender_id) != UserRole.ADMIN: return
    if not e.is_group: return
    if e.chat_id in allowed_groups:
        allowed_groups.discard(e.chat_id)
        await e.reply("🗑️ Grupo eliminado de la lista permitida.")

@bot.on(events.NewMessage(pattern=r"/url (.+)"))
async def cmd_url(e):
    uid = e.sender_id
    user = db.get_user(uid)
    lang = user.get('language', 'es')
    role = get_user_role(uid)
    if role == UserRole.FREE: return await e.reply(UI.text("access_denied", lang), buttons=Keyboards.back(), parse_mode='md')
    kw = normalizar_url(e.pattern_match.group(1))
    temp_state[uid] = {'kw': kw}
    await e.reply(UI.text("search_step_time", lang, kw), buttons=Keyboards.time(), parse_mode='md')

# --- COMANDOS DE BROADCAST ---

@bot.on(events.NewMessage(pattern=r"/bc (.+)"))
async def cmd_bc(e):
    if get_user_role(e.sender_id) != UserRole.ADMIN: return
    msg_text = e.pattern_match.group(1)
    users = db.get_all_users()
    total = len(users)
    if total == 0:
        await e.reply("❌ No hay usuarios registrados para broadcast.")
        return

    status = await e.reply(f"📣 **Broadcast Global Iniciado**\n\n👥 Total usuarios: `{total}`\n⚡ Enviando...")
    sent = 0
    errors = 0
    
    for uid in users:
        try:
            await bot.send_message(uid, msg_text, parse_mode='md')
            sent += 1
            await asyncio.sleep(0.05) 
            if sent % 50 == 0:
                try:
                    await status.edit(f"📣 **Broadcast Global**\n\n✅ Enviados: `{sent}/{total}`\n❌ Errores: `{errors}`")
                except: pass
        except UserIsBlockedError:
            errors += 1
        except InputUserDeactivatedError:
            errors += 1
        except Exception:
            errors += 1
            await asyncio.sleep(1)

    await status.edit(f"✅ **Broadcast Finalizado**\n\n📬 Enviados: `{sent}`\n🚫 Fallidos: `{errors}`")

@bot.on(events.NewMessage(pattern=r"/bcvip (.+)"))
async def cmd_bcvip(e):
    if get_user_role(e.sender_id) != UserRole.ADMIN: return
    msg_text = e.pattern_match.group(1)
    vips_data = db.list_vips()
    total = len(vips_data)
    if total == 0:
        await e.reply("❌ No hay usuarios VIP para broadcast.")
        return

    status = await e.reply(f"👑 **Broadcast VIP Iniciado**\n\n👥 Total VIPs: `{total}`\n⚡ Enviando...")
    sent = 0
    errors = 0

    for data in vips_data:
        uid = data['user_id']
        try:
            await bot.send_message(uid, msg_text, parse_mode='md')
            sent += 1
            await asyncio.sleep(0.05)
            if sent % 20 == 0:
                try:
                    await status.edit(f"👑 **Broadcast VIP**\n\n✅ Enviados: `{sent}/{total}`\n❌ Errores: `{errors}`")
                except: pass
        except UserIsBlockedError:
            errors += 1
        except InputUserDeactivatedError:
            errors += 1
        except Exception:
            errors += 1
            await asyncio.sleep(1)

    await status.edit(f"✅ **Broadcast VIP Finalizado**\n\n📬 Enviados: `{sent}`\n🚫 Fallidos: `{errors}`")

@bot.on(events.NewMessage)
async def handle_conversation(e):
    if e.is_private:
        uid = e.sender_id
        user = db.get_user(uid)
        lang = user.get('language', 'es')
        if uid in temp_state and temp_state[uid].get('step') == 'WAITING_KEYWORD':
            kw = normalizar_url(e.text)
            temp_state[uid] = {'kw': kw}
            await e.reply(UI.text("search_step_time", lang, kw), buttons=Keyboards.time(), parse_mode='md')

# =============================================================================
# CALLBACKS
# =============================================================================

@bot.on(events.CallbackQuery)
async def callbacks(e):
    global auto_download_enabled, pending_downloads
    
    uid = e.sender_id
    user = db.get_user(uid)
    lang = user.get('language', 'es')
    role = get_user_role(uid)
    data = e.data.decode()

    try:
        if data == "back_main":
            await e.edit(UI.text("welcome", lang, role.value, user['search_count']), buttons=Keyboards.main(role, lang), parse_mode='md')
        
        elif data == "my_account":
            exp = user['vip_expiry'][:10] if user['vip_expiry'] else "N/A"
            await e.edit(f"👤 **MI CUENTA**\n\n🆔 ID: `{uid}`\n🎖 Rango: `{role.value}`\n📅 Expira: `{exp}`", buttons=Keyboards.back(), parse_mode='md')

        elif data == "buy_vip_info":
            contacts = "\n".join(config.SELLER_USERNAMES)
            await e.edit(UI.text("buy_vip_info", lang, contacts), buttons=Keyboards.back(), parse_mode='md')

        # --- GESTIÓN DE IDIOMA ---
        elif data == "ch_lang":
            await e.edit(UI.text("select_language", lang), buttons=Keyboards.language_selection(), parse_mode='md')
        
        elif data.startswith("set_lang_"):
            new_lang = data.split("_")[2]
            db.set_language(uid, new_lang)
            await e.answer(UI.text("language_selected", new_lang), alert=True)
            user = db.get_user(uid)
            await e.edit(UI.text("welcome", new_lang, role.value, user['search_count']), buttons=Keyboards.main(role, new_lang), parse_mode='md')

        # --- GESTIÓN DE ARCHIVOS ---
        elif data == "adm_files" or data == "refresh_files":
            if role != UserRole.ADMIN: return
            counts = get_file_counts()
            auto_status = "🟢 ON" if auto_download_enabled else "🔴 OFF"
            
            await e.edit(
                UI.text("file_management", lang, counts['total'], counts['24h'], counts['old'], auto_status, len(pending_downloads), len(active_downloads)), 
                buttons=Keyboards.files_control(auto_download_enabled, len(pending_downloads), len(active_downloads)), 
                parse_mode='md'
            )

        elif data == "toggle_auto_on":
            if role != UserRole.ADMIN: return
            auto_download_enabled = True
            await e.answer("✅ Auto-Descarga ACTIVADA. Descargas en streaming.", alert=True)
            counts = get_file_counts()
            await e.edit(UI.text("file_management", lang, counts['total'], counts['24h'], counts['old'], "🟢 ON", len(pending_downloads), len(active_downloads)), buttons=Keyboards.files_control(True, len(pending_downloads), len(active_downloads)), parse_mode='md')

        elif data == "toggle_auto_off":
            if role != UserRole.ADMIN: return
            auto_download_enabled = False
            await e.answer("🔴 Auto-Descarga DESACTIVADA.", alert=True)
            counts = get_file_counts()
            await e.edit(UI.text("file_management", lang, counts['total'], counts['24h'], counts['old'], "🔴 OFF", len(pending_downloads), len(active_downloads)), buttons=Keyboards.files_control(False, len(pending_downloads), len(active_downloads)), parse_mode='md')

        elif data == "dl_all":
            if role != UserRole.ADMIN: return
            if not pending_downloads: return await e.answer("No hay pendientes.", alert=True)
            msg = await e.edit("📥 **Procesando pendientes...**", buttons=None)
            asyncio.create_task(process_pending_downloads(msg))

        elif data == "clear_pending":
            if role != UserRole.ADMIN: return
            pending_downloads.clear()
            await e.edit("🗑️ **Lista vaciada.**", buttons=Keyboards.back("adm_files"))

        # --- BÚSQUEDA ---
        elif data == "search_init":
            if role == UserRole.FREE: return await e.answer("🚫 Necesitas VIP.", alert=True)
            temp_state[uid] = {'step': 'WAITING_KEYWORD'}
            await e.edit(UI.text("ask_domain", lang), buttons=Keyboards.back(), parse_mode='md')

        elif data.startswith("time_"):
            t_opt = data.split("_")[1]
            if uid in temp_state and temp_state[uid].get('kw'):
                temp_state[uid]['time'] = t_opt
                await e.edit("📄 **Formato de salida:**", buttons=Keyboards.formats(), parse_mode='md')
            else: await e.answer("Error: Usa 'Nueva Búsqueda' primero.", alert=True)

        elif data.startswith("fmt_"):
            if uid not in temp_state or not temp_state[uid].get('kw'): 
                return await e.answer("Sesión expirada.", alert=True)
            
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
            
            # INICIO CARGA ANIMADA SOLICITADA
            frames = ["🔄", "🔄", "↪️", "↩️", "⤴️", "↪️"]
            msg = await e.edit("⚙️ Procesando...\n🔄", buttons=None, parse_mode='md')

            # Crear tarea de búsqueda
            search_task = asyncio.create_task(search_engine(kw, t_opt, modo))

            i = 0
            while not search_task.done():
                await asyncio.sleep(0.8)  # velocidad animación
                frame = frames[i % len(frames)]
                try:
                    await msg.edit(f"⚙️ **Procesando...**\n{frame}", parse_mode='md')
                except MessageNotModifiedError:
                    pass
                except Exception:
                    pass
                i += 1

            result_file = await search_task
            # FIN CARGA ANIMADA
            
            if result_file:
                db.add_search(uid)
                count = sum(1 for _ in open(result_file))
                await e.delete()
                await bot.send_file(uid, result_file, caption=f"✅ **BÚSQUEDA COMPLETADA**\n\n🔍 Dominio: `{kw}`\n📑 Tipo: `{tipo_texto}`\n📊 Resultados: `{count}`", parse_mode='md')
                try: os.remove(result_file)
                except: pass
            else:
                await e.edit(UI.text("no_results", lang, kw), buttons=Keyboards.no_results(kw), parse_mode='md')
        
        # --- REPORTAR URL ---
        elif data == "report_url":
            kw = temp_state.get(uid, {}).get('kw', 'Desconocido')
            for admin_id in config.ADMIN_IDS:
                try:
                    await bot.send_message(admin_id, f"⚠️ **REPORTE DE URL**\n\n👤 Usuario: `{uid}`\n🔍 URL: `{kw}`")
                except: pass
            await e.answer("✅ Reporte enviado a los desarrolladores.", alert=True)

        elif data == "admin_enter":
            if role != UserRole.ADMIN: return
            stats = db.get_stats()
            await e.edit(f"🔐 **PANEL ADMIN**\n\n👑 VIPs: `{stats['vips']}`\n💼 Sellers: `{stats['sellers']}`\n🔍 Búsquedas: `{stats['searches']}`", buttons=Keyboards.admin(), parse_mode='md')

        elif data == "adm_stats":
            if role != UserRole.ADMIN: return
            stats = db.get_stats()
            text = (
                "📊 **ESTADÍSTICAS GLOBALES**\n\n"
                f"👑 Usuarios VIP: `{stats['vips']}`\n"
                f"💼 Sellers: `{stats['sellers']}`\n"
                f"🔍 Búsquedas Totales: `{stats['searches']}`"
            )
            await e.edit(text, buttons=Keyboards.back("admin_enter"), parse_mode='md')

        elif data == "adm_sellers":
            if role != UserRole.ADMIN: return
            sellers = db.list_sellers()
            if not sellers:
                text = "💼 **LISTA DE SELLERS**\n\nNo hay sellers registrados."
            else:
                lines = [f"👤 ID: `{s}`" for s in sellers]
                text = "💼 **LISTA DE SELLERS**\n\n" + "\n".join(lines)
            await e.edit(text, buttons=Keyboards.back("admin_enter"), parse_mode='md')

        elif data == "adm_genkey":
            await e.edit("🔑 **Generador**", buttons=Keyboards.gen_key())
        
        # --- FIX: SELLER GENKEY ---
        elif data == "seller_genkey":
            await e.edit("🔑 **Generador**", buttons=Keyboards.gen_key())
        
        elif data.startswith("gen_"):
            days = int(data.split("_")[1])
            code = db.gen_key(uid, days)
            link = f"https://t.me/{config.BOT_USERNAME}?start={code}"
            
            msg = (
                "✅ **KEY GENERADA EXITOSAMENTE**\n\n"
                f"🔑 Código:\n`{code}`\n\n"
                f"🔗 Link de canje:\n{link}\n\n"
                f"📅 Días: {days}"
            )
            await e.edit(msg, buttons=Keyboards.back("admin_enter"), parse_mode='md')

        elif data == "adm_vips":
            vips = db.list_vips()
            text = "👑 **LISTA DE VIPs**\n\n" + "\n".join([f"👤 `{v['user_id']}` | 📅 {v['vip_expiry'][:10] if v['vip_expiry'] else 'N/A'}" for v in vips[:20]])
            await e.edit(text, buttons=Keyboards.back("admin_enter"), parse_mode='md')

    except MessageNotModifiedError: pass
    except Exception as ex: logger.error(f"Error callback: {ex}")

# =============================================================================
# INICIO
# =============================================================================

async def main():
    logger.info("🚀 Iniciando Bot HJ & GHOST Pro...")
    await bot.start(bot_token=config.BOT_TOKEN)
    await userbot.start()
    
    userbot.add_event_handler(realtime_listener, events.NewMessage)
    logger.info("🎧 Escucha automática de archivos ACTIVADA (Streaming Mode).")
    
    await mover_y_limpiar_archivos()
    
    logger.info("✅ Sistema operativo.")
    await bot.run_until_disconnected()

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: logger.info("🛑 Apagando...")
