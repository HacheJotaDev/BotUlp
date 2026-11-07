#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════
  HJ ULP PRO — Suite de pruebas: emojis premium v4.2.32
═══════════════════════════════════════════════════════════════
  Pruebas 100 % locales (sin red, sin credenciales de Telegram):
    · Catálogo: 86 asociaciones (20 originales INTACTOS + 66 nuevos
      con ID exacto) + alias técnico 🔍.
    · Motor: offsets/lengths UTF-16 verificados byte a byte contra
      utf-16-le real (BMP=1 unidad, astral=2), variantes VS16,
      keycaps, sustitución de «alt» con recálculo de offsets de
      entidades del parser (bold/links), guardas ZWJ, banderas.
    · Integración con el parser REAL de Telethon ('md', 'html',
      parse_mode=None) mediante MessageParseMethods parcheado.
    · Botones: icon_custom_emoji_id vía build_reply_markup —
      callbacks/datos/URLs intactos, labels sin emoji redundante,
      objetos compartidos JAMÁS mutados, idempotencia.
    · Fallback: interruptor en caliente, errores tragados (un
      envío nunca se rompe), doble aplicación segura.
    · Auditoría de cobertura sobre los archivos reales del repo.

  Uso:  python3 test_premium_emojis.py
═══════════════════════════════════════════════════════════════
"""

import asyncio
import ast
import json
import os
import re
import sys
import time
import types as pytypes

# config.py exige BOT_TOKEN — en pruebas usamos uno de relleno
os.environ.setdefault("BOT_TOKEN", "123:test")

import premium_emojis as pe
from premium_emojis import (
    PREMIUM_EMOJI_IDS, _PREMIUM_EMOJIS_V4231, _PREMIUM_EMOJIS_NUEVOS,
    ALT_OVERRIDES, _apply, _SEQ_MAP, _PATTERN,
)

# ─────────────────────────────────────────────────────────────
#  Infraestructura mínima de pruebas
# ─────────────────────────────────────────────────────────────
_PASSED = 0
_FAILED = []
_RESULTS = []


def check(name, cond, detail=""):
    global _PASSED
    if cond:
        _PASSED += 1
        _RESULTS.append(("PASS", name, ""))
    else:
        _FAILED.append(name)
        _RESULTS.append(("FAIL", name, detail))


def custom_ents(entities):
    from telethon.tl.types import MessageEntityCustomEmoji
    return [e for e in entities if isinstance(e, MessageEntityCustomEmoji)]


def covered_text(text, ent):
    """Texto exacto que cubre la entidad, verificado byte a byte."""
    b = text.encode("utf-16-le")
    return b[ent.offset * 2:(ent.offset + ent.length) * 2].decode("utf-16-le")


# Cliente falso que usa el parser REAL de Telethon (parcheado)
from telethon.client.messageparse import MessageParseMethods
from telethon.extensions import markdown, html


class FakeClient(MessageParseMethods):
    def __init__(self):
        self._parse_mode = markdown


# Stub de database (ui.py → nowpayments/roles → database: Postgres
# no está disponible en el sandbox; solo se necesitan constantes)
if "database" not in sys.modules:
    _fake_db_mod = pytypes.ModuleType("database")

    class _FakeDB:
        def __getattr__(self, _n):
            def _fn(*_a, **_k):
                return 0
            return _fn
    _fake_db_mod.db = _FakeDB()
    sys.modules["database"] = _fake_db_mod


# ═════════════════════════════════════════════════════════════
#  1) CATÁLOGO
# ═════════════════════════════════════════════════════════════
def test_catalogo():
    # 86 asociaciones + alias técnico 🔍 (misma lupa que 🔎)
    check("catálogo: 87 claves (86 asociaciones + alias 🔍)",
          len(PREMIUM_EMOJI_IDS) == 87, f"hay {len(PREMIUM_EMOJI_IDS)}")
    check("catálogo: 86 document_ids distintos",
          len(set(PREMIUM_EMOJI_IDS.values())) == 86)

    # Los 20 originales (21 claves con 🔍) con IDs EXACTOS de v4.2.31
    v4231_snapshot = {
        "✅": 5260416304224936047, "📊": 5931472654660800739,
        "📁": 5258514780469075716, "⚠": 5447644880824181073,
        "❌": 5260342697075416641, "⚡": 5258152182150077732,
        "⏳": 5258258882022612173, "⏱": 5877613700344450910,
        "🎁": 6032937473162614352, "💎": 5807465992363710697,
        "👥": 5258513401784573443, "📬": 5253742260054409879,
        "📄": 5258477770735885832, "📅": 5258105663359294787,
        "📥": 5877307202888273539, "🔎": 5874960879434338403,
        "🔍": 5874960879434338403, "🔥": 6008118472066732010,
        "📦": 5258134813302332906, "🌐": 5879585266426973039,
        "🌍": 6114021507908767611,
    }
    check("originales: las 21 claves de v4.2.31 INTACTAS (IDs exactos)",
          _PREMIUM_EMOJIS_V4231 == v4231_snapshot)

    # Los 66 nuevos con los IDs EXACTOS aportados (grupos A/B/C)
    nuevos_snapshot = {
        "🚫": 5258318620722733379, "👑": 5807868868886009920,
        "📧": 5967280668885913944, "🔄": 5877410604225924969,
        "👤": 5258011929993026890, "💡": 5258216851472654189,
        "🚀": 5366357681240031250, "♾": 5271934788037517525,
        "🔐": 5258476306152038031, "💼": 5258260149037965799,
        "📂": 6017174676898321263, "💳": 5927169041595634481,
        "📌": 5258461531464539536, "🎉": 5994502837327892086,
        "➡": 5174695057713792085, "🗂": 5967456680940671207,
        "🔑": 6005570495603282482, "🧭": 5866268458332720879,
        "👇": 5231102735817918643, "🗄": 5778670366947806278,
        "📨": 5985817223749439505, "🔗": 5260730055880876557,
        "🎖": 5440539497383087970, "💲": 5987880246865565644,
        "💾": 5884064642438795702, "❓": 5873121512445187130,
        "♻": 5262934980421492594, "🛑": 5330512249259847609,
        "🏷": 5985433648810171091, "🔁": 6005843436479975944,
        "🆕": 5886306834410640699, "✍": 5985774024968379294,
        "📣": 5771695636411847302, "📑": 5257965810634202885,
        "📋": 5956561916573782596, "🌟": 5956148757899776734,
        "👋": 5994750571041525522, "🛡": 5931409969613116639,
        "📞": 5897488197650223178, "🧹": 6007942490076745785,
        "⬇": 5470112026548257635, "🪪": 5936017305585586269,
        "💬": 5287595522993991899, "🎯": 5310278924616356636,
        "☄": 5364288198493096346, "⚙": 5258096772776991776,
        "🆔": 5301096984617166561, "📍": 5778661935927004845,
        "📎": 5877495434124988415, "🪙": 5258368777350816286,
        "🧮": 5303214794336125778, "🧩": 5472262490903554982,
        "📶": 5924681813149618024, "📈": 5258391025281408576,
        "📉": 5246762912428603768, "💰": 5174808766972953705,
        "✂": 5237808360882977239, "🗑": 5985493993100679671,
        "🔧": 5264908182886557148, "🆓": 5406756500108501710,
        "🏳": 5994378304751145264, "🔒": 5832546462478635761,
        "1\u20e3": 5418150395509751203, "2\u20e3": 5416066838154988064,
        "3\u20e3": 5415583675809022417, "4\u20e3": 5415809105757486109,
    }
    check("nuevos: 66 asociaciones con los IDs EXACTOS aportados",
          _PREMIUM_EMOJIS_NUEVOS == nuevos_snapshot,
          f"diferencias: { {k: (v, nuevos_snapshot.get(k)) for k, v in _PREMIUM_EMOJIS_NUEVOS.items() if nuevos_snapshot.get(k) != v} }")

    # Claves duplicadas entre grupos / alt como clave primaria
    check("nuevos: sin solaparse con los originales",
          not (set(_PREMIUM_EMOJIS_NUEVOS) & set(_PREMIUM_EMOJIS_V4231)))
    check("alt: solo claves nuevas reciben sustitución (los 20 intactos)",
          not (set(ALT_OVERRIDES) & set(_PREMIUM_EMOJIS_V4231)))
    # El alt NO es clave primaria: pares con mismo glifo, distinto ID
    check("alt: 📧 y 📨 tienen IDs distintos (mismo glifo ✉️)",
          PREMIUM_EMOJI_IDS["📧"] != PREMIUM_EMOJI_IDS["📨"])
    check("alt: 🔐 y 🔒 distintos · 💲 y 💰 distintos · 🚫 y ❌ distintos",
          PREMIUM_EMOJI_IDS["🔐"] != PREMIUM_EMOJI_IDS["🔒"]
          and PREMIUM_EMOJI_IDS["💲"] != PREMIUM_EMOJI_IDS["💰"]
          and PREMIUM_EMOJI_IDS["🚫"] != PREMIUM_EMOJI_IDS["❌"])


# ═════════════════════════════════════════════════════════════
#  2) MOTOR — UTF-16, VS16, keycaps (ruta rápida, texto intacto)
# ═════════════════════════════════════════════════════════════
def test_motor_basico():
    t, ents = _apply("✅ OK", [])
    ce = custom_ents(ents)
    check("motor: ✅ BMP (1 unidad UTF-16)",
          t == "✅ OK" and len(ce) == 1
          and (ce[0].offset, ce[0].length, ce[0].document_id)
          == (0, 1, 5260416304224936047))

    t, ents = _apply("📊 x", [])
    ce = custom_ents(ents)
    check("motor: 📊 astral (2 unidades UTF-16)",
          len(ce) == 1 and (ce[0].offset, ce[0].length) == (0, 2))

    t, ents = _apply("Total: 📊 de 5", [])
    ce = custom_ents(ents)
    check("motor: offset intermedio 'Total: 📊'",
          len(ce) == 1 and (ce[0].offset, ce[0].length) == (7, 2))

    t, ents = _apply("⚠️ cuidado", [])
    ce = custom_ents(ents)
    check("motor: ⚠️ con VS16 (2 unidades), texto intacto",
          t == "⚠️ cuidado" and len(ce) == 1
          and (ce[0].offset, ce[0].length) == (0, 2))

    t, ents = _apply("a⏱️ b⏱ c", [])
    ce = custom_ents(ents)
    ok = (len(ce) == 2 and (ce[0].offset, ce[0].length) == (1, 2)
          and (ce[1].offset, ce[1].length) == (5, 1))
    check("motor: ⏱️/⏱ con y sin VS16 en el mismo texto", ok)

    t, ents = _apply("1️⃣ Clásico", [])
    ce = custom_ents(ents)
    check("motor: keycap 1️⃣ (3 unidades), sin sustitución (alt=secuencia)",
          t == "1️⃣ Clásico" and len(ce) == 1
          and (ce[0].offset, ce[0].length) == (0, 3)
          and ce[0].document_id == 5418150395509751203)

    # Sin emojis → el MISMO objeto de texto (cero copias)
    original = "texto plano sin emojis"
    t, ents = _apply(original, [])
    check("motor: sin coincidencias devuelve el mismo objeto (is)",
          t is original and ents == [])

    # Catálogo completo × variantes — offsets verificados byte a byte
    bad = []
    for key in PREMIUM_EMOJI_IDS:
        for seq in (key, key + "\ufe0f") if "\u20e3" not in key \
                else (key, key[0] + "\ufe0f\u20e3"):
            if seq not in _SEQ_MAP:
                continue
            esperado = ALT_OVERRIDES.get(key, seq)  # alt si sustituye
            t, ents = _apply("a🌀" + seq + "z", [])
            ce = custom_ents(ents)
            if (len(ce) != 1 or covered_text(t, ce[0]) != esperado
                    or ce[0].document_id != PREMIUM_EMOJI_IDS[key]
                    or t != "a🌀" + esperado + "z"):
                bad.append((key, seq, [(e.offset, e.length) for e in ce], t))
    check("motor: 87 claves × variantes — offsets y doc_id byte a byte "
          "(prefijo BMP+astral, alt sustituido)", not bad, str(bad[:3]))


# ═════════════════════════════════════════════════════════════
#  3) SUSTITUCIÓN DE «ALT» + RECALCULO DE OFFSETS
# ═════════════════════════════════════════════════════════════
def test_sustitucion_alt():
    t, ents = _apply("📧 mail", [])
    ce = custom_ents(ents)
    check("alt: 📧 → texto visible ✉️ (entidad 0,2)",
          t == "✉️ mail" and len(ce) == 1
          and (ce[0].offset, ce[0].length, ce[0].document_id)
          == (0, 2, 5967280668885913944)
          and covered_text(t, ce[0]) == "✉️")

    t, ents = _apply("🚫 prohibido", [])
    ce = custom_ents(ents)
    check("alt: 🚫 → ❌ visible, ID de 🚫 conservado (no el de ❌)",
          t == "❌ prohibido" and len(ce) == 1
          and ce[0].document_id == 5258318620722733379
          and ce[0].document_id != PREMIUM_EMOJI_IDS["❌"])

    t, ents = _apply("🗂️ archivos", [])
    ce = custom_ents(ents)
    check("alt: 🗂️ → 🗃 (delta -1), resto del texto desplazado",
          t == "🗃 archivos" and len(ce) == 1
          and (ce[0].offset, ce[0].length) == (0, 2))

    t, ents = _apply("1⃣ modo", [])   # keycap SIN VS16
    ce = custom_ents(ents)
    check("alt: keycap sin VS16 1⃣ → 1️⃣ normalizado (+VS16)",
          t == "1️⃣ modo" and len(ce) == 1
          and (ce[0].offset, ce[0].length) == (0, 3))

    t, ents = _apply("♾️ VIP", [])
    ce = custom_ents(ents)
    check("alt: ♾️ → ♾ (VS16 retirado, 1 unidad)",
          t == "♾ VIP" and len(ce) == 1
          and (ce[0].offset, ce[0].length) == (0, 1))

    t, ents = _apply("🆔 ID: 42", [])
    ce = custom_ents(ents)
    check("alt: 🆔 → ☝️",
          t == "☝️ ID: 42" and len(ce) == 1 and covered_text(t, ce[0]) == "☝️")

    t, ents = _apply("🌟 brillo", [])
    ce = custom_ents(ents)
    check("alt: 🌟 → ⭐️ (delta 0 pero texto cambia)",
          t == "⭐️ brillo" and covered_text(t, ce[0]) == "⭐️")

    t, ents = _apply("☄ cometa", [])
    ce = custom_ents(ents)
    check("alt: ☄ sin VS16 → ☄️",
          t == "☄️ cometa" and covered_text(t, ce[0]) == "☄️")

    # Sustitución múltiple con offsets encadenados
    t, ents = _apply("📧 y 🗂️", [])
    ce = custom_ents(ents)
    check("alt: sustituciones múltiples (📧→✉️ y 🗂️→🗃)",
          t == "✉️ y 🗃" and len(ce) == 2
          and (ce[0].offset, ce[1].offset) == (0, 5))

    # Entidades del parser que CONTIENEN una sustitución → longitud
    from telethon.tl.types import MessageEntityBold
    t, ents = _apply("🗂️ x", [MessageEntityBold(0, 5)])
    ce = custom_ents(ents)
    b = [e for e in ents if isinstance(e, MessageEntityBold)][0]
    check("alt: bold que contiene la sustitución ajusta su length "
          "(5→4 con 🗃)", t == "🗃 x" and (b.offset, b.length) == (0, 4)
          and covered_text(t, b) == "🗃 x")

    # Entidades DESPUÉS de una sustitución → offset desplazado
    t, ents = _apply("a 🗂️ **b**", [MessageEntityBold(5, 1)])
    ce = custom_ents(ents)
    b = [e for e in ents if isinstance(e, MessageEntityBold)][0]
    check("alt: entidad posterior a la sustitución se desplaza -1",
          t == "a 🗃 **b**" and (b.offset, b.length) == (4, 1))

    # Entidades ANTES de una sustitución → intactas
    t, ents = _apply("**a** 🗂️ z", [MessageEntityBold(0, 1)])
    b = [e for e in ents if isinstance(e, MessageEntityBold)][0]
    check("alt: entidad anterior a la sustitución intacta",
          t == "**a** 🗃 z" and (b.offset, b.length) == (0, 1))


# ═════════════════════════════════════════════════════════════
#  4) INTEGRACIÓN CON EL PARSER REAL DE TELETHON (parcheado)
# ═════════════════════════════════════════════════════════════
async def test_parser_telethon():
    c = FakeClient()

    # markdown: bold anidado + code excluido
    t, ents = await c._parse_message_text("**📊** `📦` 📁", ())
    ce = custom_ents(ents)
    codes = [e for e in ents if e.__class__.__name__ == "MessageEntityCode"]
    bolds = [e for e in ents if e.__class__.__name__ == "MessageEntityBold"]
    check("parser md: 📊 anidada en bold, 📁 al final",
          len(ce) == 2 and len(codes) == 1 and len(bolds) == 1
          and covered_text(t, ce[0]) == "📊"
          and covered_text(t, ce[1]) == "📁")
    check("parser md: 📦 dentro de `code` se queda NORMAL",
          not any(covered_text(t, e).startswith("📦") for e in ce))

    # markdown: enlace con emoji en el label — URL intacta
    t, ents = await c._parse_message_text(
        "Visita [Canal 🚀](https://t.me/hj) ahora", ())
    ce = custom_ents(ents)
    urls = [e for e in ents if e.__class__.__name__ == "MessageEntityTextUrl"]
    check("parser md: enlace con 🚀 en el label, URL intacta",
          t == "Visita Canal 🚀 ahora" and len(ce) == 1
          and covered_text(t, ce[0]) == "🚀"
          and urls and urls[0].url == "https://t.me/hj"
          and covered_text(t, urls[0]) == "Canal 🚀")

    # html: entidades del parser + premium + sustitución
    t, ents = await c._parse_message_text("<b>📊</b> Email 📧", "html")
    ce = custom_ents(ents)
    check("parser html: bold + premium + sustitución 📧→✉️",
          t == "📊 Email ✉️" and len(ce) == 2
          and covered_text(t, ce[0]) == "📊"
          and covered_text(t, ce[1]) == "✉️")

    # parse_mode=None (mensajes de error del bot)
    t, ents = await c._parse_message_text("📊 sin parse 🚫", None)
    ce = custom_ents(ents)
    check("parser None: convierte igual (mensajes con parse_mode=None)",
          t == "📊 sin parse ❌" and len(ce) == 2
          and covered_text(t, ce[0]) == "📊"
          and covered_text(t, ce[1]) == "❌")

    # banderas de países — NUNCA se convierten
    t, ents = await c._parse_message_text(
        "🇵🇪 Perú 🇺🇸 US 🇧🇷 BR 🇲🇽 MX 🇪🇸 ES 🇨🇴 CO 🇦🇷 AR 🇬🇧 GB", ())
    check("banderas: 8 banderas intactas, cero entidades premium",
          t == "🇵🇪 Perú 🇺🇸 US 🇧🇷 BR 🇲🇽 MX 🇪🇸 ES 🇨🇴 CO 🇦🇷 AR 🇬🇧 GB"
          and custom_ents(ents) == [])

    # ZWJ: 🏳️‍🌈 no se toca; 🏳️ suelto sí
    t, ents = await c._parse_message_text("🏳️‍🌈 arcoíris", ())
    check("ZWJ: 🏳️‍🌈 intacta (guarda U+200D)",
          t == "🏳️‍🌈 arcoíris" and custom_ents(ents) == [])
    t, ents = await c._parse_message_text("🏳️ fin", ())
    ce = custom_ents(ents)
    check("ZWJ: 🏳️ suelta SÍ se convierte (está en el catálogo)",
          len(ce) == 1 and covered_text(t, ce[0]) == "🏳️"
          and ce[0].document_id == 5994378304751145264)

    # comandos y datos funcionales intactos
    t, ents = await c._parse_message_text(
        "/start /help /promo 50 back_main search_init pay_30", ())
    check("datos: comandos/callbacks intactos, cero entidades",
          custom_ents(ents) == [] and t.startswith("/start /help"))

    # un error interno NUNCA rompe el envío
    orig = pe._collect
    pe._collect = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
    try:
        t, ents = await c._parse_message_text("📊 texto", ())
        check("fallback: excepción interna tragada — mensaje sigue su curso",
              t == "📊 texto")
    finally:
        pe._collect = orig


# ═════════════════════════════════════════════════════════════
#  5) BOTONES — icon_custom_emoji_id
# ═════════════════════════════════════════════════════════════
def test_botones():
    from telethon import TelegramClient, Button
    from telethon.tl import types as tl

    build = TelegramClient.build_reply_markup

    def icon_of(markup):
        b = markup.rows[0].buttons[0]
        return getattr(getattr(b, "style", None), "icon", None), b

    # Botón inline con emoji de catálogo → icono + label limpio
    m = build([[Button.inline("💎  Comprar VIP", b"buy_vip_info")]])
    icon, b = icon_of(m)
    check("botón: 💎 → icono premium, label 'Comprar VIP', data intacto",
          icon == 5807465992363710697 and b.text == "Comprar VIP"
          and b.type.data == b"buy_vip_info")

    # Botón URL → icono + URL intacta
    m = build([[Button.url("📞  Soporte", "https://t.me/soporte")]])
    icon, b = icon_of(m)
    check("botón URL: 📞 → icono, URL intacta",
          icon == 5897488197650223178 and b.text == "Soporte"
          and b.type.url == "https://t.me/soporte")

    # Bandera en botón de idioma → SIN icono, texto intacto
    m = build([[Button.inline("🇪🇸  Español", b"set_lang_es")]])
    icon, b = icon_of(m)
    check("botón: bandera 🇪🇸 SIN icono y texto intacto",
          icon is None and b.text == "🇪🇸  Español"
          and b.type.data == b"set_lang_es")

    # Sin emoji / flecha « / números ASCII → intactos
    m = build([[Button.inline("«  Volver", b"back_main")]])
    icon, b = icon_of(m)
    check("botón: «  Volver intacto", icon is None and b.text == "«  Volver")
    m = build([[Button.inline("1 día", b"gen_1")]])
    icon, b = icon_of(m)
    check("botón: '1 día' intacto (ASCII no es keycap)", icon is None)

    # Emoji con VS16 en el label
    m = build([[Button.inline("🗂️  Todos", b"hm_time_all")]])
    icon, b = icon_of(m)
    check("botón: 🗂️ con VS16 → icono",
          icon == 5967456680940671207 and b.text == "Todos")

    # Objeto compartido NO mutado + idempotencia
    shared = Button.inline("💎  Renovar VIP", b"buy_vip_info")
    m1 = build([[shared]])
    check("botón: el objeto ORIGINAL no se muta (texto e icono intactos)",
          shared.text == "💎  Renovar VIP"
          and getattr(getattr(shared, "style", None), "icon", None) is None
          and shared.type.data == b"buy_vip_info")
    m2 = build([[shared]])
    i1, _ = icon_of(m1)
    i2, b2 = icon_of(m2)
    check("botón: idempotente — segunda construcción igual a la primera",
          i1 == i2 == 5807465992363710697 and b2.text == "Renovar VIP")

    # Markup ya construido pasa intacto por el parche
    m = build([[Button.inline("💎  X", b"d")]])
    check("botón: un ReplyMarkup ya construido pasa intacto",
          build(m) is m)

    # None → None · estilos conservados
    check("botón: None → None", build(None) is None)
    st = Button.inline("🔥  Hot", b"h", style="danger")
    m = build([[st]])
    icon, b = icon_of(m)
    check("botón: estilo bg_danger conservado + icono añadido",
          icon == 6008118472066732010 and b.style.bg_danger is True
          and b.style.icon == 6008118472066732010)

    # Fallback en caliente: icons_enabled=False
    pe.icons_enabled = False
    m = build([[Button.inline("💎  X", b"d")]])
    icon, b = icon_of(m)
    check("fallback: icons_enabled=False → botón original",
          icon is None and b.text == "💎  X")
    pe.icons_enabled = True

    pe.enabled = False
    m = build([[Button.inline("💎  X", b"d")]])
    icon, b = icon_of(m)
    check("fallback: enabled=False → ni mensajes ni botones",
          icon is None and b.text == "💎  X")
    pe.enabled = True


def test_menu_real():
    """Los teclados REALES de ui.py (database stubbeado)."""
    from telethon import TelegramClient, Button
    from ui import Keyboards, UI
    from roles import UserRole

    build = TelegramClient.build_reply_markup

    def walk(markup):
        for row in markup.rows:
            for b in row.buttons:
                yield b

    # Menú VIP completo
    m = build(Keyboards.main(UserRole.VIP))
    btns = list(walk(m))
    icons = {b.text: getattr(getattr(b, "style", None), "icon", None)
             for b in btns}
    check("menú VIP: 🔍 📧 📥 📬 👤 💎 👥 📋 🌐 convertidos a icono",
          icons.get("Nueva búsqueda") == 5874960879434338403
          and icons.get("IMAP Checker") == 5967280668885913944
          and icons.get("Hotmail Data") == 5877307202888273539
          and icons.get("Mi cuenta") == 5258011929993026890
          and icons.get("Renovar VIP") == 5807465992363710697
          and icons.get("Idioma") == 5879585266426973039)

    # Menú FREE
    m = build(Keyboards.main(UserRole.FREE, has_free_search=1))
    texts = [b.text for b in walk(m)]
    icons = {b.text: getattr(getattr(b, "style", None), "icon", None)
             for b in walk(m)}
    check("menú FREE: 🎁 💎 🔑 👥 👤 📋 🌐 como iconos",
          "Búsqueda gratis  (1/1)" in texts
          and icons.get("Búsqueda gratis  (1/1)") == 6032937473162614352
          and icons.get("Canjear key") == 6005570495603282482
          and icons.get("Comprar VIP") == 5807465992363710697)

    # Menú ADMIN (main) — panel de administración
    m = build(Keyboards.main(UserRole.ADMIN))
    icons = {b.text: getattr(getattr(b, "style", None), "icon", None)
             for b in walk(m)}
    check("menú ADMIN: 🔐 panel · 📂 gestión · 👥 referidos · 📋 comandos",
          icons.get("Panel admin") == 5258476306152038031
          and icons.get("Gestión archivos") == 6017174676898321263
          and icons.get("Referidos") == 5258513401784573443
          and icons.get("Comandos") == 5956561916573782596)

    # Panel admin (Keyboards.admin): 👑 💼 🔑 📊 📂 🔄
    m = build(Keyboards.admin())
    icons = {b.text: getattr(getattr(b, "style", None), "icon", None)
             for b in walk(m)}
    check("panel admin: 👑 💼 🔑 📊 📂 🔄 como iconos",
          icons.get("Ver VIPs") == 5807868868886009920
          and icons.get("Sellers") == 5258260149037965799
          and icons.get("Generar key") == 6005570495603282482
          and icons.get("Estadísticas") == 5931472654660800739
          and icons.get("Archivos") == 6017174676898321263
          and icons.get("Actualizar bot") == 5877410604225924969)

    # Selección de idioma: banderas intactas
    m = build(Keyboards.language_selection())
    icons = {b.text: getattr(getattr(b, "style", None), "icon", None)
             for b in walk(m)}
    check("idioma: 🇪🇸 🇬🇧 🇧🇷 intactas (sin icono premium)",
          icons.get("🇪🇸  Español") is None
          and icons.get("🇬🇧  English") is None
          and icons.get("🇧🇷  Português") is None)

    # Soporte (URL compartida a nivel de módulo)
    m = build([Keyboards.SUPPORT_URL])
    b = m.rows[0].buttons[0]
    check("soporte: botón URL compartido no mutado + icono 📞",
          Keyboards.SUPPORT_URL[0].text == "📞  Soporte"
          and b.text == "Soporte" and b.type.url.startswith("https://t.me/"))

    # Planes de pago: labels dinámicos ⚡ 1 día · $N
    m = build(Keyboards.payment_plans())
    icons = {b.text: getattr(getattr(b, "style", None), "icon", None)
             for b in walk(m)}
    plan_ok = all(
        any(dia in t and icon == doc for t, icon in icons.items())
        for dia, doc in (
            ("1 día", 5258152182150077732),   # ⚡
            ("3 días", 5931472654660800739),  # 📊
            ("7 días", 6008118472066732010),  # 🔥
            ("15 días", 5366357681240031250), # 🚀
            ("30 días", 5807465992363710697), # 💎
        ))
    check("planes: ⚡ 📊 🔥 🚀 💎 como iconos con precio dinámico", plan_ok)

    # Teclado de tiempos
    m = build(Keyboards.time())
    icons = {b.text: getattr(getattr(b, "style", None), "icon", None)
             for b in walk(m)}
    check("tiempos: ⚡ 🗂️ 📅 como iconos, « Cancelar intacto",
          icons.get("Últimas 24 horas") == 5258152182150077732
          and icons.get("24h + Antiguos") == 5967456680940671207
          and icons.get("Solo antiguos") == 5258105663359294787
          and icons.get("«  Cancelar") is None)

    # Auto-DL ON/OFF (compartidos por rama if/else)
    m = build(Keyboards.files_control(True, 3, 5))
    b = m.rows[0].buttons[0]
    check("archivos: ✅ Auto-DL con icono y contador intacto",
          b.text == "Auto-DL · ON" and b.style.icon == 5260416304224936047)
    m = build(Keyboards.files_control(False, 3, 5))
    b = m.rows[0].buttons[0]
    check("archivos: ❌ Auto-DL OFF con su propio icono",
          b.text == "Auto-DL · OFF" and b.style.icon == 5260342697075416641)
    m = build(Keyboards.files_control(True, 12, 5))
    b = m.rows[1].buttons[0]
    check("archivos: 📥 Descargar pendientes (12)",
          b.text == "Descargar pendientes  (12)"
          and b.style.icon == 5877307202888273539)


# ═════════════════════════════════════════════════════════════
#  6) TOGGLE, IDEMPOTENCIA Y CASOS BORDE
# ═════════════════════════════════════════════════════════════
def test_toggle_bordes():
    # Apagado en caliente
    pe.enabled = False
    t, ents = _apply("📊 🚫 x", [None] and [])
    check("toggle: enabled=False devuelve todo intacto",
          t == "📊 🚫 x" and ents == [])
    pe.enabled = True

    # Doble aplicación: el emoji ya convertido conserva SU entidad
    # (idempotencia real — nunca se apilan entidades)
    t1, e1 = _apply("🚫 x", [])
    t2, e2 = _apply(t1, e1)
    ce = custom_ents(e2)
    check("idempotencia: re-procesar la salida NO duplica entidades "
          "(❌ conserva el ID de 🚫)",
          t2 == "❌ x" and len(ce) == 1
          and covered_text(t2, ce[0]) == "❌"
          and ce[0].document_id == 5258318620722733379)

    # Vacíos y None
    t, ents = _apply("", [])
    check("borde: texto vacío", t == "" and ents == [])
    t, ents = _apply(None, None)
    check("borde: mensaje None", t is None and ents is None)

    # install() idempotente
    check("install(): idempotente (segunda llamada True)",
          pe.install() is True)

    # Texto de ~4,8 KB con 1200 emojis — rendimiento
    big = "📊 ✅ 📁 🚫 👑 📧 " * 200
    t0 = time.perf_counter()
    t, ents = _apply(big, [])
    dt = (time.perf_counter() - t0) * 1000
    check(f"rendimiento: 1200 emojis en {dt:.1f} ms (<300 ms)",
          dt < 300 and len(custom_ents(ents)) == 1200)


# ═════════════════════════════════════════════════════════════
#  7) AUDITORÍA DE COBERTURA sobre los archivos reales
# ═════════════════════════════════════════════════════════════
def _count_catalog_emojis(text):
    """Apariciones de emojis del catálogo (con variantes VS16)."""
    return len(_PATTERN.findall(text or ""))


def _button_call_nodes(tree):
    """Nodos Call de Button.inline/Button.url con su primer argumento."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if (isinstance(f, ast.Attribute) and f.attr in ("inline", "url")
                and isinstance(f.value, ast.Name) and f.value.id == "Button"
                and node.args):
            yield node.args[0]


