"""
═══════════════════════════════════════════════════════════════
  HJ ULP EXTRACTOR BOT — UI & Keyboards Module v6.0 · Obsidian
═══════════════════════════════════════════════════════════════
  • Botones con jerarquía visual consistente
  • Botones URL reales (pagar invoice, soporte)
  • Insignias únicas por rango: 🆓 FREE · 💎 VIP · 💼 SELLER · 👑 OWNER
  • Roles FREE / VIP / SELLER / OWNER
═══════════════════════════════════════════════════════════════
"""

from urllib.parse import quote

from telethon import Button

from locale import locale_manager
from roles import UserRole
from config import config


class UI:
    # Insignias visuales unicas por rango (identidad del bot)
    ROLE_BADGES = {
        UserRole.OWNER: "👑 OWNER",
        UserRole.SELLER: "💼 SELLER",
        UserRole.VIP: "💎 VIP",
        UserRole.FREE: "🆓 FREE",
    }

    @staticmethod
    def role_badge(role: UserRole) -> str:
        """Insignia con emoji por rango — se muestra en bienvenida y cuenta."""
        return UI.ROLE_BADGES.get(role, role.value)

    @staticmethod
    def text(key: str, lang: str = 'es', *args) -> str:
        localized = locale_manager.get(key, lang, *args)
        if localized:
            return localized
        return locale_manager.get(key, 'es', *args) or key


