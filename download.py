"""
═══════════════════════════════════════════════════════════════
  HJ ULP EXTRACTOR BOT — Download System Module v3.4
═══════════════════════════════════════════════════════════════
  • Download de archivos hasta 4GB con streaming + progreso
  • Progress updates con task cancellation (sin pileup)
  • FloodWait backoff adaptativo (no spam a Telegram)
  • Auto-limpieza de archivos expirados
  • Cola secuencial para evitar FloodWait
═══════════════════════════════════════════════════════════════
"""

import os
import re
import asyncio
import time
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable

from telethon.errors import (
    MessageNotModifiedError, FloodWaitError,
    TimedOutError, FileReferenceExpiredError
)
from telethon.tl.types import DocumentAttributeFilename

from config import config
from logger_setup import logger
from utils import format_size, format_time, progress_bar
from database import db

# FIX: Usar `import state` en vez de `from state import X`
import state


# ═════════════════════════════════════════════════════════════
# v4.2.11 — Detector de variantes HOTMAIL en el nombre del archivo
# ═════════════════════════════════════════════════════════════
# Detecta obfuscaciones típicas de "hotmail" en filenames:
#   hotmail, hotmails, hotma1il, hotma¡l, h0tmail, hotm4il,
#   hotmai1, hot__ma!l, HOTMAIL-2024.txt, etc.
_LEET_TABLE = str.maketrans({
    '0': 'o', '1': 'i', '4': 'a', '3': 'e', '5': 's', '7': 't', '8': 'b',
    '@': 'a', '¡': 'i', '!': 'i', '|': 'l', '$': 's', '+': 't', '¢': 'c',
    '€': 'e', '£': 'l', '¦': 'i', '·': '', '·': '',
})


def _levenshtein(a: str, b: str) -> int:
    """Damerau-Levenshtein (con transposición de adyacentes) para strings cortos."""
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if la == 0:
        return lb
    if lb == 0:
        return la
    d = [[0] * (lb + 1) for _ in range(la + 1)]
    for i in range(la + 1):
        d[i][0] = i
    for j in range(lb + 1):
        d[0][j] = j
    for i in range(1, la + 1):
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[la][lb]


def _fuzzy_hotmail(norm: str) -> bool:
    """Busca una ventana de 7-9 letras con distancia <=1 de 'hotmail'.

    Cubre inserciones/duplicados tipo hotma1il → hotmaiil (dist 1).
    """
    target = "hotmail"
    n = len(norm)
    if n < 7:
        return False
    for size in (7, 8, 9):
        if size > n:
            break
        for i in range(n - size + 1):
            if _levenshtein(norm[i:i + size], target) <= 1:
                return True
    return False


def es_nombre_hotmail(filename: str) -> bool:
    """True si el nombre del archivo contiene 'hotmail' (aunque esté ofuscado).

    Normaliza en 2 pasadas para cubrir ambas ambigüedades del '1' y aplica
    matching fuzzy (distancia <=1) para obfuscaciones con letras extra:
      • hotma1il, hotma¡l, h0tma!l, hotm4il, hotmai1, hot__mails, ...
    Ignora separadores ( _ - . espacio ) y mayúsculas.
    """
    if not filename:
        return False
    base = filename.lower()

    # Pasada 1: leet estándar (1→i) + solo letras
    norm = base.translate(_LEET_TABLE)
    norm = re.sub(r'[^a-z]', '', norm)
    if 'hotmail' in norm or _fuzzy_hotmail(norm):
        return True

    # Pasada 2: variante 1→l (hotmai1 → hotmail)
    norm2 = re.sub(r'[^a-z0-9]', '', base).replace('1', 'l')
    if 'hotmail' in norm2 or _fuzzy_hotmail(norm2):
        return True

    return False


def destino_hotmail(filename: str) -> Path:
    """Destino correcto para un .txt: carpeta HOTMAIL (sin mínimo) o descargas generales."""
    if es_nombre_hotmail(filename):
        return config.DIR_HOTMAIL / filename
    return config.DIR_DOWNLOADS / filename


# ═════════════════════════════════════════════════════════════
# v4.2.16 — Detector de variantes IMAP/MAIL en el nombre
# v4.2.26 — tipo MIX ELIMINADO: solo mail / mailaccess (+ variantes)
# ═════════════════════════════════════════════════════════════
# Silo "mail access" (paralelo al silo hotmail). Detecta ofuscaciones de:
#   mail · m4il · ma¡l · ma1l · ma!l · mails
#   mailaccess · ma¡l4access · mail4access · mail acces(s)
# (v4.2.26: mix/m1x/m¡x/m!x/mixs YA NO entran al silo imap —
#  _IMAP_TOKENS_EXACT los retiró; quedan solo en _MIX_TOKENS_EXACT
#  para que el extractor /imap salte los archivos mix LEGACY.)
# Prioridad: si el nombre ya es HOTMAIL (v4.2.11), NO cuenta como imap
# (los silos quedan separados: "hotmail mix.txt" → silo hotmail).

# Tokens que identificación EXACTA tras normalizar leet
_IMAP_TOKENS_EXACT = {'mail', 'mails', 'mailacces', 'mailaccess'}

# v4.2.26: tokens MIX retirados del silo IMAP. Se conservan SOLO para
# identificar archivos mix LEGACY ya descargados y que el extractor
# /imap los salte (search.imap_extract_engine).
_MIX_TOKENS_EXACT = {'mix', 'mixs'}

# Fuzzy (distancia <=1) solo contra estas palabras, y solo para tokens que
# empiezan por 'm' (evita falsos positivos tipo nail/bail/email/gmail)
_IMAP_FUZZY_TARGETS = ('mail', 'mails', 'mailaccess')


def es_nombre_imap(filename: str) -> bool:
    """True si el nombre del archivo es de una base MAIL/MAILACCESS.

    Normaliza leet (1/!/¡→i, 4→a, 0→o, 3→e, 5→s...) y parte el nombre en
    tokens alfanuméricos. Un token cuenta si:
      • es exactamente una variante conocida (mail, mailaccess...), o
      • empieza por 'm', tiene longitud ±1 de un target y distancia
        Damerau-Levenshtein <=1 (typos tipo maill, mailz, mailacces).
    Los nombres HOTMAIL devuelven False (tienen su propio silo).
    Los nombres SOLO-MIX (mix, m1x, mixs...) devuelven False desde v4.2.26.
    """
    if not filename:
        return False
    if es_nombre_hotmail(filename):
        return False

    norm = filename.lower().translate(_LEET_TABLE)
    for tok in re.findall(r'[a-z]+', norm):
        if tok in _IMAP_TOKENS_EXACT:
            return True
        if len(tok) >= 4 and tok.startswith('m'):
            for target in _IMAP_FUZZY_TARGETS:
                if abs(len(tok) - len(target)) <= 1 and _levenshtein(tok, target) <= 1:
                    return True
    return False


