"""
═══════════════════════════════════════════════════════════════
  HJ ULP PRO — Emojis Premium (custom emoji) · v4.2.32
═══════════════════════════════════════════════════════════════
  • Catálogo de 86 asociaciones: los 20 de v4.2.31 (INTACTOS, ya
    funcionan) + 66 nuevas aportadas con IDs reales de Telegram.
  • Convierte los emojis del bot en EMOJIS PREMIUM (custom emoji)
    en TODOS los mensajes: /start, menús, búsquedas, progreso de
    descargas, captions, errores, traducciones ES/EN/PT, textos
    dinámicos… (cualquier parse_mode: 'md', 'html' y None).
  • v4.2.32 — NUEVO: iconos premium en BOTONES inline y URL
    (icon_custom_emoji_id, Bot API 9.4 / layer 211). El emoji
    pasa a ser el ICONO del botón y se quita del label — sin
    copias redundantes. Callbacks, datos y URLs intactos.
  • v4.2.32 — NUEVO: sustitución de «alt» verificado. Cuando el
    emoji original y el glifo premium no coinciden (p. ej. 🚫 →
    glifo ❌), el texto visible se sustituye por el alt REAL del
    documento (validado al arrancar vía MTProto con
    GetCustomEmojiDocuments) y se recalculan los offsets UTF-16
    de TODAS las entidades (negritas, enlaces, code…).
  • Arquitectura: DOS parches centrales en Telethon cubren el
    100 % de las salidas sin tocar un solo call site:
        1. MessageParseMethods._parse_message_text
           → send_message, edit, reply, respond, captions…
        2. TelegramClient.build_reply_markup
           → botones de cualquier send/edit/send_file.
  • Las banderas de países (🇵🇪 🇺🇸 …) NUNCA se convierten: no
    hay IDs para ellas y los indicadores regionales no son claves
    del catálogo. Las secuencias ZWJ (🏳️‍🌈 y similares) tampoco
    se tocan (guarda de U+200D).
  • Degradación elegante: si algo falla calculando entidades, el
    mensaje se envía con emojis normales (NUNCA se rompe un
    envío). El self-test del arranque valida los documentos vía
    MTProto, prueba en vivo los custom emojis y los iconos de
    botones, y desactiva lo que el servidor rechace.
  • Interruptor: PREMIUM_EMOJIS=0 en .env apaga todo al instante.
═══════════════════════════════════════════════════════════════
"""

import asyncio
import re

from telethon import TelegramClient
from telethon.client.messageparse import MessageParseMethods
from telethon.tl import functions, types
from telethon.tl.types import (
    MessageEntityCustomEmoji,
    MessageEntityCode,
    MessageEntityPre,
)
from telethon.utils import is_list_like

from config import config
from logger_setup import logger

# ═════════════════════════════════════════════════════════════
#  1) LOS 20 ORIGINALES (v4.2.31) — INTACTOS, YA FUNCIONAN
#     (21 claves: incluye el alias 🔍 → misma lupa que 🔎)
# ═════════════════════════════════════════════════════════════
_PREMIUM_EMOJIS_V4231 = {
    "✅": 5260416304224936047,
    "📊": 5931472654660800739,
    "📁": 5258514780469075716,   # glifo premium: 📂
    "⚠": 5447644880824181073,    # cubre ⚠️ (con VS16) y ⚠
    "❌": 5260342697075416641,
    "⚡": 5258152182150077732,    # cubre ⚡️ y ⚡
    "⏳": 5258258882022612173,
    "⏱": 5877613700344450910,    # cubre ⏱️ y ⏱
    "🎁": 6032937473162614352,
    "💎": 5807465992363710697,
    "👥": 5258513401784573443,
    "📬": 5253742260054409879,    # glifo premium: ✉️
    "📄": 5258477770735885832,
    "📅": 5258105663359294787,    # glifo premium: 🗓
    "📥": 5877307202888273539,
    "🔎": 5874960879434338403,
    "🔍": 5874960879434338403,    # misma lupa que 🔎 → mismo premium
    "🔥": 6008118472066732010,
    "📦": 5258134813302332906,
    "🌐": 5879585266426973039,
    "🌍": 6114021507908767611,    # glifo premium: 🌎
}

