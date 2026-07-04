"""
═══════════════════════════════════════════════════════════════
  HJ ULP EXTRACTOR BOT — UI & Keyboards Module
═══════════════════════════════════════════════════════════════
"""

from telethon import Button

from locale import locale_manager
from roles import UserRole


class UI:
    @staticmethod
    def text(key: str, lang: str = 'es', *args) -> str:
        localized = locale_manager.get(key, lang, *args)
        if localized:
            return localized
        return locale_manager.get(key, 'es', *args) or key


class Keyboards:
    @staticmethod
    def main(role: UserRole, lang: str = 'es', has_free_search: bool = False):
        lang_btn = [Button.inline("🌐 Idioma / Language", b"ch_lang")]

        if role == UserRole.FREE:
            buttons = []
            if has_free_search:
                buttons.append([Button.inline("🔍 BÚSQUEDA GRATIS (1/1)", b"search_init")])
            buttons.append([Button.inline("💰 COMPRAR VIP", b"buy_vip_info")])
            buttons.append([Button.inline("🔑 CANJEAR KEY", b"canjear_key")])
            buttons.append([Button.inline("👤 MI CUENTA", b"my_account")])
            buttons.append(lang_btn)
            return buttons
        elif role == UserRole.VIP:
            return [
                [Button.inline("🔍 NUEVA BÚSQUEDA", b"search_init")],
                [Button.inline("👤 MI CUENTA", b"my_account")],
                lang_btn
            ]
        elif role == UserRole.SELLER:
            return [
                [Button.inline("🔍 NUEVA BÚSQUEDA", b"search_init")],
                [Button.inline("🔑 GENERAR KEY", b"seller_genkey")],
                [Button.inline("👤 MI CUENTA", b"my_account")]
            ]
        elif role == UserRole.ADMIN:
            return [
                [Button.inline("🔍 NUEVA BÚSQUEDA", b"search_init")],
                [Button.inline("🔐 PANEL ADMIN", b"admin_enter")],
                [Button.inline("📂 GESTIÓN ARCHIVOS", b"adm_files")],
                [Button.inline("👤 MI CUENTA", b"my_account")]
            ]
        return []

    @staticmethod
    def time():
        return [
            [Button.inline("⚡ Últimas 24h", b"time_24h")],
            [Button.inline("🗂 24h + Antiguos", b"time_all")],
            [Button.inline("📅 Solo Antiguos", b"time_old")],
            [Button.inline("❌ Cancelar", b"back_main")]
        ]

    @staticmethod
    def formats():
        return [
            [Button.inline("📄 ULP (Completo)", b"fmt_ulp")],
            [Button.inline("📧 MAIL:PASS", b"fmt_mail")],
            [Button.inline("👤 USER:PASS", b"fmt_user")],
            [Button.inline("❌ Cancelar", b"back_main")]
        ]

    @staticmethod
    def no_results(kw: str):
        return [
            [Button.inline("⚠️ REPORTAR URL", b"report_url")],
            [Button.inline("🔙 Volver", b"back_main")]
        ]

    @staticmethod
    def admin():
        return [
            [Button.inline("👑 Ver VIPs", b"adm_vips"),
             Button.inline("💼 Sellers", b"adm_sellers")],
            [Button.inline("🔑 Generar Key", b"adm_genkey")],
            [Button.inline("📊 Stats", b"adm_stats")],
            [Button.inline("📂 Gestión Archivos", b"adm_files")],
            [Button.inline("🔄 Actualizar Bot", b"adm_update_bot")],
            [Button.inline("🔙 Volver", b"back_main")]
        ]

    @staticmethod
    def gen_key():
        return [
            [Button.inline("1 Día", b"gen_1"),
             Button.inline("3 Días", b"gen_3"),
             Button.inline("7 Días", b"gen_7")],
            [Button.inline("30 Días", b"gen_30")],
            [Button.inline("🔙 Volver", b"back_main")]
        ]

    @staticmethod
    def files_control(auto_dl: bool, pending_count: int, active_count: int):
        if auto_dl:
            btn_auto = Button.inline("✅ Auto-DL ON", b"toggle_auto_off")
        else:
            btn_auto = Button.inline("❌ Auto-DL OFF", b"toggle_auto_on")

        return [
            [btn_auto],
            [Button.inline(f"📥 Descargar Pendientes ({pending_count})", b"dl_all")],
            [Button.inline("🗑 Vaciar Pendientes", b"clear_pending")],
            [Button.inline("🔄 Refrescar", b"refresh_files")],
            [Button.inline("🔙 Volver", b"admin_enter")]
        ]

    @staticmethod
    def language_selection():
        return [
            [Button.inline("🇪🇸 Español", b"set_lang_es")],
            [Button.inline("🇬🇧 English", b"set_lang_en")],
            [Button.inline("🇧🇷 Português", b"set_lang_pt")],
            [Button.inline("🔙 Volver", b"back_main")]
        ]

    @staticmethod
    def back(data: str = "back_main"):
        return [[Button.inline("🔙 Volver", data.encode())]]