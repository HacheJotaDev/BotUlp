"""
═══════════════════════════════════════════════════════════════
  HJ ULP EXTRACTOR BOT — Download System Module v3.2
═══════════════════════════════════════════════════════════════
  • Download de archivos hasta 4GB con streaming + progreso
  • Progress updates con task cancellation (sin pileup)
  • FloodWait backoff adaptativo (no spam a Telegram)
  • Auto-limpieza de archivos expirados
  • Cola secuencial para evitar FloodWait
═══════════════════════════════════════════════════════════════
"""

import os
import asyncio
import time
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

# FIX #1,#2,#3: Usar `import state` en vez de `from state import X`
# Los imports estáticos capturan None/False/[] en import time y NUNCA se actualizan
# cuando bot.py asigna los valores reales (state.bot = bot_client, etc.)
import state


class DownloadProgressTracker:
    """Gestor de progreso de descarga con actualizaciones en Telegram en tiempo real.
    
    FIX v3.2: 
    - Usa asyncio.get_running_loop() en vez de get_event_loop()
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
            fname_short = self.filename[:30]
            size_str = format_size(self.file_size) if self.file_size > 0 else "Desconocido"
            text = (
                "╭───✦ 📥 DESCARGANDO ({}/{})\n"
                "├● 📄 `{}`\n"
                "├● 📊 Tamaño: `{}`\n"
                "├● ⏳ Preparando descarga...\n"
                "│\n"
                "├● [░░░░░░░░░░░░] 0.0%\n"
                "│\n"
                "├● ✅ Nuevos: `{}` │ 💾 Existentes: `{}` │ ❌ Errores: `{}`\n"
                "╰───✦ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
            ).format(
                self.file_index, self.total_files,
                fname_short, size_str,
                self.stats['new'], self.stats['existing'], self.stats['errors']
            )
            self.message = await client.send_message(
                self.chat_id, text, parse_mode='md'
            )
        except Exception as e:
            logger.error(f"Error creando mensaje de progreso: {e}")

    def notify_progress(self, current: int, total: int, speed: float, eta: float, pct: float):
        """Notificar progreso de forma NO-BLOQUEANTE (fire-and-forget).
        
        FIX v3.2: 
        - Usa get_running_loop() (no deprecated)
        - Cancela task anterior para evitar pileup
        - Respeta FloodWait backoff (no intenta editar si está en cooldown)
        """
        now = time.time()
        
        # Respetar FloodWait backoff - no intentar editar si estamos en cooldown
        if now < self._floodwait_until:
            return
        
        if now - self._last_edit_time < self._edit_interval:
            return
        self._last_edit_time = now

        if not self.message:
            return

        # Cancelar task anterior si aún no terminó (evita pileup)
        if self._pending_task is not None and not self._pending_task.done():
            self._pending_task.cancel()

        # Fire-and-forget: crear tarea sin await
        try:
            loop = asyncio.get_running_loop()
            self._pending_task = loop.create_task(
                self._do_update(current, total, speed, eta, pct)
            )
        except RuntimeError:
            pass  # Event loop no disponible

    async def _do_update(self, current: int, total: int, speed: float, eta: float, pct: float):
        """Actualizar mensaje de Telegram (ejecutado como background task).
        
        FIX v3.2:
        - FloodWait aplica backoff adaptativo
        - Errores consecutivos aumentan el intervalo
        - Cancelación segura via try/except CancelledError
        """
        if not self.message:
            return
        try:
            fname_short = self.filename[:30]
            size_str = format_size(self.file_size) if self.file_size > 0 else "Desconocido"
            bar = progress_bar(pct)
            speed_str = format_size(speed) + "/s" if speed > 0 else "Calculando..."
            eta_str = format_time(eta) if eta > 0 else "Calculando..."
            downloaded_str = format_size(current)
            total_str = format_size(total) if total > 0 else size_str

            text = (
                "╭───✦ 📥 DESCARGANDO ({}/{})\n"
                "├● 📄 `{}`\n"
                "├● 📊 Tamaño: `{}` / `{}`\n"
                "├● ⚡ Velocidad: `{}`\n"
                "│\n"
                "├● {}\n"
                "├● ⏱️ ETA: `{}`\n"
                "│\n"
                "├● ✅ Nuevos: `{}` │ 💾 Existentes: `{}` │ ❌ Errores: `{}`\n"
                "╰───✦ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
            ).format(
                self.file_index, self.total_files,
                fname_short,
                downloaded_str, total_str,
                speed_str,
                bar,
                eta_str,
                self.stats['new'], self.stats['existing'], self.stats['errors']
            )
            await self.message.edit(text, parse_mode='md')
            # Éxito - resetear errores consecutivos
            self._consecutive_errors = 0
            
        except asyncio.CancelledError:
            # Task cancelado por nuevo update - normal, no es error
            return
            
        except MessageNotModifiedError:
            pass
            
        except FloodWaitError as e:
            # FIX: Backoff adaptativo - respetar FloodWait de Telegram
            wait_seconds = e.seconds
            logger.warning(f"FloodWait al editar progreso: {wait_seconds}s - aplicando backoff")
            self._floodwait_until = time.time() + wait_seconds + 1
            # Aumentar intervalo temporalmente
            self._edit_interval = min(self._edit_interval + 2, 10)
            self._consecutive_errors += 1
            
        except ConnectionError:
            # Conexión perdida temporalmente - aumentar intervalo
            logger.debug("Conexión perdida al editar progreso")
            self._consecutive_errors += 1
            self._edit_interval = min(self._edit_interval + 1, 8)
            
        except Exception as e:
            self._consecutive_errors += 1
            # Si hay muchos errores consecutivos, aumentar intervalo significativamente
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
        
        # Esperar un poco si estamos en FloodWait para que el mensaje final llegue
        now = time.time()
        if now < self._floodwait_until:
            wait = self._floodwait_until - now + 1
            if wait < 15:  # Solo esperar si es poco tiempo
                await asyncio.sleep(wait)
        
        try:
            fname_short = self.filename[:30]
            size_str = format_size(self.file_size) if self.file_size > 0 else "Desconocido"
            status = "✅ COMPLETADO" if success else "❌ FALLIDO"
            icon = "✅" if success else "❌"

            if success:
                speed = self.file_size / elapsed if elapsed > 0 and self.file_size > 0 else 0
                speed_str = format_size(speed) + "/s" if speed > 0 else "-"
                time_str = format_time(elapsed)
                text = (
                    "╭───✦ {} DESCARGA {}\n"
                    "├● 📄 `{}`\n"
                    "├● 📊 Tamaño: `{}`\n"
                    "├● ⏱️ Tiempo: `{}`\n"
                    "├● ⚡ Velocidad: `{}`\n"
                    "│\n"
                    "├● ✅ Nuevos: `{}` │ 💾 Existentes: `{}` │ ❌ Errores: `{}`\n"
                    "╰───✦ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
                ).format(
                    icon, status,
                    fname_short, size_str,
                    time_str, speed_str,
                    self.stats['new'], self.stats['existing'], self.stats['errors']
                )
            else:
                text = (
                    "╭───✦ ❌ DESCARGA FALLIDA\n"
                    "├● 📄 `{}`\n"
                    "├● 📊 Tamaño: `{}`\n"
                    "│\n"
                    "├● ✅ Nuevos: `{}` │ 💾 Existentes: `{}` │ ❌ Errores: `{}`\n"
                    "╰───✦ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
                ).format(
                    fname_short, size_str,
                    self.stats['new'], self.stats['existing'], self.stats['errors']
                )

            await self.message.edit(text, parse_mode='md')
        except Exception as e:
            logger.debug(f"Error en finish de progreso: {e}")


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

    for f in config.DIR_TEMP.glob('*'):
        try:
            if (ahora - f.stat().st_mtime) > 3600:
                f.unlink()
                deleted += 1
        except Exception:
            pass

    for f in config.DIR_CACHE.glob('*.txt'):
        try:
            if (ahora - f.stat().st_mtime) > 86400:
                f.unlink()
        except Exception:
            pass

    if moved or deleted:
        logger.info(f"Limpieza: {moved} archivados, {deleted} eliminados")


async def _download_with_progress(
    event_or_msg,
    filename: str,
    dest_path: Path,
    progress_callback=None,
    _retry_count: int = 0
) -> bool:
    """
    Descarga archivos de Telegram con soporte para archivos grandes (hasta 4GB).
    
    FIX v3.2: 
    - notify_progress usa get_running_loop() + task cancellation
    - Backoff adaptativo en FloodWait para ediciones
    - Throttle reducido a 0.03s para mejor velocidad
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

                    # Log en consola cada 15 segundos (más frecuente para diagnóstico)
                    if (now - last_progress_log[0]) >= 15:
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
                            # FIRE-AND-FORGET con task cancellation: notify_progress NO hace await
                            if hasattr(progress_callback, 'notify_progress'):
                                progress_callback.notify_progress(downloaded[0], file_size, speed, eta, pct)

                    # Throttle mínimo entre chunks
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

        # Verificar descarga
        if temp_path.exists() and temp_path.stat().st_size > 0:
            if dest_path.exists():
                dest_path.unlink()
            temp_path.rename(dest_path)

            elapsed = time.time() - start_time
            final_size = dest_path.stat().st_size
            speed = final_size / elapsed if elapsed > 0 else 0

            logger.info(
                f"Descarga OK: {filename} "
                f"({format_size(final_size)}) en {format_time(elapsed)} "
                f"({format_size(speed)}/s)"
            )

            chat_id = getattr(event_or_msg, 'chat_id', 0)
            db.log_download(filename, final_size, chat_id)
            return True
        else:
            logger.warning(f"Descarga vacía: {filename}")
            if temp_path.exists():
                temp_path.unlink()
            return False

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

    except ConnectionError:
        logger.warning(f"Conexión perdida en {filename} - reintentando en 30s...")
        await asyncio.sleep(30)
        if _retry_count < MAX_RETRIES:
            return await _download_with_progress(
                event_or_msg, filename, dest_path,
                progress_callback, _retry_count + 1
            )
        return False

    except Exception as e:
        logger.error(f"Error en descarga {filename}: {e}", exc_info=True)
        if temp_path.exists():
            try:
                temp_path.unlink()
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
        state.state.active_downloads[filename] = {
            'start_time': time.time(),
            'size': 0,
            'status': 'downloading'
        }
        success = await _download_with_progress(event, filename, dest_path)
        if not success and filename in state.active_downloads:
            state.state.active_downloads[filename]['status'] = 'failed'
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
                state.state.auto_dl_queue.task_done()
                continue

            logger.info(f"Auto-DL: Descargando {filename} ({format_size(file_size)})")
            state.state.active_downloads[filename] = {
                'start_time': time.time(),
                'size': file_size,
                'status': 'downloading'
            }

            queue_remaining = state.state.auto_dl_queue.qsize()
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

            await tracker.finish(success, dl_elapsed)

            logger.info(f"Auto-DL: Esperando {config.DOWNLOAD_DELAY_BETWEEN}s...")
            await asyncio.sleep(config.DOWNLOAD_DELAY_BETWEEN)

            state.auto_dl_queue.task_done()

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error en auto-dl worker: {e}", exc_info=True)
            await asyncio.sleep(5)

    auto_dl_worker_running = False
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

        text_content = event.message.message or ""
        text_lower = text_content.lower()
        filename_lower = filename.lower()

        keywords = ["ulp", "url:log:pass", "url:pass", "combo", "database", "leak", "db"]
        if not any(k in filename_lower for k in keywords):
            if not any(k in text_lower for k in keywords):
                return

        dest_path = config.DIR_DOWNLOADS / filename

        if dest_path.exists() and dest_path.stat().st_size > 0:
            return

        if filename in state.active_downloads:
            return

        if state.auto_download_enabled:
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
                    'size': file_size
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
    stats = {'new': 0, 'existing': 0, 'errors': 0}
    start_time = time.time()

    if status_msg:
        try:
            await status_msg.edit(
                "╭───✦ 📥 INICIANDO DESCARGAS\n"
                f"├● 📦 Total: `{total}` archivos en cola\n"
                f"├● ⏳ Preparando...\n"
                "╰───✦ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈",
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

            dest_path = config.DIR_DOWNLOADS / item['filename']

            if dest_path.exists() and dest_path.stat().st_size > 0:
                stats['existing'] += 1
                continue

            file_size = item.get('size', 0) or (msg.document.size if msg.document else 0)
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

            await tracker.finish(success, dl_elapsed)
            await asyncio.sleep(0.3)

        except Exception as e:
            logger.error(f"Error descargando pendiente: {e}")
            stats['errors'] += 1

    elapsed = time.time() - start_time

    if status_msg:
        from ui import Keyboards
        report = (
            "╭───✦ ✅ DESCARGAS COMPLETADAS\n"
            f"├● 📥 Nuevos: `{stats['new']}`\n"
            f"├● 💾 Existentes: `{stats['existing']}`\n"
            f"├● ❌ Errores: `{stats['errors']}`\n"
            f"├● ⏱️ Tiempo total: `{format_time(elapsed)}`\n"
            "╰───✦ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
        )
        try:
            await status_msg.edit(report, buttons=Keyboards.back("adm_files"), parse_mode='md')
        except Exception:
            pass