# ═════════════════════════════════════════════════════════════
#  2) LOS 66 NUEVOS (v4.2.32) — IDs reales aportados
#     Clave = emoji ORIGINAL tal como aparece en el código del
#     bot (forma base, sin VS16). NO se usa el emoji alternativo
#     como clave: 📧 y 📨 tienen IDs distintos aunque ambos usan
#     ✉️ de glifo; ídem 🔐/🔒, 💲/💰, 🚫/❌, 📑/📁, 📋/📄…
# ═════════════════════════════════════════════════════════════
_PREMIUM_EMOJIS_NUEVOS = {
    # ── GRUPO A — 38 ──────────────────────────────────────
    "🚫": 5258318620722733379,
    "👑": 5807868868886009920,
    "📧": 5967280668885913944,
    "🔄": 5877410604225924969,
    "👤": 5258011929993026890,
    "💡": 5258216851472654189,
    "🚀": 5366357681240031250,
    "♾": 5271934788037517525,
    "🔐": 5258476306152038031,
    "💼": 5258260149037965799,
    "📂": 6017174676898321263,
    "💳": 5927169041595634481,
    "📌": 5258461531464539536,
    "🎉": 5994502837327892086,
    "➡": 5174695057713792085,
    "🗂": 5967456680940671207,
    "🔑": 6005570495603282482,
    "🧭": 5866268458332720879,
    "👇": 5231102735817918643,
    "🗄": 5778670366947806278,
    "📨": 5985817223749439505,
    "🔗": 5260730055880876557,
    "🎖": 5440539497383087970,
    "💲": 5987880246865565644,
    "💾": 5884064642438795702,
    "❓": 5873121512445187130,
    "♻": 5262934980421492594,
    "🛑": 5330512249259847609,
    "🏷": 5985433648810171091,
    "🔁": 6005843436479975944,
    "🆕": 5886306834410640699,
    "✍": 5985774024968379294,
    "📣": 5771695636411847302,
    "📑": 5257965810634202885,
    "📋": 5956561916573782596,
    "🌟": 5956148757899776734,
    "👋": 5994750571041525522,
    "🛡": 5931409969613116639,
    # ── GRUPO B — 24 ──────────────────────────────────────
    "📞": 5897488197650223178,
    "🧹": 6007942490076745785,
    "⬇": 5470112026548257635,
    "🪪": 5936017305585586269,
    "💬": 5287595522993991899,
    "🎯": 5310278924616356636,
    "☄": 5364288198493096346,
    "⚙": 5258096772776991776,
    "🆔": 5301096984617166561,
    "📍": 5778661935927004845,
    "📎": 5877495434124988415,
    "🪙": 5258368777350816286,
    "🧮": 5303214794336125778,
    "🧩": 5472262490903554982,
    "📶": 5924681813149618024,
    "📈": 5258391025281408576,
    "📉": 5246762912428603768,
    "💰": 5174808766972953705,
    "✂": 5237808360882977239,
    "🗑": 5985493993100679671,
    "🔧": 5264908182886557148,
    "🆓": 5406756500108501710,
    "🏳": 5994378304751145264,
    "🔒": 5832546462478635761,
    # ── GRUPO C — números ─────────────────────────────────
    "1\u20e3": 5418150395509751203,
    "2\u20e3": 5416066838154988064,
    "3\u20e3": 5415583675809022417,
    "4\u20e3": 5415809105757486109,
}

# Catálogo completo: 86 asociaciones + el alias técnico 🔍 (=87 claves)
PREMIUM_EMOJI_IDS = {**_PREMIUM_EMOJIS_V4231, **_PREMIUM_EMOJIS_NUEVOS}

# ═════════════════════════════════════════════════════════════
#  3) ALT de cada documento nuevo — el emoji Unicode EXACTO que
#     Telegram exige cubrir con la entidad (DocumentAttribute-
#     CustomEmoji.alt). Solo aplica a los 66 nuevos: los 20
#     originales ya funcionan cubriendo su propio texto.
#     Al arrancar, _validate_documents() los re-verifica en vivo
#     vía MTProto y corrige este mapa con los alt REALES.
# ═════════════════════════════════════════════════════════════
_ALT_ESTATICOS = {
    "🚫": "❌",
    "📧": "✉️",
    "📨": "✉️",
    "🔐": "🔒",
    "🗂": "🗃",
    "🗄": "🖼",
    "🎖": "🥇",
    "💲": "💰",
    "🔗": "⛓",
    "🆔": "☝️",
    "📶": "🛜",
    "♾": "♾",
    "🏷": "🏷",
    "✍": "🖊",
    "📣": "📢",
    "📑": "📁",
    "📋": "📄",
    "🌟": "⭐️",
    "🛡": "🛡",
    "⚙": "⚙",
    "♻": "♻️",
    "➡": "➡️",
    "⬇": "⬇️",
    "☄": "☄️",
    "✂": "✂️",
    "1\u20e3": "1\ufe0f\u20e3",
    "2\u20e3": "2\ufe0f\u20e3",
    "3\u20e3": "3\ufe0f\u20e3",
    "4\u20e3": "4\ufe0f\u20e3",
}
# Mapa vivo (el self-test lo refina con los alt verificados)
ALT_OVERRIDES: dict = dict(_ALT_ESTATICOS)