def es_nombre_mix(filename: str) -> bool:
    """v4.2.26 — True si el nombre es una variante MIX (mix, m1x, m¡x...).

    El tipo mix fue ELIMINADO del silo IMAP: los archivos con nombre mix
    ya no se descargan al silo. Esta función SOLO existe para reconocer
    los archivos mix LEGACY que puedan quedar en HJDescargas_Imap y que
    el extractor /imap los salte. Nunca matchea mail/mailaccess.
    """
    if not filename:
        return False
    norm = filename.lower().translate(_LEET_TABLE)
    return any(tok in _MIX_TOKENS_EXACT for tok in re.findall(r'[a-z]+', norm))


# ═════════════════════════════════════════════════════════════
# v4.2.14 — ANTI-DUPLICADOS: no re-descargar archivos ya bajados
# Fuente persistente: download_log (DB). Fast-path: state.seen_downloads.
# Criterio: mismo filename (+ mismo tamaño si se conoce). Fail-open:
# si la DB falla, se permite la descarga (jamás bloquear por telemetría).
# ═════════════════════════════════════════════════════════════

def _dedup_key(filename: str, file_size: int) -> str:
    """Clave de dedupe: nombre normalizado + tamaño (0 → solo nombre)."""
    name = (filename or '').strip().lower()
    return f"{name}|{file_size or 0}"


def _is_duplicate_download(filename: str, file_size: int) -> bool:
    """True si este archivo (nombre+tamaño) ya fue descargado antes.

    1) Fast-path en memoria (state.seen_downloads) — cubre reposts
       consecutivos y descargas ya en curso (anti-carrera).
    2) Persistente en DB (download_log) — sobrevive reinicios.
    Al consultar se cachea la clave en memoria para no golpear la DB
    con el mismo repost una y otra vez.
    """
    key = _dedup_key(filename, file_size)

    if key in state.seen_downloads:
        return True

    try:
        if db.is_file_downloaded(filename, file_size):
            state.seen_downloads.add(key)
            return True
    except Exception as e:
        logger.error(f"DEDUP_DB_ERROR: {filename}: {e}")

    return False


def _reserve_download(filename: str, file_size: int):
    """Reservar la clave en memoria (descarga aceptada / en curso)."""
    state.seen_downloads.add(_dedup_key(filename, file_size))


def _release_download(filename: str, file_size: int):
    """Liberar la reserva si la descarga FALLÓ (permite reintento futuro)."""
    state.seen_downloads.discard(_dedup_key(filename, file_size))


class DownloadProgressTracker:
    """Gestor de progreso de descarga con actualizaciones en Telegram en tiempo real.
    
    FIX v3.4: 
    - Usa asyncio.get_running_loop() (no deprecated)
    - Cancela task anterior antes de crear nuevo (evita pileup)
    - Backoff adaptativo cuando FloodWait detectado
    - _do_update con manejo robusto de errores
    """

    def __init__(self, chat_id: int, filename: str, file_size: int,
                 file_index: int = 1, total_files: int = 1,
                 stats: Optional[Dict] = None):
        self.chat_id = chat_id
        self.filename = filename
        self.file_size = file_size
        self.file_index = file_index
        self.total_files = total_files
        self.stats = stats or {'new': 0, 'existing': 0, 'errors': 0}
        self.message = None
        self._last_edit_time = 0
        self._edit_interval = 3  # Editar cada 3 segundos mínimo
        self._pending_task = None  # Task activo de update
        self._floodwait_until = 0  # Timestamp hasta el cual no editar (backoff)
        self._consecutive_errors = 0  # Errores consecutivos de edición

    async def create_message(self, client):
        """Crear el mensaje inicial de progreso."""
        try:
            fname_display = self.filename[:40]
            size_str = format_size(self.file_size) if self.file_size > 0 else "Desconocido"
            text = (
                "╭───✦ 📥 **DESCARGANDO** ({}/{})\n"
                "├─ 📄 `{}`\n"
                "├─ 📊 Tamaño: `{}`\n"
                "├─ ⏳ Preparando descarga...\n"
                "│\n"
                "├─ {}\n"
                "│\n"
                "├─ ✅ Nuevos: `{}` · 💾 Existentes: `{}` · ❌ Errores: `{}`\n"
                "╰───✦"
            ).format(
                self.file_index, self.total_files,
                fname_display, size_str,
                progress_bar(0),
                self.stats['new'], self.stats['existing'], self.stats['errors']
            )
            self.message = await client.send_message(
                self.chat_id, text, parse_mode='md'
            )
        except Exception as e:
            logger.error(f"Error creando mensaje de progreso: {e}")

    def notify_progress(self, current: int, total: int, speed: float, eta: float, pct: float):
        """Notificar progreso de forma NO-BLOQUEANTE (fire-and-forget).
        
        FIX v3.4: 
        - Usa get_running_loop() (no deprecated)
        - Cancela task anterior para evitar pileup
        - Respeta FloodWait backoff (no intenta editar si está en cooldown)
        """
        now = time.time()
        
        # Respetar FloodWait backoff
        if now < self._floodwait_until:
            return
        
        if now - self._last_edit_time < self._edit_interval:
            return
        self._last_edit_time = now

        if not self.message:
            return

        # Cancelar task anterior si aún no terminó
        if self._pending_task is not None and not self._pending_task.done():
            self._pending_task.cancel()

        # Fire-and-forget: crear tarea sin await
        try:
            loop = asyncio.get_running_loop()
            self._pending_task = loop.create_task(
                self._do_update(current, total, speed, eta, pct)
            )
        except RuntimeError:
            pass

    async def _do_update(self, current: int, total: int, speed: float, eta: float, pct: float):
        """Actualizar mensaje de Telegram (ejecutado como background task)."""
        if not self.message:
            return
        try:
            fname_display = self.filename[:40]
            size_str = format_size(self.file_size) if self.file_size > 0 else "Desconocido"
            bar = progress_bar(pct)
            speed_str = format_size(speed) + "/s" if speed > 0 else "Calculando..."
            eta_str = format_time(eta) if eta > 0 else "Calculando..."
            downloaded_str = format_size(current)
            total_str = format_size(total) if total > 0 else size_str

            text = (
                "╭───✦ 📥 **DESCARGANDO** ({}/{})\n"
                "├─ 📄 `{}`\n"
                "├─ 📊 Tamaño: `{}` / `{}`\n"
                "├─ ⚡ Velocidad: `{}`\n"
                "│\n"
                "├─ {}\n"
                "├─ ⏱️ ETA: `{}`\n"
                "│\n"
                "├─ ✅ Nuevos: `{}` · 💾 Existentes: `{}` · ❌ Errores: `{}`\n"
                "╰───✦"
            ).format(
                self.file_index, self.total_files,
                fname_display,
                downloaded_str, total_str,
                speed_str,
                bar,
                eta_str,
                self.stats['new'], self.stats['existing'], self.stats['errors']
            )
            await self.message.edit(text, parse_mode='md')
            self._consecutive_errors = 0
            
        except asyncio.CancelledError:
            return
            
        except MessageNotModifiedError:
            pass
            
        except FloodWaitError as e:
            wait_seconds = e.seconds
            logger.warning(f"FloodWait al editar progreso: {wait_seconds}s - aplicando backoff")
            self._floodwait_until = time.time() + wait_seconds + 1
            self._edit_interval = min(self._edit_interval + 2, 10)
            self._consecutive_errors += 1
            
        except ConnectionError:
            logger.debug("Conexión perdida al editar progreso")
            self._consecutive_errors += 1
            self._edit_interval = min(self._edit_interval + 1, 8)
            
        except Exception as e:
            self._consecutive_errors += 1
            if self._consecutive_errors > 3:
                self._edit_interval = min(self._edit_interval + 2, 15)
                logger.warning(f"Errores consecutivos en progreso ({self._consecutive_errors}): {e}")
            else:
                logger.debug(f"Error actualizando progreso: {e}")

    async def finish(self, success: bool, elapsed: float = 0):
        """Actualizar mensaje al finalizar la descarga."""
        if not self.message:
            return
        
        # Cancelar task pendiente antes de finalizar
        if self._pending_task is not None and not self._pending_task.done():
            self._pending_task.cancel()
            try:
                await self._pending_task
            except (asyncio.CancelledError, Exception):
                pass
        
        # Esperar un poco si estamos en FloodWait
        now = time.time()
        if now < self._floodwait_until:
            wait = self._floodwait_until - now + 1
            if wait < 15:
                await asyncio.sleep(wait)
        
        try:
            fname_display = self.filename[:40]
            size_str = format_size(self.file_size) if self.file_size > 0 else "Desconocido"
            status = "✅ COMPLETADO" if success else "❌ FALLIDO"

            if success:
                speed = self.file_size / elapsed if elapsed > 0 and self.file_size > 0 else 0
                speed_str = format_size(speed) + "/s" if speed > 0 else "-"
                time_str = format_time(elapsed)
                text = (
                    "╭───✦ ✅ **DESCARGA COMPLETADA**\n"
                    "├─ 📄 `{}`\n"
                    "├─ 📊 Tamaño: `{}`\n"
                    "├─ ⏱️ Tiempo: `{}`\n"
                    "├─ ⚡ Velocidad: `{}`\n"
                    "│\n"
                    "├─ ✅ Nuevos: `{}` · 💾 Existentes: `{}` · ❌ Errores: `{}`\n"
                    "╰───✦"
                ).format(
                    fname_display, size_str,
                    time_str, speed_str,
                    self.stats['new'], self.stats['existing'], self.stats['errors']
                )
            else:
                text = (
                    "╭───✦ ❌ **DESCARGA FALLIDA**\n"
                    "├─ 📄 `{}`\n"
                    "├─ 📊 Tamaño: `{}`\n"
                    "│\n"
                    "├─ ✅ Nuevos: `{}` · 💾 Existentes: `{}` · ❌ Errores: `{}`\n"
                    "╰───✦"
                ).format(
                    fname_display, size_str,
                    self.stats['new'], self.stats['existing'], self.stats['errors']
                )

            await self.message.edit(text, parse_mode='md')
        except Exception as e:
            logger.debug(f"Error en finish de progreso: {e}")


