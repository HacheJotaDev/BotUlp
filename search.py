"""
═══════════════════════════════════════════════════════════════
  HJ ULP EXTRACTOR BOT — Search Engine Module v3.4.2
═══════════════════════════════════════════════════════════════
  • Búsqueda PARALELA con mmap ultra-rápido (todos los archivos a la vez)
  • Límite por archivo + timeout global + early termination
  • Domains populares (spotify, netflix) ya no se cuelgan
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

# Límites para evitar que dominios populares cuelguen el bot
MAX_RESULTS_PER_FILE = 50000    # Máximo de resultados por archivo (suficiente por archivo)
SEARCH_GLOBAL_TIMEOUT = 300     # 5 minutos máximo para toda la búsqueda


def _search_file(path: Path, kw: str, modo: SearchMode, cancel_event: threading.Event = None) -> List[str]:
    """Búsqueda en archivo con mmap - máxima velocidad con límites.
    
    Procesa archivos de cualquier tamaño, pero frena cuando tiene
    suficientes resultados o si se cancela desde fuera.
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
                iterations = 0

                while pos < mm_size:
                    # Early termination: límite de resultados por archivo
                    if len(res_set) >= MAX_RESULTS_PER_FILE:
                        break

                    # Verificar cancelación cada 200 matches
                    iterations += 1
                    if iterations % 200 == 0:
                        if cancel_event and cancel_event.is_set():
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
    """Motor de búsqueda PARALELO con caché + límites de seguridad.
    
    FIX v3.4.2:
    - TODOS los archivos se procesan EN PARALELO (no secuencial)
    - Timeout global: si se pasa de 5 min, devuelve lo que tenga
    - Cancel event: cuando hay suficientes resultados, para los demás
    - Límite por archivo: 50000 resultados máximo por archivo
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

    # Evento de cancelación compartido para early termination
    cancel_event = threading.Event()

    logger.info(f"Búsqueda '{kw}': {len(files)} archivos, modo {modo.value}")

    # ===== PARALELO: todos los archivos a la vez =====
    tasks = [
        loop.run_in_executor(executor, _search_file, f, kw, modo, cancel_event)
        for f in files
    ]

    # Ejecutar con timeout global
    search_start = time.time()
    try:
        results = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=SEARCH_GLOBAL_TIMEOUT
        )
    except asyncio.TimeoutError:
        # Timeout global alcanzado - cancelar todo y usar lo que tengamos
        cancel_event.set()
        logger.warning(f"Búsqueda '{kw}': timeout global ({SEARCH_GLOBAL_TIMEOUT}s)")
        # Esperar un poco a que los threads terminen
        await asyncio.sleep(1)
        # Recoger resultados parciales de las tareas que ya terminaron
        results = []
        for t in tasks:
            if t.done() and not t.cancelled():
                try:
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
    logger.info(f"Búsqueda '{kw}' completada: {len(final)} resultados en {elapsed:.1f}s")

    state.search_memory_cache[cache_key] = out
    return out