# ═════════════════════════════════════════════════════════════
#  REGEX única — variantes VS16 por clave + guardas ZWJ
#  · Emoji normal "💎": acepta "💎" y "💎️"
#  · Keycap "1⃣": acepta "1⃣" y "1️⃣" (VS16 en medio)
#  · Nunca matchea pegado a U+200D (protege 🏳️‍🌈 y similares)
# ═════════════════════════════════════════════════════════════
_VS16 = "\ufe0f"
_KEYCAP = "\u20e3"
_ZWJ = "\u200d"


def _variants(key: str):
    """Secuencias Unicode que deben activar esta clave."""
    if _KEYCAP in key:                      # "1⃣" → ("1⃣", "1️⃣")
        return (key, key[0] + _VS16 + _KEYCAP)
    return (key, key + _VS16)               # "💎" → ("💎", "💎️")


# secuencia completa matcheada → clave base del catálogo
_SEQ_MAP = {}
for _k in PREMIUM_EMOJI_IDS:
    for _v in _variants(_k):
        _SEQ_MAP[_v] = _k

_PATTERN = re.compile(
    "(%s)" % "|".join(
        re.escape(v) for v in sorted(_SEQ_MAP, key=len, reverse=True)
    )
)

# Estado del módulo
enabled: bool = True        # emojis premium en mensajes (v4.2.31)
icons_enabled: bool = True  # iconos premium en botones (v4.2.32)
_installed: bool = False


# ═════════════════════════════════════════════════════════════
#  NÚCLEO — escanear, sustituir el alt y generar entidades
#  (offsets/lengths en unidades UTF-16, como exige Telegram)
# ═════════════════════════════════════════════════════════════
def _u16len(s: str) -> int:
    return sum(2 if ord(c) > 0xFFFF else 1 for c in s)


def _collect(text: str, skip_ranges):
    """Recorre el texto UNA vez.

    Devuelve [(start_cp, end_cp, seq, start16, len16)] de cada
    emoji del catálogo, saltando los bloques code/pre (rangos en
    unidades UTF-16) y las secuencias ZWJ (🏳️‍🌈 y compuestos).
    """
    out = []
    pos16 = 0        # posición UTF-16 acumulada
    consumed = 0     # codepoints ya contabilizados
    for m in _PATTERN.finditer(text):
        if m.start() > consumed:
            pos16 += _u16len(text[consumed:m.start()])
            consumed = m.start()
        seq = m.group(0)
        length16 = _u16len(seq)
        end16 = pos16 + length16
        # Guarda ZWJ: el match no puede formar parte de una secuencia
        # compuesta (ni pegado a U+200D por delante ni por detrás —
        # incluido el caso VS16+ZWJ, p. ej. 🏳️‍🌈 tras el backtracking
        # del regex a la variante corta).
        tail = text[m.end():m.end() + 2]
        zwj = (
            (m.start() > 0 and text[m.start() - 1] == _ZWJ)
            or tail[:1] == _ZWJ
            or tail == _VS16 + _ZWJ
        )
        # ¿cae dentro de un bloque code/pre? → se queda como emoji normal
        if not zwj and not any(s < end16 and pos16 < e for s, e in skip_ranges):
            out.append((m.start(), m.end(), seq, pos16, length16))
        pos16 += length16
        consumed = m.end()
    return out


