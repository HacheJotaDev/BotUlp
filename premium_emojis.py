"""
═══════════════════════════════════════════════════════════════
  HJ ULP PRO — Emojis Premium (custom emoji) · v4.2.31
═══════════════════════════════════════════════════════════════
  • Convierte los emojis normales del bot en EMOJIS PREMIUM de
    Telegram (custom emoji) en TODOS los mensajes: /start, menús,
    búsquedas, progreso de descargas, captions de archivos, etc.
  • Lo hace a nivel del parser de Telethon (_parse_message_text):
    UN SOLO punto cubre send_message, edit, reply, respond,
    captions de send_file y los 3 parse_mode ('md', 'html', None).
  • Los textos fuente NO se tocan: cero riesgo para la lógica
    (comparaciones, splits, truncados) y para los locale files.
  • Degradación elegante: si algo falla al calcular entidades,
    el mensaje se envía con emojis normales (NUNCA se rompe un
    envío). Y si el servidor rechaza los custom emojis (los bots
    necesitan un username coleccionable de Fragment), el self-test
    del arranque los desactiva solos.
  • Interruptor: PREMIUM_EMOJIS=0 en .env los apaga al instante.
═══════════════════════════════════════════════════════════════
"""

import asyncio
import re

from telethon.client.messageparse import MessageParseMethods
from telethon.tl.types import (
    MessageEntityCustomEmoji,
    MessageEntityCode,
    MessageEntityPre,
)

from config import config
from logger_setup import logger

# ═════════════════════════════════════════════════════════════
#  MAPA: emoji normal → document_id del emoji premium
#  (el custom_emoji_id que entrega Telegram)
# ═════════════════════════════════════════════════════════════
PREMIUM_EMOJI_IDS = {
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

# Regex única: cada emoji con VS16 (\ufe0f) opcional. Ninguna clave
# es prefijo de otra → el orden del alternation es irrelevante.
_VS16 = "\ufe0f"
_PATTERN = re.compile(
    "|".join(re.escape(e) + _VS16 + "?" for e in PREMIUM_EMOJI_IDS)
)

# Estado del módulo
enabled: bool = True   # el self-test del arranque puede apagarlo en caliente
_installed: bool = False


# ═════════════════════════════════════════════════════════════
#  NÚCLEO: escanear texto y generar entidades custom_emoji
#  (offsets/lengths en unidades UTF-16, como exige Telegram)
# ═════════════════════════════════════════════════════════════
def _scan(text: str, skip_ranges):
    """Recorre el texto UNA vez y devuelve [MessageEntityCustomEmoji].

    skip_ranges: lista de (inicio, fin) en unidades UTF-16 donde NO
    se aplica premium (bloques code/pre del markdown ya parseado).
    """
    entities = []
    pos16 = 0        # posición UTF-16 acumulada
    consumed = 0     # codepoints ya contabilizados
    for m in _PATTERN.finditer(text):
        if m.start() > consumed:
            for ch in text[consumed:m.start()]:
                pos16 += 2 if ord(ch) > 0xFFFF else 1
            consumed = m.start()
        seq = m.group(0)
        length16 = sum(2 if ord(c) > 0xFFFF else 1 for c in seq)
        end16 = pos16 + length16
        # ¿cae dentro de un bloque code/pre? → se queda como emoji normal
        if not any(s < end16 and pos16 < e for s, e in skip_ranges):
            doc_id = PREMIUM_EMOJI_IDS[seq.rstrip(_VS16)]
            entities.append(MessageEntityCustomEmoji(pos16, length16, doc_id))
        pos16 += length16
        consumed = m.end()
    return entities


def _apply(message: str, entities):
    """Añade las entidades premium a las que ya produjo el parser."""
    if not enabled or not message or not PREMIUM_EMOJI_IDS:
        return entities
    entities = list(entities or [])
    skip = [
        (e.offset, e.offset + e.length) for e in entities
        if isinstance(e, (MessageEntityCode, MessageEntityPre))
    ]
    nuevos = _scan(message, skip)
    if nuevos:
        entities.extend(nuevos)
        # orden estable: las del parser conservan su orden relativo
        entities.sort(key=lambda e: (e.offset, e.length))
    return entities


# ═════════════════════════════════════════════════════════════
#  PATCH de Telethon — un único cuello de botella cubre TODO
# ═════════════════════════════════════════════════════════════
_orig_parse_message_text = MessageParseMethods._parse_message_text


async def _premium_parse_message_text(self, message, parse_mode):
    """Envoltorio del parser original: mismas entidades + premium.

    Cualquier fallo interno se traga y se envía el mensaje con los
    emojis normales — un envío JAMÁS se rompe por esto.
    """
    message, entities = await _orig_parse_message_text(self, message, parse_mode)
    if enabled and message:
        try:
            entities = _apply(message, entities)
        except Exception:
            logger.warning(
                "PREMIUM_EMOJI_ERROR: se envía sin emojis premium",
                exc_info=True,
            )
    return message, entities


def install() -> bool:
    """Instala el parche del parser. Idempotente.

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
    _installed = True
    logger.info(
        f"premium_emojis: {len(PREMIUM_EMOJI_IDS)} emojis premium activos "
        "en todos los mensajes del bot"
    )
    return True


# ═════════════════════════════════════════════════════════════
#  SELF-TEST del arranque — el bot se protege solo
# ═════════════════════════════════════════════════════════════
async def self_test(client) -> bool:
    """Comprueba EN VIVO que el bot puede enviar custom emojis.

    Envía un «✅ premium» al primer ADMIN y lo borra al instante.
    · Si el servidor lo acepta → premium queda activo.
    · Si el servidor lo rechaza (típicamente porque el bot no tiene
      un username coleccionable de Fragment) → se desactivan solos
      y el bot sigue funcionando con emojis normales.
    · Si la prueba no se puede hacer (red, admin bloqueado…) → se
      quedan activos (no castigamos por causas ajenas).
    """
    global enabled
    if not (_installed and enabled):
        return enabled
    admins = [a for a in (config.ADMIN_IDS or []) if a]
    if not admins:
        return enabled
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
        return True
    except asyncio.TimeoutError:
        logger.warning("premium_emojis: verificación sin respuesta — se dejan activos")
        return True
    except Exception as e:
        err = str(e).lower()
        if "emoji" in err or "entit" in err:
            enabled = False
            logger.warning(
                "premium_emojis: el servidor rechazó los custom emojis "
                f"({e}) — DESACTIVADOS automáticamente, el bot sigue "
                "normal con emojis comunes. NOTA: los bots necesitan un "
                "username coleccionable (Fragment) para emojis premium."
            )
            return False
        logger.info(f"premium_emojis: verificación no concluyente ({e}) — se dejan activos")
        return True
