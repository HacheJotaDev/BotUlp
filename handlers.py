"""
═══════════════════════════════════════════════════════════════
  HJ ULP EXTRACTOR BOT — Handlers Module v4.0
═══════════════════════════════════════════════════════════════
  • Comandos: /start, /cmd, /url, /vip, /seller, /gp, /imap, etc.
  • Callbacks: todos los botones inline
  • /updateBot: actualizacion remota desde Telegram
  • Broadcast: /bc, /bcvip
  • Sistema de busqueda gratis para nuevos usuarios
  • v4.0: Agregado /cmd, bugs corregidos, UI mejorada
  • Cola de busquedas por usuario (anti-superposicion)
═══════════════════════════════════════════════════════════════
"""

import os
import sys
import math
import asyncio
import subprocess
import time
import tempfile
import shutil
from datetime import datetime, timezone
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
from utils import (
    normalizar_url, get_file_counts, format_size, format_time,
    format_uptime, sanitize_md, progress_bar
)
from search import search_engine
from nowpayments import (
    create_invoice, VIP_PLANS, get_payment_status,
    SUCCESS_STATUSES, WAITING_STATUSES, FAIL_STATUSES, _deliver_vip
)
from imap_checker import imap_check_file
from geoip_checker import get_country_for_email
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

# Umbrales (segundos) de cada fase de la búsqueda
PHASE_SCANNING_UNTIL = 8
PHASE_PROCESSING_UNTIL = 25

# Caché de @usernames para listas admin (uid -> (valor, timestamp))
_USERNAME_CACHE = {}


async def animate_loading(msg, search_task: asyncio.Task, kw: str, lang: str = 'es'):
    """Animación de carga elegante por fases durante la búsqueda.

    v4.0: fases dinámicas localizadas + intervalo suave (anti-FloodWait).
    """
    i = 0
    start = time.time()
    while not search_task.done():
        frame = LOADING_FRAMES[i % len(LOADING_FRAMES)]
        elapsed = int(time.time() - start)
        if elapsed < PHASE_SCANNING_UNTIL:
            phase = UI.text("phase_scanning", lang)
        elif elapsed < PHASE_PROCESSING_UNTIL:
            phase = UI.text("phase_processing", lang)
        else:
            phase = UI.text("phase_filtering", lang)
        try:
            await msg.edit(
                UI.text("search_loading", lang, kw, frame, phase, elapsed),
                parse_mode='md'
            )
        except MessageNotModifiedError:
            pass
        except Exception:
            pass
        i += 1
        await asyncio.sleep(config.SEARCH_ANIM_INTERVAL)


async def _display_name(e, uid: int) -> str:
    """Nombre amigable del usuario (con caché) para los saludos."""
    cached = state.USER_NAMES.get(uid)
    if cached:
        return cached
    name = None
    try:
        sender = await e.get_sender()
        name = getattr(sender, 'first_name', None) or getattr(sender, 'title', None)
    except Exception:
        name = None
    if not name:
        name = "Usuario"
    name = sanitize_md(str(name))[:24]
    state.USER_NAMES[uid] = name
    return name


async def _lookup_username(uid: int) -> str:
    """@username con caché y timeout — listas admin instantáneas y sin FloodWait."""
    cached = _USERNAME_CACHE.get(uid)
    if cached and (time.time() - cached[1]) < 900:
        return f" · {cached[0]}" if cached[0] else ""
    val = ""
    try:
        entity = await asyncio.wait_for(state.bot.get_entity(uid), timeout=4)
        if entity and getattr(entity, 'username', None):
            val = f"@{entity.username}"
    except Exception:
        val = ""
    _USERNAME_CACHE[uid] = (val, time.time())
    return f" · {val}" if val else ""

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

    user = db.get_user(uid)
    lang = user.get('language', 'es')

    status_msg = await event.reply(UI.text("update_bot_start", lang), parse_mode='md')

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
                UI.text("update_bot_fail", lang, error_msg),
                parse_mode='md'
            )
            return

        if "Already up to date" in output or "Already up-to-date" in output:
            await status_msg.edit(
                UI.text("update_bot_uptodate", lang),
                parse_mode='md'
            )
            # Instalar/actualizar dependencias
            try:
                pip_result = subprocess.run(
                    [sys.executable, '-m', 'pip', 'install', '-r',
                     os.path.join(os.path.dirname(os.path.abspath(__file__)), 'requirements.txt'),
                     '--quiet'],
                    capture_output=True, text=True, timeout=120
                )
                if pip_result.returncode == 0:
                    logger.info("Dependencias instaladas/actualizadas correctamente")
                else:
                    logger.warning(f"pip install: {pip_result.stderr[:200]}")
            except Exception as pip_err:
                logger.warning(f"Error instalando dependencias: {pip_err}")

            return

        await status_msg.edit(
            UI.text("update_bot_success", lang),
            parse_mode='md'
        )

        # Instalar/actualizar dependencias nuevas
        try:
            pip_result = subprocess.run(
                [sys.executable, '-m', 'pip', 'install', '-r',
                 os.path.join(os.path.dirname(os.path.abspath(__file__)), 'requirements.txt'),
                 '--quiet'],
                capture_output=True, text=True, timeout=120
            )
            if pip_result.returncode == 0:
                logger.info("Dependencias instaladas/actualizadas correctamente")
            else:
                logger.warning(f"pip install: {pip_result.stderr[:200]}")
        except Exception as pip_err:
            logger.warning(f"Error instalando dependencias: {pip_err}")


        await asyncio.sleep(3)

        try:
            pm2_check = subprocess.run(
                ['pm2', 'list'], capture_output=True, timeout=5
            )
            if pm2_check.returncode == 0:
                logger.info("Reiniciando via pm2...")
                for pm2_name in config.PM2_NAMES:
                    subprocess.Popen(
                        ['pm2', 'restart', pm2_name],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                    )
                sys.exit(0)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        os.execv(sys.executable, [sys.executable] + sys.argv)

    except subprocess.TimeoutExpired:
        await status_msg.edit(
            UI.text("update_bot_fail", lang, "Timeout: git pull tardó demasiado"),
            parse_mode='md'
        )
    except SystemExit:
        raise
    except Exception as e:
        logger.error(f"Error en /updateBot: {e}")
        await status_msg.edit(
            UI.text("update_bot_fail", lang, str(e)[:100]),
            parse_mode='md'
        )

# ═════════════════════════════════════════════════════════════
# HELPERS
# ═════════════════════════════════════════════════════════════

