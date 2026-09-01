"""
═══════════════════════════════════════════════════════════════
  HJ ULP EXTRACTOR BOT — Utilities Module v4.0
═══════════════════════════════════════════════════════════════
  • Barras de progreso premium (▰▱)
  • Formateadores de tamaño, tiempo y uptime
  • Helpers de dominio
═══════════════════════════════════════════════════════════════
"""

import time
from pathlib import Path
from typing import Dict

from config import config

# Caracteres de la barra de progreso (estilo premium)
BAR_FILLED = "▰"
BAR_EMPTY = "▱"


def format_size(size_bytes: float) -> str:
    """Formatear bytes a formato legible."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def format_time(seconds: float) -> str:
    """Formatear segundos a formato legible."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds//60:.0f}m {seconds%60:.0f}s"
    else:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        return f"{h:.0f}h {m:.0f}m"


def format_uptime(seconds: float) -> str:
    """Formatear uptime del bot: 2d 5h 31m."""
    seconds = int(seconds)
    d, rem = divmod(seconds, 86400)
    h, rem = divmod(rem, 3600)
    m, s = divmod(rem, 60)
    parts = []
    if d:
        parts.append(f"{d}d")
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    if not parts:
        parts.append(f"{s}s")
    return " ".join(parts)


def progress_bar(pct: float, width: int = 12) -> str:
    """Barra de progreso premium: ▰▰▰▰▰▰▱▱▱▱ 52.3%"""
    pct = max(0.0, min(100.0, pct))
    filled = int(width * pct / 100)
    empty = width - filled
    bar = BAR_FILLED * filled + BAR_EMPTY * empty
    return f"{bar} {pct:.1f}%"


def get_file_counts() -> Dict[str, int]:
    """Contar archivos en directorios de descarga y archivo.

    Usa sum() con generador para no cargar miles de Path en memoria.
    """
    count_24h = sum(1 for _ in config.DIR_DOWNLOADS.glob('*.txt'))
    count_old = sum(1 for _ in config.DIR_ARCHIVE.glob('*.txt'))
    return {'total': count_24h + count_old, '24h': count_24h, 'old': count_old}


def normalizar_url(url: str) -> str:
    """Normalizar URL para búsqueda."""
    url = url.strip().lower()
    for prefix in ['https://', 'http://', 'www.']:
        if url.startswith(prefix):
            url = url[len(prefix):]
    return url.split('/')[0].split('?')[0].split(':')[0]


def sanitize_md(text: str) -> str:
    """Sanitizar texto de usuario para Markdown de Telegram (nombres, etc)."""
    if not text:
        return ""
    for ch in ('*', '_', '`', '[', ']', '«', '»'):
        text = text.replace(ch, '')
    return text.strip()
