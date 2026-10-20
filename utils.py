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


def _count_txt(directory: Path) -> int:
    """Contar *.txt de un directorio de forma segura (0 si no existe)."""
    try:
        return sum(1 for _ in directory.glob('*.txt'))
    except OSError:
        return 0


def get_file_counts() -> Dict[str, int]:
    """Contar archivos en directorios de descarga y archivo.

    Incluye el silo HOTMAIL (v4.2.12) y el silo IMAP (v4.2.16) para el
    panel de GESTIÓN DE ARCHIVOS:
      hm_24h  → HJDescargas_Hotmail (nuevos)
      hm_old  → Archivo_Hotmail     (histórico)
      im_24h  → HJDescargas_Imap    (nuevos)
      im_old  → Archivo_Imap        (histórico)
    Usa sum() con generador para no cargar miles de Path en memoria.
    """
    count_24h = _count_txt(config.DIR_DOWNLOADS)
    count_old = _count_txt(config.DIR_ARCHIVE)
    hm_24h = _count_txt(config.DIR_HOTMAIL)
    hm_old = _count_txt(config.DIR_HOTMAIL_ARCHIVE)
    im_24h = _count_txt(config.DIR_IMAP)
    im_old = _count_txt(config.DIR_IMAP_ARCHIVE)
    return {
        'total': count_24h + count_old,
        '24h': count_24h,
        'old': count_old,
        'hm_total': hm_24h + hm_old,
        'hm_24h': hm_24h,
        'hm_old': hm_old,
        'im_total': im_24h + im_old,
        'im_24h': im_24h,
        'im_old': im_old,
    }


def build_files_txt() -> tuple:
    """v4.2.22: listado completo de archivos descargados para /listatxt (admin).

    Recorre los 6 folders del ciclo de vida (generales / hotmail / imap,
    nuevos + antiguos) y arma un texto plano con una línea por archivo:
    nombre — peso — fecha. Ordenado por fecha descendente (lo nuevo arriba).
    Devuelve (texto, total). Nunca lanza: los folders con problema salen
    como "(error al leer)".
    """
    secciones = [
        ("📁 GENERALES — NUEVOS", config.DIR_DOWNLOADS),
        ("📁 GENERALES — ANTIGUOS", config.DIR_ARCHIVE),
        ("📥 HOTMAIL — NUEVOS", config.DIR_HOTMAIL),
        ("📥 HOTMAIL — ANTIGUOS", config.DIR_HOTMAIL_ARCHIVE),
        ("📬 IMAP — NUEVOS", config.DIR_IMAP),
        ("📬 IMAP — ANTIGUOS", config.DIR_IMAP_ARCHIVE),
    ]
    out = []
    total = 0
    for titulo, carpeta in secciones:
        try:
            archivos = sorted(
                carpeta.glob('*.txt'),
                key=lambda f: f.stat().st_mtime,
                reverse=True,
            )
        except OSError:
            archivos = []
            out.append(f"━━━ {titulo} (error al leer) ━━━")
            out.append("")
            continue
        out.append(f"━━━ {titulo} ({len(archivos)}) ━━━")
        if not archivos:
            out.append("(vacío)")
        for f in archivos:
            try:
                st = f.stat()
                fecha = time.strftime('%d/%m/%Y %H:%M', time.localtime(st.st_mtime))
                out.append(f"{f.name} — {format_size(st.st_size)} — {fecha}")
                total += 1
            except OSError:
                out.append(f.name)
                total += 1
        out.append("")
    header = (
        f"📂 ARCHIVOS DESCARGADOS — {time.strftime('%d/%m/%Y %H:%M')}\n"
        f"Total: {total} archivos\n"
        f"{'=' * 46}\n\n"
    )
    return header + "\n".join(out).rstrip() + "\n", total


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