# FASE B FIX: no borrar archivos .tmp en DIR_TEMP durante esta fase
# de estabilización. Puede haber descargas interrumpidas que queremos
# poder resumir. Cambiar a True cuando termine la fase de verificación.
CLEANUP_TMP_ENABLED = False


async def mover_y_limpiar_archivos():
    """Auto-limpieza de archivos expirados.

    PURAMENTE FILESYSTEM — no toca PostgreSQL. Errores individuales
    por archivo NO rompen el loop. Tags de log diferenciados:
    CLEANUP_ARCHIVE_ERROR, CLEANUP_DELETE_ERROR, CLEANUP_CACHE_ERROR,
    CLEANUP_TMP_ERROR.
    """
    ahora = time.time()
    segundos_archive = config.ARCHIVE_AFTER_HOURS * 3600
    segundos_delete = config.DELETE_AFTER_HOURS * 3600

    moved = 0
    deleted = 0

    # ── Archivar descargas viejas (>24h) ──
    for f in config.DIR_DOWNLOADS.glob('*.txt'):
        try:
            if (ahora - f.stat().st_mtime) > segundos_archive:
                dest = config.DIR_ARCHIVE / f.name
                if dest.exists():
                    dest.unlink()
                os.replace(f, dest)  # atómico en mismo FS
                moved += 1
        except Exception as e:
            logger.warning(f"CLEANUP_ARCHIVE_ERROR: {f.name}: {e}")

    # v4.2.11: mismo ciclo de vida para el silo HOTMAIL (nuevos → antiguos)
    for f in config.DIR_HOTMAIL.glob('*.txt'):
        try:
            if (ahora - f.stat().st_mtime) > segundos_archive:
                dest = config.DIR_HOTMAIL_ARCHIVE / f.name
                if dest.exists():
                    dest.unlink()
                os.replace(f, dest)
                moved += 1
        except Exception as e:
            logger.warning(f"CLEANUP_HOTMAIL_ARCHIVE_ERROR: {f.name}: {e}")

    # v4.2.16: mismo ciclo de vida para el silo IMAP/MIX (nuevos → antiguos)
    for f in config.DIR_IMAP.glob('*.txt'):
        try:
            if (ahora - f.stat().st_mtime) > segundos_archive:
                dest = config.DIR_IMAP_ARCHIVE / f.name
                if dest.exists():
                    dest.unlink()
                os.replace(f, dest)
                moved += 1
        except Exception as e:
            logger.warning(f"CLEANUP_IMAP_ARCHIVE_ERROR: {f.name}: {e}")

    # ── Borrar archivados muy viejos (>120h) ──
    for f in config.DIR_ARCHIVE.glob('*.txt'):
        try:
            if (ahora - f.stat().st_mtime) > segundos_delete:
                f.unlink()
                deleted += 1
        except Exception as e:
            logger.warning(f"CLEANUP_DELETE_ERROR: {f.name}: {e}")

    # v4.2.11: borrar hotmail antiguos muy viejos (mismo ciclo 120h)
    for f in config.DIR_HOTMAIL_ARCHIVE.glob('*.txt'):
        try:
            if (ahora - f.stat().st_mtime) > segundos_delete:
                f.unlink()
                deleted += 1
        except Exception as e:
            logger.warning(f"CLEANUP_HOTMAIL_DELETE_ERROR: {f.name}: {e}")

    # v4.2.16: borrar imap antiguos muy viejos (mismo ciclo 120h)
    for f in config.DIR_IMAP_ARCHIVE.glob('*.txt'):
        try:
            if (ahora - f.stat().st_mtime) > segundos_delete:
                f.unlink()
                deleted += 1
        except Exception as e:
            logger.warning(f"CLEANUP_IMAP_DELETE_ERROR: {f.name}: {e}")

    # ── Temporales (.tmp) — SKIP durante fase de estabilización ──
    # NO borramos para permitir resume de descargas interrumpidas.
    # Reactivar poniendo CLEANUP_TMP_ENABLED = True cuando termine.
    if CLEANUP_TMP_ENABLED:
        for f in config.DIR_TEMP.glob('*'):
            try:
                if (ahora - f.stat().st_mtime) > 3600:
                    f.unlink()
                    deleted += 1
            except Exception as e:
                logger.warning(f"CLEANUP_TMP_ERROR: {f.name}: {e}")
    else:
        # Solo loguear cuántos hay, no borrar
        try:
            tmp_count = sum(1 for _ in config.DIR_TEMP.glob('*'))
            if tmp_count > 0:
                logger.info(f"CLEANUP_TMP_SKIP: {tmp_count} archivos en DIR_TEMP "
                            f"(no se borran — fase estabilización)")
        except Exception:
            pass

    # ── Cache de resultados viejos (>24h) ──
    for f in config.DIR_CACHE.glob('*.txt'):
        try:
            if (ahora - f.stat().st_mtime) > 86400:
                f.unlink()
        except Exception as e:
            logger.warning(f"CLEANUP_CACHE_ERROR: {f.name}: {e}")

    # v4.2.14: acotar download_log (fuente del anti-duplicados) — best effort
    try:
        log_deleted = db.cleanup_download_log(30)
        if log_deleted > 0:
            logger.info(f"Limpieza: download_log recortado ({log_deleted} registros >30d)")
    except Exception as e:
        logger.warning(f"CLEANUP_DOWNLOAD_LOG_ERROR: {e}")

    if moved or deleted:
        logger.info(f"Limpieza: {moved} archivados, {deleted} eliminados")


