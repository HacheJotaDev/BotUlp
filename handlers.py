"""
═══════════════════════════════════════════════════════════════
  HJ ULP EXTRACTOR BOT — Handlers Module
═══════════════════════════════════════════════════════════════
  • Comandos: /start, /url, /vip, /seller, /gp, etc.
  • Callbacks: todos los botones inline
  • /updateBot: actualización remota desde Telegram
  • Broadcast: /bc, /bcvip
═══════════════════════════════════════════════════════════════
"""

import os
import asyncio
import subprocess
import time

from telethon import events
from telethon.errors import (
    MessageNotModifiedError, UserIsBlockedError,
    InputUserDeactivatedError, FloodWaitError
)

from config import config
from logger_setup import logger
from database import db
from roles import UserRole, SearchMode, get_user_role
from locale import locale_manager
from ui import UI, Keyboards
from utils import normalizar_url, get_file_counts, format_size, format_time
from search import search_engine
from download import (
    _download_with_progress, DownloadProgressTracker,
    process_pending_downloads, realtime_listener, mover_y_limpiar_archivos
)
from state import (
    temp_state, pending_downloads, active_downloads,
    auto_download_enabled, auto_dl_queue, auto_dl_worker_running,
    bot, userbot
)

# ═════════════════════════════════════════════════════════════
# ANIMACIONES DE CARGA
# ═════════════════════════════════════════════════════════════

LOADING_FRAMES = [
    "⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"
]

async def animate_loading(msg, search_task: asyncio.Task, kw: str):
    """Animación de carga elegante durante la búsqueda."""
    i = 0
    while not search_task.done():
        frame = LOADING_FRAMES[i % len(LOADING_FRAMES)]
        try:
            await msg.edit(
                f"⚙️ **Buscando** `{kw}`...\n\n"
                f"{frame} Procesando bases de datos\n"
                f"⏱️ Transcurrido: `{i * 0.6:.0f}s`",
                parse_mode='md'
            )
        except MessageNotModifiedError:
            pass
        except Exception:
            pass
        i += 1
        await asyncio.sleep(0.6)

# ═════════════════════════════════════════════════════════════
# COMANDO /updateBot
# ═════════════════════════════════════════════════════════════

async def cmd_update_bot(event):
    """Actualizar el bot desde GitHub sin entrar al VPS."""
    uid = event.sender_id
    if uid not in config.ADMIN_IDS:
        return

    status_msg = await event.reply(
        "╭───✦ 🔄 ACTUALIZANDO BOT\n"
        "├● ⏳ Descargando cambios...\n"
        "╰───✦ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
    )

    try:
        # Git pull
        result = subprocess.run(
            ['git', 'pull', 'origin', 'main'],
            capture_output=True, text=True, timeout=60,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )

        output = result.stdout.strip()
        logger.info(f"git pull output: {output}")

        if result.returncode != 0:
            error_msg = result.stderr.strip()[:200] or "Error desconocido"
            await status_msg.edit(
                "╭───✦ ❌ ERROR AL ACTUALIZAR\n"
                f"├● 📄 `{error_msg}`\n"
                "╰───✦ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈",
                parse_mode='md'
            )
            return

        # Verificar si hubo cambios
        if "Already up to date" in output or "Already up-to-date" in output:
            await status_msg.edit(
                "╭───✦ ✅ BOT ACTUALIZADO\n"
                "├● Ya está en la última versión\n"
                "╰───✦ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
            )
            return

        # Hubo cambios - reiniciar el bot
        await status_msg.edit(
            "╭───✦ ✅ BOT ACTUALIZADO\n"
            "├● 🔄 Cambios descargados\n"
            "├● ⏳ Reiniciando en 3 segundos...\n"
            "╰───✦ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
        )

        # Esperar 3 segundos para que el mensaje llegue
        await asyncio.sleep(3)

        # Reiniciar usando os.execv (reemplaza el proceso actual)
        import sys
        os.execv(sys.executable, [sys.executable] + sys.argv)

    except subprocess.TimeoutExpired:
        await status_msg.edit(
            "╭───✦ ❌ ERROR AL ACTUALIZAR\n"
            "├● 📄 `Timeout: git pull tardó demasiado`\n"
            "╰───✦ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈",
            parse_mode='md'
        )
    except Exception as e:
        logger.error(f"Error en /updateBot: {e}")
        await status_msg.edit(
            "╭───✦ ❌ ERROR AL ACTUALIZAR\n"
            f"├● 📄 `{str(e)[:100]}`\n"
            "╰───✦ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈",
            parse_mode='md'
        )