def _get_commands_by_role(role: UserRole, has_free: bool = False) -> str:
    """Construir la lista de comandos disponibles segun el rol del usuario."""
    if role == UserRole.FREE:
        cmds = "/start • /canjear"
        if has_free:
            cmds += " • /url"
        return cmds
    elif role == UserRole.VIP:
        return "/start • /url • /imap • /ping • /canjear"
    elif role == UserRole.SELLER:
        return "/start • /url • /imap • /ping"
    elif role == UserRole.ADMIN:
        return ("/start • /url • /imap • /vip • /unvip • /seller • /unseller"
                " • /gp • /ungp • /bc • /bcvip • /sizedisp • /ping • /updateBot")
    return "/start • /canjear"


def _get_access_denied_text(lang: str) -> str:
    """Obtener texto de acceso denegado segun idioma. Prioriza el mensaje de 'busqueda gratis usada'."""
    key = "access_denied"
    text = locale_manager.get(key, lang)
    if text and text != key:
        return text
    return locale_manager.get("access_denied_no_free", lang) or locale_manager.get("access_denied", 'es')


async def _check_search_access(uid: int, lang: str, is_group_allowed: bool, is_private: bool):
    """Verificar si un usuario puede buscar.

    Retorna (allowed: bool, free_type: str|None) donde free_type es:
      • 'initial' → usa su búsqueda gratis inicial (regalo de bienvenida)
      • 'bonus'   → usa una búsqueda de bono ganada con el sistema de referidos
      • None      → búsqueda normal (VIP/SELLER/OWNER o grupo permitido)
    """
    role = get_user_role(uid)

    # VIP, SELLER, ADMIN siempre pueden (en privado o grupo permitido)
    if role in (UserRole.VIP, UserRole.SELLER, UserRole.ADMIN):
        return True, None

    if role == UserRole.FREE:
        user = db.get_user(uid)

        # FREE en grupo permitido (no consume gratis ni bono)
        if is_group_allowed and not is_private:
            return True, None

        # 1) Búsqueda inicial gratis
        if db.is_new_user(uid):
            return True, 'initial'

        # 2) Bonos ganados con referidos
        if (user.get('bonus_searches') or 0) > 0:
            return True, 'bonus'

    return False, None


def _free_search_count(user: dict) -> int:
    """Total de búsquedas gratis disponibles para un usuario FREE.

    1 inicial (si no la usó) + bonos ganados vía referidos.
    """
    n = 0 if user.get('free_search_used', 0) else 1
    return n + (user.get('bonus_searches') or 0)


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


def _vip_days_left(user: dict):
    """Días restantes de VIP (redondeo hacia arriba), o None si no tiene expiración.

    Con redondeo hacia arriba un VIP con 23h restantes muestra "1 día", no "0".
    """
    exp = user.get('vip_expiry')
    if not exp:
        return None
    try:
        dt = datetime.fromisoformat(exp)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = dt - datetime.now(timezone.utc)
        if delta.total_seconds() <= 0:
            return 0
        return max(1, math.ceil(delta.total_seconds() / 86400))
    except Exception:
        return None


def _welcome_extra(user: dict, role: UserRole, lang: str) -> str:
    """Línea opcional que se añade al final de la bienvenida.

    • VIP  → aviso de renovación si está a punto de expirar (≤ 3 días).
    • FREE → tarjeta de bono de referidos si tiene búsquedas de bonus.
    Para el resto retorna cadena vacía (no rompe el layout).
    """
    if role == UserRole.VIP:
        days = _vip_days_left(user)
        if days is None:
            return ""
        if days <= 1:
            return UI.text("vip_expiring_today", lang) + "\n\n"
        if days <= 3:
            return UI.text("vip_expiring", lang, days) + "\n\n"
        return ""

    if role == UserRole.FREE:
        bonus = user.get('bonus_searches') or 0
        if bonus > 0:
            total = _free_search_count(user)
            return UI.text("welcome_ref_bonus", lang, total) + "\n\n"

    return ""


def _account_block(user: dict, role: UserRole, lang: str) -> str:
    """Bloque {4} de «Mi cuenta»: información específica por rango.

    VIP   → fecha de expiración, días restantes y barra de vigencia.
    FREE  → estado de la búsqueda gratis con upsell.
    Resto → cadena vacía.
    """
    if role == UserRole.VIP:
        exp_raw = (user.get('vip_expiry') or '')[:10]
        exp = _fmt_date_slash(exp_raw) if exp_raw else 'N/A'
        days = _vip_days_left(user)
        # Barra de vigencia (30 días = ciclo de referencia del plan máximo)
        try:
            ratio = min(max(days or 0, 0), 30) / 30
        except Exception:
            ratio = 0
        bar = progress_bar(ratio * 100, width=12).rsplit(' ', 1)[0]
        if days is not None and days > 0:
            days_phrase = (UI.text("acct_vip_days_one", lang)
                           if days == 1 else UI.text("acct_vip_days_many", lang, days))
        else:
            days_phrase = UI.text("acct_vip_days_many", lang, 0)
        line = UI.text("acct_vip_line", lang, exp, days_phrase, bar)
        if days is not None and days <= 3:
            warn = UI.text("vip_expiring_today" if days <= 1 else "vip_expiring", lang, days)
            line += "├─ " + warn + "\n"
        return line

    if role == UserRole.FREE:
        if db.is_new_user(user['user_id']):
            line = UI.text("acct_free_available", lang)
        else:
            line = UI.text("acct_free_used", lang)
        # Estadísticas de referidos
        bonus = user.get('bonus_searches') or 0
        refs = db.get_referral_count(user['user_id'])
        line += UI.text("acct_ref_line", lang, refs, bonus)
        return line

    return ""


def _fmt_member_since(user: dict) -> str:
    """Fecha de registro del usuario en formato DD/MM/AAAA (o —)."""
    return _fmt_date_slash(str(user.get('first_seen') or '')[:10]) or "—"


def _fmt_date_slash(iso_date: str) -> str:
    """Convertir 'AAAA-MM-DD' a 'DD/MM/AAAA'. Retorna '' si es inválido."""
    try:
        y, m, d = iso_date.split('-')
        return f"{d}/{m}/{y}"
    except Exception:
        return iso_date


async def _auto_delete_msg(msg, delay=4):
    """Eliminar un mensaje despues de un delay."""
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except Exception:
        pass


