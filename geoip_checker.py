"""
═══════════════════════════════════════════════════════════════
  HJ ULP EXTRACTOR BOT — GeoIP Checker Module
═══════════════════════════════════════════════════════════════
  • Resuelve el pais de un correo via DNS MX + IP geolocation
  • Usa dns.resolver con DNS personalizados (8.8.8.8, 1.1.1.1)
  • Consulta ip-api.com para geolocalizacion
  • Cache en memoria para evitar consultas repetidas al mismo dominio
  • Thread-safe con LRU cache
═══════════════════════════════════════════════════════════════
"""

import socket
import threading
from typing import Optional, Tuple
from functools import lru_cache
from collections import OrderedDict

import dns.resolver
import requests

from logger_setup import logger

# Timeout para DNS y HTTP
DNS_TIMEOUT = 5
HTTP_TIMEOUT = 5

# Cache thread-safe por dominio
_cache_lock = threading.Lock()
_geoip_cache: OrderedDict = OrderedDict()
_GEOIP_CACHE_MAX = 500


# DNS personalizados para evitar problemas de resolv.conf
_custom_resolver = None


def _get_resolver() -> dns.resolver.Resolver:
    """Obtener o crear el resolver DNS personalizado (thread-safe)."""
    global _custom_resolver
    if _custom_resolver is None:
        _custom_resolver = dns.resolver.Resolver(configure=False)
        _custom_resolver.nameservers = ['8.8.8.8', '1.1.1.1']
        _custom_resolver.lifetime = DNS_TIMEOUT
    return _custom_resolver


def _cache_get(domain: str) -> Optional[dict]:
    """Obtener del cache thread-safe."""
    with _cache_lock:
        if domain in _geoip_cache:
            _geoip_cache.move_to_end(domain)
            return _geoip_cache[domain]
    return None


def _cache_set(domain: str, data: dict):
    """Guardar en cache thread-safe con LRU eviction."""
    with _cache_lock:
        _geoip_cache[domain] = data
        _geoip_cache.move_to_end(domain)
        while len(_geoip_cache) > _GEOIP_CACHE_MAX:
            _geoip_cache.popitem(last=False)


def get_country_for_email(email_addr: str) -> dict:
    """Obtener pais, ISP y proveedor para un correo electronico.

    Args:
        email_addr: Direccion de correo (ej: user@gmail.com)

    Returns:
        dict con:
            - country: str (nombre del pais o 'Unknown')
            - country_code: str (codigo ISO 2 letras o 'N/A')
            - isp: str (proveedor ISP o 'N/A')
            - ip: str (IP del servidor MX o 'N/A')
            - mx_server: str (servidor MX o 'N/A')
            - error: str (mensaje de error si falla, o None)
    """
    try:
        domain = email_addr.split('@')[1].lower()
    except (IndexError, AttributeError):
        return {
            'country': 'Unknown', 'country_code': 'N/A',
            'isp': 'N/A', 'ip': 'N/A', 'mx_server': 'N/A',
            'error': 'Invalid email'
        }

    # Revisar cache
    cached = _cache_get(domain)
    if cached is not None:
        return cached

    result = {
        'country': 'Unknown', 'country_code': 'N/A',
        'isp': 'N/A', 'ip': 'N/A', 'mx_server': 'N/A',
        'error': None
    }

    try:
        resolver = _get_resolver()

        # 1. Obtener registro MX
        registros_mx = resolver.resolve(domain, 'MX')
        mx_server = str(registros_mx[0].exchange).rstrip('.')
        result['mx_server'] = mx_server

        # 2. Resolver IP del servidor MX
        ip_servidor = socket.gethostbyname(mx_server)
        result['ip'] = ip_servidor

        # 3. Consultar API ip-api.com
        url_api = f"http://ip-api.com/json/{ip_servidor}"
        respuesta = requests.get(url_api, timeout=HTTP_TIMEOUT).json()

        if respuesta.get('status') == 'success':
            result['country'] = respuesta.get('country', 'Unknown')
            result['country_code'] = respuesta.get('countryCode', 'N/A')
            result['isp'] = respuesta.get('isp', 'N/A')
        else:
            result['error'] = 'API status: ' + respuesta.get('status', 'unknown')

    except dns.resolver.NXDOMAIN:
        result['error'] = 'Domain does not exist'
    except dns.resolver.NoAnswer:
        result['error'] = 'No MX records'
    except dns.resolver.NoNameservers:
        result['error'] = 'No nameservers available'
    except socket.gaierror:
        result['error'] = 'DNS resolution failed'
    except requests.RequestException as e:
        result['error'] = f'HTTP error: {str(e)[:50]}'
    except Exception as e:
        result['error'] = str(e)[:80]
        logger.warning(f"[GeoIP] Error resolviendo {domain}: {e}")

    # Guardar en cache
    _cache_set(domain, result)

    return result


def get_country_simple(email_addr: str) -> str:
    """Retorna solo el nombre del pais para un correo."""
    info = get_country_for_email(email_addr)
    return info['country']