# ═════════════════════════════════════════════════════════════
# v4.2.28 — EXPULSIÓN POR ESPACIO LLENO (el más antiguo sale primero)
# ═════════════════════════════════════════════════════════════
# Mientras haya espacio disponible, los archivos nuevos se descargan
# normalmente. Cuando el almacenamiento esté lleno (o no exista espacio
# suficiente para un archivo nuevo), se identifica el archivo MÁS
# ANTIGUO almacenado y se elimina primero — nunca uno reciente. Si ese
# borrado no libera suficiente, se siguen eliminando los siguientes más
# antiguos, UNO POR UNO, hasta conseguir el espacio necesario. Liberado
# el espacio, la descarga arranca automáticamente. Si llega otro nuevo
# y vuelve a faltar espacio, se repite exactamente el mismo proceso.

def _carpetas_almacen() -> list:
    """Carpetas que forman el 'almacenamiento' del bot (expulsables).

    Silos + archivo + resultados de cache + temporales: todo lo que el
    bot guarda en disco entra al pool, sin distinción de silo — el más
    antiguo GLOBAL sale primero.
    """
    return [
        config.DIR_DOWNLOADS, config.DIR_ARCHIVE,
        config.DIR_HOTMAIL, config.DIR_HOTMAIL_ARCHIVE,
        config.DIR_IMAP, config.DIR_IMAP_ARCHIVE,
        config.DIR_CACHE, config.DIR_TEMP,
    ]


def espacio_libre_bytes() -> int:
    """Bytes libres en el disco donde vive el bot. -1 si no se puede saber."""
    try:
        return shutil.disk_usage(str(config.BASE_DIR)).free
    except Exception:
        return -1


def _candidatos_expulsion(min_age_sec: float) -> list:
    """Archivos expulsables ordenados del MÁS ANTIGUO al más nuevo.

    Solo archivos regulares (>0 bytes) de las carpetas del bot, con edad
    mayor al window de protección — NUNCA un archivo reciente. Los .tmp
    (descargas en vuelo) no se tocan. Cada candidato: (mtime, size, path).
    """
    now = time.time()
    cand = []
    for d in _carpetas_almacen():
        try:
            items = list(d.iterdir())
        except OSError:
            continue
        for f in items:
            try:
                if not f.is_file() or f.name.endswith(('.tmp', '.part')):
                    continue
                st = f.stat()
                if st.st_size <= 0 or (now - st.st_mtime) < min_age_sec:
                    continue  # vacío o demasiado reciente → protegido
                cand.append((st.st_mtime, st.st_size, f))
            except OSError:
                continue
    cand.sort(key=lambda t: (t[0], t[2].name))  # más antiguo primero
    return cand


