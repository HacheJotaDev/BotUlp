"""
═══════════════════════════════════════════════════════════════
  HJ ULP EXTRACTOR BOT — Locale Module v6.0 · Obsidian Design
═══════════════════════════════════════════════════════════════
  • Sistema de diseño unificado: tarjetas ╭───✦ + separadores ┈
  • Banner premium con identidad propia
  • Textos con ortografía completa (acentos y eñes)
  • Los JSON de locales/*.json sobrescriben este diccionario
═══════════════════════════════════════════════════════════════
"""

import json
from pathlib import Path
from typing import Dict

from config import config
from logger_setup import logger

# ── Componentes del sistema de diseño ────────────────────────
SEP = "┈" * 18            # separador entre tarjetas
CARD_TOP = "╭───✦"          # cabecera de tarjeta
CARD_END = "╰───✦"          # cierre de tarjeta


class LocaleManager:
    """Gestor de idiomas con fallback automático a español."""

    def __init__(self, locales_dir: Path):
        self.locales_dir = locales_dir
        self.translations: Dict[str, Dict[str, str]] = {}
        self.default_lang = 'es'
        self._load_translations()

    def _load_translations(self):
        # Diccionario base ES (diseño Obsidian v4.0)
        self.translations['es'] = {
            # ── Bienvenida ──────────────────────────────────
            "welcome": (
                "╭━━━━━━━━━━━━━━━━━━━━╮\n"
                "┃ ✦ ☾ **HJ ULP PRO** ☽ ✦\n"
                "┃ ⚡ v4.2 · Professional\n"
                "╰━━━━━━━━━━━━━━━━━━━━╯\n"
                "\n"
                "👋 Hola, **{0}**\n"
                "\n"
                "╭───✦ ⚡ **VENTAJAS**\n"
                "├─ 🔎 Búsqueda paralela ultra-rápida\n"
                "├─ 🗄️ Bases de datos actualizadas 24/7\n"
                "├─ 🛡️ Privacidad y anonimato total\n"
                "├─ 📦 Data lista para usar\n"
                "╰───✦\n"
                "\n"
                + SEP + "\n\n"
                "╭───✦ 🧭 **COMANDOS**\n"
                "├─ {1}\n"
                "╰───✦\n"
                "\n"
                + SEP + "\n\n"
                "╭───✦ 👤 **TU CUENTA**\n"
                "├─ 🎖️ Rango: **{2}**\n"
                "├─ 📊 Búsquedas: `{3}`\n"
                "╰───✦\n"
                "\n"
                "{4}"
                "🌟 Soporte: @hjofc20"
            ),
            "welcome_new": (
                "╭━━━━━━━━━━━━━━━━━━━━╮\n"
                "┃ ✦ ☾ **HJ ULP PRO** ☽ ✦\n"
                "┃ ⚡ v4.2 · Professional\n"
                "╰━━━━━━━━━━━━━━━━━━━━╯\n"
                "\n"
                "👋 Hola, **{0}**\n"
                "\n"
                "╭───✦ ⚡ **VENTAJAS**\n"
                "├─ 🔎 Búsqueda paralela ultra-rápida\n"
                "├─ 🗄️ Bases de datos actualizadas 24/7\n"
                "├─ 🛡️ Privacidad y anonimato total\n"
                "├─ 📦 Data lista para usar\n"
                "╰───✦\n"
                "\n"
                "╭───✦ 🎁 **REGALO DE BIENVENIDA**\n"
                "├─ Tienes **1 búsqueda gratis** para probar\n"
                "├─ Luego necesitarás VIP para seguir buscando\n"
                "╰───✦\n"
                "\n"
                + SEP + "\n\n"
                "╭───✦ 🧭 **COMANDOS**\n"
                "├─ {1}\n"
                "╰───✦\n"
                "\n"
                + SEP + "\n\n"
                "╭───✦ 👤 **TU CUENTA**\n"
                "├─ 🎖️ Rango: **{2}**\n"
                "├─ 📊 Búsquedas: `{3}`\n"
                "╰───✦\n"
                "\n"
                "{4}"
                "🌟 Soporte: @hjofc20"
            ),

            # ── Navegación general ──────────────────────────
            "cmd_list": (
                "╭───✦ 🧭 **COMANDOS DISPONIBLES**\n"
                "├─ {0}\n"
                "╰───✦\n"
                "\n"
                "💡 También puedes usar los botones de abajo."
            ),
            "select_language": (
                "╭───✦ 🌐 **IDIOMA / LANGUAGE**\n"
                "├─ Selecciona tu idioma preferido\n"
                "╰───✦"
            ),
            "language_selected": "🌐 Idioma actualizado correctamente.",
            "my_account": (
                "╭───✦ 👤 **MI CUENTA**\n"
                "├─ 🆔 ID: `{0}`\n"
                "├─ 🎖️ Rango: **{1}**\n"
                "├─ 📅 Miembro desde: `{2}`\n"
                "├─ 📊 Búsquedas totales: `{3}`\n"
                "{4}"
                "╰───✦"
            ),
            "vip_expiring": "⚠️ **Tu VIP expira en {0} día(s)** — renuévalo desde «💎 Renovar VIP» para no perder acceso",
            "vip_expiring_today": "⚠️ **Tu VIP expira HOY** — renuévalo ahora desde «💎 Renovar VIP»",
            "acct_vip_line": "├─ ⏳ VIP activo hasta: `{0}` · {1}\n├─ {2}\n",
            "acct_vip_days_many": "restan **{0} días**",
            "acct_vip_days_one": "resta **1 día**",
            "acct_free_available": "├─ 🎁 Búsqueda gratis: **Disponible**\n",
            "acct_free_used": "├─ 🎁 Búsqueda gratis: **Usada** — hazte 💎 **VIP** para seguir buscando\n",
            "ping_info": (
                "╭───✦ 📶 **PONG**\n"
                "├─ ⚡ Latencia: `{0:.0f} ms`\n"
                "├─ ⏱️ Uptime: `{1}`\n"
                "├─ 🧩 Versión: `{2}`\n"
                "╰───✦"
            ),
            "id_info": (
                "╭───✦ 🪪 **INFORMACIÓN**\n"
                "├─ 👤 Tu ID: `{0}`\n"
                "├─ 💬 Chat ID: `{1}`\n"
                "├─ 📌 Tipo: `{2}`\n"
                "╰───✦"
            ),

            # ── Búsqueda ────────────────────────────────────
            "ask_domain": (
                "╭───✦ 🔍 **NUEVA BÚSQUEDA**\n"
                "├─ ✍️ Escribe el dominio que deseas buscar\n"
                "├─ 💡 Ejemplo: `ejemplo.com`\n"
                "╰───✦"
            ),
            "search_step_time": (
                "╭───✦ 🔍 **NUEVA BÚSQUEDA**\n"
                "├─ 🔎 Dominio: `{0}`\n"
                "╰───✦\n"
                "\n"
                "⏳ Selecciona el rango de tiempo:"
            ),
            "search_step_format": (
                "╭───✦ 📄 **FORMATO DE SALIDA**\n"
                "├─ Elige cómo quieres recibir los resultados\n"
                "╰───✦"
            ),
            "search_loading": (
                "╭───✦ 🔍 **BUSCANDO**\n"
                "├─ 🔎 Dominio: `{0}`\n"
                "├─ ⏱️ Transcurrido: `{3}s`\n"
                "╰───✦\n"
                "\n"
                "{1} {2}"
            ),
            "search_completed": (
                "╭───✦ ✅ **BÚSQUEDA COMPLETADA**\n"
                "├─ 🔎 Dominio: `{0}`\n"
                "├─ 📑 Formato: `{1}`\n"
                "├─ 📊 Resultados: **{2}**\n"
                "├─ ⏱️ Tiempo: `{3:.1f}s`\n"
                "╰───✦"
            ),
            "search_completed_free": (
                "╭───✦ ✅ **BÚSQUEDA COMPLETADA**\n"
                "├─ 🔎 Dominio: `{0}`\n"
                "├─ 📑 Formato: `{1}`\n"
                "├─ 📊 Resultados: **{2}**\n"
                "├─ ⏱️ Tiempo: `{3:.1f}s`\n"
                "╰───✦\n"
                "\n"
                "🎁 Esta fue tu **búsqueda gratis**.\n"
                "💎 Consigue VIP para seguir buscando."
            ),
            "no_results": (
                "╭───✦ ⚠️ **SIN RESULTADOS**\n"
                "├─ No se encontraron datos para `{0}`\n"
                "├─ 🔁 Prueba con «24h + Antiguos» o reporta la URL\n"
                "╰───✦"
            ),
            # v4.2.7: sin resultados tras escanear YA «24h + Antiguos» →
            # no se ofrece reintento (no queda nada más que revisar).
            "no_results_all": (
                "╭───✦ ⚠️ **SIN RESULTADOS**\n"
                "├─ No se encontraron datos para `{0}`\n"
                "├─ 📂 Ya se escanearon las bases «24h + Antiguos»\n"
                "├─ 📨 Reporta la URL para revisión manual\n"
                "╰───✦"
            ),
            "search_in_progress": (
                "⏳ **Búsqueda en curso**\n"
                "\n"
                "Tu búsqueda se ejecutará automáticamente al terminar la actual.\n"
                "📋 Posición en cola: `{0}`"
            ),
            "search_already_running": (
                "⏳ **Búsqueda en curso** — se ejecutará automáticamente al terminar la actual."
            ),
            "url_usage": (
                "╭───✦ ⚠️ **FALTA EL ENLACE**\n"
                "├─ Escribe `/url` seguido del dominio a buscar\n"
                "├─ ✍️ Ejemplo: `/url ejemplo.com`\n"
                "╰───✦"
            ),
            "start_error": (
                "⚠️ Ocurrió un error interno al procesar tu comando.\n"
                "Por favor, inténtalo de nuevo enviando /start"
            ),
            "access_denied": (
                "╭───✦ 🚫 **ACCESO DENEGADO**\n"
                "├─ Tu búsqueda gratis ya fue utilizada\n"
                "├─ 💎 Hazte VIP para buscar sin límites\n"
                "├─ 👥 O invita amigos y gana búsquedas gratis\n"
                "╰───✦"
            ),
            "access_denied_no_free": (
                "╭───✦ 🚫 **ACCESO DENEGADO**\n"
                "├─ Esta función es exclusiva para usuarios **VIP**\n"
                "├─ 💎 Consigue tu VIP desde «Comprar VIP»\n"
                "╰───✦"
            ),
            "loading": "⚙️ **Procesando...**",

            # ── Keys / canje ────────────────────────────────
            "redeem_success": (
                "╭━━━━━━━━━━━━━━━━━━━━╮\n"
                "┃ 🎉 **¡VIP ACTIVADO!**\n"
                "╰━━━━━━━━━━━━━━━━━━━━╯\n"
                "\n"
                "✅ Tu cuenta VIP se activó correctamente.\n"
                "🚀 Disfruta de todas las funciones premium."
            ),
            "canjear_invalid": (
                "╭───✦ ❌ **KEY INVÁLIDA**\n"
                "├─ El código no existe o ya fue utilizado\n"
                "├─ 📌 Formato: `/canjear HJ-XXXXXXXXXXXX`\n"
                "╰───✦"
            ),
            "canjear_info": (
                "╭───✦ 🔑 **CANJEAR KEY VIP**\n"
                "├─ Activa tu VIP con el comando:\n"
                "├─ ➡️ `/canjear HJ-XXXXXXXXXXXX`\n"
                "├─\n"
                "├─ 💡 Ejemplo:\n"
                "├─ ➡️ `/canjear HJ-ABC123DEF456`\n"
                "╰───✦\n"
                "\n"
                "📞 Consigue tu key en: @hjofc20"
            ),
            "key_generated": (
                "╭───✦ ✅ **KEY GENERADA**\n"
                "├─ 🔑 Código: `{0}`\n"
                "├─ 🔗 Canje: {1}\n"
                "├─ 📅 Duración: **{2} días**\n"
                "╰───✦\n"
                "\n"
                "📤 Comparte el link con tu cliente para activarlo."
            ),

            # ── Compra VIP ──────────────────────────────────
            "buy_vip_info": (
                "╭───✦ 💎 **COMPRAR VIP**\n"
                "├─ ⚡ 1 día » $6\n"
                "├─ 📊 3 días » $10\n"
                "├─ 🔥 7 días » $25\n"
                "├─ 👑 30 días » $100\n"
                "╰───✦\n"
                "\n"
                "📬 Contacto: {0}"
            ),
            "pay_plans": (
                "╭───✦ 💳 **COMPRAR VIP**\n"
                "├─ 🪙 Pago automático multi-cripto\n"
                "├─ ⚡ Activación instantánea al confirmar\n"
                "╰───✦\n"
                "\n"
                "👇 Selecciona tu plan:"
            ),
            "pay_invoice": (
                "╭───✦ 💳 **PAGO CREADO**\n"
                "├─ 📦 Plan: **{0}**\n"
                "├─ 💲 Monto: **${1:.2f} USD**\n"
                "╰───✦\n"
                "\n"
                "🔗 Paga aquí: {2}\n"
                "\n"
                "⏳ Tu VIP se activa automáticamente al confirmar el pago."
            ),
            "pay_checking": "⏳ Verificando el estado de tu pago...",
            "pay_pending": (
                "╭───✦ ⏳ **PAGO PENDIENTE**\n"
                "├─ Tu pago está siendo procesado por la red\n"
                "├─ ⚡ El VIP se activará automáticamente al confirmar\n"
                "╰───✦"
            ),
            "pay_status_pending": (
                "╭───✦ ⏳ **PAGO EN PROCESO**\n"
                "├─ 📦 Plan: **{0}**\n"
                "├─ 💲 Monto: **${1:.2f} USD**\n"
                "├─ 🌐 La red está confirmando tu transacción\n"
                "├─ ⚡ El VIP se activa automáticamente al confirmar\n"
                "╰───✦"
            ),
            "pay_no_pending": (
                "╭───✦ 💳 **SIN PAGOS PENDIENTES**\n"
                "├─ No encontramos pagos en proceso para tu cuenta\n"
                "├─ 💎 Crea uno desde «Comprar VIP»\n"
                "╰───✦"
            ),
            "pay_expired": (
                "╭───✦ ❌ **PAGO EXPIRADO**\n"
                "├─ La factura ha expirado\n"
                "├─ 🔄 Crea una nueva desde «Comprar VIP»\n"
                "╰───✦"
            ),
            "pay_failed": (
                "╭───✦ ❌ **PAGO FALLIDO**\n"
                "├─ Hubo un error procesando el pago\n"
                "├─ 🔄 Inténtalo de nuevo o contacta a soporte\n"
                "╰───✦"
            ),
            "pay_success": (
                "╭━━━━━━━━━━━━━━━━━━━━╮\n"
                "┃ ✅ **PAGO CONFIRMADO**\n"
                "╰━━━━━━━━━━━━━━━━━━━━╯\n"
                "\n"
                "🎉 Tu VIP fue activado por **{0} días**.\n"
                "🚀 Ya puedes usar /url o el menú para buscar."
            ),
            "pay_api_error": (
                "╭───✦ ❌ **ERROR DE PAGO**\n"
                "├─ No se pudo crear la factura\n"
                "├─ ⏳ Inténtalo de nuevo en unos minutos\n"
                "╰───✦"
            ),
            "pay_deposit": (
                "╭───✦ 💳 **PAGO CREADO**\n"
                "├─ 📦 Plan: **{0}**\n"
                "├─ 💲 Precio: **${1:.2f} USD**\n"
                "╰───✦\n"
                "\n"
                "📎 Envía exactamente: **{2} {3}**\n"
                "📍 A la dirección: `{4}`\n"
                "\n"
                "⏳ El VIP se activa automáticamente al confirmar."
            ),

            # ── Admin ───────────────────────────────────────
            "admin_panel": (
                "╭───✦ 🔐 **PANEL DE ADMINISTRACIÓN**\n"
                "├─ 👑 VIPs activos: `{0}`\n"
                "├─ 💼 Sellers: `{1}`\n"
                "├─ 🔍 Búsquedas totales: `{2}`\n"
                "├─ 👥 Usuarios registrados: `{3}`\n"
                "├─ 🆕 Nuevos (sin buscar): `{4}`\n"
                "╰───✦"
            ),
            "stats_global": (
                "╭───✦ 📊 **ESTADÍSTICAS GLOBALES**\n"
                "├─ 👑 Usuarios VIP: `{0}`\n"
                "├─ 💼 Sellers: `{1}`\n"
                "├─ 🔍 Búsquedas totales: `{2}`\n"
                "├─ 👥 Usuarios totales: `{3}`\n"
                "├─ 🆕 Nuevos (sin buscar): `{4}`\n"
                "╰───✦"
            ),
            "vip_list_header": "╭───✦ 👑 **USUARIOS VIP** · {0}",
            "sellers_list_header": "╭───✦ 💼 **SELLERS** · {0}",
            "vip_list_empty": (
                "╭───✦ 👑 **USUARIOS VIP**\n"
                "├─ No hay usuarios VIP activos\n"
                "╰───✦"
            ),
            "sellers_list_empty": (
                "╭───✦ 💼 **SELLERS**\n"
                "├─ No hay sellers registrados\n"
                "╰───✦"
            ),
            "list_footer": "╰───✦",
            "list_more": "├─ … y **{0}** más",
            "broadcast_started": (
                "╭───✦ 📣 **{0} INICIADO**\n"
                "├─ 👥 Destinatarios: `{1}`\n"
                "├─ ⏳ Enviando...\n"
                "╰───✦"
            ),
            "broadcast_progress": (
                "╭───✦ 📣 **{0}**\n"
                "├─ 📬 Enviados: `{1}/{2}`\n"
                "├─ 🚫 Fallidos: `{3}`\n"
                "╰───✦"
            ),
            "broadcast_done": (
                "╭───✦ ✅ **BROADCAST FINALIZADO**\n"
                "├─ 📬 Enviados: `{0}`\n"
                "├─ 🚫 Fallidos: `{1}`\n"
                "╰───✦"
            ),
            "sizedisp_info": (
                "╭───✦ 💾 **ALMACENAMIENTO VPS**\n"
                "├─ 📊 Total: `{0}`\n"
                "├─ 📈 Usado: `{1}` (`{2:.1f}%`)\n"
                "├─ 📉 Libre: `{3}`\n"
                "╰───✦\n"
                "\n"
                "`{4}`"
            ),

            # ── Actualización ───────────────────────────────
            "update_bot_start": (
                "╭───✦ 🔄 **ACTUALIZANDO BOT**\n"
                "├─ ⏳ Descargando cambios desde GitHub...\n"
                "╰───✦"
            ),
            "update_bot_success": (
                "╭───✦ ✅ **BOT ACTUALIZADO**\n"
                "├─ 🔄 Reiniciando en 3 segundos...\n"
                "╰───✦"
            ),
            "update_bot_fail": (
                "╭───✦ ❌ **ERROR AL ACTUALIZAR**\n"
                "├─ 📄 `{0}`\n"
                "╰───✦"
            ),
            "update_bot_uptodate": (
                "╭───✦ ✅ **BOT ACTUALIZADO**\n"
                "├─ Ya estás en la última versión\n"
                "╰───✦"
            ),

            # ── IMAP Checker ────────────────────────────────
            "imap_info": (
                "╭───✦ 📧 **IMAP CHECKER**\n"
                "├─ Verifica combos **mail:pass** vía IMAP SSL\n"
                "╰───✦\n"
                "\n"
                "**Modos de uso:**\n"
                "\n"
                "1️⃣ **Clásico** — hits directos:\n"
                "     Responde a un .txt + `/imap`\n"
                "\n"
                "2️⃣ **Con keywords** — filtro + ZIP:\n"
                "     Responde a un .txt + `/imap kw1, kw2`\n"
                "\n"
                "3️⃣ **Por país** — geolocalización + ZIP:\n"
                "     Responde a un .txt + `/imap country`\n"
                "\n"
                "4️⃣ **Por remitentes** — buzones con mensajes de esos correos + ZIP:\n"
                "     Responde a un .txt + `/imap r1@dom.com, r2@dom.com`\n"
                "\n"
                "📌 Ejemplo: `/imap netflix, spotify, amazon`\n"
                "📌 Ejemplo remitentes: `/imap disneyplus@trx.mail2.disneyplus.com`\n"
                "📌 Máximo **10 keywords** o **10 remitentes** separados por coma\n"
                "\n"
                "📁 El ZIP incluye:\n"
                "     📄 `all_hits.txt` — todos los hits\n"
                "     📄 `bad_accounts.txt` — cuentas fallidas\n"
                "     📁 `domains/` — agrupados por dominio\n"
                "     📁 `keywords/` — por keyword con detalle\n"
                "     📁 `sender/` — buzones con mensajes de los remitentes\n"
                "     📁 `countries/` — por país (modo country)"
            ),
            "imap_no_file": (
                "╭───✦ ❌ **IMAP CHECKER**\n"
                "├─ Debes responder a un archivo **.txt** con combos `mail:pass`\n"
                "╰───✦\n"
                "\n"
                "💡 Uso: responde al archivo + `/imap kw1, kw2`"
            ),
            "imap_too_many_keywords": (
                "╭───✦ ⚠️ **IMAP CHECKER**\n"
                "├─ Máximo **10 keywords** permitidas\n"
                "├─ Usaste: `{0}`\n"
                "╰───✦"
            ),
            "imap_too_many_senders": (
                "╭───✦ ⚠️ **IMAP CHECKER**\n"
                "├─ Máximo **10 remitentes** permitidos\n"
                "├─ Usaste: `{0}`\n"
                "╰───✦"
            ),
            "imap_keywords_waiting_file": (
                "╭───✦ 📧 **IMAP CHECKER**\n"
                "├─ 🔎 Keywords: `{0}`\n"
                "╰───✦\n"
                "\n"
                "⏳ Ahora envía un archivo .txt con `mail:pass` para iniciar."
            ),
            "imap_country_waiting_file": (
                "╭───✦ 🌍 **IMAP CHECKER · MODO PAÍS**\n"
                "├─ Los hits se agruparán por geolocalización\n"
                "╰───✦\n"
                "\n"
                "⏳ Ahora envía un archivo .txt con `mail:pass` para iniciar."
            ),
            # v4.2.8: modo por remitente
            "imap_sender_waiting_file": (
                "╭───✦ 📬 **IMAP · BÚSQUEDA POR REMITENTES**\n"
                "├─ 📨 Remitentes ({0}): {1}\n"
                "╰───✦\n"
                "\n"
                "⏳ Ahora envía un archivo .txt con `mail:pass` para iniciar.\n"
                "🎯 Buscaré TODOS los buzones con mensajes de cualquiera de ellos"
            ),
            "imap_zip_caption_sender": (
                "╭───✦ 📬 **IMAP + REMITENTES**\n"
                "├─ 📨 Remitentes: `{0}`\n"
                "├─ 📊 Total: `{1}` · 📬 Buzones con mensajes: `{2}` · ❌ Descartados: `{3}`\n"
                "├─ ⏱️ Tiempo: `{4:.1f}s`\n"
                "╰───✦\n"
                "\n"
                "📁 `sender/` — {5} buzones con mensajes de esos remitentes\n"
                "📁 `bad_accounts.txt` — descartados (login fallido o sin mensajes)"
            ),
            "imap_processing": (
                "╭───✦ 📧 **IMAP CHECKER**\n"
                "├─ 📊 Progreso: `{0}/{1}` · ✅ Hits: `{2}`\n"
                "╰───✦\n"
                "\n"
                "{3}"
            ),
            "imap_country_resolving": (
                "╭───✦ 🌍 **GEOLOCALIZANDO HITS**\n"
                "├─ 📧 Resolviendo: `{0}` cuentas\n"
                "╰───✦"
            ),
            "imap_country_progress": (
                "╭───✦ 🌍 **GEOLOCALIZANDO HITS**\n"
                "├─ 📊 Progreso: `{0}/{1}` · 🌍 Países: `{2}`\n"
                "╰───✦\n"
                "\n"
                "{3}"
            ),
            "imap_completed": (
                "╭───✦ 📧 **IMAP CHECK FINALIZADO**\n"
                "├─ 📊 Total: `{0}`\n"
                "├─ ✅ Hits: `{1}`\n"
                "├─ ❌ Bads: `{2}`\n"
                "├─ ⏱️ Tiempo: `{3:.1f}s`\n"
                "╰───✦"
            ),
            "imap_no_hits": (
                "╭───✦ 📧 **IMAP CHECK FINALIZADO**\n"
                "├─ 📊 Total: `{0}`\n"
                "├─ ❌ 0 hits encontrados\n"
                "├─ ⏱️ Tiempo: `{1:.1f}s`\n"
                "╰───✦"
            ),
            "imap_zip_caption": (
                "╭───✦ 📧 **IMAP + KEYWORDS**\n"
                "├─ 📊 Total: `{0}` · ✅ Hits: `{1}` · ❌ Bads: `{2}`\n"
                "├─ ⏱️ Tiempo: `{3:.1f}s`\n"
                "├─ 🔎 Keywords: `{4}`\n"
                "╰───✦\n"
                "\n"
                "📁 `all_hits.txt` — {5} hits totales\n"
                "📁 `bad_accounts.txt` — cuentas fallidas\n"
                "📁 `domains/` — agrupados por dominio\n"
                "📁 `keywords/` — por keyword con detalle"
            ),
            "imap_zip_caption_country": (
                "╭───✦ 🌍 **IMAP + PAÍSES**\n"
                "├─ 📊 Total: `{0}` · ✅ Hits: `{1}` · ❌ Bads: `{2}`\n"
                "├─ ⏱️ Tiempo: `{3:.1f}s`\n"
                "├─ 🌍 Países detectados: `{4}`\n"
                "╰───✦\n"
                "\n"
                "📁 `all_hits.txt` — todos los hits\n"
                "📁 `bad_accounts.txt` — cuentas fallidas\n"
                "📁 `domains/` — agrupados por dominio\n"
                "📁 `countries/` — por país con resumen"
            ),
            "imap_zip_caption_country_kw": (
                "╭───✦ 🌍 **IMAP + KEYWORDS + PAÍSES**\n"
                "├─ 📊 Total: `{0}` · ✅ Hits: `{1}` · ❌ Bads: `{2}`\n"
                "├─ ⏱️ Tiempo: `{3:.1f}s`\n"
                "├─ 🔎 Keywords: `{4}`\n"
                "├─ 🌍 Países detectados: `{6}`\n"
                "╰───✦\n"
                "\n"
                "📁 `all_hits.txt` — {5} hits totales\n"
                "📁 `bad_accounts.txt` — cuentas fallidas\n"
                "📁 `domains/` — agrupados por dominio\n"
                "📁 `keywords/` — por keyword con detalle\n"
                "📁 `countries/` — por país con resumen"
            ),

            # ── Descargas ───────────────────────────────────
            "file_management": (
                "╭───✦ 📂 **GESTIÓN DE ARCHIVOS**\n"
                "├─ 📁 Total: `{0}` archivos\n"
                "├─ ⚡ Últimas 24h: `{1}`\n"
                "├─ 🗄️ Histórico: `{2}`\n"
                "╰───✦\n"
                "\n"
                "╭───✦ 🔄 **DESCARGAS**\n"
                "├─ ♻️ Auto-DL: **{3}**\n"
                "├─ 📥 En cola: `{4}` archivos\n"
                "├─ ⬇️ Activas: `{5}` descargas\n"
                "╰───✦"
            ),
            "download_progress": (
                "📥 **Descargando:** `{0}`\n"
                "\n"
                "📊 Progreso: `{1}`\n"
                "⚡ Velocidad: `{2}`\n"
                "⏱️ ETA: `{3}`"
            ),

            # ── Errores ─────────────────────────────────────
            "error_generic": (
                "╭───✦ ❌ **ERROR**\n"
                "├─ Ocurrió un problema: `{0}`\n"
                "├─ 🔄 Inténtalo de nuevo en unos segundos\n"
                "╰───✦"
            ),

            # ── Fases de búsqueda / misc ────────────────────
            "phase_scanning": "📂 Escaneando bases de datos...",
            "phase_processing": "⚡ Procesando coincidencias...",
            "phase_filtering": "🧮 Filtrando resultados...",
            "free_available": "Disponible",
            "free_used": "Usada",
            "report_received": (
                "╭───✦ ⚠️ **REPORTE DE URL**\n"
                "├─ 👤 Usuario: `{0}`\n"
                "├─ 🔍 URL: `{1}`\n"
                "╰───✦"
            ),

            # ── Sistema de referidos ────────────────────────
            "ref_info": (
                "╭───✦ 👥 **PROGRAMA DE REFERIDOS**\n"
                "├─ 🔗 Tu enlace personal:\n"
                "├─ ➡️ `{0}`\n"
                "╰───✦\n"
                "\n"
                "╭───✦ 📊 **TUS NÚMEROS**\n"
                "├─ 👥 Amigos invitados: `{1}`\n"
                "├─ 🎁 Búsquedas gratis disponibles: `{2}`\n"
                "╰───✦\n"
                "\n"
                "💰 **¿Cómo funciona?**\n"
                "├─ 🎁 Tu amigo se une → él recibe **+1 búsqueda**\n"
                "├─ 🎁 Y tú también ganas **+1 búsqueda gratis**\n"
                "╰─ ♾️ ¡Sin límite! Invita a todos los que quieras"
            ),
            "ref_share_text": (
                "🔥 Descubre HJ ULP PRO — el extractor más rápido\n"
                "🎁 Únete con mi enlace y llévate búsquedas gratis extra 🚀"
            ),
            "ref_notify_referrer": (
                "╭───✦ 🎉 **¡NUEVO REFERIDO!**\n"
                "├─ 👥 **{0}** se unió con tu enlace\n"
                "├─ 🎁 Recompensa: **+1 búsqueda gratis**\n"
                "├─ 📊 Total invitados: `{1}`\n"
                "╰───✦\n"
                "\n"
                "👥 Sigue invitando y gana búsquedas ilimitadas"
            ),
            "welcome_ref_bonus": (
                "╭───✦ 🎁 **BONO DE INVITACIÓN**\n"
                "├─ Entraste con un enlace de referido\n"
                "├─ 🎁 Búsquedas gratis totales: **{0}**\n"
                "╰───✦"
            ),
            "acct_ref_line": "├─ 👥 Referidos: `{0}` · 🎁 Bonos: `{1}`\n",
            "bonus_consumed": "🎁 Usaste una búsqueda de tu **bono de referidos**.",
            "free_remaining": "🎁 Te quedan **{0}** búsqueda(s) gratis.",
            "free_exhausted": "💎 Consigue VIP o invita amigos con «👥 Referidos» para seguir buscando.",
        }

        # Los archivos locales/*.json sobrescriben el diccionario base
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
        except (IndexError, KeyError, ValueError):
            return text


locale_manager = LocaleManager(config.DIR_LOCALES)