class Keyboards:
    # Botones compartidos
    BACK = [[Button.inline("«  Volver", b"back_main")]]
    # v4.2.4 FIX: separar el BOTÓN individual de la FILA. Met una lista dentro
    # de una fila provocaba "AttributeError: 'list' object has no attribute
    # 'SUBCLASS_OF_ID'" al serializar el teclado (rompía /start para FREE y OWNER).
    LANG_BUTTON = Button.inline("🌐  Idioma", b"ch_lang")   # botón suelto (filas de 2)
    LANG_BTN = [LANG_BUTTON]                               # fila de 1 (VIP/SELLER)
    SUPPORT_URL = [Button.url("📞  Soporte", f"https://t.me/{config.SUPPORT_CONTACT.lstrip('@')}")]

    @staticmethod
    def main(role: UserRole, lang: str = 'es', has_free_search: bool = False):
        # has_free_search acepta int (cantidad de búsquedas gratis) o bool.
        free_n = int(has_free_search or 0)

        if role == UserRole.FREE:
            buttons = []
            if free_n == 1:
                buttons.append([Button.inline("🎁  Búsqueda gratis  (1/1)", b"search_init")])
            elif free_n > 1:
                buttons.append([Button.inline(f"🎁  Búsquedas gratis  ({free_n})", b"search_init")])
            # Comprar VIP SIEMPRE visible para usuarios FREE
            buttons.append([Button.inline("💎  Comprar VIP", b"buy_vip_info"),
                            Button.inline("🔑  Canjear key", b"canjear_key")])
            buttons.append([Button.inline("👥  Referidos", b"ref_info"),
                            Button.inline("👤  Mi cuenta", b"my_account")])
            buttons.append([Button.inline("📋  Comandos", b"cmd_list"),
                            Keyboards.LANG_BUTTON])
            return buttons

        elif role == UserRole.VIP:
            return [
                [Button.inline("🔍  Nueva búsqueda", b"search_init"),
                 Button.inline("📧  IMAP Checker", b"imap_info")],
                [Button.inline("💎  Renovar VIP", b"buy_vip_info"),
                 Button.inline("👤  Mi cuenta", b"my_account")],
                [Button.inline("👥  Referidos", b"ref_info"),
                 Button.inline("📋  Comandos", b"cmd_list")],
                Keyboards.LANG_BTN,
            ]

        elif role == UserRole.SELLER:
            return [
                [Button.inline("🔍  Nueva búsqueda", b"search_init"),
                 Button.inline("📧  IMAP Checker", b"imap_info")],
                [Button.inline("🔑  Generar key", b"seller_genkey"),
                 Button.inline("👤  Mi cuenta", b"my_account")],
                [Button.inline("👥  Referidos", b"ref_info"),
                 Button.inline("📋  Comandos", b"cmd_list")],
                Keyboards.LANG_BTN,
            ]

        elif role == UserRole.ADMIN:
            return [
                [Button.inline("🔍  Nueva búsqueda", b"search_init"),
                 Button.inline("📧  IMAP Checker", b"imap_info")],
                [Button.inline("🔐  Panel admin", b"admin_enter"),
                 Button.inline("📂  Gestión archivos", b"adm_files")],
                [Button.inline("👥  Referidos", b"ref_info"),
                 Button.inline("👤  Mi cuenta", b"my_account")],
                [Button.inline("📋  Comandos", b"cmd_list"),
                 Keyboards.LANG_BUTTON],
            ]

        return []

    @staticmethod
    def time():
        return [
            [Button.inline("⚡  Últimas 24 horas", b"time_24h"),
             Button.inline("🗂️  24h + Antiguos", b"time_all")],
            [Button.inline("📅  Solo antiguos", b"time_old")],
            [Button.inline("«  Cancelar", b"back_main")],
        ]

    @staticmethod
    def formats():
        return [
            [Button.inline("📄  ULP  (completo)", b"fmt_ulp"),
             Button.inline("📧  mail:pass", b"fmt_mail")],
            [Button.inline("👤  user:pass", b"fmt_user")],
            [Button.inline("«  Cancelar", b"back_main")],
        ]

    @staticmethod
    def no_results(kw: str):
        return [
            [Button.inline("🔍  Nueva búsqueda", b"search_init"),
             Button.inline("⚠️  Reportar URL", b"report_url")],
            [Button.inline("💎  Comprar VIP", b"buy_vip_info")],
            [Button.inline("«  Volver", b"back_main")],
        ]

    @staticmethod
    def result_actions():
        """Acciones bajo el archivo de resultados de una búsqueda."""
        return [
            [Button.inline("🔍  Nueva búsqueda", b"search_init"),
             Button.inline("👤  Mi cuenta", b"my_account")],
        ]

    @staticmethod
    def admin():
        return [
            [Button.inline("👑  Ver VIPs", b"adm_vips"),
             Button.inline("💼  Sellers", b"adm_sellers")],
            [Button.inline("🔑  Generar key", b"adm_genkey"),
             Button.inline("📊  Estadísticas", b"adm_stats")],
            [Button.inline("📂  Archivos", b"adm_files"),
             Button.inline("🔄  Actualizar bot", b"adm_update_bot")],
            [Button.inline("«  Volver", b"back_main")],
        ]

    @staticmethod
    def gen_key():
        return [
            [Button.inline("1 día", b"gen_1"),
             Button.inline("3 días", b"gen_3"),
             Button.inline("7 días", b"gen_7")],
            [Button.inline("30 días", b"gen_30")],
            [Button.inline("«  Volver", b"back_main")],
        ]

    @staticmethod
    def files_control(auto_dl: bool, pending_count: int, active_count: int):
        if auto_dl:
            btn_auto = Button.inline("✅  Auto-DL · ON", b"toggle_auto_off")
        else:
            btn_auto = Button.inline("❌  Auto-DL · OFF", b"toggle_auto_on")

        return [
            [btn_auto],
            [Button.inline(f"📥  Descargar pendientes  ({pending_count})", b"dl_all")],
            [Button.inline("🗑️  Vaciar pendientes", b"clear_pending")],
            [Button.inline("🔄  Refrescar", b"refresh_files"),
             Button.inline("«  Panel", b"admin_enter")],
        ]

    @staticmethod
    def language_selection():
        return [
            [Button.inline("🇪🇸  Español", b"set_lang_es"),
             Button.inline("🇬🇧  English", b"set_lang_en")],
            [Button.inline("🇧🇷  Português", b"set_lang_pt")],
            [Button.inline("«  Volver", b"back_main")],
        ]

    @staticmethod
    def back(data: str = "back_main"):
        return [[Button.inline("«  Volver", data.encode())]]

    @staticmethod
    def payment_plans():
        return [
            [Button.inline("⚡  1 día  ·  $6", b"pay_1"),
             Button.inline("📊  3 días  ·  $10", b"pay_3")],
            [Button.inline("🔥  7 días  ·  $25", b"pay_7"),
             Button.inline("💎  30 días  ·  $100", b"pay_30")],
            Keyboards.SUPPORT_URL,
            [Button.inline("«  Volver", b"back_main")],
        ]

    @staticmethod
    def payment_invoice(url: str):
        """Teclado post-invoice: botón URL real + verificación manual."""
        return [
            [Button.url("💳  Pagar ahora", url)],
            [Button.inline("🔄  Ya pagué — verificar", b"pay_check")],
            Keyboards.SUPPORT_URL,
            [Button.inline("«  Volver", b"back_main")],
        ]

    @staticmethod
    def payment_checking():
        """Mientras se verifica el estado del pago."""
        return [
            [Button.inline("🔄  Verificar de nuevo", b"pay_check")],
            [Button.inline("💎  Ver planes", b"buy_vip_info")],
            [Button.inline("«  Volver", b"back_main")],
        ]

    @staticmethod
    def imap_info():
        return [
            [Button.inline("«  Volver", b"back_main")]
        ]

    @staticmethod
    def ref_panel(link: str, lang: str = 'es'):
        """Panel de referidos: compartir link (diálogo nativo de Telegram) + volver."""
        share_text = quote(UI.text("ref_share_text", lang))
        share_url = (f"https://t.me/share/url?url={quote(link)}"
                     f"&text={share_text}")
        return [
            [Button.url("📢  Compartir mi link", share_url)],
            [Button.inline("👤  Mi cuenta", b"my_account")],
            [Button.inline("«  Volver", b"back_main")],   # fila directa (back() es [[btn]])
        ]