async def liberar_espacio_para(necesario_bytes: int, filename: str = "") -> bool:
    """v4.2.28 — Garantiza espacio libre suficiente para un archivo nuevo.

    Ya hay espacio → True sin tocar nada. Si falta: elimina el archivo
    MÁS ANTIGUO del almacenamiento, uno por uno (re-consultando el
    espacio real tras cada borrado), hasta que el nuevo quepa
    (tamaño + STORAGE_SAFETY_MARGIN_MB). Nunca elimina archivos con
    menos de STORAGE_PROTECT_MINUTES de antigüedad. Si aun así no se
    consigue espacio → False (el llamador aborta la descarga).
    """
    if not config.STORAGE_EVICT_ENABLED:
        return True

    objetivo = necesario_bytes + config.STORAGE_SAFETY_MARGIN_MB * 1024 * 1024
    if necesario_bytes <= 0:
        objetivo = config.STORAGE_SAFETY_MARGIN_MB * 1024 * 1024

    libre = espacio_libre_bytes()
    if libre < 0:
        return True  # espacio desconocido → no bloquear descargas
    if libre >= objetivo:
        return True

    min_age = config.STORAGE_PROTECT_MINUTES * 60
    objetivo_legible = format_size(objetivo)
    logger.warning(
        f"🧹 ESPACIO LLENO: {format_size(libre)} libres < {objetivo_legible} "
        f"necesarios para '{filename or 'nuevo archivo'}' — "
        f"eliminando los MÁS ANTIGUOS uno por uno..."
    )

    ahora = time.time()
    skip: set = set()
    borrados = 0
    liberado = 0

    while espacio_libre_bytes() < objetivo:
        cand = [c for c in _candidatos_expulsion(min_age) if c[2] not in skip]
        if not cand:
            faltan = objetivo - espacio_libre_bytes()
            logger.error(
                f"🧹 ESPACIO: sin más archivos expulsables "
                f"(protegidos los < {config.STORAGE_PROTECT_MINUTES}min) y faltan "
                f"{format_size(max(faltan, 0))} — descarga de "
                f"'{filename or 'nuevo archivo'}' ABORTADA"
            )
            return False
        mtime, size, path = cand[0]  # el MÁS ANTIGUO que exista
        edad_h = max((ahora - mtime) / 3600.0, 0.0)
        try:
            path.unlink()
            borrados += 1
            liberado += size
            logger.info(
                f"🧹 ESPACIO: eliminado el más antiguo '{path.name}' "
                f"({format_size(size)}, {edad_h:.1f}h de antigüedad) — "
                f"{format_size(liberado)} liberados acumulados"
            )
        except OSError as exc:
            logger.warning(f"🧹 ESPACIO: no se pudo eliminar '{path.name}': {exc}")
            skip.add(path)  # saltarlo y probar con el siguiente más antiguo
        await asyncio.sleep(0)  # ceder el loop entre borrados

    logger.info(
        f"🧹 ESPACIO: listo para '{filename or 'nuevo archivo'}' — "
        f"{borrados} archivo(s) antiguo(s) eliminado(s), "
        f"{format_size(liberado)} liberados, "
        f"{format_size(espacio_libre_bytes())} libres ahora"
    )
    return True


