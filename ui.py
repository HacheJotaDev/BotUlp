"""
═══════════════════════════════════════════════════════════════
  HJ ULP EXTRACTOR BOT — UI & Keyboards Module v7.0 · Obsidian
═══════════════════════════════════════════════════════════════
  • v4.3.0 REDISEÑO UI/UX — sistema de diseño unificado:
      · Menús por rol en filas balanceadas 2×2 (máx. 4 filas)
      · Botón «Nueva búsqueda» ELIMINADO de VIP/SELLER/ADMIN
        (la búsqueda vive en /url; FREE conserva su botón de
        regalo con contador, que es su entrada funcional)
      · Teclados de periodo UNIFICADOS (mismo patrón /url,
        /hotmail y /imap)
      · Generador de keys con paridad total a /keygen (añade
        la opción ILIMITADA que solo existía por comando)
      · Funnel de conversión: acceso denegado con CTA directo
      · Confirmación en 2 pasos para acciones destructivas
      · Panel admin: control de promo con presets
  • Insignias únicas por rango: 🆓 FREE · 💎 VIP · 💼 SELLER · 👑 OWNER
  • Roles FREE / VIP / SELLER / OWNER
═══════════════════════════════════════════════════════════════
"""

from urllib.parse import quote

from telethon import Button

from bot_locale import locale_manager
from roles import UserRole
from config import config
from nowpayments import VIP_PLANS, effective_price, get_promo_percent, format_price


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


# v4.2.30: emoji por plan (identidad visual que siempre tuvieron)
_PLAN_EMOJIS = {1: "⚡", 3: "📊", 7: "🔥", 15: "🚀", 30: "💎"}


def _plan_emoji(days: int) -> str:
    return _PLAN_EMOJIS.get(days, "💎")


