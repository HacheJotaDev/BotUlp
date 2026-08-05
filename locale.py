"""
═══════════════════════════════════════════════════════════════
  HJ ULP EXTRACTOR BOT — Locale Module v4.0
═══════════════════════════════════════════════════════════════
  • Textos renovados con mejor diseño
  • Nuevos textos para IMAP con keywords
═══════════════════════════════════════════════════════════════
"""

import json
from pathlib import Path
from typing import Dict

from config import config
from logger_setup import logger


class LocaleManager:
    """Gestor de idiomas con soporte de fallback a espanol."""

    def __init__(self, locales_dir: Path):
        self.locales_dir = locales_dir
        self.translations: Dict[str, Dict[str, str]] = {}
        self.default_lang = 'es'
        self._load_translations()

    def _load_translations(self):
        self.translations['es'] = {
            "welcome_new": (
                "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                "┃   ☾  HJ ULP PRO  ☽  彡\n"
                "┃   by @hjofc20\n"
                "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                "▸ Busqueda ultra-rapida (paralela)\n"
                "▸ Bases actualizadas 24/7\n"
                "▸ Privacidad y anonimato total\n"
                "▸ Data lista para usar\n\n"
                "┌─────────────────────────────┐\n"
                "│  🎁  BIENVENIDO NUEVO USUARIO  │\n"
                "│  Tienes **1 busqueda gratis**  │\n"
                "│  para probar el bot           │\n"
                "└─────────────────────────────┘\n\n"
                "┌─────────────────────────────┐\n"
                "│  📋  Comandos:                 │\n"
                "│  {}  │\n"
                "└─────────────────────────────┘\n\n"
                "🌟 Soporte: @hjofc20\n\n"
                "👤 **Rol:** `{}`  │  📊 **Busquedas:** `{}`"
            ),
            "welcome": (
                "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                "┃   ☾  HJ ULP PRO  ☽  彡\n"
                "┃   by @hjofc20\n"
                "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                "▸ Busqueda ultra-rapida (paralela)\n"
                "▸ Bases actualizadas 24/7\n"
                "▸ Privacidad y anonimato total\n"
                "▸ Data lista para usar\n\n"
                "┌─────────────────────────────┐\n"
                "│  📋  Comandos:                 │\n"
                "│  {}  │\n"
                "└─────────────────────────────┘\n\n"
                "🌟 Soporte: @hjofc20\n\n"
                "👤 **Rol:** `{}`  │  📊 **Busquedas:** `{}`"
            ),
            "buy_vip_info": (
                "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                "┃  💰  COMPRAR VIP ACCESS  💰  ┃\n"
                "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                "┌─────────────────────────────┐\n"
                "│  ⚡  1 dia     »  $6          │\n"
                "│  📊  3 dias    »  $10         │\n"
                "│  🔥  7 dias    »  $25         │\n"
                "│  💎  30 dias   »  $100        │\n"
                "└─────────────────────────────┘\n\n"
                "📬 **CONTACTO:**\n{}"
            ),
            "file_management": (
                "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                "┃  📂  GESTION DE ARCHIVOS     ┃\n"
                "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                "📊 **Base de Datos:**\n"
                "  📁 Total: `{}` archivos\n"
                "  ⚡ Ultimas 24h: `{}`\n"
                "  🗄  Historico: `{}`\n\n"
                "🔄 **Descargas:**\n"
                "  ♻  Auto-DL: `{}`\n"
                "  📝 En cola: `{}` archivos\n"
                "  ⬇  Activas: `{}` descargas"
            ),
            "no_results": (
                "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                "┃    ❌  SIN RESULTADOS        ┃\n"
                "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                "No se encontraron datos para `{}`"
            ),
            "search_step_time": (
                "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                "┃    🔍  NUEVA BUSQUEDA        ┃\n"
                "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                "🔎 **Dominio:** `{}`\n\n"
                "⏳ Selecciona el rango de tiempo:"
            ),
            "loading": "⚙️ **Procesando...**",
            "access_denied": (
                "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                "┃   🚫  ACCESO DENEGADO       ┃\n"
                "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                "Tu busqueda gratis ya fue usada.\n"
                "Necesitas VIP para seguir buscando."
            ),
            "access_denied_no_free": (
                "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                "┃   🚫  ACCESO DENEGADO       ┃\n"
                "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                "Solo usuarios VIP pueden usar esta funcion."
            ),
            "search_in_progress": (
                "⏳ **Busqueda en curso...**\n\n"
                "Tu nueva busqueda se iniciara automaticamente.\n"
                "Posicion en cola: `{}`"
            ),
            "search_already_running": (
                "⏳ **Busqueda en curso.**\n\n"
                "Se ejecutara automaticamente al terminar la actual."
            ),
            "ask_domain": (
                "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                "┃    🔍  NUEVA BUSQUEDA        ┃\n"
                "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                "Escribe el dominio que deseas buscar:"
            ),
            "language_selected": "🌐  Idioma actualizado correctamente.",
            "select_language": (
                "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                "┃   🌐  SELECT LANGUAGE         ┃\n"
                "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                "Elige tu idioma preferido:"
            ),
            "my_account": (
                "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                "┃     👤  MI CUENTA            ┃\n"
                "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                "🆔 **ID:** `{}`\n"
                "🎖 **Rango:** `{}`\n"
                "📅 **Expira:** `{}`\n"
                "📊 **Busquedas:** `{}`\n"
                "🔍 **Busqueda gratis:** `{}`"
            ),
            "search_completed": (
                "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                "┃  ✅  BUSQUEDA COMPLETADA     ┃\n"
                "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                "🔎 **Dominio:** `{}`\n"
                "📄 **Tipo:** `{}`\n"
                "📊 **Resultados:** `{}`\n"
                "⏱ **Tiempo:** `{:.1f}s`"
            ),
            "search_completed_free": (
                "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                "┃  ✅  BUSQUEDA COMPLETADA     ┃\n"
                "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                "🔎 **Dominio:** `{}`\n"
                "📄 **Tipo:** `{}`\n"
                "📊 **Resultados:** `{}`\n"
                "⏱ **Tiempo:** `{:.1f}s`\n\n"
                "🎁 Esta fue tu **busqueda gratis**. Para seguir buscando, compra VIP."
            ),
            "download_progress": (
                "📥 **Descargando:** `{}`\n\n"
                "📊 Progreso: `{}`\n"
                "⚡ Velocidad: `{}`\n"
                "⏱ ETA: `{}`"
            ),
            "redeem_success": (
                "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                "┃      🎉  FELICIDADES!        ┃\n"
                "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                "Tu cuenta VIP ha sido activada exitosamente."
            ),
            "canjear_invalid": (
                "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                "┃     ❌  KEY INVALIDA          ┃\n"
                "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                "El codigo no es valido o ya fue usado.\n\n"
                "💡 Usa: `/canjear HJ-XXXXXXXXXXXX`"
            ),
            "canjear_info": (
                "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                "┃    🔑  CANJEAR KEY VIP        ┃\n"
                "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                "Usa el comando para activar tu VIP:\n"
                "`/canjear HJ-XXXXXXXXXXXX`\n\n"
                "💡 **Ejemplo:**\n"
                "`/canjear HJ-ABC123DEF456`\n\n"
                "📬 Consigue una key contactando a:\n"
                "@hjofc20"
            ),
            "key_generated": (
                "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                "┃  ✅  KEY GENERADA EXITO.     ┃\n"
                "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                "🔑 **Codigo:**\n`{}`\n\n"
                "🔗 **Link de canje:**\n{}\n\n"
                "📅 **Duracion:** {} dias"
            ),
            "admin_panel": (
                "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                "┃     🔐  PANEL ADMIN          ┃\n"
                "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                "👑 **VIPs:** `{}`\n"
                "💼 **Sellers:** `{}`\n"
                "🔍 **Busquedas:** `{}`\n"
                "👥 **Total usuarios:** `{}`\n"
                "🆕 **Nuevos (sin buscar):** `{}`"
            ),
            "stats_global": (
                "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                "┃ 📊  ESTADISTICAS GLOBALES    ┃\n"
                "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                "👑 **Usuarios VIP:** `{}`\n"
                "💼 **Sellers:** `{}`\n"
                "🔍 **Busquedas Totales:** `{}`\n"
                "👥 **Total Usuarios:** `{}`\n"
                "🆕 **Nuevos (sin buscar):** `{}`"
            ),
            "broadcast_done": (
                "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                "┃ ✅  BROADCAST FINALIZADO      ┃\n"
                "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                "📬 **Enviados:** `{}`\n"
                "🚫 **Fallidos:** `{}`"
            ),
            "update_bot_start": (
                "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                "┃  🔄  ACTUALIZANDO BOT        ┃\n"
                "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                "⏳ Descargando cambios..."
            ),
            "update_bot_success": (
                "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                "┃   ✅  BOT ACTUALIZADO        ┃\n"
                "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                "🔄 Reiniciando en 3 segundos..."
            ),
            "update_bot_fail": (
                "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                "┃ ❌  ERROR AL ACTUALIZAR       ┃\n"
                "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                "📄 `{}`"
            ),
            "update_bot_uptodate": (
                "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                "┃   ✅  BOT ACTUALIZADO        ┃\n"
                "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                "Ya esta en la ultima version."
            ),
            # ── IMAP CHECKER v2 ──
            "imap_info": (
                "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                "┃    📧  IMAP CHECKER           ┃\n"
                "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                "Chequea combos **mail:pass** via IMAP SSL.\n\n"
                "**Formas de uso:**\n\n"
                "1️⃣ **Sin keywords** (hits directos):\n"
                "   Responde a un .txt + `/imap`\n\n"
                "2️⃣ **Con keywords** (filtro + ZIP):\n"
                "   Responde a un .txt + `/imap kw1, kw2`\n\n"
                "**Ejemplo:**\n"
                "`/imap netflix, spotify, amazon`\n\n"
                "📌 **Maximo 10 keywords** separadas por coma\n\n"
                "📁 El ZIP contiene:\n"
                "  📄 `hits.txt` — todos los hits\n"
                "  📄 `keyword_results.txt` — filtrados por keyword"
            ),
            "imap_no_file": (
                "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                "┃  ❌  IMAP CHECKER              ┃\n"
                "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                "Debes **responder a un .txt** con combos mail:pass.\n\n"
                "💡 Responde al archivo + `/imap kw1, kw2`"
            ),
            "imap_too_many_keywords": (
                "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                "┃  ⚠️  IMAP CHECKER              ┃\n"
                "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                "Maximo **10 keywords** permitidas.\n"
                "Usaste: `{}`"
            ),
            "imap_keywords_waiting_file": (
                "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                "┃    📧  IMAP CHECKER           ┃\n"
                "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                "🔎 **Keywords:** `{}`\n\n"
                "⏳ Ahora responde a un .txt con mail:pass para iniciar."
            ),
            "imap_processing": (
                "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                "┃    📧  IMAP CHECKER           ┃\n"
                "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                "📊 **Progreso:** `{}/{}` │ ✅ **Hits:** `{}`\n"
                "{}"
            ),
            "imap_completed": (
                "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                "┃     📧  IMAP CHECK            ┃\n"
                "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                "📊 **Total:** `{}`\n"
                "✅ **Hits:** `{}`\n"
                "❌ **Bads:** `{}`\n"
                "⏱ **Tiempo:** `{:.1f}s`"
            ),
            "imap_no_hits": (
                "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                "┃     📧  IMAP CHECK            ┃\n"
                "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                "📊 **Total:** `{}`\n"
                "❌ **0 Hits encontrados**\n"
                "⏱ **Tiempo:** `{:.1f}s`"
            ),
            "imap_zip_caption": (
                "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                "┃  📧  IMAP + KEYWORDS          ┃\n"
                "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                "📊 Total: `{}` │ ✅ Hits: `{}` │ ❌ Bads: `{}`\n"
                "⏱ Tiempo: `{:.1f}s`\n"
                "🔎 Keywords: `{}`\n\n"
                "📁 hits.txt — `{}` hits totales\n"
                "📁 keyword_results.txt — filtrados"
            ),
            # ── PAYMENT ──
            "pay_plans": (
                "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                "┃ 💳  COMPRAR VIP — PAGO     ┃\n"
                "┃    AUTOMATICO               ┃\n"
                "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                "Moneda: **Multi-Cripto (USDT, TRX, etc.)**\n\n"
                "Selecciona tu plan:"
            ),
            "pay_invoice": (
                "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                "┃     💳  PAGO CREADO          ┃\n"
                "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                "📦 **Plan:** {}\n"
                "💲 **Monto:** **${:.2f} USD**\n\n"
                "🔗 **Paga aqui:**\n{}\n\n"
                "⏳ VIP se activara automaticamente al confirmar.\n"
                "📋 Verificacion cada 30 segundos."
            ),
            "pay_checking": "⏳ Verificando estado del pago...",
            "pay_pending": (
                "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                "┃   ⏳  PAGO PENDIENTE           ┃\n"
                "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                "Tu pago esta siendo procesado.\n"
                "El VIP se activara automaticamente."
            ),
            "pay_expired": (
                "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                "┃   ❌  PAGO EXPIRADO            ┃\n"
                "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                "La factura expiro.\n"
                "Crea una nueva para intentar de nuevo."
            ),
            "pay_failed": (
                "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                "┃   ❌  PAGO FALLIDO             ┃\n"
                "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                "Hubo un error con el pago.\n"
                "Intenta nuevamente o contacta soporte."
            ),
            "pay_success": (
                "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                "┃  ✅  PAGO CONFIRMADO           ┃\n"
                "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                "🎉 Tu VIP ha sido activado por **{} dias**\n"
                "Ya puedes usar /url para buscar."
            ),
            "pay_api_error": (
                "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                "┃   ❌  ERROR DE PAGO             ┃\n"
                "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                "No se pudo crear la factura.\n"
                "Intenta de nuevo en unos minutos."
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
