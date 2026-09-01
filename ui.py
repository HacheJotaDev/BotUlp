"""
═══════════════════════════════════════════════════════════════
  HJ ULP EXTRACTOR BOT — UI & Keyboards Module v6.0 · Obsidian
═══════════════════════════════════════════════════════════════
  • Botones con jerarquía visual consistente
  • Botones URL reales (pagar invoice, soporte)
  • Roles FREE / VIP / SELLER / ADMIN
═══════════════════════════════════════════════════════════════
"""

from telethon import Button

from locale import locale_manager
from roles import UserRole
from config import config


class UI:
    @staticmethod
    def text(key: str, lang: str = 'es', *args) -> str:
        localized = locale_manager.get(key, lang, *args)
        if localized:
            return localized
        return locale_manager.get(key, 'es', *args) or key


class Keyboards:
    # Botones compartidos
    BACK = [[Button.inline("«  Volver", b"back_main")]]
    LANG_BTN = [Button.inline("🌐  Idioma", b"ch_lang")]
    SUPPORT_URL = [Button.url("📞  Soporte", f"https://t.me/{config.SUPPORT_CONTACT.lstrip('@')}")]

    @staticmethod
    def main(role: UserRole, lang: str = 'es', has_free_search: bool = False):
        if role == UserRole.FREE:
            buttons = []
            if has_free_search:
                buttons.append([Button.inline("🎁  Búsqueda gratis  (1/1)", b"search_init")])
            else:
                buttons.append([Button.inline("💎  Comprar VIP", b"buy_vip_info")])
            buttons.append([Button.inline("🔑  Canjear key", b"canjear_key"),
                            Button.inline("👤  Mi cuenta", b"my_account")])
            buttons.append([Button.inline("📋  Comandos", b"cmd_list")])
            buttons.append(Keyboards.LANG_BTN)
            return buttons

        elif role == UserRole.VIP:
            return [
                [Button.inline("🔍  Nueva búsqueda", b"search_init"),
                 Button.inline("📧  IMAP Checker", b"imap_info")],
                [Button.inline("👤  Mi cuenta", b"my_account"),
                 Button.inline("📋  Comandos", b"cmd_list")],
                Keyboards.LANG_BTN,
            ]

        elif role == UserRole.SELLER:
            return [
                [Button.inline("🔍  Nueva búsqueda", b"search_init"),
                 Button.inline("📧  IMAP Checker", b"imap_info")],
                [Button.inline("🔑  Generar key", b"seller_genkey"),
                 Button.inline("👤  Mi cuenta", b"my_account")],
                [Button.inline("📋  Comandos", b"cmd_list")],
                Keyboards.LANG_BTN,
            ]

        elif role == UserRole.ADMIN:
            return [
                [Button.inline("🔍  Nueva búsqueda", b"search_init"),
                 Button.inline("📧  IMAP Checker", b"imap_info")],
                [Button.inline("🔐  Panel admin", b"admin_enter"),
                 Button.inline("📂  Gestión archivos", b"adm_files")],
                [Button.inline("👤  Mi cuenta", b"my_account"),
                 Button.inline("📋  Comandos", b"cmd_list")],
                Keyboards.LANG_BTN,
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
            [Button.inline("⚠️  Reportar URL", b"report_url")],
            [Button.inline("«  Volver", b"back_main")],
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