class Keyboards:
    # Botones compartidos
    BACK = [[Button.inline("«  Volver", b"back_main")]]
    # v4.2.4 FIX: separar el BOTÓN individual de la FILA. Met una lista dentro
    # de una fila provocaba "AttributeError: 'list' object has no attribute
    # 'SUBCLASS_OF_ID'" al serializar el teclado (rompía /start para FREE y OWNER).
    LANG_BUTTON = Button.inline("🌐  Idioma", b"ch_lang")   # botón suelto (filas de 2)
    SUPPORT_URL = [Button.url("📞  Soporte", f"https://t.me/{config.SUPPORT_CONTACT.lstrip('@')}")]

    @staticmethod
    def main(role: UserRole, lang: str = 'es', has_free_search: bool = False):
        """Menú principal por rol — filas balanceadas 2×2 (v4.3.0).

        v4.3.0: el botón «🔍 Nueva búsqueda» se ELIMINA de VIP/SELLER/
        ADMIN (la búsqueda se hace con /url, listado en COMANDOS). FREE
        conserva su botón de regalo porque es su entrada funcional:
        muestra el contador de búsquedas gratis en vivo.
        Estructura idéntica entre roles (memoria muscular): solo cambia
        el botón propio de cada rango (Renovar VIP / Generar key /
        Panel admin)."""
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
                [Button.inline("📧  IMAP Checker", b"imap_info"),
                 Button.inline("📥  Hotmail Data", b"hotmail_dl_info")],
                [Button.inline("📬  IMAP Data", b"imap_dl_info"),
                 Button.inline("👤  Mi cuenta", b"my_account")],
                [Button.inline("💎  Renovar VIP", b"buy_vip_info"),
                 Button.inline("👥  Referidos", b"ref_info")],
                [Button.inline("📋  Comandos", b"cmd_list"),
                 Keyboards.LANG_BUTTON],
            ]

        elif role == UserRole.SELLER:
            return [
                [Button.inline("📧  IMAP Checker", b"imap_info"),
                 Button.inline("📥  Hotmail Data", b"hotmail_dl_info")],
                [Button.inline("📬  IMAP Data", b"imap_dl_info"),
                 Button.inline("👤  Mi cuenta", b"my_account")],
                [Button.inline("🔑  Generar key", b"seller_genkey"),
                 Button.inline("👥  Referidos", b"ref_info")],
                [Button.inline("📋  Comandos", b"cmd_list"),
                 Keyboards.LANG_BUTTON],
            ]

        elif role == UserRole.ADMIN:
            # v4.3.0: «Gestión archivos» sale del menú principal — ya vive
            # en el Panel admin (antes duplicaba «📂 Archivos» a 1 tap).
            return [
                [Button.inline("📧  IMAP Checker", b"imap_info"),
                 Button.inline("📥  Hotmail Data", b"hotmail_dl_info")],
                [Button.inline("📬  IMAP Data", b"imap_dl_info"),
                 Button.inline("👤  Mi cuenta", b"my_account")],
                [Button.inline("🔐  Panel admin", b"admin_enter"),
                 Button.inline("👥  Referidos", b"ref_info")],
                [Button.inline("📋  Comandos", b"cmd_list"),
                 Keyboards.LANG_BUTTON],
            ]

        return []

    @staticmethod
    def _period_keyboard(prefix: str):
        """v4.3.0: teclado de periodo UNIFICADO — el mismo patrón visual
        para /url (time_), /hotmail (hm_time_) e /imap (im_time_).
        Antes había 3 estilos distintos para el mismo concepto.
        Las tarjetas de cada pantalla explican el detalle de cada opción."""
        return [
            [Button.inline("⚡  Nuevos · 24h", (prefix + "24h").encode()),
             Button.inline("🗂️  Todos · 24h + antiguos", (prefix + "all").encode())],
            [Button.inline("📅  Antiguos · histórico", (prefix + "old").encode())],
            [Button.inline("«  Cancelar", b"back_main")],
        ]

    @staticmethod
    def time():
        return Keyboards._period_keyboard("time_")

    @staticmethod
    def hotmail_time():
        """Selección de periodo para /hotmail (patrón unificado v4.3.0)."""
        return Keyboards._period_keyboard("hm_time_")

    @staticmethod
    def imap_time():
        """Selección de periodo para /imap (patrón unificado v4.3.0)."""
        return Keyboards._period_keyboard("im_time_")

    @staticmethod
    def formats():
        return [
            [Button.inline("📄  ULP  (completo)", b"fmt_ulp"),
             Button.inline("📧  mail:pass", b"fmt_mail")],
            [Button.inline("👤  user:pass", b"fmt_user")],
            [Button.inline("«  Cancelar", b"back_main")],
        ]

    @staticmethod
    def no_results():
        """Teclado de SIN RESULTADOS (búsquedas parciales «24h» o «Antiguos»):
        reintento directo con el mismo dominio en «24h + Antiguos» (lo que
        promete el mensaje) + reporte. Sin botones vanosos: Comprar VIP y
        Nueva búsqueda ya viven en el menú principal."""
        return [
            [Button.inline("🔁  Reintentar · 24h + Antiguos", b"retry_all")],
            [Button.inline("⚠️  Reportar URL", b"report_url")],
            [Button.inline("«  Volver", b"back_main")],
        ]

    @staticmethod
    def no_results_exhausted():
        """v4.2.7: SIN RESULTADOS cuando ya se escaneó «24h + Antiguos».
        No queda nada más que reintentar → solo reporte y volver."""
        return [
            [Button.inline("⚠️  Reportar URL", b"report_url")],
            [Button.inline("«  Volver", b"back_main")],
        ]

    @staticmethod
    def admin():
        """v4.3.0: «Actualizar bot» aislado en su propia fila (acción que
        reinicia el bot — separada de las consultas) + nuevo control de
        promo con presets (antes solo por comando /promo)."""
        return [
            [Button.inline("👑  Ver VIPs", b"adm_vips"),
             Button.inline("💼  Sellers", b"adm_sellers")],
            [Button.inline("🔑  Generar key", b"adm_genkey"),
             Button.inline("📊  Estadísticas", b"adm_stats")],
            [Button.inline("📂  Archivos", b"adm_files"),
             Button.inline("🏷️  Promo", b"adm_promo")],
            [Button.inline("🔄  Actualizar bot", b"adm_update_bot")],
            [Button.inline("«  Volver", b"back_main")],
        ]

    @staticmethod
    def admin_promo(active_pct: int):
        """v4.3.0: presets de promo desde el panel — misma ruta interna que
        /promo (config.set_promo_percent). El botón activo se marca para
        que el admin vea de un vistazo el estado actual."""
        def _preset(pct: int, label: str):
            if active_pct == pct:
                return Button.inline(f"✅  {label}", b"promo_noop")
            return Button.inline(f"🏷️  {label}", f"promo_set_{pct}".encode())

        off = (Button.inline("✅  Promo desactivada", b"promo_noop")
               if active_pct == 0 else
               Button.inline("🛑  Desactivar promo", b"promo_set_0"))
        return [
            [_preset(25, "-25%"), _preset(50, "-50%")],
            [_preset(70, "-70%"), _preset(100, "100% gratis")],
            [off],
            [Button.inline("«  Panel", b"admin_enter")],
        ]

    @staticmethod
    def gen_key(back_data: str = "back_main"):
        """v4.3.0: paridad total con /keygen — se añade la opción ILIMITADA
        (antes solo existía con «/keygen» sin días) y el emoji por plan,
        con el MISMO mapa de identidad de payment_plans (⚡📊🔥🚀💎)."""
        return [
            [Button.inline("⚡  1 día", b"gen_1"),
             Button.inline("📊  3 días", b"gen_3")],
            [Button.inline("🔥  7 días", b"gen_7"),
             Button.inline("🚀  15 días", b"gen_15")],
            [Button.inline("💎  30 días", b"gen_30"),
             Button.inline("♾️  Ilimitada", b"gen_0")],
            [Button.inline("«  Volver", back_data.encode())],
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
    def clear_pending_confirm(count: int):
        """v4.3.0: confirmación en 2 pasos para vaciar pendientes —
        antes un solo tap borraba la cola sin aviso (acción destructiva)."""
        return [
            [Button.inline(f"🗑️  Sí, vaciar  ({count})", b"clear_pending_yes")],
            [Button.inline("«  Cancelar", b"adm_files")],
        ]

    @staticmethod
    def access_denied():
        """v4.3.0: funnel de conversión — el mensaje de acceso denegado
        dice «Hazte VIP / invita amigos» pero no llevaba a ningún lado.
        CTA directo a las dos rutas que el propio texto menciona."""
        return [
            [Button.inline("💎  Comprar VIP", b"buy_vip_info"),
             Button.inline("👥  Referidos", b"ref_info")],
            [Button.inline("«  Volver", b"back_main")],
        ]

    @staticmethod
    def access_denied_feature():
        """v4.3.0: variante para funciones VIP-only (/imapchk) — aquí los
        referidos NO resuelven el problema, solo el CTA de compra."""
        return [
            [Button.inline("💎  Comprar VIP", b"buy_vip_info")],
            [Button.inline("«  Volver", b"back_main")],
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
        """v4.2.30: precios dinámicos — los labels se construyen desde
        VIP_PLANS + effective_price() (promo global aplicada). Con promo
        activa se añade una fila banner arriba y el precio rebajado en
        cada botón. Sin promo queda IDÉNTICO a la versión anterior
        (⚡ 1 día · $6 ... 💎 30 días · $100)."""
        rows = []
        pct = get_promo_percent()
        if pct > 0:
            rows.append([Button.inline(f"🏷️  PROMO  -{pct}%  ·  precios rebajados", b"promo_info")])

        # Planes en el mismo orden de siempre: 1/3 · 7/15 · 30
        plan_buttons = []
        for days in (1, 3, 7, 15, 30):
            plan = VIP_PLANS.get(days)
            if not plan:
                continue
            price_txt = format_price(effective_price(days))
            label = f"{_plan_emoji(days)}  {days} día{'s' if days != 1 else ''}  ·  ${price_txt}"
            plan_buttons.append(Button.inline(label, f"pay_{days}".encode()))

        rows.append([plan_buttons[0], plan_buttons[1]])
        rows.append([plan_buttons[2], plan_buttons[3]])
        rows.append([plan_buttons[4]])
        rows.append(Keyboards.SUPPORT_URL)
        rows.append([Button.inline("«  Volver", b"back_main")])
        return rows

    @staticmethod
    def imap_cancel(token: str):
        """v4.2.25 — Botón para cancelar un /imapchk en curso.

        Al cancelar, el check se detiene y el usuario recibe TODAS las
        hits encontradas hasta ese momento.
        """
        return [[Button.inline("🛑  Cancelar y recibir hits", token.encode())]]

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
    def hotmail_info():
        return [
            [Button.inline("«  Volver", b"back_main")]
        ]

    @staticmethod
    def ref_panel(link: str, lang: str = 'es'):
        """Panel de referidos: compartir link (diálogo nativo de Telegram) + volver.
        v4.3.0: el emoji megáfono antiguo (sin ID premium) se cambia por
        📣, que SÍ tiene ID registrado y cuyo glifo premium es el mismo
        diseño de megáfono: el botón gana icono premium."""
        share_text = quote(UI.text("ref_share_text", lang))
        share_url = (f"https://t.me/share/url?url={quote(link)}"
                     f"&text={share_text}")
        return [
            [Button.url("📣  Compartir mi link", share_url)],
            [Button.inline("«  Volver", b"back_main")],   # fila directa (back() es [[btn]])
        ]
