"""
═══════════════════════════════════════════════════════════════
  HJ ULP EXTRACTOR BOT — Handlers Module v3.5
═══════════════════════════════════════════════════════════════
  • Comandos: /start, /url, /vip, /seller, /gp, /imap, etc.
  • Callbacks: todos los botones inline
  • /updateBot: actualizacion remota desde Telegram
  • Broadcast: /bc, /bcvip
  • Sistema de busqueda gratis para nuevos usuarios
  • v3.5: Eliminado /ma, codigo optimizado
  • Cola de busquedas por usuario (anti-superposicion)
═══════════════════════════════════════════════════════════════
"""

import os
import asyncio
import subprocess
import time
import tempfile
import shutil
from pathlib import Path

from telethon import events
from telethon.errors import (
    MessageNotModifiedError, UserIsBlockedError,
    InputUserDeactivatedError, FloodWaitError
)

from config import config
from logger_setup import logger
from database import db
from roles import UserRole, SearchMode, get_user_role, can_search
from locale import locale_manager
from ui import UI, Keyboards
from utils import normalizar_url, get_file_counts, format_size, format_time
from search import search_engine
from imap_checker import imap_check_file
from download import (
    DownloadProgressTracker,
    process_pending_downloads, realtime_listener, mover_y_limpiar_archivos
)

import state

# ═════════════════════════════════════════════════════════════
# ANIMACIONES DE CARGA
# ═════════════════════════════════════════════════════════════

LOADING_FRAMES = [
    "⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"
]

async def animate_loading(msg, search_task: asyncio.Task, kw: str):
    """Animacion de carga elegante durante la busqueda."""
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