async def _send_search_result(target_chat, result_file, caption, e=None, msg=None, reply_to=None, buttons=None):
    """Enviar archivo de resultados y limpiar."""
    try:
        await state.bot.send_file(
            target_chat, result_file,
            caption=caption,
            parse_mode='md',
            reply_to=reply_to,
            buttons=buttons
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

async def _execute_imap_check(event, file_msg, keywords, lang, uid, mode_country=False):
    """Execute IMAP check with optional keyword/country search + generate proper ZIP."""
    import zipfile
    from datetime import datetime
    from collections import defaultdict
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from utils import progress_bar

    status_msg = await event.reply(
        UI.text("imap_processing", lang, 0, "?", 0, LOADING_FRAMES[0]),
        parse_mode='md'
    )

    try:
        temp_dir = tempfile.mkdtemp(prefix="imap_")
        input_path = os.path.join(temp_dir, "combos.txt")
        output_path = os.path.join(temp_dir, "hits.txt")

        await state.bot.download_media(file_msg, file=input_path)

        if not os.path.isfile(input_path):
            await status_msg.edit(UI.text("imap_no_file", lang), parse_mode='md')
            shutil.rmtree(temp_dir, ignore_errors=True)
            return

        with open(input_path, 'r', encoding='utf-8', errors='ignore') as f:
            total = sum(1 for line in f if ":" in line.strip())

        if total == 0:
            await status_msg.edit(UI.text("imap_no_file", lang), parse_mode='md')
            shutil.rmtree(temp_dir, ignore_errors=True)
            return

        await status_msg.edit(
            UI.text("imap_processing", lang, 0, total, 0, LOADING_FRAMES[0]),
            parse_mode='md'
        )

        main_loop = asyncio.get_running_loop()
        progress_data = {'last_edit': 0, 'frame_idx': 0}

        def progress_cb(checked, tot, hits):
            now = time.time()
            if now - progress_data['last_edit'] < 3:
                return
            progress_data['last_edit'] = now
            progress_data['frame_idx'] += 1
            frame = LOADING_FRAMES[progress_data['frame_idx'] % len(LOADING_FRAMES)]
            pct = (checked / tot * 100) if tot > 0 else 0
            bar = progress_bar(pct)

            async def _update_msg():
                try:
                    await status_msg.edit(
                        UI.text("imap_processing", lang, checked, tot, hits, f"{bar}  {pct:.1f}%"),
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
                keywords=keywords,
                progress_callback=progress_cb
            )
        )

        hits_data = stats.get('hits_data', [])
        bads_list = stats.get('bads_list', [])

        if stats['hits'] > 0:
            now_str = datetime.now().strftime('%m/%d/%Y, %I:%M:%S %p')

            def sanitize_domain(domain):
                import re
                d = domain.lower().strip()
                d = re.sub(r'[^a-z0-9._-]', '_', d)
                d = re.sub(r'_+', '_', d).strip('_')
                return d or 'unknown'

            def sanitize_country(name):
                import re
                c = name.strip()
                c = re.sub(r'[^a-zA-Z0-9 ()-]', '', c)
                c = c.strip()
                return c or 'Unknown'

            # Determinar si generamos ZIP (keywords o country)
            need_zip = keywords or mode_country

            if need_zip:
                domains_dir = os.path.join(temp_dir, 'domains')
                os.makedirs(domains_dir, exist_ok=True)

                # 1) all_hits.txt
                all_hits_path = os.path.join(temp_dir, 'all_hits.txt')
                with open(all_hits_path, 'w', encoding='utf-8') as f:
                    f.write('# CHECKER BOT RESULTS - ' + now_str + '\n')
                    f.write('# User: ' + str(uid) + ' | Type: imap\n\n')
                    for h in hits_data:
                        f.write(h['combo'] + '\n')

                # 2) bad_accounts.txt
                bads_path = os.path.join(temp_dir, 'bad_accounts.txt')
                with open(bads_path, 'w', encoding='utf-8') as f:
                    f.write('# BAD ACCOUNTS\n\n')
                    for bad in bads_list:
                        f.write(bad + '\n')

                # 3) domains/ - group by domain
                domain_groups = defaultdict(list)
                for h in hits_data:
                    domain_groups[h['domain']].append(h['combo'])

                for domain, combos in domain_groups.items():
                    safe = sanitize_domain(domain)
                    fname = str(len(combos)) + '_' + safe + '.txt'
                    dpath = os.path.join(domains_dir, fname)
                    with open(dpath, 'w', encoding='utf-8') as f:
                        f.write('\n'.join(combos) + '\n')

                # 4) keywords/ si hay keywords
                if keywords:
                    keywords_dir = os.path.join(temp_dir, 'keywords')
                    os.makedirs(keywords_dir, exist_ok=True)

                    for kw in keywords:
                        kw_path = os.path.join(keywords_dir, kw + '.txt')
                        with open(kw_path, 'w', encoding='utf-8') as f:
                            f.write('# ' + kw.upper() + ' HITS\n\n')
                            for h in hits_data:
                                kw_res = h.get('keyword_results', {}).get(kw)
                                if kw_res:
                                    match_count, email_infos = kw_res
                                    if match_count > 0 and email_infos:
                                        subj, from_addr, date_str = email_infos[0]
                                        combo = h['combo']
                                        parts = [
                                            combo,
                                            'Matches: ' + str(match_count),
                                            'Subject: ' + subj,
                                            'From: ' + from_addr,
                                            'Date: ' + date_str
                                        ]
                                        f.write(' | '.join(parts) + '\n')

                # 5) countries/ si modo country
                countries_dir = None
                if mode_country:
                    countries_dir = os.path.join(temp_dir, 'countries')
                    os.makedirs(countries_dir, exist_ok=True)

                    # Progress para geoip
                    geo_status = await event.reply(
                        UI.text("imap_country_resolving", lang, len(hits_data)),
                        parse_mode='md'
                    )

                    country_groups = defaultdict(list)
                    country_details = {}

                    loop = asyncio.get_running_loop()

                    def resolve_geo(h):
                        email_addr = h['combo'].split(':')[0]
                        info = get_country_for_email(email_addr)
                        country = info['country']
                        isp = info['isp']
                        mx = info['mx_server']
                        return h, country, isp, mx

                    resolved = 0
                    with ThreadPoolExecutor(max_workers=10, thread_name_prefix="geoip") as geo_exec:
                        future_to_hit = {geo_exec.submit(resolve_geo, h): h for h in hits_data}
                        for future in as_completed(future_to_hit):
                            try:
                                h, country, isp, mx = future.result()
                                country_groups[country].append({
                                    'combo': h['combo'],
                                    'isp': isp,
                                    'mx': mx
                                })
                                if country not in country_details:
                                    country_details[country] = {'count': 0, 'isp': isp}
                                country_details[country]['count'] += 1
                            except Exception:
                                country_groups['Unknown'].append({
                                    'combo': h['combo'], 'isp': 'N/A', 'mx': 'N/A'
                                })

                            resolved += 1
                            if resolved % 5 == 0:
                                try:
                                    pct = resolved / len(hits_data) * 100
                                    bar = progress_bar(pct)
                                    snap_resolved = resolved
                                    snap_total = len(hits_data)
                                    snap_countries = len(country_groups)
                                    async def _upd(r=snap_resolved, t=snap_total, c=snap_countries, b=bar, p=pct):
                                        try:
                                            await geo_status.edit(
                                                UI.text("imap_country_progress", lang,
                                                        r, t, c,
                                                        f"{b}  {p:.1f}%"),
                                                parse_mode='md'
                                            )
                                        except Exception:
                                            pass
                                    loop.call_soon_threadsafe(
                                        lambda: asyncio.ensure_future(_upd(), loop=loop)
                                    )
                                except Exception:
                                    pass

                    # Escribir archivos por pais
                    for country, hits in sorted(country_groups.items(),
                                                    key=lambda x: -len(x[1])):
                        safe_c = sanitize_country(country)
                        cpath = os.path.join(countries_dir, str(len(hits)) + '_' + safe_c + '.txt')
                        with open(cpath, 'w', encoding='utf-8') as f:
                            f.write('# ' + country.upper() + ' — ' + str(len(hits)) + ' hits\n\n')
                            for hit in hits:
                                f.write(hit['combo'] + '\n')

                    # country_summary.txt
                    summary_path = os.path.join(countries_dir, 'country_summary.txt')
                    with open(summary_path, 'w', encoding='utf-8') as f:
                        f.write('# COUNTRY SUMMARY - ' + now_str + '\n\n')
                        for country, details in sorted(country_details.items(),
                                                        key=lambda x: -x[1]['count']):
                            f.write(country + ' (' + str(details['count']) + ' hits) — ISP: ' + details['isp'] + '\n')

                    try:
                        await geo_status.delete()
                    except Exception:
                        pass

                # Build ZIP
                zip_path = os.path.join(temp_dir, 'imap_results.zip')
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                    zf.write(all_hits_path, 'all_hits.txt')
                    zf.write(bads_path, 'bad_accounts.txt')
                    for fn in os.listdir(domains_dir):
                        zf.write(os.path.join(domains_dir, fn), 'domains/' + fn)
                    if keywords:
                        kw_dir = os.path.join(temp_dir, 'keywords')
                        for fn in os.listdir(kw_dir):
                            zf.write(os.path.join(kw_dir, fn), 'keywords/' + fn)
                    if countries_dir:
                        for fn in os.listdir(countries_dir):
                            zf.write(os.path.join(countries_dir, fn), 'countries/' + fn)

                # Caption del ZIP
                if mode_country and keywords:
                    kw_str = ', '.join(keywords)
                    caption = UI.text(
                        'imap_zip_caption_country_kw', lang,
                        stats['total'], stats['hits'], stats['bads'],
                        stats['elapsed'], kw_str, stats['hits'],
                        len(country_groups) if mode_country else 0
                    )
                elif mode_country:
                    caption = UI.text(
                        'imap_zip_caption_country', lang,
                        stats['total'], stats['hits'], stats['bads'],
                        stats['elapsed'],
                        len(country_groups) if mode_country else 0
                    )
                else:
                    kw_str = ', '.join(keywords)
                    caption = UI.text(
                        'imap_zip_caption', lang,
                        stats['total'], stats['hits'], stats['bads'],
                        stats['elapsed'], kw_str, stats['hits']
                    )

                await state.bot.send_file(
                    event.chat_id, zip_path,
                    caption=caption,
                    parse_mode='md'
                )
            else:
                # No keywords: send all_hits.txt
                all_hits_path = os.path.join(temp_dir, 'all_hits.txt')
                with open(all_hits_path, 'w', encoding='utf-8') as f:
                    f.write('# CHECKER BOT RESULTS - ' + now_str + '\n')
                    f.write('# User: ' + str(uid) + '\n\n')
                    for h in hits_data:
                        f.write(h['combo'] + '\n')

                caption = UI.text('imap_completed', lang, stats['total'], stats['hits'], stats['bads'], stats['elapsed'])
                await state.bot.send_file(
                    event.chat_id, all_hits_path,
                    caption=caption,
                    parse_mode='md'
                )

            try:
                await status_msg.delete()
            except Exception:
                pass
        else:
            await status_msg.edit(
                UI.text('imap_no_hits', lang, stats['total'], stats['elapsed']),
                parse_mode='md'
            )

        shutil.rmtree(temp_dir, ignore_errors=True)

    except Exception as exc:
        logger.error(f"Error en /imap: {exc}")
        import traceback
        traceback.print_exc()
        try:
            await status_msg.edit(
                '❌ **Error en IMAP Check**\n\n`' + str(exc)[:200] + '`',
                parse_mode='md'
            )
        except Exception:
            pass
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass



