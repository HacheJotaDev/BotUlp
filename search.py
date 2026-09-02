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

# v4.2.6 — Anti-bloqueo del event loop:
#   mmap.find()/slices NO liberan el GIL: un scan de GBs congelaba TODO el bot
#   (por eso /ping llegaba con 68s de latencia durante una busqueda).
#   Ahora se lee por CHUNKS con open/read (el read del SO SI libera el GIL) y
#   cada bytes.find() queda acotado a 32MB (~5ms de GIL maximo).
READ_CHUNK = 16 * 1024 * 1024   # 16MB por lectura (stall C ~15ms)
LINE_LIMIT = 65536              # lineas mayores = basura binaria: solo se mira el inicio
GIANT_SKIP_CHUNK = 8 * 1024 * 1024  # al saltar una linea gigante, scans acotados
GIANT_LINE_THRESHOLD = 8 * 1024 * 1024 + 65536  # carry mayor = linea gigante (basura)


def _search_file(path: Path, kw: str, modo: SearchMode, cancel_event: threading.Event = None) -> List[str]:
    """Busqueda en archivo por chunks — rapida Y fluida para el event loop.

    v4.2.6: reemplaza mmap.find() (que retenia el GIL durante scans de GBs y
    congelaba el bot entero) por lecturas de 32MB. El read() del SO libera el
    GIL y cada operacion C queda acotada al tamano de un chunk (~15-30ms max).

    Estrategia por chunk:
      1. Deteccion case-insensitive del keyword en el chunk (2 scans C).
         Si NO esta → cero procesamiento de lineas (solo continuidad).
      2. Si esta → loop de lineas del chunk (con carry entre chunks).
    Mantiene los mismos limites duros de resultados, matches y tiempo.
    """
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

        carry = b''     # cola de linea incompleta del chunk anterior
        tail = b''      # ultimos 1KB (keyword cruzando el borde del chunk)
        done = False

        with open(path, 'rb') as f:
            while not done:
                # === LIMITES DUROS (por chunk) ===
                if len(res_set) >= MAX_RESULTS_PER_FILE:
                    break
                if matches_processed >= MAX_MATCHES_PER_FILE:
                    logger.info(f"Archivo {path.name}: hard stop {MAX_MATCHES_PER_FILE} matches procesados")
                    break
                if time.time() - start_time > FILE_TIME_LIMIT:
                    logger.info(f"Archivo {path.name}: time limit {FILE_TIME_LIMIT}s alcanzado")
                    break
                if cancel_event and cancel_event.is_set():
                    break

                chunk = f.read(READ_CHUNK)   # syscall: LIBERA el GIL aqui
                if not chunk:
                    break

                # ── Fase 1: detección case-insensitive acotada ──
                # (a) frontera: keyword cruzando el borde del chunk anterior
                #     — copia mínima de ~3KB, NO un concat de 32MB
                if tail:
                    boundary = tail + chunk[:2048]
                    hit = enc_kw in boundary.lower()
                else:
                    hit = False
                # (b) chunk completo (scan C ~15ms con 16MB)
                if not hit:
                    hit = enc_kw in chunk.lower()
                if not hit:
                    # Sin keyword en este chunk: cero procesamiento de lineas
                    nl_last = chunk.rfind(b'\n')
                    if nl_last == -1:
                        carry = carry + chunk if carry else chunk
                    else:
                        carry = chunk[nl_last + 1:]
                    tail = chunk[-1024:]

                    # linea gigante creciendo sin \n: scan acotado y salto
                    if len(carry) > GIANT_LINE_THRESHOLD:
                        ok, rem = _skip_giant_line(f, carry, enc_kw, res_set, kw_lower, modo)
                        if not ok:
                            break   # EOF dentro de una linea gigante
                        carry = rem
                        tail = rem[-1024:] if rem else b''
                    continue

                # ── Fase 2: el chunk contiene el keyword → procesar lineas ──
                buf = (carry + chunk) if carry else chunk
                start = 0
                while True:
                    nl = buf.find(b'\n', start)
                    if nl == -1:
                        break
                    if nl > start:
                        line = buf[start:nl]

                        if len(line) <= LINE_LIMIT:
                            low = line.lower()
                            if enc_kw in low:
                                # Solo cuentan los candidatos reales (igual
                                # que el algoritmo mmap original)
                                matches_processed += 1
                                if matches_processed % 500 == 0 and cancel_event and cancel_event.is_set():
                                    done = True
                                    break
                                try:
                                    decoded = line.decode('utf-8', 'ignore').strip()
                                    if decoded and kw_lower in decoded.lower():
                                        _add_result(res_set, decoded, modo)
                                except Exception:
                                    pass
                        else:
                            # Linea gigante (dump corrupto): solo el inicio acotado
                            seg = line[:LINE_LIMIT]
                            if enc_kw in seg.lower():
                                matches_processed += 1
                                try:
                                    decoded = seg.decode('utf-8', 'ignore').strip()
                                    if decoded and kw_lower in decoded.lower():
                                        _add_result(res_set, decoded, modo)
                                except Exception:
                                    pass
                            if cancel_event and cancel_event.is_set():
                                done = True
                                break
                    start = nl + 1

                if done:
                    break

                carry = buf[start:]
                tail = chunk[-1024:]

                if len(carry) > GIANT_LINE_THRESHOLD:
                    ok, rem = _skip_giant_line(f, carry, enc_kw, res_set, kw_lower, modo)
                    if not ok:
                        break
                    carry = rem
                    tail = rem[-1024:] if rem else b''

                time.sleep(0)    # yield explicito del GIL entre chunks

            # Ultima linea del archivo (sin \n final), acotada
            if carry and not done:
                seg = carry[:LINE_LIMIT]
                if enc_kw in seg.lower():
                    matches_processed += 1
                    try:
                        decoded = seg.decode('utf-8', 'ignore').strip()
                        if decoded and kw_lower in decoded.lower():
                            _add_result(res_set, decoded, modo)
                    except Exception:
                        pass

    except Exception:
        pass

    elapsed = time.time() - start_time
    if elapsed > 5 or len(res_set) > 0:
        logger.info(f"Archivo {path.name}: {len(res_set)} resultados en {elapsed:.1f}s ({matches_processed} matches procesados)")

    return list(res_set)