async def _download_with_progress(
    event_or_msg,
    filename: str,
    dest_path: Path,
    progress_callback=None,
    _retry_count: int = 0
) -> bool:
    """
    Descarga archivos de Telegram con soporte para archivos grandes (hasta 4GB).
    
    FIX v3.4: 
    - notify_progress usa get_running_loop() + task cancellation
    - Backoff adaptativo en FloodWait para ediciones
    - Throttle optimizado para máxima velocidad
    - Logging mejorado para diagnóstico
    """
    MAX_RETRIES = 5
    temp_path = dest_path.with_suffix('.tmp')

    try:
        file_size = 0
        if hasattr(event_or_msg, 'document') and event_or_msg.document:
            file_size = event_or_msg.document.size or 0

        if _retry_count == 0:
            logger.info(f"Descarga iniciada: {filename} ({format_size(file_size)})")

        # Si hay archivo temporal previo (reintento), verificar progreso
        if temp_path.exists():
            existing_size = temp_path.stat().st_size
            if existing_size >= file_size and file_size > 0:
                if dest_path.exists():
                    dest_path.unlink()
                temp_path.rename(dest_path)
                logger.info(f"Descarga completada (resume): {filename}")
                return True

        # v4.2.28: GARANTÍA DE ESPACIO — si el disco está lleno (o no cabe
        # el archivo nuevo), eliminar el archivo MÁS ANTIGUO del bot, uno
        # por uno, hasta liberar lo necesario. Una vez liberado, la descarga
        # continúa automáticamente aquí mismo.
        try:
            if not await liberar_espacio_para(file_size, filename):
                logger.error(
                    f"Descarga ABORTADA por falta de espacio (nada expulsable): {filename}"
                )
                return False
        except Exception as exc:
            # fail-open: un fallo del chequeo de espacio JAMÁS bloquea descargas
            logger.warning(f"Chequeo de espacio falló (fail-open): {exc}")

        start_time = time.time()
        last_progress_log = [0]

        downloaded = [0]

        # Descargar usando iter_download con chunks grandes
        try:
            doc = event_or_msg.document
            if doc is None and hasattr(event_or_msg, 'media') and event_or_msg.media:
                doc = event_or_msg.media.document
            
            if doc is None:
                logger.error(f"Documento es None para: {filename}")
                return False
                
            part_size = config.DOWNLOAD_PART_SIZE_KB * 1024

            with open(temp_path, 'wb') as f:
                async for chunk in state.userbot.iter_download(
                    doc,
                    request_size=part_size,
                    file_size=file_size if file_size > 0 else None
                ):
                    f.write(chunk)
                    downloaded[0] += len(chunk)
                    now = time.time()

                    # Log en consola cada 10 segundos
                    if (now - last_progress_log[0]) >= 10:
                        last_progress_log[0] = now
                        pct = (downloaded[0] / file_size * 100) if file_size > 0 else 0
                        elapsed = now - start_time
                        speed = downloaded[0] / elapsed if elapsed > 0 else 0
                        logger.info(
                            f"DL {filename[:30]}: {pct:.1f}% "
                            f"({format_size(downloaded[0])}/{format_size(file_size)}) "
                            f"@ {format_size(speed)}/s"
                        )

                    # Notificar progreso de forma NO-BLOQUEANTE
                    if progress_callback and (now - start_time) >= 1:
                        elapsed = now - start_time
                        if elapsed > 0 and downloaded[0] > 0:
                            speed = downloaded[0] / elapsed
                            eta = (file_size - downloaded[0]) / speed if speed > 0 and file_size > 0 else 0
                            pct = (downloaded[0] / file_size * 100) if file_size > 0 else 0
                            if hasattr(progress_callback, 'notify_progress'):
                                progress_callback.notify_progress(downloaded[0], file_size, speed, eta, pct)

                    # Throttle mínimo entre chunks - más bajo = más velocidad
                    if config.DOWNLOAD_THROTTLE > 0:
                        await asyncio.sleep(config.DOWNLOAD_THROTTLE)

        except AttributeError as ae:
            logger.info(f"Fallback a download_media para: {filename} ({ae})")
            def _simple_progress(current, total):
                downloaded[0] = current
                now = time.time()
                if (now - last_progress_log[0]) >= 30:
                    last_progress_log[0] = now
                    pct = (current / total * 100) if total > 0 else 0
                    logger.info(f"DL {filename[:30]}: {pct:.0f}%")

            await event_or_msg.download_media(
                file=str(temp_path),
                progress_callback=_simple_progress if file_size > 10 * 1024 * 1024 else None
            )

        # Verificar descarga — NUEVA LÓGICA:
        # 1) Validar que temp existe y tiene tamaño correcto
        # 2) Reemplazo atómico con os.replace (mismo FS → atómico en Linux)
        # 3) Solo DESPUÉS del rename exitoso: log DB (best-effort, no contagia)
        if not temp_path.exists():
            logger.error(f"DOWNLOAD_STREAM_ERROR: temp_path no existe para {filename}")
            return False

        actual_size = temp_path.stat().st_size

        # Si Telegram proporcionó file_size, validar tamaño real vs esperado
        if file_size > 0 and actual_size != file_size:
            logger.error(
                f"DOWNLOAD_SIZE_MISMATCH: {filename} "
                f"expected={file_size} ({format_size(file_size)}) "
                f"actual={actual_size} ({format_size(actual_size)}) "
                f"diff={file_size - actual_size}"
            )
            # NO borrar temp_path — preservación de parcial para diagnóstico.
            # El path de detección (líneas 347-354) ve temp_path.exists() pero el
            # streaming actual re-abre con .wb. (trunca) — NO resume byte-level real.
            # Solo si el archivo está vacío lo descartamos (no hay nada
            # útil para preservar).
            if actual_size == 0:
                try:
                    temp_path.unlink()
                except Exception:
                    pass
            else:
                logger.info(
                    f"DOWNLOAD_SIZE_PRESERVED: {filename} temp_path preservado "
                    f"({actual_size} bytes) para diagnóstico/futura reanudación"
                )
            return False

        if actual_size == 0:
            logger.warning(f"DOWNLOAD_SIZE_MISMATCH: {filename} size=0 (vacío)")
            try:
                temp_path.unlink()
            except Exception:
                pass
            return False

        # Reemplazo atómico con os.replace — mismo filesystem → atómico en
        # Linux. NO usamos unlink+rename (ventana peligrosa donde si rename
        # falla, perdés tanto el anterior como el nuevo).
        try:
            os.replace(temp_path, dest_path)
        except OSError as e:
            logger.error(f"DOWNLOAD_RENAME_ERROR: {filename}: {e}")
            # temp_path sigue existiendo, reintento puede resumir
            return False

        # ─────────────────────────────────────────────────────────
        # A PARTIR DE ACÁ, LA DESCARGA ESTÁ COMPLETA Y EL ARCHIVO
        # ESTÁ EN dest_path CON EL TAMAÑO CORRECTO.
        # Cualquier error de telemetría DB NO debe convertir esto en False.
        # ─────────────────────────────────────────────────────────
        elapsed = time.time() - start_time
        final_size = dest_path.stat().st_size
        speed = final_size / elapsed if elapsed > 0 else 0

        logger.info(
            f"Descarga OK: {filename} "
            f"({format_size(final_size)}) en {format_time(elapsed)} "
            f"({format_size(speed)}/s)"
        )

        # Telemetría DB — best effort, NUNCA afecta el resultado.
        # log_download tiene su propio try/except interno y NO propaga.
        chat_id = getattr(event_or_msg, 'chat_id', 0)
        try:
            db.log_download(filename, final_size, chat_id)
        except Exception as e:
            # log_download ya loguea internamente, pero capturamos por
            # si acaso el método cambia en el futuro.
            logger.error(f"DB_LOG_DOWNLOAD_ERROR: descarga OK pero log falló: {filename}: {e}")

        return True   # ← SIEMPRE True si el archivo está OK en disco

    except FloodWaitError as e:
        logger.warning(f"FloodWait {e.seconds}s en {filename} (intento {_retry_count+1}/{MAX_RETRIES})")
        await asyncio.sleep(e.seconds + 2)
        if _retry_count < MAX_RETRIES:
            return await _download_with_progress(
                event_or_msg, filename, dest_path,
                progress_callback, _retry_count + 1
            )
        return False

    except TimedOutError:
        logger.warning(f"Timeout en {filename} (intento {_retry_count+1}/{MAX_RETRIES})")
        if _retry_count < MAX_RETRIES:
            await asyncio.sleep(10)
            return await _download_with_progress(
                event_or_msg, filename, dest_path,
                progress_callback, _retry_count + 1
            )
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass
        return False

    except FileReferenceExpiredError:
        logger.warning(f"FileReference expirada en {filename} - reintentando...")
        if _retry_count < MAX_RETRIES:
            await asyncio.sleep(5)
            return await _download_with_progress(
                event_or_msg, filename, dest_path,
                progress_callback, _retry_count + 1
            )
        return False

    except ConnectionError as e:
        logger.warning(
            f"DOWNLOAD_STREAM_ERROR: ConnectionError en {filename} "
            f"(intento {_retry_count+1}/{MAX_RETRIES}): {e}"
        )
        await asyncio.sleep(30)
        if _retry_count < MAX_RETRIES:
            return await _download_with_progress(
                event_or_msg, filename, dest_path,
                progress_callback, _retry_count + 1
            )
        return False

    except Exception as e:
        # Tag de log diferenciado para distinguir errores desconocidos de
        # errores conocidos (FloodWait/Timeout/Connection/SSL arriba).
        # NO borramos temp_path acá para permitir reintentos manuales
        # posteriores (puede haber descarga parcial utilizable).
        logger.error(
            f"DOWNLOAD_UNKNOWN_ERROR: {filename} "
            f"{type(e).__name__}: {e}",
            exc_info=True
        )
        # Solo borramos temp_path si está vacío o claramente truncado.
        # Si tiene tamaño razonable, lo dejamos para posible resume.
        try:
            if temp_path.exists():
                temp_size = temp_path.stat().st_size
                if temp_size == 0:
                    temp_path.unlink()
                # else: dejarlo, puede servir para resume
        except Exception:
            pass
        return False

    finally:
        if filename in state.active_downloads:
            state.active_downloads.pop(filename, None)


async def _download_large_file_task(event, filename: str, dest_path: Path):
    """Task de descarga con semáforo para control de concurrencia."""
    if state.download_semaphore is None:
        state.download_semaphore = asyncio.Semaphore(config.MAX_CONCURRENT_DOWNLOADS)

    async with state.download_semaphore:
        # FIX v3.4: state.active_downloads (NO state.state.active_downloads)
        state.active_downloads[filename] = {
            'start_time': time.time(),
            'size': 0,
            'status': 'downloading'
        }
        _file_size = event.document.size if getattr(event, 'document', None) else 0
        success = await _download_with_progress(event, filename, dest_path)
        if not success and filename in state.active_downloads:
            state.active_downloads[filename]['status'] = 'failed'
            # v4.2.14: fallo → liberar reserva de dedupe (permite reintento)
            _release_download(filename, _file_size or 0)
        if success:
            logger.info(f"Esperando {config.DOWNLOAD_DELAY_BETWEEN}s antes de siguiente descarga...")
            await asyncio.sleep(config.DOWNLOAD_DELAY_BETWEEN)