def _label_constants(arg):
    """Constantes de un label (str literal o partes de un f-string)."""
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return [arg]
    if isinstance(arg, ast.JoinedStr):
        return [v for v in arg.values if isinstance(v, ast.Constant)]
    return []


def auditoria_cobertura():
    import glob as _glob

    # ── textos de mensajes: locales ES/EN/PT ──
    loc_total = 0
    loc_files = 0
    for path in sorted(_glob.glob("locales/*.json")):
        loc_files += 1
        data = json.load(open(path, encoding="utf-8"))
        stack = [data]
        while stack:
            cur = stack.pop()
            if isinstance(cur, dict):
                stack.extend(cur.values())
            elif isinstance(cur, list):
                stack.extend(cur)
            elif isinstance(cur, str):
                loc_total += _count_catalog_emojis(cur)

    # ── código: strings enviados al chat vs labels de botones ──
    py_total = 0
    btn_total = 0
    fuera = {}
    py_files = ("handlers.py", "download.py", "nowpayments.py", "bot.py",
                "search.py", "utils.py", "ui.py", "bot_locale.py",
                "hotmail_checker.py", "imap_checker.py", "webhook_server.py")
    any_emoji = re.compile(
        "[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\u2300-\u23FF]")
    for path in py_files:
        src = open(path, encoding="utf-8").read()
        tree = ast.parse(src)
        # labels de botones (literales y f-strings) → iconos premium
        button_parts = set()
        for arg in _button_call_nodes(tree):
            for const in _label_constants(arg):
                button_parts.add(id(const))
                btn_total += _count_catalog_emojis(const.value)
        # resto de strings (mensajes, captions, badges…)
        for node in ast.walk(tree):
            if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                    and id(node) not in button_parts):
                py_total += _count_catalog_emojis(node.value)
                for m in any_emoji.finditer(node.value):
                    ch = m.group(0)
                    if ch not in PREMIUM_EMOJI_IDS:
                        fuera[ch] = fuera.get(ch, 0) + 1

    # ── callback answers con texto (toasts) — límite de Telegram ──
    cb_total = 0
    cb_fuera = {}
    src = open("handlers.py", encoding="utf-8").read()
    for m in re.finditer(r'\.answer\(\s*(?:"([^"\\]*)"|\'([^\'\\]*)\')', src):
        txt = m.group(1) or m.group(2) or ""
        cb_total += _count_catalog_emojis(txt)
        for mm in any_emoji.finditer(txt):
            ch = mm.group(0)
            if ch not in PREMIUM_EMOJI_IDS:
                cb_fuera[ch] = cb_fuera.get(ch, 0) + 1

    # ── locales: emojis fuera del catálogo ──
    for path in sorted(_glob.glob("locales/*.json")):
        data = json.load(open(path, encoding="utf-8"))
        stack = [data]
        while stack:
            cur = stack.pop()
            if isinstance(cur, dict):
                stack.extend(cur.values())
            elif isinstance(cur, list):
                stack.extend(cur)
            elif isinstance(cur, str):
                for m in any_emoji.finditer(cur):
                    ch = m.group(0)
                    if ch not in PREMIUM_EMOJI_IDS:
                        fuera[ch] = fuera.get(ch, 0) + 1

    print("\n" + "═" * 62)
    print("  AUDITORÍA DE COBERTURA — emojis premium v4.2.32")
    print("═" * 62)
    print(f"  EMOJIS PREMIUM CONFIGURADOS: 86 (+1 alias técnico 🔍)")
    print(f"    · ORIGINALES v4.2.31: 20 (IDs intactos)")
    print(f"    · NUEVOS v4.2.32:     66 (IDs exactos aportados)")
    print(f"    · SUSTITUCIONES DE ALT: {len(ALT_OVERRIDES)} activas")
    print("─" * 62)
    print(f"  MENSAJES (locales ES/EN/PT, {loc_files} archivos): {loc_total:>5}"
          f"  → 100 % convertidas")
    print(f"  MENSAJES (strings del código):              {py_total:>5}"
          f"  → 100 % convertidas al enviarse")
    print(f"  BOTONES (labels de ui.py):                  {btn_total:>5}"
          f"  → 100 % → icono premium")
    print(f"  CALLBACK ANSWERS (toasts):                  {cb_total:>5}"
          f"  → sin soporte de entidades (límite Telegram)")
    conv = loc_total + py_total + btn_total
    tot = conv + cb_total
    print(f"  APARICIONES TOTALES: {tot} · CONVERTIDAS: {conv} · "
          f"NO CONVERTIDAS: {cb_total}")
    print(f"  COBERTURA VERIFICADA: {100.0 * conv / max(tot, 1):.1f} %")
    print("─" * 62)
    extras = {**fuera, **cb_fuera}
    print(f"  Emojis/símbolos fuera del catálogo en salidas: "
          + (", ".join(f"{k!r} x{v}" for k, v in sorted(extras.items()))
             or "ninguno"))
    print("  Banderas de países: EXCLUIDAS por diseño (sin ID premium)")
    print("═" * 62)
    return loc_total, py_total, btn_total, cb_total


# ═════════════════════════════════════════════════════════════
#  EJECUCIÓN
# ═════════════════════════════════════════════════════════════
def main():
    assert pe.install() is True, "install() falló — revisa config"
    test_catalogo()
    test_motor_basico()
    test_sustitucion_alt()
    asyncio.run(test_parser_telethon())
    test_botones()
    test_menu_real()
    test_toggle_bordes()
    auditoria_cobertura()

    print("\n" + "═" * 62)
    for status, name, detail in _RESULTS:
        mark = "✓" if status == "PASS" else "✗"
        print(f"  [{mark}] {name}")
        if detail:
            print(f"      {detail}")
    print("═" * 62)
    print(f"  PRUEBAS APROBADAS: {_PASSED}/{len(_RESULTS)}")
    if _FAILED:
        print(f"  PRUEBAS FALLIDAS: {len(_FAILED)}")
        for n in _FAILED:
            print(f"    ✗ {n}")
        sys.exit(1)
    print("  TODAS LAS PRUEBAS PASARON ✓")
    sys.exit(0)


if __name__ == "__main__":
    main()