def _apply(message: str, entities):
    """Añade las entidades premium y sustituye los alt cuando toca.

    Devuelve (nuevo_texto, entidades). Si ninguna sustitución
    cambia el texto (el caso normal), el objeto `message` se
    devuelve TAL CUAL — cero copias, cero regresiones.
    """
    if not enabled or not message or not PREMIUM_EMOJI_IDS:
        return message, entities
    entities = list(entities or [])
    skip = [
        (e.offset, e.offset + e.length) for e in entities
        if isinstance(e, (MessageEntityCode, MessageEntityPre))
    ]
    found = _collect(message, skip)
    if not found:
        return message, entities

    # Idempotencia: nunca se re-convierte un emoji que ya tiene una
    # entidad custom (protege cualquier doble parseo hipotético)
    ya_custom = [
        (e.offset, e.offset + e.length) for e in entities
        if isinstance(e, MessageEntityCustomEmoji)
    ]
    if ya_custom:
        found = [
            f for f in found
            if not any(s < f[3] + f[4] and f[3] < e for s, e in ya_custom)
        ]
    if not found:
        return message, entities

    # ¿hay que sustituir algún texto visible por su alt?
    plan = []
    for (s_cp, e_cp, seq, s16, len16) in found:
        key = _SEQ_MAP[seq]
        doc_id = PREMIUM_EMOJI_IDS[key]
        alt = ALT_OVERRIDES.get(key)
        if alt is not None and alt != seq:
            plan.append((s_cp, e_cp, seq, s16, len16, alt, doc_id))
        else:
            plan.append((s_cp, e_cp, seq, s16, len16, seq, doc_id))

    if all(p[5] == p[2] for p in plan):
        # ── RUTA RÁPIDA: sin sustituciones, texto intacto ──
        for (_, _, _, s16, len16, _, doc_id) in plan:
            entities.append(MessageEntityCustomEmoji(s16, len16, doc_id))
    else:
        # ── RUTA COMPLETA: sustituir alt + recalcular offsets ──
        parts = []
        last_cp = 0
        new16 = 0
        deltas = []     # (inicio16_viejo, fin16_viejo, delta16)
        for (s_cp, e_cp, seq, s16, len16, alt, doc_id) in plan:
            seg = message[last_cp:s_cp]
            parts.append(seg)
            new16 += _u16len(seg)
            parts.append(alt)
            alt16 = _u16len(alt)
            entities.append(MessageEntityCustomEmoji(new16, alt16, doc_id))
            if alt16 != len16:
                deltas.append((s16, s16 + len16, alt16 - len16))
            new16 += alt16
            last_cp = e_cp
        parts.append(message[last_cp:])
        message = "".join(parts)

        # Ajustar las entidades del parser (bold/links/…) al nuevo
        # texto: las que empiezan después de una sustitución se
        # desplazan; las que la contienen cambian de longitud.
        for e in entities:
            if isinstance(e, MessageEntityCustomEmoji):
                continue
            for (s16, e16, d) in deltas:
                if e.offset >= e16:
                    e.offset += d
                elif e.offset + e.length > s16:
                    e.length += d

    entities.sort(key=lambda e: (e.offset, e.length))
    return message, entities


# ═════════════════════════════════════════════════════════════
#  BOTONES — emoji inicial → icono premium (icon_custom_emoji_id)
#  El label pierde el emoji (queda solo el icono premium) y el
#  botón se RECONSTRUYE: nunca se mutan los objetos compartidos
#  (BACK, LANG_BUTTON, SUPPORT_URL…). Callbacks, datos y URLs
#  quedan intactos porque .type se reutiliza tal cual.
# ═════════════════════════════════════════════════════════════
_BUTTON_EMOJI_RE = re.compile(
    "^(%s)(?:\\s+|$)" % "|".join(
        re.escape(v) for v in sorted(_SEQ_MAP, key=len, reverse=True)
    )
)


def _icon_button(button):
    """Convierte el emoji inicial de UN botón en su icono premium."""
    if not isinstance(button, types.KeyboardInlineButton):
        return button  # reply-keyboard u otros: sin soporte de icono
    text = button.text or ""
    m = _BUTTON_EMOJI_RE.match(text)
    if not m:
        return button  # «  Volver, banderas 🇪🇸, emojis sin ID…
    key = _SEQ_MAP.get(m.group(1))
    if not key:
        return button
    new_text = text[m.end():].lstrip()
    if not new_text:
        return button  # nunca un label vacío
    st = button.style
    new_style = types.KeyboardButtonStyle(
        bg_primary=getattr(st, "bg_primary", None) if st else None,
        bg_danger=getattr(st, "bg_danger", None) if st else None,
        bg_success=getattr(st, "bg_success", None) if st else None,
        icon=PREMIUM_EMOJI_IDS[key],
    )
    return types.KeyboardInlineButton(new_text, button.type, new_style)


