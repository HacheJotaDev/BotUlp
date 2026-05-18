"""
═══════════════════════════════════════════════════════════════
  HJ ULP EXTRACTOR BOT — Search Engine Module v3.4
═══════════════════════════════════════════════════════════════
  • Búsqueda paralela con mmap ultra-rápido
  • FIX: Límite por archivo + timeout + early termination
  • FIX: Domains populares (spotify, netflix, etc.) ya no se cuelgan
═══════════════════════════════════════════════════════════════
"""

import re
import mmap
import asyncio
import time
import threading
from pathlib import Path
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from config import config
from logger_setup import logger
from roles import SearchMode
import state

executor = ThreadPoolExecutor(
    max_workers=config.MAX_WORKERS,
    thread_name_prefix="search_worker"
)

# Regex pre-compilado
_EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

# Límites para evitar que dominios populares cuelguen el bot
MAX_RESULTS_PER_FILE = 500000   # Máximo de resultados por archivo individual (mismo que SEARCH_MAX_RESULTS)
SEARCH_TIMEOUT_PER_FILE = 180   # 3 minutos máximo por archivo (archivos de 4GB necesitan más tiempo)
SEARCH_TOTAL_TIMEOUT = 600      # 10 minutos máximo para toda la búsqueda


def _search_file(path: Path, kw: str, modo: SearchMode, cancel_event: threading.Event = None) -> List[str]:
    """Búsqueda en archivo con mmap - máxima velocidad con límites de seguridad.
    
    FIX v3.4:
    - Límite de resultados por archivo (MAX_RESULTS_PER_FILE)
    - Verificación de cancelación para early termination
    - Timeout por archivo como protección (no límite de tamaño)
    """
    if cancel_event and cancel_event.is_set():
        return []

    res_set = set()
    enc_kw = kw.lower().encode()
    kw_lower = kw.lower()

    try:
        file_size = path.stat().st_size
        if file_size == 0:
            return []

        with open(path, 'rb') as f:
            with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                pos = 0
                mm_size = mm.size()

                check_counter = 0
                while pos < mm_size:
                    # Early termination: si ya tenemos suficientes resultados
                    if len(res_set) >= MAX_RESULTS_PER_FILE:
                        logger.info(f"Archivo {path.name}: límite por archivo alcanzado ({MAX_RESULTS_PER_FILE})")
                        break

                    # Verificar cancelación cada 500 matches
                    check_counter += 1
                    if check_counter % 500 == 0 and cancel_event and cancel_event.is_set():
                        break

                    found = mm.find(enc_kw, pos)
                    if found == -1:
                        break

                    line_start = mm.rfind(b'\n', max(0, found - 4096), found)
                    if line_start == -1:
                        line_start = 0
                    else:
                        line_start += 1

                    line_end = mm.find(b'\n', found)
                    if line_end == -1:
                        line_end = mm_size
                    else:
                        line_end += 1

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

                    pos = line_end

    except Exception:
        pass

    return list(res_set)


async def search_engine(kw: str, time_opt: str, modo: SearchMode) -> Optional[Path]:
    """Motor de búsqueda paralelo con caché inteligente + límites de seguridad.
    
    FIX v3.4:
    - Timeout por archivo (no se cuelga con archivos enormes)
    - Timeout global para toda la búsqueda
    - Cancelación temprana cuando ya hay suficientes resultados
    - Progreso en log para diagnóstico
    """
    cache_key = f"{kw}:{time_opt}:{modo.value}"
    if cache_key in state.search_memory_cache:
        cached_path = state.search_memory_cache[cache_key]
        if cached_path and cached_path.exists():
            logger.info(f"Cache HIT: {cache_key}")
            return cached_path

    loop = asyncio.get_running_loop()
    dirs = []
    if time_opt in ['24h', 'all']:
        dirs.append(config.DIR_DOWNLOADS)
    if time_opt in ['old', 'all']:
        dirs.append(config.DIR_ARCHIVE)

    def _safe_size(f):
        try:
            return f.stat().st_size
        except OSError:
            return 0

    files = [f for d in dirs for f in d.glob('*.txt') if _safe_size(f) > 0]
    if not files:
        return None

    # Ordenar archivos: pequeños primero (resultados más rápidos)
    files.sort(key=lambda f: _safe_size(f))

    # Evento de cancelación compartido para early termination
    cancel_event = threading.Event()

    logger.info(f"Búsqueda '{kw}': {len(files)} archivos, modo {modo.value}")

    # Crear tareas con timeout individual por archivo
    tasks = []
    for f in files:
        task = loop.run_in_executor(
            executor, _search_file, f, kw, modo, cancel_event
        )
        tasks.append((f, task))

    # Recopilar resultados con timeout global
    final = set()
    total_search_start = time.time()

    for f, task in tasks:
        # Si ya tenemos suficientes resultados globales, cancelar resto
        if len(final) >= config.SEARCH_MAX_RESULTS:
            cancel_event.set()
            logger.info(f"Búsqueda '{kw}': early termination, {len(final)} resultados suficientes")
            break

        # Timeout global
        elapsed_total = time.time() - total_search_start
        if elapsed_total > SEARCH_TOTAL_TIMEOUT:
            cancel_event.set()
            logger.warning(f"Búsqueda '{kw}': timeout global ({SEARCH_TOTAL_TIMEOUT}s), parando")
            break

        remaining_timeout = max(5, SEARCH_TOTAL_TIMEOUT - elapsed_total)
        per_file_timeout = min(SEARCH_TIMEOUT_PER_FILE, remaining_timeout)

        try:
            result = await asyncio.wait_for(task, timeout=per_file_timeout)
            if isinstance(result, list):
                before = len(final)
                final.update(result)
                added = len(final) - before
                if added > 0:
                    logger.info(f"Archivo {f.name}: +{added} resultados (total: {len(final)})")
        except asyncio.TimeoutError:
            logger.warning(f"Timeout en archivo {f.name} ({_safe_size(f)/1024/1024:.0f}MB) - skip")
        except Exception as e:
            logger.error(f"Error en archivo {f.name}: {e}")

    if not final:
        return None

    if len(final) > config.SEARCH_MAX_RESULTS:
        logger.info(f"Resultados truncados: {len(final)} -> {config.SEARCH_MAX_RESULTS}")
        final = set(list(final)[:config.SEARCH_MAX_RESULTS])

    kw_safe = re.sub(r'[^\w\-.]', '_', kw[:20])
    out = config.DIR_CACHE / f"result_{int(time.time())}_{kw_safe}.txt"

    # Escribir resultados usando buffer grande para archivos grandes
    with open(out, 'w', encoding='utf-8', buffering=1024*64) as f:
        f.write('\n'.join(final))

    total_elapsed = time.time() - total_search_start
    logger.info(f"Búsqueda '{kw}' completada: {len(final)} resultados en {total_elapsed:.1f}s")

    state.search_memory_cache[cache_key] = out
    return out
