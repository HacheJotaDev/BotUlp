"""
═══════════════════════════════════════════════════════════════
  HJ ULP EXTRACTOR BOT — Locale Module
═══════════════════════════════════════════════════════════════
"""

import json
from pathlib import Path
from typing import Dict

from config import config
from logger_setup import logger


class LocaleManager:
    """Gestor de idiomas con soporte de fallback a español."""

    def __init__(self, locales_dir: Path):
        self.locales_dir = locales_dir
        self.translations: Dict[str, Dict[str, str]] = {}
        self.default_lang = 'es'
        self._load_translations()

    def _load_translations(self):
        # Español base integrado
        self.translations['es'] = {
            "welcome": (
                "╭───✦ ☾ HJ ULP PRO ☽ 彡\n"
                "├● ▸ Búsqueda ultra-rápida (paralela)\n"
                "├● ▸ Bases actualizadas 24/7\n"
                "├● ▸ Privacidad & anonimato total\n"
                "├● ▸ Data lista para usar\n"
                "╰───✦ 🚀 by @hjofc20\n"
                "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
                "╭───✦ COMANDOS\n"
                "├● │ {}\n"
                "╰───✦ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n\n"
                "🌟 Soporte:\n"
                "  ✦ @hjofc20\n\n"
                "👤 **Rol:** `{}` │ 📊 **Búsquedas:** `{}`"
            ),
            "buy_vip_info": (
                "╭───✦ 💰 COMPRAR VIP ACCESS 💰\n"
                "├● ⟡ 1 día  »  6$\n"
                "├● ⟡ 3 días »  10$\n"
                "├● ⟡ 7 días »  25$\n"
                "├● ⟡ 30 días » 100$\n"
                "╰───✦ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n\n"
                "📬 **CONTACTO:**\n{}"
            ),
            "file_management": (
                "╭───✦ 📂 GESTIÓN DE ARCHIVOS\n"
                "├● 📊 **Base de Datos:**\n"
                "├● 📁 Total: `{}` archivos\n"
                "├● ⚡ Últimas 24h: `{}`\n"
                "├● 🗄️ Histórico: `{}`\n"
                "╰───✦ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
                "╭───✦ 🔄 DESCARGAS\n"
                "├● ♻️ Auto-Download: `{}`\n"
                "├● 📝 En cola: `{}` archivos\n"
                "├● ⬇️ Activos: `{}` descargas\n"
                "╰───✦ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
            ),
            "no_results": (
                "╭───✦ ❌ SIN RESULTADOS\n"
                "├● No se encontraron datos para `{}`\n"
                "╰───✦ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
            ),
            "search_step_time": (
                "╭───✦ 🔍 BÚSQUEDA\n"
                "├● 🔍 **Dominio:** `{}`\n"
                "╰───✦ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n\n"
                "⏳ Selecciona el rango de tiempo:"
            ),
            "loading": "⚙️ **Procesando...**",
            "access_denied": (
                "╭───✦ 🚫 ACCESO DENEGADO\n"
                "├● Solo usuarios VIP pueden realizar búsquedas\n"
                "╰───✦ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
            ),
            "ask_domain": (
                "╭───✦ 🔍 NUEVA BÚSQUEDA\n"
                "├● Escribe el dominio a buscar\n"
                "╰───✦ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
            ),
            "language_selected": "🌐 Idioma actualizado correctamente.",
            "select_language": "🌐 **SELECT LANGUAGE / IDIOMA / IDIOMA**\n\nChoose your preferred language:",
            "my_account": (
                "╭───✦ 👤 MI CUENTA\n"
                "├● 🆔 ID: `{}`\n"
                "├● 🎖 Rango: `{}`\n"
                "├● 📅 Expira: `{}`\n"
                "├● 📊 Búsquedas: `{}`\n"
                "╰───✦ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
            ),
            "search_completed": (
                "╭───✦ ✅ BÚSQUEDA COMPLETADA\n"
                "├● 🔍 Dominio: `{}`\n"
                "├● 📑 Tipo: `{}`\n"
                "├● 📊 Resultados: `{}`\n"
                "├● ⏱️ Tiempo: `{:.1f}s`\n"
                "╰───✦ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
            ),
            "download_progress": "📥 Descargando: `{}`\n\n📊 Progreso: `{}`\n⚡ Velocidad: `{}`\n⏱️ ETA: `{}`",
            "redeem_success": "🎉 **¡Felicidades!**\n\nTu cuenta VIP ha sido activada exitosamente.",
            "canjear_invalid": (
                "╭───✦ ❌ KEY INVÁLIDA\n"
                "├● El código ingresado no es válido o ya fue usado\n"
                "├● Usa: /canjear HJ-XXXXXXXXXXXX\n"
                "╰───✦ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
            ),
            "canjear_info": (
                "╭───✦ 🔑 CANJEAR KEY VIP\n"
                "├● Usa el comando para activar tu VIP:\n"
                "├● /canjear HJ-XXXXXXXXXXXX\n"
                "├●\n"
                "├● 💡 Ejemplo:\n"
                "├● /canjear HJ-ABC123DEF456\n"
                "├●\n"
                "├● 📬 Consigue una key contactando a:\n"
                "├● @hjofc20\n"
                "╰───✦ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
            ),
            "key_generated": (
                "╭───✦ ✅ KEY GENERADA EXITOSAMENTE\n"
                "├● 🔑 Código:\n`{}`\n"
                "├● 🔗 Link de canje:\n{}\n"
                "├● 📅 Días: {}\n"
                "╰───✦ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
            ),
            "admin_panel": (
                "╭───✦ 🔐 PANEL ADMIN\n"
                "├● 👑 VIPs: `{}`\n"
                "├● 💼 Sellers: `{}`\n"
                "├● 🔍 Búsquedas: `{}`\n"
                "├● 👥 Total usuarios: `{}`\n"
                "╰───✦ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
            ),
            "stats_global": (
                "╭───✦ 📊 ESTADÍSTICAS GLOBALES\n"
                "├● 👑 Usuarios VIP: `{}`\n"
                "├● 💼 Sellers: `{}`\n"
                "├● 🔍 Búsquedas Totales: `{}`\n"
                "├● 👥 Total Usuarios: `{}`\n"
                "╰───✦ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
            ),
            "broadcast_done": (
                "╭───✦ ✅ BROADCAST FINALIZADO\n"
                "├● 📬 Enviados: `{}`\n"
                "├● 🚫 Fallidos: `{}`\n"
                "╰───✦ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
            ),
            "update_bot_start": (
                "╭───✦ 🔄 ACTUALIZANDO BOT\n"
                "├● ⏳ Descargando cambios...\n"
                "╰───✦ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
            ),
            "update_bot_success": (
                "╭───✦ ✅ BOT ACTUALIZADO\n"
                "├● 🔄 Reiniciando en 3 segundos...\n"
                "╰───✦ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
            ),
            "update_bot_fail": (
                "╭───✦ ❌ ERROR AL ACTUALIZAR\n"
                "├● 📄 `{}`\n"
                "╰───✦ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
            ),
            "update_bot_uptodate": (
                "╭───✦ ✅ BOT ACTUALIZADO\n"
                "├● Ya está en la última versión\n"
                "╰───✦ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
            ),
            "ma_intro": (
                "╭───✦ 📧 MAIL ACCESS\n"
                "├● 🚫 Sin: gmail, outlook, yahoo, hotmail\n"
                "╰───✦ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n\n"
                "⏱️ **Selecciona el rango de tiempo:**"
            ),
            "ma_searching": (
                "⚙️ **Buscando todos los correos...**\n\n"
                "📧 MAIL ACCESS\n"
                "🚫 Sin: gmail, outlook, yahoo, hotmail\n"
                "⠋ Procesando"
            ),
            "ma_completed": (
                "╭───✦ 📧 MAIL ACCESS\n"
                "├● 🔍 Todos los correos\n"
                "├● 📊 Resultados: `{}`\n"
                "├● ⏱️ Tiempo: `{:.1f}s`\n"
                "├● 🚫 Sin: gmail, outlook, yahoo, hotmail\n"
                "╰───✦ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
            ),
            "ma_no_results": (
                "╭───✦ ⚠️ SIN RESULTADOS\n"
                "├● No hay correos filtrados en el rango seleccionado\n"
                "╰───✦ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
            ),
            "imap_intro": (
                "╭───✦ 📧 IMAP CHECKER\n"
                "├● Responde a un archivo .txt con mail:pass\n"
                "├● Usa: responder a archivo + /imap\n"
                "╰───✦ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
            ),
            "imap_no_file": (
                "╭───✦ ❌ IMAP CHECKER\n"
                "├● Responde a un archivo .txt con combos mail:pass\n"
                "├● Ejemplo: responder a archivo + /imap\n"
                "╰───✦ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
            ),
            "imap_processing": (
                "⚙️ **IMAP Check en progreso...**\n\n"
                "📧 Chequeando combos\n"
                "📊 Progreso: `{}/{}` | Hits: `{}`\n"
                "⠋ Procesando"
            ),
            "imap_completed": (
                "╭───✦ 📧 IMAP CHECK\n"
                "├● 📊 Total: `{}`\n"
                "├● ✅ Hits: `{}`\n"
                "├● ❌ Bads: `{}`\n"
                "├● ⏱️ Tiempo: `{:.1f}s`\n"
                "╰───✦ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
            ),
            "imap_no_hits": (
                "╭───✦ 📧 IMAP CHECK\n"
                "├● 📊 Total: `{}`\n"
                "├● ❌ 0 Hits encontrados\n"
                "├● ⏱️ Tiempo: `{:.1f}s`\n"
                "╰───✦ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
            ),
        }

        # Cargar archivos de locale externos
        for lang_file in self.locales_dir.glob('*.json'):
            lang_code = lang_file.stem
            try:
                with open(lang_file, 'r', encoding='utf-8') as f:
                    self.translations[lang_code] = json.load(f)
                logger.info(f"Locale cargado: {lang_code}")
            except Exception as e:
                logger.error(f"Error cargando locale {lang_file}: {e}")

    def get(self, key: str, lang: str = 'es', *args) -> str:
        msg_dict = self.translations.get(lang, {})
        text = msg_dict.get(key)
        if text is None:
            if lang == 'es':
                return self.translations.get('es', {}).get(key, key)
            return self.get(key, 'es', *args)
        try:
            return text.format(*args) if args else text
        except (IndexError, KeyError):
            return text


locale_manager = LocaleManager(config.DIR_LOCALES)
