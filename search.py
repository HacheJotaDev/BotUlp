"""
═══════════════════════════════════════════════════════════════
  HJ ULP EXTRACTOR BOT — Search Engine Module v3.5
═══════════════════════════════════════════════════════════════
  • Busqueda PARALELA con mmap ultra-rapido
  • FIX: Limite de MATCHES procesados (no solo resultados)
  • FIX: Timer interno por archivo (threads no se pueden cancelar)
  • Dominios populares (spotify, netflix) ya no se cuelgan
  • v3.5: Eliminado /ma, codigo limpiado y optimizado
═══════════════════════════════════════════════════════════════
"""

import re
import mmap
import asyncio
import time
import threading
from pathlib import Path
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor

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

# Limites para evitar que dominios populares cuelguen el bot
MAX_RESULTS_PER_FILE = 10000    # Maximo de resultados unicos por archivo
MAX_MATCHES_PER_FILE = 100000   # Maximo de MATCHES procesados por archivo (hard stop)
FILE_TIME_LIMIT = 60            # 60 segundos maximo por archivo dentro del thread


def _search_file(path: Path, kw: str, modo: SearchMode, cancel_event: threading.Event = None) -> List[str]:
    """Busqueda en archivo con mmap - con limites duros de matches y tiempo."""
    if cancel_event and cancel_event.is_set():
        return []

    res_set = set()
    enc_kw = kw.lower().encode()
    kw_lower = kw.lower()
    start_time = time.time()
    matches_processed = 0

    try:
        file_size = path.stat().st_size
        if file_size == 0:
            return []

        with open(path, 'rb') as f:
            with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                pos = 0
                mm_size = mm.size()

                while pos < mm_size:
                    # === LIMITES DUROS ===
                    if len(res_set) >= MAX_RESULTS_PER_FILE:
                        break
                    if matches_processed >= MAX_MATCHES_PER_FILE:
                        logger.info(f"Archivo {path.name}: hard stop {MAX_MATCHES_PER_FILE} matches procesados")
                        break
                    if time.time() - start_time > FILE_TIME_LIMIT:
                        logger.info(f"Archivo {path.name}: time limit {FILE_TIME_LIMIT}s alcanzado")
                        break

                    matches_processed += 1
                    if matches_processed % 500 == 0 and cancel_event and cancel_event.is_set():
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

    elapsed = time.time() - start_time
    if elapsed > 5 or len(res_set) > 0:
        logger.info(f"Archivo {path.name}: {len(res_set)} resultados en {elapsed:.1f}s ({matches_processed} matches procesados)")

    return list(res_set)


async def search_engine(kw: str, time_opt: str, modo: SearchMode) -> Optional[Path]:
    """Motor de busqueda PARALELO con cache + limites de seguridad."""
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

    cancel_event = threading.Event()

    logger.info(f"Busqueda '{kw}': {len(files)} archivos, modo {modo.value}")

    # PARALELO: todos los archivos a la vez
    tasks = [
        loop.run_in_executor(executor, _search_file, f, kw, modo, cancel_event)
        for f in files
    ]

    # Timeout global amplio (los threads se frenan solos con FILE_TIME_LIMIT)
    search_start = time.time()
    try:
        results = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=600
        )
    except asyncio.TimeoutError:
        cancel_event.set()
        logger.warning(f"Busqueda '{kw}': timeout global, usando resultados parciales")
        await asyncio.sleep(2)
        results = []
        for t in tasks:
            try:
                if t.done() and not t.cancelled():
                    r = t.result()
                    if isinstance(r, list):
                        results.append(r)
            except Exception:
                pass

    # Combinar resultados
    final = set()
    for r in results:
        if isinstance(r, list):
            final.update(r)

    if not final:
        return None

    if len(final) > config.SEARCH_MAX_RESULTS:
        logger.info(f"Resultados truncados: {len(final)} -> {config.SEARCH_MAX_RESULTS}")
        final = set(list(final)[:config.SEARCH_MAX_RESULTS])

    kw_safe = re.sub(r'[^\w\-.]', '_', kw[:20])
    out = config.DIR_CACHE / f"result_{int(time.time())}_{kw_safe}.txt"

    with open(out, 'w', encoding='utf-8', buffering=1024*64) as f:
        f.write('\n'.join(final))

    elapsed = time.time() - search_start
    logger.info(f"Busqueda '{kw}' completada: {len(final)} resultados en {elapsed:.1f}s")

    state.search_memory_cache[cache_key] = out
    return out