# ═════════════════════════════════════════════════════════════
# HANDLERS DE COMANDOS
# ═════════════════════════════════════════════════════════════

def register_handlers(bot_client):
    """Registrar todos los handlers en el bot client."""

    @bot_client.on(events.NewMessage(pattern="/start"))
    async def start(e):
        uid = e.sender_id
        user = db.get_user(uid)
        lang = user.get('language', 'es')
        role = get_user_role(uid)

        args = e.message.message.split()
        if len(args) > 1:
            code = args[1]
            if db.redeem(uid, code):
                role = get_user_role(uid)
                await e.reply(
                    locale_manager.get("redeem_success", lang),
                    buttons=Keyboards.main(role, lang),
                    parse_mode='md'
                )
                return

        await e.reply(
            UI.text("welcome", lang, role.value, user['search_count']),
            buttons=Keyboards.main(role, lang),
            parse_mode='md'
        )

    @bot_client.on(events.NewMessage(pattern="/updateBot"))
    async def update_bot_cmd(e):
        await cmd_update_bot(e)

    @bot_client.on(events.NewMessage(pattern=r"/vip (\d+)"))
    async def cmd_vip_perm(e):
        if get_user_role(e.sender_id) != UserRole.ADMIN:
            return
        uid = int(e.pattern_match.group(1))
        db.set_role(uid, 'VIP', days=36500)
        await e.reply(f"✅ Usuario `{uid}` ahora es **VIP Permanente**.", parse_mode='md')

    @bot_client.on(events.NewMessage(pattern=r"/seller (\d+)"))
    async def cmd_seller(e):
        if get_user_role(e.sender_id) != UserRole.ADMIN:
            return
        uid = int(e.pattern_match.group(1))
        db.set_role(uid, 'SELLER')
        await e.reply(f"✅ Usuario `{uid}` promovido a **SELLER**.", parse_mode='md')

    @bot_client.on(events.NewMessage(pattern=r"/unseller (\d+)"))
    async def cmd_unseller(e):
        if get_user_role(e.sender_id) != UserRole.ADMIN:
            return
        uid = int(e.pattern_match.group(1))
        db.set_role(uid, 'FREE')
        await e.reply(f"❌ Usuario `{uid}` removido de **SELLER**.", parse_mode='md')

    @bot_client.on(events.NewMessage(pattern=r"/unvip (\d+)"))
    async def cmd_unvip(e):
        if get_user_role(e.sender_id) != UserRole.ADMIN:
            return
        uid = int(e.pattern_match.group(1))
        db.remove_vip(uid)
        await e.reply(f"🗑 Usuario `{uid}` eliminado de VIP.", parse_mode='md')

    @bot_client.on(events.NewMessage(pattern=r"/gp"))
    async def cmd_gp(e):
        if get_user_role(e.sender_id) != UserRole.ADMIN:
            return
        if not e.is_group:
            return
        from state import allowed_groups
        allowed_groups.add(e.chat_id)
        await e.reply("✅ Grupo añadido a la lista permitida.")

    @bot_client.on(events.NewMessage(pattern=r"/ungp"))
    async def cmd_ungp(e):
        if get_user_role(e.sender_id) != UserRole.ADMIN:
            return
        if not e.is_group:
            return
        from state import allowed_groups
        if e.chat_id in allowed_groups:
            allowed_groups.discard(e.chat_id)
            await e.reply("🗑 Grupo eliminado de la lista permitida.")

    @bot_client.on(events.NewMessage(pattern=r"/url (.+)"))
    async def cmd_url(e):
        uid = e.sender_id
        user = db.get_user(uid)
        lang = user.get('language', 'es')
        role = get_user_role(uid)
        if role == UserRole.FREE:
            return await e.reply(
                UI.text("access_denied", lang),
                buttons=Keyboards.back(),
                parse_mode='md'
            )
        kw = normalizar_url(e.pattern_match.group(1))
        temp_state[uid] = {'kw': kw}
        await e.reply(
            UI.text("search_step_time", lang, kw),
            buttons=Keyboards.time(),
            parse_mode='md'
        )

    # --- BROADCAST ---

    async def _broadcast(sender_id: int, targets: list, msg_text: str, status_msg, label: str):
        total = len(targets)
        if total == 0:
            await status_msg.edit("No hay usuarios para broadcast.")
            return

        sent = 0
        errors = 0

        for idx, target in enumerate(targets):
            uid = target if isinstance(target, int) else target['user_id']
            try:
                await bot.send_message(uid, msg_text, parse_mode='md')
                sent += 1
                await asyncio.sleep(0.05)

                if sent % 50 == 0:
                    try:
                        await status_msg.edit(
                            f"📣 **{label}**\n\n"
                            f"✅ Enviados: `{sent}/{total}`\n"
                            f"❌ Errores: `{errors}`"
                        )
                    except Exception:
                        pass
            except FloodWaitError as fw:
                logger.warning(f"FloodWait: {fw.seconds}s en broadcast")
                await asyncio.sleep(fw.seconds + 1)
                try:
                    await bot.send_message(uid, msg_text, parse_mode='md')
                    sent += 1
                except Exception:
                    errors += 1
            except (UserIsBlockedError, InputUserDeactivatedError):
                errors += 1
            except Exception:
                errors += 1
                await asyncio.sleep(0.5)

        await status_msg.edit(
            f"✅ **{label} Finalizado**\n\n"
            f"📬 Enviados: `{sent}`\n"
            f"🚫 Fallidos: `{errors}`"
        )

    @bot_client.on(events.NewMessage(pattern=r"/bc (.+)"))
    async def cmd_bc(e):
        if get_user_role(e.sender_id) != UserRole.ADMIN:
            return
        msg_text = e.pattern_match.group(1)
        users = db.get_all_users()
        status = await e.reply(
            f"📣 **Broadcast Global Iniciado**\n\n👥 Total: `{len(users)}`\n⚡ Enviando..."
        )
        await _broadcast(e.sender_id, users, msg_text, status, "Broadcast Global")

    @bot_client.on(events.NewMessage(pattern=r"/bcvip (.+)"))
    async def cmd_bcvip(e):
        if get_user_role(e.sender_id) != UserRole.ADMIN:
            return
        msg_text = e.pattern_match.group(1)
        vips_data = db.list_vips()
        status = await e.reply(
            f"👑 **Broadcast VIP Iniciado**\n\n👥 Total VIPs: `{len(vips_data)}`\n⚡ Enviando..."
        )
        await _broadcast(e.sender_id, vips_data, msg_text, status, "Broadcast VIP")

    # --- CONVERSATION HANDLER ---

    @bot_client.on(events.NewMessage)
    async def handle_conversation(e):
        if not e.is_private:
            return
        uid = e.sender_id
        if uid in temp_state and temp_state[uid].get('step') == 'WAITING_KEYWORD':
            user = db.get_user(uid)
            lang = user.get('language', 'es')
            kw = normalizar_url(e.text)
            temp_state[uid] = {'kw': kw}
            await e.reply(
                UI.text("search_step_time", lang, kw),
                buttons=Keyboards.time(),
                parse_mode='md'
            )

    # ═════════════════════════════════════════════════════════════
    # CALLBACKS - TODOS LOS BOTONES FUNCIONALES
    # ═════════════════════════════════════════════════════════════

    @bot_client.on(events.CallbackQuery)
    async def callbacks(e):
        uid = e.sender_id
        user = db.get_user(uid)
        lang = user.get('language', 'es')
        role = get_user_role(uid)
        data = e.data.decode()

        try:
            # ─── VOLVER AL MENÚ PRINCIPAL ───
            if data == "back_main":
                await e.edit(
                    UI.text("welcome", lang, role.value, user['search_count']),
                    buttons=Keyboards.main(role, lang),
                    parse_mode='md'
                )

            # ─── MI CUENTA ───
            elif data == "my_account":
                exp = user['vip_expiry'][:10] if user['vip_expiry'] else "N/A"
                await e.edit(
                    UI.text("my_account", lang, uid, role.value, exp, user['search_count']),
                    buttons=Keyboards.back(),
                    parse_mode='md'
                )

            # ─── COMPRAR VIP ───
            elif data == "buy_vip_info":
                contacts = "\n".join(config.SELLER_USERNAMES)
                await e.edit(
                    UI.text("buy_vip_info", lang, contacts),
                    buttons=Keyboards.back(),
                    parse_mode='md'
                )

            # ─── IDIOMA ───
            elif data == "ch_lang":
                await e.edit(
                    UI.text("select_language", lang),
                    buttons=Keyboards.language_selection(),
                    parse_mode='md'
                )

            elif data.startswith("set_lang_"):
                parts = data.split("_")
                new_lang = parts[2] if len(parts) >= 3 else 'es'
                db.set_language(uid, new_lang)
                await e.answer(UI.text("language_selected", new_lang), alert=True)
                user = db.get_user(uid)
                await e.edit(
                    UI.text("welcome", new_lang, role.value, user['search_count']),
                    buttons=Keyboards.main(role, new_lang),
                    parse_mode='md'
                )

            # ─── GESTIÓN DE ARCHIVOS ───
            elif data in ("adm_files", "refresh_files"):
                if role != UserRole.ADMIN:
                    return await e.answer("Acceso denegado.", alert=True)
                counts = get_file_counts()
                auto_status = "ON" if auto_download_enabled else "OFF"
                queue_count = auto_dl_queue.qsize() if auto_dl_queue else 0
                total_pending = len(pending_downloads) + queue_count
                await e.edit(
                    UI.text("file_management", lang,
                            counts['total'], counts['24h'], counts['old'],
                            auto_status, total_pending, len(active_downloads)),
                    buttons=Keyboards.files_control(
                        auto_download_enabled, total_pending, len(active_downloads)
                    ),
                    parse_mode='md'
                )

            elif data == "toggle_auto_on":
                if role != UserRole.ADMIN:
                    return await e.answer("Acceso denegado.", alert=True)
                import state as st
                st.auto_download_enabled = True
                await e.answer("Auto-Descarga ACTIVADA (secuencial)", alert=True)
                counts = get_file_counts()
                queue_count = auto_dl_queue.qsize() if auto_dl_queue else 0
                total_pending = len(pending_downloads) + queue_count
                await e.edit(
                    UI.text("file_management", lang,
                            counts['total'], counts['24h'], counts['old'],
                            "ON", total_pending, len(active_downloads)),
                    buttons=Keyboards.files_control(True, total_pending, len(active_downloads)),
                    parse_mode='md'
                )

            elif data == "toggle_auto_off":
                if role != UserRole.ADMIN:
                    return await e.answer("Acceso denegado.", alert=True)
                import state as st
                st.auto_download_enabled = False
                await e.answer("Auto-Descarga DESACTIVADA", alert=True)
                counts = get_file_counts()
                queue_count = auto_dl_queue.qsize() if auto_dl_queue else 0
                total_pending = len(pending_downloads) + queue_count
                await e.edit(
                    UI.text("file_management", lang,
                            counts['total'], counts['24h'], counts['old'],
                            "OFF", total_pending, len(active_downloads)),
                    buttons=Keyboards.files_control(False, total_pending, len(active_downloads)),
                    parse_mode='md'
                )

            elif data == "dl_all":
                if role != UserRole.ADMIN:
                    return await e.answer("Acceso denegado.", alert=True)
                if not pending_downloads:
                    return await e.answer("No hay archivos pendientes.", alert=True)
                msg = await e.edit("📥 **Procesando descargas pendientes...**", buttons=None)
                asyncio.create_task(process_pending_downloads(msg))

            elif data == "clear_pending":
                if role != UserRole.ADMIN:
                    return await e.answer("Acceso denegado.", alert=True)
                count = len(pending_downloads)
                pending_downloads.clear()
                await e.edit(
                    f"🗑 **{count} archivos pendientes eliminados.**",
                    buttons=Keyboards.back("adm_files")
                )

            # ─── BÚSQUEDA ───
            elif data == "search_init":
                if role == UserRole.FREE:
                    return await e.answer("Necesitas VIP para buscar.", alert=True)
                temp_state[uid] = {'step': 'WAITING_KEYWORD'}
                await e.edit(
                    UI.text("ask_domain", lang),
                    buttons=Keyboards.back(),
                    parse_mode='md'
                )

            elif data.startswith("time_"):
                t_opt = data.split("_")[1]
                if uid in temp_state and temp_state[uid].get('kw'):
                    temp_state[uid]['time'] = t_opt
                    await e.edit(
                        "📄 **Formato de salida:**",
                        buttons=Keyboards.formats()
                    )
                else:
                    await e.answer("Usa 'Nueva Búsqueda' primero.", alert=True)

            elif data.startswith("fmt_"):
                if uid not in temp_state or not temp_state[uid].get('kw'):
                    return await e.answer("Sesión expirada. Inicia nueva búsqueda.", alert=True)

                kw = temp_state[uid]['kw']
                t_opt = temp_state[uid].get('time', '24h')

                modo = SearchMode.ULP
                tipo_texto = "ULP"
                if data == "fmt_mail":
                    modo = SearchMode.MAIL
                    tipo_texto = "MAIL:PASS"
                elif data == "fmt_user":
                    modo = SearchMode.USERPASS
                    tipo_texto = "USER:PASS"

                msg = await e.edit(
                    f"⚙️ **Buscando** `{kw}`...\n\n⠋ Procesando",
                    buttons=None,
                    parse_mode='md'
                )

                start_time = time.time()
                search_task = asyncio.create_task(search_engine(kw, t_opt, modo))

                await animate_loading(msg, search_task, kw)

                result_file = await search_task
                elapsed = time.time() - start_time

                if result_file:
                    db.add_search(uid)
                    count = 0
                    with open(result_file, 'rb') as f:
                        for _ in f:
                            count += 1

                    preview_lines = []
                    with open(result_file, 'r', encoding='utf-8') as f:
                        for i, line in enumerate(f):
                            if i >= config.SEARCH_RESULT_PREVIEW_LINES:
                                break
                            preview_lines.append(line.strip())

                    if uid in temp_state:
                        del temp_state[uid]

                    await e.delete()

                    preview_text = '\n'.join(preview_lines)
                    if len(preview_text) > 3000:
                        preview_text = preview_text[:3000] + "..."

                    caption = (
                        "╭───✦ ✅ BÚSQUEDA COMPLETADA\n"
                        f"├● 🔍 Dominio: `{kw}`\n"
                        f"├● 📑 Tipo: `{tipo_texto}`\n"
                        f"├● 📊 Resultados: `{count}`\n"
                        f"├● ⏱️ Tiempo: `{elapsed:.1f}s`\n"
                        "╰───✦ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
                    )

                    await bot.send_file(
                        uid, result_file,
                        caption=caption,
                        parse_mode='md'
                    )

                    try:
                        os.remove(result_file)
                    except Exception:
                        pass
                else:
                    await e.edit(
                        UI.text("no_results", lang, kw),
                        buttons=Keyboards.no_results(kw),
                        parse_mode='md'
                    )

            # ─── REPORTAR URL ───
            elif data == "report_url":
                kw = temp_state.get(uid, {}).get('kw', 'Desconocido')
                for admin_id in config.ADMIN_IDS:
                    try:
                        await bot.send_message(
                            admin_id,
                            f"⚠️ **REPORTE DE URL**\n\n👤 Usuario: `{uid}`\n🔍 URL: `{kw}`"
                        )
                    except Exception:
                        pass
                await e.answer("Reporte enviado correctamente.", alert=True)

            # ─── PANEL ADMIN ───
            elif data == "admin_enter":
                if role != UserRole.ADMIN:
                    return await e.answer("Acceso denegado.", alert=True)
                stats = db.get_stats()
                await e.edit(
                    UI.text("admin_panel", lang,
                            stats['vips'], stats['sellers'],
                            stats['searches'], stats['total_users']),
                    buttons=Keyboards.admin(),
                    parse_mode='md'
                )

            elif data == "adm_stats":
                if role != UserRole.ADMIN:
                    return await e.answer("Acceso denegado.", alert=True)
                stats = db.get_stats()
                await e.edit(
                    UI.text("stats_global", lang,
                            stats['vips'], stats['sellers'],
                            stats['searches'], stats['total_users']),
                    buttons=Keyboards.back("admin_enter"),
                    parse_mode='md'
                )

            elif data == "adm_sellers":
                if role != UserRole.ADMIN:
                    return await e.answer("Acceso denegado.", alert=True)
                sellers = db.list_sellers()
                if not sellers:
                    text = "💼 **SELLERS**\n\nNo hay sellers registrados."
                else:
                    lines = [f"👤 ID: `{s}`" for s in sellers]
                    text = "💼 **SELLERS**\n\n" + "\n".join(lines)
                await e.edit(text, buttons=Keyboards.back("admin_enter"), parse_mode='md')

            elif data == "adm_vips":
                if role != UserRole.ADMIN:
                    return await e.answer("Acceso denegado.", alert=True)
                vips = db.list_vips()
                if not vips:
                    text = "👑 **VIPs**\n\nNo hay usuarios VIP."
                else:
                    lines = []
                    for v in vips[:50]:
                        exp = v.get('vip_expiry', 'N/A')
                        if exp and len(exp) > 10:
                            exp = exp[:10]
                        lines.append(f"👤 `{v['user_id']}` → Exp: `{exp}`")
                    text = "👑 **VIPs**\n\n" + "\n".join(lines)
                    if len(vips) > 50:
                        text += f"\n\n... y {len(vips) - 50} más"
                await e.edit(text, buttons=Keyboards.back("admin_enter"), parse_mode='md')

            elif data == "adm_genkey":
                if role not in (UserRole.ADMIN, UserRole.SELLER):
                    return await e.answer("Acceso denegado.", alert=True)
                await e.edit("🔑 **Generador de Keys**", buttons=Keyboards.gen_key())

            elif data == "seller_genkey":
                if role not in (UserRole.ADMIN, UserRole.SELLER):
                    return await e.answer("Acceso denegado.", alert=True)
                await e.edit("🔑 **Generador de Keys**", buttons=Keyboards.gen_key())

            elif data.startswith("gen_"):
                days = int(data.split("_")[1])
                code = db.gen_key(uid, days)
                link = f"https://t.me/{config.BOT_USERNAME}?start={code}"

                back_data = "admin_enter" if role == UserRole.ADMIN else "back_main"
                await e.edit(
                    UI.text("key_generated", lang, code, link, days),
                    buttons=Keyboards.back(back_data),
                    parse_mode='md'
                )

            # ─── ACTUALIZAR BOT ───
            elif data == "adm_update_bot":
                if role != UserRole.ADMIN:
                    return await e.answer("Acceso denegado.", alert=True)
                # Crear un evento falso para reutilizar cmd_update_bot
                class FakeEvent:
                    def __init__(self, sender_id, reply_func):
                        self.sender_id = sender_id
                        self._reply = reply_func
                    async def reply(self, text, **kwargs):
                        return await self._reply(text, **kwargs)

                fake_event = FakeEvent(uid, e.message.reply)
                await cmd_update_bot(fake_event)

        except Exception as exc:
            logger.error(f"Error en callback {data}: {exc}")
            try:
                await e.answer("Error procesando solicitud.", alert=True)
            except Exception:
                pass
