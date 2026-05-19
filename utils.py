"""
═══════════════════════════════════════════════════════════════
  HJ ULP EXTRACTOR BOT — Utilities Module
═══════════════════════════════════════════════════════════════
"""

import time
from pathlib import Path
from typing import Dict

from config import config


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


def progress_bar(pct: float, width: int = 12) -> str:
    """Barra de progreso visual [████████░░░░] 53%"""
    filled = int(width * pct / 100)
    empty = width - filled
    bar = '█' * filled + '░' * empty
    return f"[{bar}] {pct:.1f}%"


def get_file_counts() -> Dict[str, int]:
    """Contar archivos en directorios de descarga y archivo."""
    count_24h = len(list(config.DIR_DOWNLOADS.glob('*.txt')))
    count_old = len(list(config.DIR_ARCHIVE.glob('*.txt')))
    return {'total': count_24h + count_old, '24h': count_24h, 'old': count_old}


def normalizar_url(url: str) -> str:
    """Normalizar URL para búsqueda."""
    url = url.strip().lower()
    for prefix in ['https://', 'http://', 'www.']:
        if url.startswith(prefix):
            url = url[len(prefix):]
    return url.split('/')[0].split('?')[0].split(':')[0]