def register_handlers(bot_client):
    """Registrar todos los handlers en el bot client."""

    async def _execute_search(uid, kw, t_opt, modo, tipo_texto, is_free_search,
                                chat_id, lang, callback_event=None, reply_to=None):
        """Ejecutar una busqueda completa con animacion, resultado y procesamiento de cola."""
        state.active_searches.add(uid)

        # Normalizar tipo de búsqueda gratis (bool legacy → 'initial')
        if is_free_search is True:
            is_free_search = 'initial'

        # Re-validar el acceso gratis al momento de ejecutar: la búsqueda pudo
        # encolarse y el estado de gratis/bono pudo cambiar desde entonces.
        if is_free_search:
            u_now = db.get_user(uid)
            if get_user_role(uid) != UserRole.FREE:
                is_free_search = None
            elif is_free_search == 'initial' and u_now.get('free_search_used'):
                is_free_search = 'bonus' if (u_now.get('bonus_searches') or 0) > 0 else None
            elif is_free_search == 'bonus' and not (u_now.get('bonus_searches') or 0):
                is_free_search = None

        loading_text = UI.text(
            "search_loading", lang, kw,
            LOADING_FRAMES[0], UI.text("phase_scanning", lang), 0
        )

        # Respuesta instantánea del botón (fluidez) + mensaje de carga
        if callback_event:
            try:
                await callback_event.answer()
            except Exception:
                pass
            try:
                loading_msg = await callback_event.edit(
                    loading_text,
                    buttons=None,
                    parse_mode='md'
                )
            except Exception:
                loading_msg = await state.bot.send_message(
                    chat_id,
                    loading_text,
                    parse_mode='md'
                )
        else:
            loading_msg = await state.bot.send_message(
                chat_id,
                loading_text,
                parse_mode='md'
            )

        try:
            start_time = time.time()
            search_task = asyncio.create_task(search_engine(kw, t_opt, modo))

            await animate_loading(loading_msg, search_task, kw, lang)

            result_file = await search_task
            elapsed = time.time() - start_time

            if result_file:
                if is_free_search == 'bonus':
                    db.consume_bonus_search(uid)
                elif is_free_search == 'initial':
                    db.mark_free_search_used(uid)
                else:
                    db.add_search(uid)

                count = 0
                with open(result_file, 'rb') as f:
                    for _ in f:
                        count += 1

                if is_free_search:
                    caption = UI.text("search_completed_free", lang, kw, tipo_texto, count, elapsed)
                    u_now = db.get_user(uid)
                    remaining = _free_search_count(u_now)
                    if is_free_search == 'bonus':
                        caption += "\n\n" + UI.text("bonus_consumed", lang)
                    if remaining > 0:
                        caption += "\n" + UI.text("free_remaining", lang, remaining)
                    else:
                        caption += "\n" + UI.text("free_exhausted", lang)
                else:
                    caption = UI.text("search_completed", lang, kw, tipo_texto, count, elapsed)

                await _send_search_result(chat_id, result_file, caption,
                                               e=callback_event, msg=loading_msg,
                                               reply_to=reply_to,
                                               buttons=Keyboards.result_actions())
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
                    UI.text("error_generic", lang, str(exc)[:120]),
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
                callback_event=None,
                reply_to=next_search.get('reply_to')
            )
        except Exception as exc:
            logger.error(f"Error en busqueda encolada de {uid}: {exc}")
            try:
                await state.bot.send_message(
                    next_search['chat_id'],
                    UI.text("error_generic", next_search.get('lang', 'es'), str(exc)[:120]),
                    parse_mode='md'
                )
            except Exception:
                pass

    @bot_client.on(events.NewMessage(pattern=r"/(start|cmds)(@\w+)?(\s|$)"))
    async def start(e):
        """Bienvenida + menú principal. /start y /cmds son el mismo comando
        (alias el uno del otro, por si acaso el usuario usa cualquiera).
        Acepta también la forma con mención que Telegram usa en grupos:
        /start@MiBot [param]."""
        if e.is_group and e.chat_id not in state.allowed_groups:
            return

        lang = 'es'
        try:
            uid = e.sender_id

            # Deep link: /start <param>   (ref_<uid> = referidos · HJ-xxx = keys)
            args = e.message.message.split()
            param = args[1] if len(args) > 1 else None

            # Referido: evaluar ANTES de crear el registro (solo usuarios nuevos)
            is_brand_new = not db.user_exists(uid)

            user = db.get_user(uid)
            lang = user.get('language', 'es')
            role = get_user_role(uid)
            has_free = db.is_new_user(uid) and role == UserRole.FREE
            name = await _display_name(e, uid)

            referral_applied = False
            if param and param.startswith("ref_"):
                try:
                    referrer_id = int(param[4:])
                except ValueError:
                    referrer_id = None
                if referrer_id and is_brand_new:
                    referral_applied = db.apply_referral(uid, referrer_id)
                    if referral_applied:
                        # Refrescar datos del invitado (ahora tiene +1 bono)
                        user = db.get_user(uid)
                        # Notificar al referidor en SU idioma
                        referrer_user = db.get_user(referrer_id)
                        try:
                            await state.bot.send_message(
                                referrer_id,
                                UI.text("ref_notify_referrer",
                                        referrer_user.get('language', 'es'),
                                        name, db.get_referral_count(referrer_id)),
                                parse_mode='md'
                            )
                        except Exception:
                            pass
            elif param:
                # Deep link para canjear key VIP
                if db.redeem(uid, param):
                    role = get_user_role(uid)
                    await e.reply(
                        locale_manager.get("redeem_success", lang),
                        buttons=Keyboards.main(role, lang, 0),
                        parse_mode='md'
                    )
                    return

            # Elegir texto de bienvenida
            if has_free:
                welcome_key = "welcome_new"
            else:
                welcome_key = "welcome"

            free_n = _free_search_count(user) if role == UserRole.FREE else 0

            welcome_text = UI.text(welcome_key, lang, name, _get_commands_by_role(role, has_free), UI.role_badge(role), user.get('search_count', 0), _welcome_extra(user, role, lang))

            main_kb = Keyboards.main(role, lang, free_n) if e.is_private else None
            try:
                await e.reply(welcome_text, buttons=main_kb, parse_mode='md')
            except Exception as send_err:
                # Red de seguridad v4.2.4: si el teclado falla al serializar,
                # reintentar sin botones para no perder la bienvenida.
                logger.error(f"/start reintento sin botones (teclado): {send_err}")
                await e.reply(welcome_text, parse_mode='md')
        except Exception as exc:
            # Garantía anti-mudez: si algo falla, NUNCA quedarse en silencio.
            # v4.2.3: el OWNER ve además la causa técnica exacta en el chat
            # (diagnóstico en vivo sin necesidad de entrar al VPS).
            logger.exception("Error en /start")
            try:
                err_txt = locale_manager.get("start_error", lang)
                if e.sender_id in config.ADMIN_IDS:
                    diag = (type(exc).__name__ + ": " + str(exc))[:200]
                    err_txt += "\n\n🔧 Diagnóstico (solo admins): " + diag
                await e.reply(err_txt, parse_mode=None)
            except Exception:
                pass

    @bot_client.on(events.NewMessage(pattern="/updateBot"))
    async def update_bot_cmd(e):
        await cmd_update_bot(e)

    @bot_client.on(events.NewMessage(pattern=r"/(cmd|help)(@\w+)?(\s|$)"))
    async def cmd_cmd(e):
        """Mostrar lista de comandos disponibles."""
        if e.is_group and e.chat_id not in state.allowed_groups:
            return
        try:
            uid = e.sender_id
            user = db.get_user(uid)
            lang = user.get('language', 'es')
            role = get_user_role(uid)
            has_free = db.is_new_user(uid) and role == UserRole.FREE
            cmds = _get_commands_by_role(role, has_free)
            try:
                await e.reply(
                    UI.text("cmd_list", lang, cmds),
                    buttons=Keyboards.back() if e.is_private else None,
                    parse_mode='md'
                )
            except Exception as send_err:
                # Red de seguridad v4.2.4: reintento sin botones
                logger.error(f"/cmd reintento sin botones (teclado): {send_err}")
                await e.reply(UI.text("cmd_list", lang, cmds), parse_mode='md')
        except Exception as exc:
            # Anti-mudez + diagnóstico para admins (mismo criterio que /start)
            logger.exception("Error en /cmd")
            try:
                err_txt = locale_manager.get("start_error", 'es')
                if e.sender_id in config.ADMIN_IDS:
                    diag = (type(exc).__name__ + ": " + str(exc))[:200]
                    err_txt += "\n\n🔧 Diagnóstico (solo admins): " + diag
                await e.reply(err_txt, parse_mode=None)
            except Exception:
                pass

    # ═════════════════════════════════════════════════════════════
    # UTILIDADES: /ping · /id · /help
    # ═════════════════════════════════════════════════════════════

    @bot_client.on(events.NewMessage(pattern=r"/ping"))
    async def cmd_ping(e):
        """Latencia, uptime y versión del bot."""
        if e.is_group and e.chat_id not in state.allowed_groups:
            return
        uid = e.sender_id
        user = db.get_user(uid)
        lang = user.get('language', 'es')
        latency_ms = max(0.0, (datetime.now(timezone.utc) - e.message.date).total_seconds() * 1000)
        uptime = format_uptime(time.time() - state.START_TIME) if state.START_TIME else "—"
        await e.reply(
            UI.text("ping_info", lang, latency_ms, uptime, config.VERSION),
            parse_mode='md'
        )

    @bot_client.on(events.NewMessage(pattern=r"^/id(@\w+)?$"))
    async def cmd_id(e):
        """Mostrar IDs del usuario y del chat actual."""
        if e.is_group and e.chat_id not in state.allowed_groups:
            return
        uid = e.sender_id
        user = db.get_user(uid)
        lang = user.get('language', 'es')
        chat_type = "Privado" if e.is_private else ("Grupo" if e.is_group else "Canal")
        await e.reply(
            UI.text("id_info", lang, uid, e.chat_id, chat_type),
            parse_mode='md'
        )

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
        await e.reply("✅ Grupo añadido a la lista permitida y guardado en la base de datos.")

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

    @bot_client.on(events.NewMessage(pattern=r"/canjear(?:@\w+)? (.+)"))
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

    @bot_client.on(events.NewMessage(pattern=r"/url(@\w+)?\s*$"))
    async def cmd_url_usage(e):
        """Ayuda de uso cuando /url se envía sin enlace (ya no se queda mudo)."""
        if e.is_group and e.chat_id not in state.allowed_groups:
            return
        uid = e.sender_id
        user = db.get_user(uid)
        lang = user.get('language', 'es')
        await e.reply(
            UI.text("url_usage", lang),
            buttons=Keyboards.back() if e.is_private else None,
            parse_mode='md'
        )

    @bot_client.on(events.NewMessage(pattern=r"/url(?:@\w+)?\s+(\S.*)"))
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

        kw = normalizar_url(e.pattern_match.group(1))

        # Anti-superposicion: encolar con defaults y auto-eliminar aviso
        if uid in state.active_searches:
            try:
                wait_msg = await e.reply(UI.text("search_already_running", lang), parse_mode='md')
                asyncio.create_task(_auto_delete_msg(wait_msg, 5))
            except Exception:
                pass
            state.search_queue.setdefault(uid, []).append({
                'kw': kw, 't_opt': '24h', 'modo': SearchMode.ULP,
                'tipo_texto': 'ULP', 'is_free_search': is_free_search,
                'chat_id': e.chat_id, 'lang': lang, 'reply_to': e.id
            })
            return

        state.temp_state[uid] = {
            'kw': kw, 'chat_id': e.chat_id,
            'is_free_search': is_free_search, 'reply_to': e.id
        }
        await e.reply(
            UI.text("search_step_time", lang, kw),
            buttons=Keyboards.time(),
            parse_mode='md'
        )

    # ═════════════════════════════════════════════════════════════
    # COMANDO /imap v2 — IMAP Checker con keywords + ZIP
    # ═════════════════════════════════════════════════════════════

    @bot_client.on(events.NewMessage(pattern=r"/imap(.*)"))
    async def cmd_imap(e):
        """IMAP Checker v2 — soporta keywords, country y genera ZIP.

        Uso:
          /imap                      → sin keywords (modo clasico)
          /imap kw1, kw2, kw3         → con keywords (genera ZIP)
          /imap country              → agrupa hits por pais (genera ZIP)
        Requiere responder a un archivo .txt con mail:pass.
        Si se pasan keywords sin archivo, las guarda y espera el archivo.
        """
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

        # Parsear keywords o modo country del comando
        raw_args = (e.pattern_match.group(1) or "").strip()
        keywords = []
        mode_country = False
        if raw_args:
            if raw_args.lower() == 'country':
                mode_country = True
            else:
                keywords = [kw.strip().lower() for kw in raw_args.split(",") if kw.strip()]

        # Validar maximo 10 keywords
        if len(keywords) > 10:
            return await e.reply(
                UI.text("imap_too_many_keywords", lang, len(keywords)),
                parse_mode='md'
            )

        reply = await e.get_reply_message()

        # Si hay keywords pero no archivo: guardar keywords y esperar archivo
        if (keywords or mode_country) and (not reply or not reply.document):
            state.temp_state[uid] = {
                'step': 'WAITING_IMAP_FILE',
                'imap_keywords': keywords,
                'imap_mode_country': mode_country,
                'chat_id': e.chat_id
            }
            if mode_country:
                return await e.reply(
                    UI.text("imap_country_waiting_file", lang),
                    parse_mode='md'
                )
            return await e.reply(
                UI.text("imap_keywords_waiting_file", lang, ", ".join(keywords)),
                parse_mode='md'
            )

        # Si no hay keywords y no hay archivo: mostrar info
        if not reply or not reply.document:
            return await e.reply(
                UI.text("imap_info", lang),
                buttons=Keyboards.imap_info(),
                parse_mode='md'
            )

        # Tenemos archivo: ejecutar IMAP check
        await _execute_imap_check(e, reply, keywords, lang, uid, mode_country=mode_country)

    # --- Conversación: usuario envía archivo después de poner keywords ---
    @bot_client.on(events.NewMessage(
        func=lambda ev: ev.is_private and
                       ev.sender_id in state.temp_state and
                       state.temp_state[ev.sender_id].get('step') == 'WAITING_IMAP_FILE' and
                       ev.document is not None
    ))
    async def handle_imap_file(e):
        uid = e.sender_id
        user = db.get_user(uid)
        lang = user.get('language', 'es')
        ts = state.temp_state.pop(uid, {})
        keywords = ts.get('imap_keywords', [])
        mode_country = ts.get('imap_mode_country', False)
        await _execute_imap_check(e, e, keywords, lang, uid, mode_country=mode_country)

    # --- Si el usuario envia texto (no archivo) mientras espera IMAP file, cancelar ---
    @bot_client.on(events.NewMessage(
        func=lambda ev: ev.is_private and
                       ev.sender_id in state.temp_state and
                       state.temp_state[ev.sender_id].get('step') == 'WAITING_IMAP_FILE' and
                       ev.document is None
    ))
    async def handle_imap_cancel(e):
        uid = e.sender_id
        user = db.get_user(uid)
        lang = user.get('language', 'es')
        state.temp_state.pop(uid, None)
        role = get_user_role(uid)
        has_free = db.is_new_user(uid) and role == UserRole.FREE
        free_n = _free_search_count(user) if role == UserRole.FREE else 0
        name = await _display_name(e, uid)
        welcome_key = "welcome_new" if has_free else "welcome"
        await e.reply(
            UI.text(welcome_key, lang, name, _get_commands_by_role(role, has_free), UI.role_badge(role), user.get('search_count', 0), _welcome_extra(user, role, lang)),
            buttons=Keyboards.main(role, lang, free_n),
            parse_mode='md'
        )

    # --- Conversación: usuario envía archivo después de poner keywords en grupo ---
    @bot_client.on(events.NewMessage(
        func=lambda ev: ev.is_group and
                       ev.chat_id in state.allowed_groups and
                       ev.sender_id in state.temp_state and
                       state.temp_state[ev.sender_id].get('step') == 'WAITING_IMAP_FILE' and
                       ev.document is not None
    ))
    async def handle_imap_file_group(e):
        uid = e.sender_id
        user = db.get_user(uid)
        lang = user.get('language', 'es')
        ts = state.temp_state.pop(uid, {})
        keywords = ts.get('imap_keywords', [])
        mode_country = ts.get('imap_mode_country', False)
        await _execute_imap_check(e, e, keywords, lang, uid, mode_country=mode_country)

    # --- BROADCAST ---

    async def _broadcast(sender_id: int, targets: list, msg_text: str, status_msg, label: str, lang: str = 'es'):
        total = len(targets)
        if total == 0:
            await status_msg.edit(UI.text("broadcast_done", lang, 0, 0), parse_mode='md')
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
                            UI.text("broadcast_progress", lang, label, sent, total, errors),
                            parse_mode='md'
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
            UI.text("broadcast_done", lang, sent, errors),
            parse_mode='md'
        )

    @bot_client.on(events.NewMessage(pattern=r"/bc ([\s\S]+)"))
    async def cmd_bc(e):
        if get_user_role(e.sender_id) != UserRole.ADMIN:
            return
        msg_text = e.pattern_match.group(1).strip()
        users = db.get_all_users()
        lang = db.get_user(e.sender_id).get('language', 'es')
        status = await e.reply(
            UI.text("broadcast_started", lang, "Broadcast Global", len(users)),
            parse_mode='md'
        )
        await _broadcast(e.sender_id, users, msg_text, status, "Broadcast Global", lang)

    @bot_client.on(events.NewMessage(pattern=r"/bcvip ([\s\S]+)"))
    async def cmd_bcvip(e):
        if get_user_role(e.sender_id) != UserRole.ADMIN:
            return
        msg_text = e.pattern_match.group(1).strip()
        vips_data = db.list_vips()
        lang = db.get_user(e.sender_id).get('language', 'es')
        status = await e.reply(
            UI.text("broadcast_started", lang, "Broadcast VIP", len(vips_data)),
            parse_mode='md'
        )
        await _broadcast(e.sender_id, vips_data, msg_text, status, "Broadcast VIP", lang)

    # --- SIZEDISP: Disco de la VPS ---
    @bot_client.on(events.NewMessage(pattern=r"/sizedisp"))
    async def cmd_sizedisp(e):
        """Admin: mostrar almacenamiento total y ocupado de la VPS."""
        if get_user_role(e.sender_id) != UserRole.ADMIN:
            return

        try:
            stat = os.statvfs('/')
            total = stat.f_blocks * stat.f_frsize
            free = stat.f_bavail * stat.f_frsize
            used = total - free
            pct = (used / total * 100) if total > 0 else 0

            total_str = format_size(total)
            used_str = format_size(used)
            free_str = format_size(free)

            # Barra visual premium
            bar = progress_bar(pct, width=20)

            user = db.get_user(e.sender_id)
            lang = user.get('language', 'es')
            await e.reply(
                UI.text("sizedisp_info", lang, total_str, used_str, pct, free_str, bar),
                parse_mode='md'
            )
        except Exception as exc:
            logger.error(f"Error en /sizedisp: {exc}")
            await e.reply(f"Error obteniendo info del disco: `{str(exc)[:200]}`", parse_mode='md')

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

        kw = normalizar_url(e.text)

        # Anti-superposicion: encolar con defaults y auto-eliminar aviso
        if uid in state.active_searches:
            try:
                wait_msg = await e.reply(UI.text("search_already_running", lang), parse_mode='md')
                asyncio.create_task(_auto_delete_msg(wait_msg, 5))
            except Exception:
                pass
            state.search_queue.setdefault(uid, []).append({
                'kw': kw, 't_opt': '24h', 'modo': SearchMode.ULP,
                'tipo_texto': 'ULP', 'is_free_search': is_free_search,
                'chat_id': e.chat_id, 'lang': lang, 'reply_to': e.id
            })
            # Limpiar estado de conversacion
            state.temp_state.pop(uid, None)
            return

        state.temp_state[uid] = {
            'kw': kw, 'chat_id': e.chat_id,
            'is_free_search': is_free_search, 'reply_to': e.id
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
                free_n = _free_search_count(user) if role == UserRole.FREE else 0
                name = await _display_name(e, uid)
                welcome_key = "welcome_new" if has_free else "welcome"
                await e.edit(
                    UI.text(welcome_key, lang, name, _get_commands_by_role(role, has_free), UI.role_badge(role), user.get('search_count', 0), _welcome_extra(user, role, lang)),
                    buttons=Keyboards.main(role, lang, free_n),
                    parse_mode='md'
                )

            # ─── LISTA DE COMANDOS ───
            elif data == "cmd_list":
                has_free = db.is_new_user(uid) and role == UserRole.FREE
                cmds = _get_commands_by_role(role, has_free)
                await e.edit(
                    UI.text("cmd_list", lang, cmds),
                    buttons=Keyboards.back(),
                    parse_mode='md'
                )

            # ─── IMAP INFO ───
            elif data == "imap_info":
                await e.edit(
                    UI.text("imap_info", lang),
                    buttons=Keyboards.imap_info(),
                    parse_mode='md'
                )

            # ─── MI CUENTA ───
            elif data == "my_account":
                await e.edit(
                    UI.text("my_account", lang, uid, UI.role_badge(role),
                            _fmt_member_since(user), user.get('search_count', 0),
                            _account_block(user, role, lang)),
                    buttons=Keyboards.back(),
                    parse_mode='md'
                )

            # ─── REFERIDOS ───
            elif data == "ref_info":
                link = f"https://t.me/{config.BOT_USERNAME}?start=ref_{uid}"
                refs = db.get_referral_count(uid)
                u_now = db.get_user(uid)
                free_n = _free_search_count(u_now) if role == UserRole.FREE else (u_now.get('bonus_searches') or 0)
                await e.edit(
                    UI.text("ref_info", lang, link, refs, free_n),
                    buttons=Keyboards.ref_panel(link, lang),
                    parse_mode='md'
                )

            # ─── COMPRAR VIP (menu con pago automatico + contacto) ───
            elif data == "buy_vip_info":
                await e.edit(
                    UI.text("pay_plans", lang),
                    buttons=Keyboards.payment_plans(),
                    parse_mode='md'
                )

            # ─── PAGO: Seleccionar plan ───
            elif data.startswith("pay_") and data != "pay_check":
                days = int(data.split("_")[1])
                plan = VIP_PLANS.get(days)
                if not plan:
                    return await e.answer("Plan invalido.", alert=True)

                await e.edit(UI.text("pay_checking", lang), parse_mode='md')

                result = await create_invoice(uid, days, lang)
                if not result or "invoice_url" not in result:
                    await e.edit(
                        UI.text("pay_api_error", lang),
                        buttons=Keyboards.back(),
                        parse_mode='md'
                    )
                    return

                invoice_url = result["invoice_url"]

                await e.edit(
                    UI.text("pay_invoice", lang, plan["label"], plan["price"], invoice_url),
                    buttons=Keyboards.payment_invoice(invoice_url),
                    parse_mode='md'
                )

            # ─── PAGO: Verificar estado (verificación real vía API) ───
            elif data == "pay_check":
                await e.edit(
                    UI.text("pay_checking", lang),
                    buttons=Keyboards.payment_checking(),
                    parse_mode='md'
                )

                pending = [p for p in db.get_user_payments(uid) if p.get('status') == 'pending']
                if not pending:
                    await e.edit(
                        UI.text("pay_no_pending", lang),
                        buttons=Keyboards.payment_plans(),
                        parse_mode='md'
                    )
                    return

                payment = pending[0]
                invoice_id = str(payment['invoice_id'])
                days = payment.get('days') or 0
                plan = VIP_PLANS.get(days, {
                    "price": float(payment.get('amount_usd') or 0.0),
                    "label": f"{days} días"
                })

                status = await get_payment_status(invoice_id)

                if status in SUCCESS_STATUSES:
                    await _deliver_vip(state, uid, days, invoice_id, lang, "manual-check")
                    new_role = get_user_role(uid)
                    await e.edit(
                        UI.text("pay_success", lang, days),
                        buttons=Keyboards.main(new_role, lang, False),
                        parse_mode='md'
                    )
                elif status in FAIL_STATUSES:
                    db.update_payment_status(invoice_id, status)
                    fail_key = "pay_expired" if status == "expired" else "pay_failed"
                    await e.edit(
                        UI.text(fail_key, lang),
                        buttons=Keyboards.payment_plans(),
                        parse_mode='md'
                    )
                else:
                    # waiting / confirming / sending / not_found / error de red
                    await e.edit(
                        UI.text("pay_status_pending", lang, plan["label"], float(plan["price"])),
                        buttons=Keyboards.payment_checking(),
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
                free_n = _free_search_count(user) if role == UserRole.FREE else 0
                name = await _display_name(e, uid)
                welcome_key = "welcome_new" if has_free else "welcome"
                await e.edit(
                    UI.text(welcome_key, new_lang, name, _get_commands_by_role(role, has_free), UI.role_badge(role), user.get('search_count', 0), _welcome_extra(user, role, new_lang)),
                    buttons=Keyboards.main(role, new_lang, free_n),
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
                        UI.text("search_step_format", lang),
                        buttons=Keyboards.formats()
                    )
                else:
                    await e.answer("Usa 'Nueva búsqueda' primero.", alert=True)

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
                        'lang': lang, 'reply_to': state.temp_state[uid].get('reply_to')
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
                chat_id = state.temp_state[uid].get('chat_id', uid)
                reply_to = state.temp_state[uid].get('reply_to')
                state.temp_state.pop(uid, None)
                await _execute_search(
                    uid=uid, kw=kw, t_opt=t_opt, modo=modo,
                    tipo_texto=tipo_texto, is_free_search=is_free_search,
                    chat_id=chat_id,
                    lang=lang, callback_event=e, reply_to=reply_to
                )
                return

            # ─── REPORTAR URL ───
            elif data == "report_url":
                kw = state.temp_state.get(uid, {}).get('kw', 'Desconocido')
                for admin_id in config.ADMIN_IDS:
                    try:
                        await state.bot.send_message(
                            admin_id,
                            UI.text("report_received", 'es', uid, kw)
                        )
                    except Exception:
                        pass
                await e.answer("Reporte enviado correctamente.", alert=True)
                return

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
                    text = UI.text("sellers_list_empty", lang)
                else:
                    lines = [UI.text("sellers_list_header", lang, len(sellers))]
                    for sid in sellers[:50]:
                        uname = await _lookup_username(sid)
                        lines.append(f"├─ 👤 `{sid}`{uname}")
                    if len(sellers) > 50:
                        lines.append(UI.text("list_more", lang, len(sellers) - 50))
                    lines.append(UI.text("list_footer", lang))
                    text = "\n".join(lines)
                await e.edit(text, buttons=Keyboards.back("admin_enter"), parse_mode='md')

            elif data == "adm_vips":
                if role != UserRole.ADMIN:
                    return await e.answer("Acceso denegado.", alert=True)
                vips = db.list_vips()
                if not vips:
                    text = UI.text("vip_list_empty", lang)
                else:
                    lines = [UI.text("vip_list_header", lang, len(vips))]
                    for v in vips[:50]:
                        exp = v.get('vip_expiry') or 'N/A'
                        if exp != 'N/A' and len(exp) > 10:
                            exp = exp[:10]
                        uname = await _lookup_username(v['user_id'])
                        lines.append(f"├─ 👤 `{v['user_id']}`{uname} · ⏳ `{exp}`")
                    if len(vips) > 50:
                        lines.append(UI.text("list_more", lang, len(vips) - 50))
                    lines.append(UI.text("list_footer", lang))
                    text = "\n".join(lines)
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
        finally:
            # Fluidez: respuesta instantánea del botón. Si ya se respondió
            # con alerta, este segundo answer se ignora silenciosamente.
            try:
                await e.answer()
            except Exception:
                pass