async def _auto_dl_worker():
    """Worker que procesa la cola de auto-descarga SECUENCIALMENTE con progreso."""
    state.auto_dl_worker_running = True
    logger.info("Auto-DL Worker iniciado (modo secuencial)")

    while True:
        try:
            item = await state.auto_dl_queue.get()
            if item is None:
                break

            event = item['event']
            filename = item['filename']
            dest_path = item['dest_path']
            file_size = item['size']

            if dest_path.exists() and dest_path.stat().st_size > 0:
                # FIX v3.4: state.auto_dl_queue (NO state.state.auto_dl_queue)
                state.auto_dl_queue.task_done()
                continue

            logger.info(f"Auto-DL: Descargando {filename} ({format_size(file_size)})")

            # FIX v3.4: state.active_downloads (NO state.state.active_downloads)
            state.active_downloads[filename] = {
                'start_time': time.time(),
                'size': file_size,
                'status': 'downloading'
            }

            # FIX v3.4: state.auto_dl_queue (NO state.state.auto_dl_queue)
            queue_remaining = state.auto_dl_queue.qsize()
            tracker = DownloadProgressTracker(
                chat_id=config.ADMIN_IDS[0],
                filename=filename,
                file_size=file_size,
                file_index=1,
                total_files=queue_remaining + 1,
                stats={'new': 0, 'existing': 0, 'errors': 0}
            )
            await tracker.create_message(state.bot)

            dl_start = time.time()
            success = await _download_with_progress(
                event, filename, dest_path,
                progress_callback=tracker
            )
            dl_elapsed = time.time() - dl_start

            if not success and filename in state.active_downloads:
                state.active_downloads[filename]['status'] = 'failed'

            # ACTUALIZAR STATS del tracker según resultado
            if success:
                tracker.stats['new'] += 1
            else:
                tracker.stats['errors'] += 1
                # v4.2.14: fallo → liberar reserva de dedupe (permite reintento)
                _release_download(filename, file_size)

            await tracker.finish(success, dl_elapsed)

            logger.info(f"Auto-DL: Esperando {config.DOWNLOAD_DELAY_BETWEEN}s...")
            await asyncio.sleep(config.DOWNLOAD_DELAY_BETWEEN)

            # FIX v3.4: state.auto_dl_queue (NO state.state.auto_dl_queue)
            state.auto_dl_queue.task_done()

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error en auto-dl worker: {e}", exc_info=True)
            await asyncio.sleep(5)

    # FIX v3.4: state.auto_dl_worker_running (NO variable local)
    state.auto_dl_worker_running = False
    logger.info("Auto-DL Worker detenido")


async def realtime_listener(event):
    """Escucha automática de archivos en canales/grupos."""
    try:
        if not event.document:
            return

        filename = None
        for attr in event.document.attributes:
            if isinstance(attr, DocumentAttributeFilename):
                filename = attr.file_name

        if not filename or not filename.lower().endswith('.txt'):
            return

        file_size = event.document.size or 0
        if file_size > config.MAX_DOWNLOAD_SIZE_MB * 1024 * 1024:
            logger.warning(f"Archivo demasiado grande: {filename} ({format_size(file_size)})")
            return

        # v4.2.11: SILO HOTMAIL — los .txt con variantes de 'hotmail' en el NOMBRE
        # (hotmail, hotmails, hotma1il, hotma¡l, h0tmail...) NO tienen peso mínimo
        # y se guardan en su propia carpeta (HJDescargas_Hotmail).
        # v4.2.16: SILO IMAP — ídem para variantes de mail/mailaccess
        # (HJDescargas_Imap; el tipo MIX fue retirado en v4.2.26).
        # Prioridad: hotmail primero (silos separados).
        # v4.2.17: ambos silos aceptan de 0 KB a 100 MB (SILO_MAX_SIZE_MB).
        # v4.2.27: los MIX NO se ignoran ni van al silo — bajan a GENERAL
        # con el mínimo de los generales y SIN filtro de keywords (el
        # nombre mix ya identifica la base; eso era el auto-bajado v4.2.16).
        is_hotmail = es_nombre_hotmail(filename)
        is_imap = (not is_hotmail) and es_nombre_imap(filename)
        is_mix = (not is_hotmail) and (not is_imap) and es_nombre_mix(filename)

        # v4.2.17: TOPE de los silos hotmail/imap — 0 KB pasa, pero por
        # encima de 100MB el .txt se ignora (no se baja, no se encola).
        if (is_hotmail or is_imap) \
                and file_size > config.SILO_MAX_SIZE_MB * 1024 * 1024:
            logger.info(
                f"Archivo demasiado grande para silo hotmail/imap, ignorado: "
                f"{filename} ({format_size(file_size)} > {config.SILO_MAX_SIZE_MB}MB)"
            )
            return

        if not (is_hotmail or is_imap):
            # v4.2.10: Filtro de tamaño MÍNIMO (solo archivos NORMALES) —
            # los hotmail/imap bajan desde 0 KB (tope 100MB ya aplicado arriba).
            # v4.2.27: los mix también pasan por este mínimo (son generales).
            if file_size < config.MIN_DOWNLOAD_SIZE_MB * 1024 * 1024:
                logger.info(
                    f"Archivo demasiado pequeño, ignorado: {filename} "
                    f"({format_size(file_size)} < {config.MIN_DOWNLOAD_SIZE_MB}MB)"
                )
                return

            text_content = event.message.message or ""
            text_lower = text_content.lower()
            filename_lower = filename.lower()

            # v4.2.27: los mix se EXIMEN del filtro de keywords — el
            # nombre (mix, m1x, mixs...) ya identifica la base de combos,
            # igual que ocurría en el silo imap sin peso por keyword.
            if not is_mix:
                keywords = ["ulp", "url:log:pass", "url:pass", "combo", "database", "leak", "db"]
                if not any(k in filename_lower for k in keywords):
                    if not any(k in text_lower for k in keywords):
                        return

        # v4.2.11: hotmail → silo hotmail · v4.2.16: imap → silo imap ·
        # resto → general (v4.2.27: los mix caen aquí, a GENERAL)
        if is_hotmail:
            dest_path = config.DIR_HOTMAIL / filename
            logger.info(
                f"HOTMAIL detectado en nombre: {filename} "
                f"({format_size(file_size)}) → {config.DIR_HOTMAIL} (0 KB–{config.SILO_MAX_SIZE_MB}MB)"
            )
        elif is_imap:
            dest_path = config.DIR_IMAP / filename
            logger.info(
                f"IMAP detectado en nombre (mail/mailaccess): {filename} "
                f"({format_size(file_size)}) → {config.DIR_IMAP} (0 KB–{config.SILO_MAX_SIZE_MB}MB)"
            )
        else:
            dest_path = config.DIR_DOWNLOADS / filename
            if is_mix:
                logger.info(
                    f"MIX detectado en nombre (fuera del silo imap desde v4.2.26): "
                    f"{filename} ({format_size(file_size)}) → GENERAL "
                    f"(mínimo {config.MIN_DOWNLOAD_SIZE_MB}MB, sin keywords)"
                )

        if dest_path.exists() and dest_path.stat().st_size > 0:
            return

        # v4.2.14: anti-duplicados — ya descargado antes (nombre+tamaño,
        # persistente en download_log) o en curso → no re-bajar
        if _is_duplicate_download(filename, file_size):
            logger.info(
                f"DUPLICADO omitido (ya descargado antes): {filename} "
                f"({format_size(file_size)})"
            )
            return

        if filename in state.active_downloads:
            return

        if state.auto_download_enabled:
            _reserve_download(filename, file_size)
            if state.auto_dl_queue is not None:
                await state.auto_dl_queue.put({
                    'event': event,
                    'filename': filename,
                    'dest_path': dest_path,
                    'size': file_size
                })
                queue_size = state.auto_dl_queue.qsize()
                logger.info(f"Auto-DL: Encolado {filename} (cola: {queue_size})")
            else:
                state.active_downloads[filename] = {
                    'start_time': time.time(),
                    'size': file_size,
                    'status': 'starting'
                }
                asyncio.create_task(_download_large_file_task(event, filename, dest_path))
        else:
            if not any(p['msg_id'] == event.id for p in state.pending_downloads):
                _reserve_download(filename, file_size)
                try:
                    chat = await event.get_chat()
                    chat_name = getattr(chat, 'title', f"Chat {event.chat_id}")
                except Exception:
                    chat_name = "Unknown"
                state.pending_downloads.append({
                    'chat_id': event.chat_id,
                    'msg_id': event.id,
                    'filename': filename,
                    'chat_name': chat_name,
                    'size': file_size,
                    'dest_path': str(dest_path),
                    'is_hotmail': is_hotmail,
                    'is_imap': is_imap
                })
                logger.info(f"Pendiente detectado: {filename} ({format_size(file_size)})")

    except Exception as e:
        logger.error(f"Error en listener: {e}")