class _FakeEvent:
    __slots__ = ('sender_id', '_reply')
    def __init__(self, sender_id, reply_func):
        self.sender_id = sender_id
        self._reply = reply_func
    async def reply(self, text, **kwargs):
        return await self._reply(text, **kwargs)


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

        if "Already up to date" in output or "Already up-to-date" in output:
            await status_msg.edit(
                "╭───✦ ✅ BOT ACTUALIZADO\n"
                "├● Ya esta en la ultima version\n"
                "╰───✦ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
            )
            return

        await status_msg.edit(
            "╭───✦ ✅ BOT ACTUALIZADO\n"
            "├● 🔄 Cambios descargados\n"
            "├● ⏳ Reiniciando en 3 segundos...\n"
            "╰───✦ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
        )

        await asyncio.sleep(3)

        try:
            pm2_check = subprocess.run(
                ['pm2', 'list'], capture_output=True, timeout=5
            )
            if pm2_check.returncode == 0:
                logger.info("Reiniciando via pm2...")
                subprocess.Popen(
                    ['pm2', 'restart', 'botulp'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                import sys
                sys.exit(0)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        import sys
        os.execv(sys.executable, [sys.executable] + sys.argv)

    except subprocess.TimeoutExpired:
        await status_msg.edit(
            "╭───✦ ❌ ERROR AL ACTUALIZAR\n"
            "├● 📄 `Timeout: git pull tardo demasiado`\n"
            "╰───✦ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈",
            parse_mode='md'
        )
    except SystemExit:
        raise
    except Exception as e:
        logger.error(f"Error en /updateBot: {e}")
        await status_msg.edit(
            "╭───✦ ❌ ERROR AL ACTUALIZAR\n"
            f"├● 📄 `{str(e)[:100]}`\n"
            "╰───✦ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈",
            parse_mode='md'
        )

# ═════════════════════════════════════════════════════════════
# HELPERS
# ═════════════════════════════════════════════════════════════

def _get_commands_by_role(role: UserRole, has_free: bool = False) -> str:
    """Construir la lista de comandos disponibles segun el rol del usuario."""
    if role == UserRole.FREE:
        cmds = "/start │ /canjear"
        if has_free:
            cmds += " │ /url"
        return cmds
    elif role == UserRole.VIP:
        return "/start │ /url │ /imap │ /canjear"
    elif role == UserRole.SELLER:
        return "/start │ /url │ /imap"
    elif role == UserRole.ADMIN:
        return "/start │ /url │ /imap │ /vip │ /unvip │ /seller │ /unseller │ /gp │ /ungp │ /bc │ /bcvip │ /updateBot"
    return "/start │ /canjear"


def _get_access_denied_text(lang: str) -> str:
    """Obtener texto de acceso denegado segun idioma. Prioriza el mensaje de 'busqueda gratis usada'."""
    key = "access_denied"
    text = locale_manager.get(key, lang)
    if text and text != key:
        return text
    return locale_manager.get("access_denied_no_free", lang) or locale_manager.get("access_denied", 'es')


async def _check_search_access(uid: int, lang: str, is_group_allowed: bool, is_private: bool):
    """Verificar si un usuario puede buscar. Retorna (allowed: bool, is_free_search: bool)."""
    role = get_user_role(uid)

    # VIP, SELLER, ADMIN siempre pueden (en privado o grupo permitido)
    if role in (UserRole.VIP, UserRole.SELLER, UserRole.ADMIN):
        return True, False

    # FREE en grupo permitido
    if role == UserRole.FREE and is_group_allowed and not is_private:
        return True, False

    # FREE con busqueda gratis disponible
    if role == UserRole.FREE and db.is_new_user(uid):
        return True, True

    return False, False


def _get_file_counts_display() -> tuple:
    """Obtener conteos de archivos y estado de auto-download. Retorna (counts, auto_status, total_pending, active_count)."""
    counts = get_file_counts()
    auto_status = "ON" if state.auto_download_enabled else "OFF"
    queue_count = 0
    try:
        if state.auto_dl_queue is not None:
            queue_count = state.auto_dl_queue.qsize()
    except Exception:
        pass
    total_pending = len(state.pending_downloads) + queue_count
    active_count = len(state.active_downloads)
    return counts, auto_status, total_pending, active_count


async def _send_search_result(target_chat, result_file, caption, e=None, msg=None):
    """Enviar archivo de resultados y limpiar."""
    try:
        await state.bot.send_file(
            target_chat, result_file,
            caption=caption,
            parse_mode='md'
        )
    except Exception as ex:
        logger.error(f"Error enviando resultado: {ex}")

    # Borrar mensaje de "buscando..."
    if e:
        try:
            await e.delete()
        except Exception:
            pass
    elif msg:
        try:
            await msg.delete()
        except Exception:
            pass

    try:
        os.remove(result_file)
    except Exception:
        pass


# ═════════════════════════════════════════════════════════════
# HANDLERS DE COMANDOS
# ═════════════════════════════════════════════════════════════

def register_handlers(bot_client):
    """Registrar todos los handlers en el bot client."""

    async def _execute_search(uid, kw, t_opt, modo, tipo_texto, is_free_search,
                                chat_id, lang, callback_event=None):
        """Ejecutar una busqueda completa con animacion, resultado y procesamiento de cola."""
        state.active_searches.add(uid)

        # Mensaje de carga
        if callback_event:
            try:
                loading_msg = await callback_event.edit(
                    f"⚙️ **Buscando** `{kw}`...\n\n⠋ Procesando",
                    buttons=None,
                    parse_mode='md'
                )
            except Exception:
                loading_msg = await state.bot.send_message(
                    chat_id,
                    f"⚙️ **Buscando** `{kw}`...\n\n⠋ Procesando",
                    parse_mode='md'
                )
        else:
            loading_msg = await state.bot.send_message(
                chat_id,
                f"⚙️ **Buscando** `{kw}`...\n\n⠋ Procesando",
                parse_mode='md'
            )

        try:
            start_time = time.time()
            search_task = asyncio.create_task(search_engine(kw, t_opt, modo))

            await animate_loading(loading_msg, search_task, kw)

            result_file = await search_task
            elapsed = time.time() - start_time

            if result_file:
                if is_free_search:
                    db.mark_free_search_used(uid)
                else:
                    db.add_search(uid)

                count = 0
                with open(result_file, 'rb') as f:
                    for _ in f:
                        count += 1

                if is_free_search:
                    caption = UI.text("search_completed_free", lang, kw, tipo_texto, count, elapsed)
                else:
                    caption = UI.text("search_completed", lang, kw, tipo_texto, count, elapsed)

                if callback_event:
                    await _send_search_result(chat_id, result_file, caption, e=callback_event)
                else:
                    await _send_search_result(chat_id, result_file, caption, msg=loading_msg)
            else:
                no_res_text = UI.text("no_results", lang, kw)
                no_res_kb = Keyboards.no_results(kw)
                if callback_event:
                    try:
                        await callback_event.edit(no_res_text, buttons=no_res_kb, parse_mode='md')
                    except Exception:
                        pass
                else:
                    try:
                        await loading_msg.edit(no_res_text, buttons=no_res_kb, parse_mode='md')
                    except Exception:
                        pass
        except Exception as exc:
            logger.error(f"Error en busqueda de {uid}: {exc}")
            try:
                await loading_msg.edit(
                    f"❌ **Error en busqueda**\n\n`{str(exc)[:200]}`",
                    parse_mode='md'
                )
            except Exception:
                pass
        finally:
            state.active_searches.discard(uid)
            await _process_next_in_queue(uid)

    async def _process_next_in_queue(uid):
        """Si hay busquedas encoladas para este usuario, ejecutar la siguiente."""
        queue = state.search_queue.get(uid)
        if not queue:
            return

        next_search = queue.pop(0)
        if not queue:
            del state.search_queue[uid]

        logger.info(f"Procesando busqueda encolada para {uid}: {next_search['kw']}")

        try:
            await _execute_search(
                uid=uid,
                kw=next_search['kw'],
                t_opt=next_search['t_opt'],
                modo=next_search['modo'],
                tipo_texto=next_search['tipo_texto'],
                is_free_search=next_search['is_free_search'],
                chat_id=next_search['chat_id'],
                lang=next_search['lang'],
                callback_event=None
            )
        except Exception as exc:
            logger.error(f"Error en busqueda encolada de {uid}: {exc}")
            try:
                await state.bot.send_message(
                    next_search['chat_id'],
                    f"❌ **Error en busqueda encolada**\n\n`{str(exc)[:200]}`",
                    parse_mode='md'
                )
            except Exception:
                pass

    @bot_client.on(events.NewMessage(pattern="/start"))
    async def start(e):
        if e.is_group and e.chat_id not in state.allowed_groups:
            return

        uid = e.sender_id
        user = db.get_user(uid)
        lang = user.get('language', 'es')
        role = get_user_role(uid)
        has_free = db.is_new_user(uid) and role == UserRole.FREE

        # Si viene con parametro (deep link para canjear key)
        args = e.message.message.split()
        if len(args) > 1:
            code = args[1]
            if db.redeem(uid, code):
                role = get_user_role(uid)
                has_free = False  # Si ya es VIP, no necesita gratis
                await e.reply(
                    locale_manager.get("redeem_success", lang),
                    buttons=Keyboards.main(role, lang, has_free),
                    parse_mode='md'
                )
                return

        # Elegir texto de bienvenida
        if has_free:
            welcome_key = "welcome_new"
        else:
            welcome_key = "welcome"

        welcome_text = UI.text(welcome_key, lang, _get_commands_by_role(role, has_free), role.value, user['search_count'])

        await e.reply(
            welcome_text,
            buttons=Keyboards.main(role, lang, has_free) if e.is_private else None,
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
            return await e.reply("⚠️ Este comando solo funciona en grupos.")
        state.allowed_groups.add(e.chat_id)
        db.add_allowed_group(e.chat_id, e.sender_id)
        await e.reply("✅ Grupo anadido a la lista permitida y guardado en la base de datos.")

    @bot_client.on(events.NewMessage(pattern=r"/ungp"))
    async def cmd_ungp(e):
        if get_user_role(e.sender_id) != UserRole.ADMIN:
            return
        if not e.is_group:
            return await e.reply("⚠️ Este comando solo funciona en grupos.")
        if e.chat_id in state.allowed_groups:
            state.allowed_groups.discard(e.chat_id)
            db.remove_allowed_group(e.chat_id)
            await e.reply("🗑 Grupo eliminado de la lista permitida y de la base de datos.")
        else:
            await e.reply("⚠️ Este grupo no esta en la lista permitida.")

    @bot_client.on(events.NewMessage(pattern=r"/canjear (.+)"))
    async def cmd_canjear(e):
        """Canjear una key VIP directamente con /canjear <codigo>."""
        uid = e.sender_id
        user = db.get_user(uid)
        lang = user.get('language', 'es')
        code = e.pattern_match.group(1).strip()

        if e.is_group and e.chat_id not in state.allowed_groups:
            return

        if db.redeem(uid, code):
            role = get_user_role(uid)
            await e.reply(
                UI.text("redeem_success", lang),
                buttons=Keyboards.main(role, lang, False),
                parse_mode='md'
            )
        else:
            await e.reply(
                UI.text("canjear_invalid", lang),
                buttons=Keyboards.back(),
                parse_mode='md'
            )

    @bot_client.on(events.NewMessage(pattern=r"/url (.+)"))
    async def cmd_url(e):
        uid = e.sender_id
        user = db.get_user(uid)
        lang = user.get('language', 'es')
        is_group_allowed = e.is_group and e.chat_id in state.allowed_groups

        if e.is_group and not is_group_allowed:
            return

        allowed, is_free_search = await _check_search_access(uid, lang, is_group_allowed, e.is_private)

        if not allowed:
            return await e.reply(
                _get_access_denied_text(lang),
                buttons=Keyboards.back() if e.is_private else None,
                parse_mode='md'
            )

        # Anti-superposicion: si ya esta buscando, bloquear
        if uid in state.active_searches:
            return await e.reply(
                UI.text("search_already_running", lang),
                parse_mode='md'
            )

        kw = normalizar_url(e.pattern_match.group(1))
        state.temp_state[uid] = {
            'kw': kw, 'chat_id': e.chat_id,
            'is_free_search': is_free_search
        }
        await e.reply(
            UI.text("search_step_time", lang, kw),
            buttons=Keyboards.time(),
            parse_mode='md'
        )

    # ═════════════════════════════════════════════════════════════
    # COMANDO /imap — IMAP Checker (responder a archivo mail:pass)
    # ═════════════════════════════════════════════════════════════

    @bot_client.on(events.NewMessage(pattern=r"/imap$"))
    async def cmd_imap(e):
        """IMAP Checker — responde a un archivo .txt con mail:pass y devuelve hits."""
        uid = e.sender_id
        user = db.get_user(uid)
        lang = user.get('language', 'es')
        role = get_user_role(uid)

        if e.is_group and e.chat_id not in state.allowed_groups:
            return

        if role == UserRole.FREE:
            return await e.reply(
                UI.text("access_denied_no_free", lang),
                buttons=Keyboards.back() if e.is_private else None,
                parse_mode='md'
            )

        reply = await e.get_reply_message()
        if not reply or not reply.document:
            return await e.reply(
                UI.text("imap_no_file", lang),
                parse_mode='md'
            )

        status_msg = await e.reply(
            UI.text("imap_processing", lang, 0, "?", 0),
            parse_mode='md'
        )

        try:
            temp_dir = tempfile.mkdtemp(prefix="imap_")
            input_path = os.path.join(temp_dir, "combos.txt")
            output_path = os.path.join(temp_dir, "hits.txt")

            await state.bot.download_media(reply, file=input_path)

            if not os.path.isfile(input_path):
                await status_msg.edit(UI.text("imap_no_file", lang), parse_mode='md')
                return

            with open(input_path, 'r', encoding='utf-8', errors='ignore') as f:
                total = sum(1 for line in f if ":" in line.strip())

            if total == 0:
                await status_msg.edit(UI.text("imap_no_file", lang), parse_mode='md')
                shutil.rmtree(temp_dir, ignore_errors=True)
                return

            await status_msg.edit(
                UI.text("imap_processing", lang, 0, total, 0),
                parse_mode='md'
            )

            main_loop = asyncio.get_running_loop()
            progress_data = {'last_edit': 0}

            def progress_cb(checked, tot, hits):
                now = time.time()
                if now - progress_data['last_edit'] < 3:
                    return
                progress_data['last_edit'] = now

                async def _update_msg():
                    try:
                        await status_msg.edit(
                            UI.text("imap_processing", lang, checked, tot, hits),
                            parse_mode='md'
                        )
                    except Exception:
                        pass

                main_loop.call_soon_threadsafe(
                    lambda: asyncio.ensure_future(_update_msg(), loop=main_loop)
                )

            stats = await main_loop.run_in_executor(
                None,
                lambda: imap_check_file(
                    Path(input_path), Path(output_path),
                    progress_callback=progress_cb
                )
            )

            if stats['hits'] > 0 and os.path.isfile(output_path):
                caption = UI.text("imap_completed", lang, stats['total'], stats['hits'], stats['bads'], stats['elapsed'])
                await state.bot.send_file(
                    e.chat_id, output_path,
                    caption=caption,
                    parse_mode='md'
                )
                try:
                    await status_msg.delete()
                except Exception:
                    pass
            else:
                await status_msg.edit(
                    UI.text("imap_no_hits", lang, stats['total'], stats['elapsed']),
                    parse_mode='md'
                )

            shutil.rmtree(temp_dir, ignore_errors=True)

        except Exception as exc:
            logger.error(f"Error en /imap: {exc}")
            await status_msg.edit(
                f"❌ **Error en IMAP Check**\n\n`{str(exc)[:200]}`",
                parse_mode='md'
            )
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass

    # --- BROADCAST ---

    async def _broadcast(sender_id: int, targets: list, msg_text: str, status_msg, label: str):
        total = len(targets)
        if total == 0:
            await status_msg.edit("No hay usuarios para broadcast.")
            return

        sent = 0
        errors = 0

        for idx, target in enumerate(targets):
            uid_t = target if isinstance(target, int) else target['user_id']
            try:
                await state.bot.send_message(uid_t, msg_text, parse_mode='md')
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
                    await state.bot.send_message(uid_t, msg_text, parse_mode='md')
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
    @bot_client.on(events.NewMessage(
        func=lambda e: (e.is_private or (e.is_group and e.chat_id in state.allowed_groups)) and
                       e.sender_id in state.temp_state and
                       state.temp_state[e.sender_id].get('step') == 'WAITING_KEYWORD'
    ))
    async def handle_conversation(e):
        uid = e.sender_id
        user = db.get_user(uid)
        lang = user.get('language', 'es')
        role = get_user_role(uid)
        is_group_allowed = e.is_group and e.chat_id in state.allowed_groups

        allowed, is_free_search = await _check_search_access(uid, lang, is_group_allowed, e.is_private)

        if not allowed:
            return await e.reply(
                _get_access_denied_text(lang),
                buttons=Keyboards.back(),
                parse_mode='md'
            )

        # Anti-superposicion: si ya esta buscando, bloquear
        if uid in state.active_searches:
            return await e.reply(
                UI.text("search_already_running", lang),
                parse_mode='md'
            )

        kw = normalizar_url(e.text)
        state.temp_state[uid] = {
            'kw': kw, 'chat_id': e.chat_id,
            'is_free_search': is_free_search
        }
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
            # ─── VOLVER AL MENU PRINCIPAL ───
            if data == "back_main":
                has_free = db.is_new_user(uid) and role == UserRole.FREE
                welcome_key = "welcome_new" if has_free else "welcome"
                await e.edit(
                    UI.text(welcome_key, lang, _get_commands_by_role(role, has_free), role.value, user['search_count']),
                    buttons=Keyboards.main(role, lang, has_free),
                    parse_mode='md'
                )

            # ─── MI CUENTA ───
            elif data == "my_account":
                exp = (user['vip_expiry'] or 'N/A')[:10] if user['vip_expiry'] else "N/A"
                free_status = "Disponible" if db.is_new_user(uid) else "Usada"
                await e.edit(
                    UI.text("my_account", lang, uid, role.value, exp, user['search_count'], free_status),
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

            # ─── CANJEAR KEY ───
            elif data == "canjear_key":
                await e.edit(
                    UI.text("canjear_info", lang),
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
                has_free = db.is_new_user(uid) and role == UserRole.FREE
                welcome_key = "welcome_new" if has_free else "welcome"
                await e.edit(
                    UI.text(welcome_key, new_lang, _get_commands_by_role(role, has_free), role.value, user['search_count']),
                    buttons=Keyboards.main(role, new_lang, has_free),
                    parse_mode='md'
                )

            # ─── GESTION DE ARCHIVOS ───
            elif data in ("adm_files", "refresh_files"):
                if role != UserRole.ADMIN:
                    return await e.answer("Acceso denegado.", alert=True)
                counts, auto_status, total_pending, active_count = _get_file_counts_display()
                await e.edit(
                    UI.text("file_management", lang,
                            counts['total'], counts['24h'], counts['old'],
                            auto_status, total_pending, active_count),
                    buttons=Keyboards.files_control(
                        state.auto_download_enabled, total_pending, active_count
                    ),
                    parse_mode='md'
                )

            elif data == "toggle_auto_on":
                if role != UserRole.ADMIN:
                    return await e.answer("Acceso denegado.", alert=True)
                state.auto_download_enabled = True
                await e.answer("Auto-Descarga ACTIVADA (secuencial)", alert=True)
                counts, _, total_pending, active_count = _get_file_counts_display()
                await e.edit(
                    UI.text("file_management", lang,
                            counts['total'], counts['24h'], counts['old'],
                            "ON", total_pending, active_count),
                    buttons=Keyboards.files_control(True, total_pending, active_count),
                    parse_mode='md'
                )

            elif data == "toggle_auto_off":
                if role != UserRole.ADMIN:
                    return await e.answer("Acceso denegado.", alert=True)
                state.auto_download_enabled = False
                await e.answer("Auto-Descarga DESACTIVADA", alert=True)
                counts, _, total_pending, active_count = _get_file_counts_display()
                await e.edit(
                    UI.text("file_management", lang,
                            counts['total'], counts['24h'], counts['old'],
                            "OFF", total_pending, active_count),
                    buttons=Keyboards.files_control(False, total_pending, active_count),
                    parse_mode='md'
                )

            elif data == "dl_all":
                if role != UserRole.ADMIN:
                    return await e.answer("Acceso denegado.", alert=True)
                if not state.pending_downloads:
                    return await e.answer("No hay archivos pendientes.", alert=True)
                msg = await e.edit("📥 **Procesando descargas pendientes...**", buttons=None)
                asyncio.create_task(process_pending_downloads(msg))

            elif data == "clear_pending":
                if role != UserRole.ADMIN:
                    return await e.answer("Acceso denegado.", alert=True)
                count = len(state.pending_downloads)
                state.pending_downloads.clear()
                await e.edit(
                    f"🗑 **{count} archivos pendientes eliminados.**",
                    buttons=Keyboards.back("adm_files")
                )

            # ─── BUSQUEDA ───
            elif data == "search_init":
                # Verificar acceso a busqueda
                allowed, is_free_search = await _check_search_access(
                    uid, lang,
                    False,  # callback siempre es privado
                    True
                )

                if not allowed:
                    return await e.answer(
                        _get_access_denied_text(lang),
                        alert=True
                    )

                # Anti-superposicion: si ya esta buscando, bloquear
                if uid in state.active_searches:
                    return await e.answer(
                        UI.text("search_already_running", lang),
                        alert=True
                    )

                ts = state.temp_state.get(uid, {})
                ts['step'] = 'WAITING_KEYWORD'
                ts['is_free_search'] = is_free_search
                state.temp_state[uid] = ts
                await e.edit(
                    UI.text("ask_domain", lang),
                    buttons=Keyboards.back(),
                    parse_mode='md'
                )

            elif data.startswith("time_"):
                t_opt = data.split("_")[1]
                if uid in state.temp_state and state.temp_state[uid].get('kw'):
                    state.temp_state[uid]['time'] = t_opt
                    await e.edit(
                        "📄 **Formato de salida:**",
                        buttons=Keyboards.formats()
                    )
                else:
                    await e.answer("Usa 'Nueva Busqueda' primero.", alert=True)

            # ─── EJECUTAR BUSQUEDA (con cola anti-superposicion) ───
            elif data.startswith("fmt_"):
                if uid not in state.temp_state or not state.temp_state[uid].get('kw'):
                    return await e.answer("Sesion expirada. Inicia nueva busqueda.", alert=True)

                kw = state.temp_state[uid]['kw']
                t_opt = state.temp_state[uid].get('time', '24h')
                is_free_search = state.temp_state[uid].get('is_free_search', False)

                modo = SearchMode.ULP
                tipo_texto = "ULP"
                if data == "fmt_mail":
                    modo = SearchMode.MAIL
                    tipo_texto = "MAIL:PASS"
                elif data == "fmt_user":
                    modo = SearchMode.USERPASS
                    tipo_texto = "USER:PASS"

                # Si ya esta buscando, encolar y avisar
                if uid in state.active_searches:
                    queue = state.search_queue.setdefault(uid, [])
                    queue.append({
                        'kw': kw, 't_opt': t_opt, 'modo': modo,
                        'tipo_texto': tipo_texto, 'is_free_search': is_free_search,
                        'chat_id': state.temp_state[uid].get('chat_id', uid),
                        'lang': lang
                    })
                    position = len(queue)
                    await e.answer(
                        UI.text("search_in_progress", lang, position),
                        alert=True
                    )
                    if uid in state.temp_state:
                        del state.temp_state[uid]
                    return

                # Ejecutar busqueda
                await _execute_search(
                    uid=uid, kw=kw, t_opt=t_opt, modo=modo,
                    tipo_texto=tipo_texto, is_free_search=is_free_search,
                    chat_id=state.temp_state.get(uid, {}).get('chat_id', uid),
                    lang=lang, callback_event=e
                )

            # ─── REPORTAR URL ───
            elif data == "report_url":
                kw = state.temp_state.get(uid, {}).get('kw', 'Desconocido')
                for admin_id in config.ADMIN_IDS:
                    try:
                        await state.bot.send_message(
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
                            stats['searches'], stats['total_users'],
                            stats['new_users']),
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
                            stats['searches'], stats['total_users'],
                            stats['new_users']),
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
                    lines = []
                    for sid in sellers:
                        username = "None"
                        try:
                            entity = await state.bot.get_entity(sid)
                            if entity and getattr(entity, 'username', None):
                                username = f"@{entity.username}"
                        except Exception:
                            pass
                        lines.append(f"👤 `{sid}` │ {username}")
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
                        exp = v.get('vip_expiry') or 'N/A'
                        if exp != 'N/A' and len(exp) > 10:
                            exp = exp[:10]
                        vuid = v['user_id']
                        username = "None"
                        try:
                            entity = await state.bot.get_entity(vuid)
                            if entity and getattr(entity, 'username', None):
                                username = f"@{entity.username}"
                        except Exception:
                            pass
                        lines.append(f"👤 `{vuid}` │ {username} → Exp: `{exp}`")
                    text = "👑 **VIPs**\n\n" + "\n".join(lines)
                    if len(vips) > 50:
                        text += f"\n\n... y {len(vips) - 50} mas"
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
                fake_event = _FakeEvent(uid, e.message.reply)
                await cmd_update_bot(fake_event)

        except Exception as exc:
            logger.error(f"Error en callback {data}: {exc}")
            try:
                await e.answer("Error procesando solicitud.", alert=True)
            except Exception:
                pass