def _premium_buttons(buttons):
    """Aplica iconos premium a una estructura MarkupLike cualquiera."""
    if not (enabled and icons_enabled) or buttons is None:
        return buttons
    try:
        if buttons.SUBCLASS_OF_ID == 0xe2e10ef2:  # ya es un ReplyMarkup
            return buttons
    except AttributeError:
        pass
    if is_list_like(buttons):
        if buttons and is_list_like(buttons[0]):
            return [[_icon_button(b) for b in row] for row in buttons]
        return [_icon_button(b) for b in buttons]
    return _icon_button(buttons)


# ═════════════════════════════════════════════════════════════
#  PATCHES de Telethon — dos cuellos de botella cubren TODO
# ═════════════════════════════════════════════════════════════
_orig_parse_message_text = MessageParseMethods._parse_message_text
_orig_build_reply_markup = TelegramClient.build_reply_markup


async def _premium_parse_message_text(self, message, parse_mode):
    """Envoltorio del parser original: mismas entidades + premium.

    Cualquier fallo interno se traga y se envía el mensaje con los
    emojis normales — un envío JAMÁS se rompe por esto.
    """
    message, entities = await _orig_parse_message_text(self, message, parse_mode)
    if enabled and message:
        try:
            message, entities = _apply(message, entities)
        except Exception:
            logger.warning(
                "PREMIUM_EMOJI_ERROR: se envía sin emojis premium",
                exc_info=True,
            )
    return message, entities


def _premium_build_reply_markup(buttons):
    """Envoltorio del constructor de teclados: emojis → iconos.

    Si algo falla, los botones salen exactamente como estaban.
    """
    try:
        buttons = _premium_buttons(buttons)
    except Exception:
        logger.warning(
            "PREMIUM_EMOJI_BUTTON_ERROR: botones sin icono premium",
            exc_info=True,
        )
    return _orig_build_reply_markup(buttons)


def install() -> bool:
    """Instala los dos parches. Idempotente.

    Devuelve True si quedó activo (ya estaba instalado o se instaló
    ahora), False si la config lo desactiva (PREMIUM_EMOJIS=0).
    """
    global _installed
    if _installed:
        return True
    if not config.PREMIUM_EMOJIS:
        logger.info("premium_emojis: desactivado por config (PREMIUM_EMOJIS=0)")
        return False
    if not hasattr(MessageParseMethods, "_parse_message_text"):
        logger.error("premium_emojis: Telethon sin _parse_message_text — no instalado")
        return False
    MessageParseMethods._parse_message_text = _premium_parse_message_text
    TelegramClient.build_reply_markup = staticmethod(_premium_build_reply_markup)
    _installed = True
    logger.info(
        f"premium_emojis: {len(PREMIUM_EMOJI_IDS)} emojis premium activos "
        "en todos los mensajes + iconos en botones compatibles"
    )
    return True


# ═════════════════════════════════════════════════════════════
#  VALIDACIÓN MTProto — alt reales de los 66 documentos nuevos
# ═════════════════════════════════════════════════════════════
async def _validate_documents(client) -> bool:
    """Pide a Telegram los documentos y verifica su campo «alt».

    Refina ALT_OVERRIDES con los alt REALES: si el alt verificado
    coincide con la clave, se retira la sustitución; si difiere,
    se usa el verificado. Los 20 originales NUNCA se tocan (ya
    funcionan cubriendo su propio texto). Si la llamada no se
    puede completar, se conserva el mapa estático.
    """
    global ALT_OVERRIDES
    doc_ids = sorted(set(_PREMIUM_EMOJIS_NUEVOS.values()))
    verified = {}
    for i in range(0, len(doc_ids), 100):
        docs = await client(
            functions.messages.GetCustomEmojiDocumentsRequest(doc_ids[i:i + 100])
        )
        for doc in docs:
            for attr in getattr(doc, "attributes", None) or []:
                if isinstance(attr, types.DocumentAttributeCustomEmoji):
                    verified[doc.id] = attr.alt
                    break
    if not verified:
        logger.warning("premium_emojis: validación MTProto sin documentos")
        return False

    merged = dict(_ALT_ESTATICOS)
    for key, doc_id in _PREMIUM_EMOJIS_NUEVOS.items():
        alt = verified.get(doc_id)
        if alt is None:
            continue            # documento no verificado → estático
        # El alt verificado pasa a ser la forma canónica de la clave:
        # si coincide con el texto matcheado no hay sustitución (ruta
        # rápida) y si difiere (p. ej. variantes VS16) se normaliza.
        merged[key] = alt
    ALT_OVERRIDES = merged
    faltan = len(doc_ids) - len(verified)
    distintas = sum(1 for k, v in merged.items() if v != k)
    logger.info(
        f"premium_emojis: {len(verified)}/{len(doc_ids)} documentos "
        f"verificados vía MTProto — {distintas} sustituciones de alt "
        "activas"
        + (f" ({faltan} sin verificar, usan alt estático)" if faltan else "")
    )
    return True