async def process_pending_downloads(status_msg=None):
    """Procesar descargas pendientes con progreso en tiempo real en Telegram."""
    if not state.pending_downloads:
        if status_msg:
            await status_msg.edit("No hay archivos pendientes.")
        return

    total = len(state.pending_downloads)
    stats = {'new': 0, 'existing': 0, 'duplicates': 0, 'errors': 0}
    start_time = time.time()

    if status_msg:
        try:
            await status_msg.edit(
                "╭───✦ 📥 **INICIANDO DESCARGAS**\n"
                f"├─ 📦 Total: `{total}` archivos en cola\n"
                f"├─ ⏳ Preparando...\n"
                "╰───✦",
                parse_mode='md'
            )
        except Exception:
            pass

    to_download = list(state.pending_downloads)
    state.pending_downloads.clear()

    for idx, item in enumerate(to_download, 1):
        try:
            msg = await state.userbot.get_messages(item['chat_id'], ids=item['msg_id'])
            if not msg or not msg.document:
                stats['errors'] += 1
                continue

            # v4.2.11-fix: usar el destino correcto (hotmail → silo hotmail)
            dest_path = Path(item['dest_path']) if item.get('dest_path') \
                else config.DIR_DOWNLOADS / item['filename']

            if dest_path.exists() and dest_path.stat().st_size > 0:
                stats['existing'] += 1
                continue

            file_size = item.get('size', 0) or (msg.document.size if msg.document else 0)

            # v4.2.10: Red de seguridad — omitir .txt menores a MIN_DOWNLOAD_SIZE_MB (5MB)
            # v4.2.11-fix: los HOTMAIL pasan sin importar el peso
            # v4.2.16: los IMAP/MIX también pasan sin importar el peso
            # v4.2.17: silos hotmail/imap — rango 0 KB a 100 MB (tope duro)
            if not item.get('is_hotmail') and not item.get('is_imap'):
                # Archivos NORMALES: mínimo 5MB
                if file_size and \
                        file_size < config.MIN_DOWNLOAD_SIZE_MB * 1024 * 1024:
                    logger.info(
                        f"Pendiente omitido por tamaño mínimo: {item['filename']} "
                        f"({format_size(file_size)} < {config.MIN_DOWNLOAD_SIZE_MB}MB)"
                    )
                    stats['existing'] += 1
                    continue
            else:
                # Silos hotmail/imap: sin mínimo (0 KB OK) pero TOPE 100MB
                if file_size and \
                        file_size > config.SILO_MAX_SIZE_MB * 1024 * 1024:
                    logger.info(
                        f"Pendiente omitido (supera tope de silo): {item['filename']} "
                        f"({format_size(file_size)} > {config.SILO_MAX_SIZE_MB}MB)"
                    )
                    stats['existing'] += 1
                    continue

            # v4.2.14: anti-duplicados — soltar la reserva propia (hecha al
            # encolar) y re-chequear contra el histórico persistente
            _release_download(item['filename'], file_size)
            if _is_duplicate_download(item['filename'], file_size):
                logger.info(
                    f"DUPLICADO omitido (pendiente): {item['filename']} "
                    f"({format_size(file_size)})"
                )
                stats['duplicates'] += 1
                continue
            _reserve_download(item['filename'], file_size)

            tracker = DownloadProgressTracker(
                chat_id=config.ADMIN_IDS[0],
                filename=item['filename'],
                file_size=file_size,
                file_index=idx,
                total_files=total,
                stats=stats
            )
            await tracker.create_message(state.bot)

            dl_start = time.time()
            success = await _download_with_progress(
                msg, item['filename'], dest_path,
                progress_callback=tracker
            )
            dl_elapsed = time.time() - dl_start

            if success:
                stats['new'] += 1
            else:
                stats['errors'] += 1
                # v4.2.14: fallo → liberar reserva de dedupe (permite reintento)
                _release_download(item['filename'], file_size)

            await tracker.finish(success, dl_elapsed)
            await asyncio.sleep(0.3)

        except Exception as e:
            logger.error(f"Error descargando pendiente: {e}")
            stats['errors'] += 1

    elapsed = time.time() - start_time

    if status_msg:
        from ui import Keyboards
        report = (
            "╭───✦ ✅ **DESCARGAS COMPLETADAS**\n"
            f"├─ 📥 Nuevos: `{stats['new']}`\n"
            f"├─ 💾 Existentes: `{stats['existing']}`\n"
            f"├─ ♻️ Duplicados: `{stats['duplicates']}`\n"
            f"├─ ❌ Errores: `{stats['errors']}`\n"
            f"├─ ⏱️ Tiempo total: `{format_time(elapsed)}`\n"
            "╰───✦"
        )
        try:
            await status_msg.edit(report, buttons=Keyboards.back("adm_files"), parse_mode='md')
        except Exception:
            pass
