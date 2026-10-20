"""
═══════════════════════════════════════════════════════════════
  HJ ULP — Datos de países (ISO → nombre + bandera)
═══════════════════════════════════════════════════════════════
  • Descarga en caliente el JSON de henryofc17/paises
  • Fallback embebido con los países más comunes (si no hay red)
  • Función get_country_info(iso) → (nombre, flag, iso)
═══════════════════════════════════════════════════════════════
"""

import json
import urllib.request
from typing import Optional, Tuple

from logger_setup import logger

PAISES_JSON_URL = (
    "https://raw.githubusercontent.com/henryofc17/paises/main/paises.json"
)

# Fallback mínimo por si no hay red al arrancar.
# Estos son los países que más aparecen en cuentas Microsoft.
_FALLBACK_PAISES = {
    "AR": ("Argentina", "🇦🇷"),
    "BO": ("Bolivia", "🇧🇴"),
    "BR": ("Brasil", "🇧🇷"),
    "CA": ("Canadá", "🇨🇦"),
    "CL": ("Chile", "🇨🇱"),
    "CO": ("Colombia", "🇨🇴"),
    "CR": ("Costa Rica", "🇨🇷"),
    "CU": ("Cuba", "🇨🇺"),
    "DO": ("República Dominicana", "🇩🇴"),
    "EC": ("Ecuador", "🇪🇨"),
    "SV": ("El Salvador", "🇸🇻"),
    "ES": ("España", "🇪🇸"),
    "US": ("Estados Unidos", "🇺🇸"),
    "FR": ("Francia", "🇫🇷"),
    "GT": ("Guatemala", "🇬🇹"),
    "HN": ("Honduras", "🇭🇳"),
    "IT": ("Italia", "🇮🇹"),
    "MX": ("México", "🇲🇽"),
    "NI": ("Nicaragua", "🇳🇮"),
    "PA": ("Panamá", "🇵🇦"),
    "PY": ("Paraguay", "🇵🇾"),
    "PE": ("Perú", "🇵🇪"),
    "PT": ("Portugal", "🇵🇹"),
    "PR": ("Puerto Rico", "🇵🇷"),
    "GB": ("Reino Unido", "🇬🇧"),
    "UY": ("Uruguay", "🇺🇾"),
    "VE": ("Venezuela", "🇻🇪"),
    "DE": ("Alemania", "🇩🇪"),
    "RU": ("Rusia", "🇷🇺"),
    "TR": ("Turquía", "🇹🇷"),
    "CN": ("China", "🇨🇳"),
    "JP": ("Japón", "🇯🇵"),
    "KR": ("Corea del Sur", "🇰🇷"),
    "IN": ("India", "🇮🇳"),
    "ID": ("Indonesia", "🇮🇩"),
    "PH": ("Filipinas", "🇵🇭"),
    "VN": ("Vietnam", "🇻🇳"),
    "TH": ("Tailandia", "🇹🇭"),
    "ZA": ("Sudáfrica", "🇿🇦"),
    "EG": ("Egipto", "🇪🇬"),
    "NG": ("Nigeria", "🇳🇬"),
    "KE": ("Kenia", "🇰🇪"),
    "SA": ("Arabia Saudita", "🇸🇦"),
    "AE": ("Emiratos Árabes", "🇦🇪"),
    "IL": ("Israel", "🇮🇱"),
    "AU": ("Australia", "🇦🇺"),
    "NZ": ("Nueva Zelanda", "🇳🇿"),
}

# Cache del dict aplanado: ISO -> (nombre, bandera)
_PAIS_DB = None


def _aplanar_json(data) -> dict:
    """Aplanar el JSON anidado (continentes → regiones → países) a un dict ISO → (nombre, flag)."""
    resultado = {}

    def _procesar_lista(lista):
        for item in lista:
            if isinstance(item, dict) and "code" in item:
                code = (item.get("code") or "").upper()
                name = item.get("name") or code
                flag = item.get("flag") or "🏳️"
                if code:
                    resultado[code] = (name, flag)

    if isinstance(data, dict):
        for value in data.values():
            if isinstance(value, list):
                _procesar_lista(value)
            elif isinstance(value, dict):
                # Sub-regiones (ej: "América" → {"América del Norte": [...], ...})
                for sub in value.values():
                    if isinstance(sub, list):
                        _procesar_lista(sub)
    elif isinstance(data, list):
        _procesar_lista(data)

    return resultado


def _cargar_paises() -> dict:
    """Cargar la base de países: intenta descargarla, sino usa el fallback."""
    try:
        req = urllib.request.Request(
            PAISES_JSON_URL,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        aplanado = _aplanar_json(data)
        if len(aplanado) >= 50:
            logger.info(f"[PAISES] Base de países cargada: {len(aplanado)} países")
            return aplanado
        logger.warning(
            f"[PAISES] JSON descargado pero solo tiene {len(aplanado)} países — "
            f"usando fallback embebido"
        )
    except Exception as e:
        logger.warning(f"[PAISES] No se pudo descargar JSON de países: {e}")

    # Fallback
    return {k: (v[0], v[1]) for k, v in _FALLBACK_PAISES.items()}


def get_country_info(iso: Optional[str]) -> Tuple[str, str]:
    """Obtener (nombre, bandera) para un código ISO de 2 letras.

    Si no se conoce el ISO, retorna ('Unknown', '🏳️').
    """
    global _PAIS_DB
    if _PAIS_DB is None:
        _PAIS_DB = _cargar_paises()

    if not iso or not isinstance(iso, str):
        return ("Unknown", "🏳️")

    iso = iso.strip().upper()
    if len(iso) != 2 or not iso.isalpha():
        return ("Unknown", "🏳️")

    info = _PAIS_DB.get(iso)
    if info:
        return info
    # Si no está en la DB, devolver el ISO como nombre y bandera blanca
    return (iso, "🏳️")


def get_flag_from_iso(iso: Optional[str]) -> str:
    """Conveniencia: solo la bandera."""
    return get_country_info(iso)[1]


def get_name_from_iso(iso: Optional[str]) -> str:
    """Conveniencia: solo el nombre del país."""
    return get_country_info(iso)[0]