def _skip_giant_line(f, carry: bytes, enc_kw: bytes, res_set: set, kw_lower: str, modo: SearchMode):
    """Linea gigante (basura binaria > umbral): scan acotado por ventanas y
    salto hasta el proximo \n. Retorna (ok, remainder): ok=False si se alcanza
    EOF dentro de ella; remainder = bytes tras el \n (lineas normales que NO
    deben perderse — estaban dentro del bloque de salto).

    El keyword detectado en la linea produce el resultado acotado a su inicio
    (LINE_LIMIT) — nunca una linea de cientos de MB en los resultados.
    """
    # Ventanas sobre lo ya acumulado (con solape anti-corte de keyword)
    wpos = 0
    found = False
    while wpos < len(carry):
        w = carry[wpos:wpos + GIANT_SKIP_CHUNK]
        if enc_kw in w.lower():
            found = True
            break
        wpos += GIANT_SKIP_CHUNK - 1024
    if found:
        try:
            seg = carry[:LINE_LIMIT]
            decoded = seg.decode('utf-8', 'ignore').strip()
            if decoded:
                _add_result(res_set, decoded, modo)
        except Exception:
            pass

    # Saltar el resto de la linea leyendo en bloques acotados
    skip_tail = carry[-1024:] if carry else b''
    while True:
        gc = f.read(GIANT_SKIP_CHUNK)
        if not gc:
            return False, b''   # EOF dentro de la linea gigante
        nl2 = gc.find(b'\n')
        # SOLO la porcion de la linea gigante (antes del \n): el keyword de
        # la linea siguiente NO pertenece a esta linea (falso positivo v4.2.6)
        scan_end = nl2 if nl2 != -1 else len(gc)
        if not found and enc_kw in (skip_tail + gc[:scan_end]).lower():
            found = True
            try:
                seg = carry[:LINE_LIMIT]
                decoded = seg.decode('utf-8', 'ignore').strip()
                if decoded:
                    _add_result(res_set, decoded, modo)
            except Exception:
                pass
        if nl2 != -1:
            return True, gc[nl2 + 1:]   # resto normal: se procesa después
        skip_tail = gc[-1024:]


def _add_result(res_set: set, decoded: str, modo: SearchMode):
    """Agregar una linea decodificada al set segun el modo de busqueda."""
    if modo == SearchMode.ULP:
        res_set.add(decoded)
        return

    if modo in (SearchMode.MAIL, SearchMode.USERPASS):
        clean_line = decoded.replace("|", ":").replace(";", ":")
        parts = [p.strip() for p in clean_line.split(":") if p.strip()]

        if len(parts) >= 3:
            user = parts[-2]
            password = parts[-1]
        elif len(parts) == 2:
            user = parts[0]
            password = parts[1]
        else:
            return

        if not user or not password:
            return

        if modo == SearchMode.MAIL:
            if _EMAIL_RE.match(user):
                res_set.add(f"{user}:{password}")
        elif modo == SearchMode.USERPASS:
            if "@" not in user:
                res_set.add(f"{user}:{password}")


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

    def _write_results(data: set, out_path: Path):
        with open(out_path, 'w', encoding='utf-8', buffering=1024 * 64) as f:
            f.write('\n'.join(data))

    # v4.2.6: la escritura de hasta 500k líneas va a un thread (no bloquea el loop)
    await asyncio.to_thread(_write_results, final, out)

    elapsed = time.time() - search_start
    logger.info(f"Busqueda '{kw}' completada: {len(final)} resultados en {elapsed:.1f}s")

    state.search_memory_cache[cache_key] = out
    return out