# ═════════════════════════════════════════════════════════════
#  SELF-TEST del arranque — el bot se protege solo
# ═════════════════════════════════════════════════════════════
async def self_test(client) -> bool:
    """Comprueba EN VIVO que el bot puede usar custom emojis.

    1. Valida vía MTProto los documentos de los 66 nuevos (alt).
    2. Envía un «✅ premium» al primer ADMIN y lo borra al instante.
    3. Envía un botón con icono premium y lo borra igual.

    · Si el servidor rechaza los custom emojis (los bots necesitan
      un username coleccionable de Fragment) → se desactivan solos.
    · Si solo rechaza los iconos de botones → se apagan los iconos
      y los mensajes siguen con premium.
    · Si la prueba no se puede hacer (red, admin bloqueado…) → se
      quedan activos (no castigamos por causas ajenas).
    """
    global enabled, icons_enabled
    if not (_installed and enabled):
        return enabled
    admins = [a for a in (config.ADMIN_IDS or []) if a]
    if not admins:
        return enabled

    # ── 1) Validar los alt de los 66 nuevos vía MTProto ──
    try:
        await asyncio.wait_for(_validate_documents(client), timeout=60)
    except Exception as e:
        logger.info(
            f"premium_emojis: validación MTProto no concluyente ({e}) "
            "— se usan los alt estáticos"
        )

    # ── 2) Sonda de custom emoji en MENSAJE ──
    doc_id = PREMIUM_EMOJI_IDS["✅"]
    try:
        msg = await asyncio.wait_for(
            client.send_message(
                admins[0],
                "✅",
                formatting_entities=[
                    MessageEntityCustomEmoji(0, 1, doc_id)
                ],
            ),
            timeout=30,
        )
        try:
            await msg.delete()
        except Exception:
            pass  # si no se borra, no pasa nada
        logger.info("premium_emojis: verificación OK — el bot puede usar custom emojis")
    except asyncio.TimeoutError:
        logger.warning("premium_emojis: verificación sin respuesta — se dejan activos")
        return True
    except Exception as e:
        err = str(e).lower()
        if "emoji" in err or "entit" in err:
            enabled = False
            icons_enabled = False
            logger.warning(
                "premium_emojis: el servidor rechazó los custom emojis "
                f"({e}) — DESACTIVADOS automáticamente, el bot sigue "
                "normal con emojis comunes. NOTA: los bots necesitan un "
                "username coleccionable (Fragment) para emojis premium."
            )
            return False
        logger.info(f"premium_emojis: verificación no concluyente ({e}) — se dejan activos")
        return True

    # ── 3) Sonda de ICONO premium en BOTÓN ──
    from telethon import Button
    try:
        msg = await asyncio.wait_for(
            client.send_message(
                admins[0],
                "✅ icono",
                buttons=[Button.inline("✅ icono", b"premium_icon_probe",
                                       icon=doc_id)],
            ),
            timeout=30,
        )
        try:
            await msg.delete()
        except Exception:
            pass
        logger.info("premium_emojis: iconos premium en botones verificados OK")
    except asyncio.TimeoutError:
        logger.warning("premium_emojis: sonda de iconos sin respuesta — se dejan activos")
    except Exception as e:
        err = str(e).lower()
        if "emoji" in err or "entit" in err or "keyboard" in err or "button" in err:
            icons_enabled = False
            logger.warning(
                "premium_emojis: el servidor rechazó los iconos premium en "
                f"botones ({e}) — iconos DESACTIVADOS, los mensajes siguen "
                "con emojis premium y los botones con su emoji normal."
            )
        else:
            logger.info(f"premium_emojis: sonda de iconos no concluyente ({e})")
    return True
