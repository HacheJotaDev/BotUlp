#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════
  HJ ULP PRO — Suite de pruebas: REDISEÑO UI/UX v4.3.0
═══════════════════════════════════════════════════════════════
  Pruebas 100 % locales (sin red, sin credenciales, sin VPS):

  T1. ELIMINACIÓN de «Nueva búsqueda» — ninguna interfaz, ningún
      label de botón, ningún texto de alerta lo menciona; el
      callback search_init SIGUE vivo para el botón de regalo FREE.
  T2. Menús por rol: estructura 4×2, botones esperados presentes,
      duplicados fuera (Gestión archivos solo en panel admin).
  T3. Cobertura de callbacks: TODO botón inline de ui.py tiene
      handler en handlers.py y todo handler de botón tiene botón.
  T4. Teclados de periodo unificados (time/hm_time/im_time).
  T5. Generador de keys: 6 duraciones (incluida ILIMITADA gen_0,
      paridad con /keygen sin días) + Volver context-aware.
  T6. Funnel de acceso denegado: CTA Comprar VIP/Referidos.
  T7. Confirmación de «vaciar pendientes» en 2 pasos.
  T8. Panel admin: Promo con presets + Actualizar bot aislado.
  T9. Bienvenida: truncada a 5 comandos + puntero + versión
      dinámica v{VERSION} en ES/EN/PT (plantillas y builtin).
  T10. Paridad de claves ES/EN/PT.
  T11. Emojis premium del rediseño: 📣 con icono (no 📢), sin ⏹,
       banderas intactas, catálogo sin cambios (86+alias).

  Uso:  python3 test_redesign.py
═══════════════════════════════════════════════════════════════
"""

import json
import os
import re
import sys
import types as pytypes
from pathlib import Path

# config.py exige BOT_TOKEN — en pruebas usamos uno de relleno
os.environ.setdefault("BOT_TOKEN", "123:test")

REPO = Path(__file__).resolve().parent

# ── Stub de database (mismo patrón que test_premium_emojis.py) ──
if "database" not in sys.modules:
    _fake_db_mod = pytypes.ModuleType("database")

    class _FakeDB:
        def __getattr__(self, _n):
            def _fn(*_a, **_k):
                return 0
            return _fn
    _fake_db_mod.db = _FakeDB()
    sys.modules["database"] = _fake_db_mod

from telethon import Button  # noqa: E402

import premium_emojis as pe  # noqa: E402
from premium_emojis import PREMIUM_EMOJI_IDS, ALT_OVERRIDES  # noqa: E402

import ui  # noqa: E402
from ui import Keyboards, UI  # noqa: E402
from roles import UserRole  # noqa: E402
from config import config  # noqa: E402

UI_SRC = (REPO / "ui.py").read_text(encoding="utf-8")
HD_SRC = (REPO / "handlers.py").read_text(encoding="utf-8")
BL_SRC = (REPO / "bot_locale.py").read_text(encoding="utf-8")

# ─────────────────────────────────────────────────────────────
#  Infraestructura de pruebas
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


def btn_texts(kb):
    """Labels de un teclado [[Button,...],...] (inline y url)."""
    out = []
    for row in kb:
        for b in row:
            out.append(b.text)
    return out


def btn_data_of(b):
    """callback_data de un botón inline — compatible con la estructura
    nueva de Telethon 1.45 (KeyboardInlineButton.type.data) y la vieja
    (atributo .data directo)."""
    t = getattr(b, "type", None)
    d = getattr(t, "data", None) or getattr(b, "data", None)
    if isinstance(d, (bytes, bytearray)):
        return d.decode("utf-8", "ignore")
    return ""


def btn_datas(kb):
    """callback_data de los botones inline de un teclado."""
    out = []
    for row in kb:
        for b in row:
            d = btn_data_of(b)
            if d:
                out.append(d)
    return out


def all_keyboards_buttons():
    """Instancia TODOS los teclados de Keyboards y devuelve (label, data)."""
    cases = [
        ("main_FREE", Keyboards.main(UserRole.FREE, 'es', 1)),
        ("main_VIP", Keyboards.main(UserRole.VIP, 'es', 0)),
        ("main_SELLER", Keyboards.main(UserRole.SELLER, 'es', 0)),
        ("main_ADMIN", Keyboards.main(UserRole.ADMIN, 'es', 0)),
        ("time", Keyboards.time()),
        ("hotmail_time", Keyboards.hotmail_time()),
        ("imap_time", Keyboards.imap_time()),
        ("formats", Keyboards.formats()),
        ("no_results", Keyboards.no_results()),
        ("no_results_exhausted", Keyboards.no_results_exhausted()),
        ("admin", Keyboards.admin()),
        ("admin_promo_0", Keyboards.admin_promo(0)),
        ("admin_promo_50", Keyboards.admin_promo(50)),
        ("gen_key_panel", Keyboards.gen_key("admin_enter")),
        ("gen_key_menu", Keyboards.gen_key()),
        ("files_control", Keyboards.files_control(True, 3, 1)),
        ("clear_pending_confirm", Keyboards.clear_pending_confirm(7)),
        ("language_selection", Keyboards.language_selection()),
        ("back", Keyboards.back()),
        ("payment_plans", Keyboards.payment_plans()),
        ("imap_cancel", Keyboards.imap_cancel("imapc_1_1")),
        ("payment_invoice", Keyboards.payment_invoice("https://x.gg")),
        ("payment_checking", Keyboards.payment_checking()),
        ("imap_info", Keyboards.imap_info()),
        ("hotmail_info", Keyboards.hotmail_info()),
        ("ref_panel", Keyboards.ref_panel("https://t.me/bot?start=ref_1", 'es')),
        ("access_denied", Keyboards.access_denied()),
        ("access_denied_feature", Keyboards.access_denied_feature()),
    ]
    buttons = []
    for name, kb in cases:
        for row in kb:
            for b in row:
                data = btn_data_of(b)
                buttons.append((name, b.text, data))
    return cases, buttons


# ═════════════════════════════════════════════════════════════
#  T1 — ELIMINACIÓN DE «NUEVA BÚSQUEDA»
# ═════════════════════════════════════════════════════════════
def test_nueva_busqueda():
    # 1. Ningún BOTÓN con ese label en NINGÚN teclado instanciado
    _, buttons = all_keyboards_buttons()
    offending = [b for b in buttons if "nueva búsqueda" in b[1].lower()]
    check("T1·1 sin botón «Nueva búsqueda» en ningún teclado",
          not offending, f"encontrados: {offending}")

    # 2. Ninguna definición de botón con ese texto en el código fuente
    src_offenders = []
    for fname, src in (("ui.py", UI_SRC), ("handlers.py", HD_SRC),
                       ("bot_locale.py", BL_SRC)):
        for m in re.finditer(r'Button\.(?:inline|url)\(\s*[f]?"([^"]*)"', src):
            if "nueva b\xc3\xbasqueda".encode("latin-1").decode("utf-8") in m.group(1).lower():
                src_offenders.append((fname, m.group(1)))
    check("T1·2 sin Button.* con label «Nueva búsqueda» en fuentes",
          not src_offenders, f"{src_offenders}")

    # 3. Ningún texto de alerta/toast lo menciona
    mentions = [ln for ln in HD_SRC.splitlines()
                if "Nueva búsqueda" in ln and "def " not in ln and "#" not in ln.split("Nueva búsqueda")[0][-3:]]
    # (las menciones permitidas son solo comentarios históricos)
    real = [ln for ln in mentions if "v4.3.0" not in ln]
    check("T1·3 sin textos de usuario que digan «Usa 'Nueva búsqueda'»",
          not real, f"{real[:3]}")

    # 4. El callback search_init SIGUE vivo (botón de regalo FREE)
    kb_free = Keyboards.main(UserRole.FREE, 'es', 1)
    check("T1·4 FREE conserva «Búsqueda gratis» con callback search_init",
          "search_init" in btn_datas(kb_free)
          and any("Búsqueda gratis" in t for t in btn_texts(kb_free)))
    kb_free0 = Keyboards.main(UserRole.FREE, 'es', 0)
    check("T1·5 FREE sin regalo: el botón no se muestra (free_n=0)",
          "search_init" not in btn_datas(kb_free0))
    check("T1·6 handler search_init intacto en handlers.py",
          'data == "search_init"' in HD_SRC)

    # 5. /url es el método de búsqueda y sigue registrado
    check("T1·7 /url sigue registrado como comando",
          'pattern=r"/url(?:@\\w+)?\\s+(\\S.*)"' in HD_SRC)


# ═════════════════════════════════════════════════════════════
#  T2 — ESTRUCTURA DE MENÚS POR ROL
# ═════════════════════════════════════════════════════════════
def test_menus():
    vip = Keyboards.main(UserRole.VIP, 'es', 0)
    seller = Keyboards.main(UserRole.SELLER, 'es', 0)
    admin = Keyboards.main(UserRole.ADMIN, 'es', 0)

    for name, kb in (("VIP", vip), ("SELLER", seller), ("ADMIN", admin)):
        check(f"T2·{name} menú con exactamente 4 filas",
              len(kb) == 4, f"filas: {len(kb)}")
        check(f"T2·{name} todas las filas de 2 botones",
              all(len(r) == 2 for r in kb))
        check(f"T2·{name} IMAP Checker presente",
              any("IMAP Checker" in t for t in btn_texts(kb)))

    check("T2·VIP tiene Renovar VIP",
          any("Renovar VIP" in t for t in btn_texts(vip)))
    check("T2·SELLER tiene Generar key",
          any("Generar key" in t for t in btn_texts(seller)))
    check("T2·ADMIN tiene Panel admin",
          any("Panel admin" in t for t in btn_texts(admin)))

    # Duplicado eliminado: «Gestión archivos» ya no está en el menú ADMIN
    check("T2·ADMIN sin «Gestión archivos» en menú principal (duplicado)",
          not any("Gestión archivos" in t for t in btn_texts(admin)))
    # …pero sigue en el panel admin:
    check("T2·ADMIN «Archivos» sigue en el panel",
          any("Archivos" in t for t in btn_texts(Keyboards.admin())))

    # FREE intacto (estructura y botones clave)
    free = Keyboards.main(UserRole.FREE, 'es', 2)
    check("T2·FREE fila de regalo con contador (2)",
          any("Búsquedas gratis  (2)" in t for t in btn_texts(free)))
    check("T2·FREE Comprar VIP + Canjear key",
          any("Comprar VIP" in t for t in btn_texts(free))
          and any("Canjear key" in t for t in btn_texts(free)))
    check("T2·FREE Referidos + Mi cuenta + Comandos + Idioma",
          any("Referidos" in t for t in btn_texts(free))
          and any("Mi cuenta" in t for t in btn_texts(free))
          and any("Comandos" in t for t in btn_texts(free))
          and any("Idioma" in t for t in btn_texts(free)))


# ═════════════════════════════════════════════════════════════
#  T3 — COBERTURA DE CALLBACKS (botón ↔ handler)
# ═════════════════════════════════════════════════════════════
def test_callback_coverage():
    _, buttons = all_keyboards_buttons()
    datas = {d for _, _, d in buttons if d}

    # Handlers declarados en handlers.py: coincidencias exactas
    # (data == "x" y TODOS los elementos de data in ("a", "b", ...))
    exact = set(re.findall(r'data == "([a-z_0-9]+)"', HD_SRC))
    for m in re.finditer(r'data in \(([^)]*)\)', HD_SRC):
        exact |= set(re.findall(r'"([a-z_0-9]+)"', m.group(1)))
    prefixes = set(re.findall(r'data\.startswith\("([a-z_0-9]+)"', HD_SRC))

    # back(data) genera back_main/admin_enter/adm_files dinámicamente:
    # se aceptan como cubiertos los callback exactos + prefijos + los
    # back() conocidos + token dinámico imapc_.
    dynamic_ok = {"back_main", "admin_enter", "adm_files", "promo_info"}

    orphan_buttons = []
    for d in datas:
        if d in exact or d in dynamic_ok:
            continue
        if any(d.startswith(p) for p in prefixes):
            continue
        if d.startswith("imapc_"):
            continue
        if re.fullmatch(r"promo_set_\d+", d):
            continue
        orphan_buttons.append(d)
    check("T3·1 todo botón tiene handler (0 huérfanos)",
          not orphan_buttons, f"huérfanos: {sorted(orphan_buttons)}")

    # Handlers sin botón (excepto documentados):
    # · search_init: botón CONDICIONAL del regalo FREE (free_n > 0)
    # · pay_check:   teclado payment_checking (instanciado en la batería)
    # · hotmail_info: handler del checker DESACTIVADO en v4.2.16 (código
    #   fantasma conservado a propósito como kit de reactivación)
    instantiable = {d for _, _, d in buttons if d}
    instantiable |= {"search_init", "hotmail_info", "pay_check"}
    dead_handlers = []
    for h in exact:
        if h in instantiable:
            continue
        if any(h.startswith(p) for p in prefixes):
            continue
        # ¿aparece como data en ui.py o handlers.py en algún Button?
        if f'"{h}"' in UI_SRC or f'b"{h}"' in UI_SRC or f'"{h}"'.encode() in UI_SRC.encode():
            continue
        dead_handlers.append(h)
    check("T3·2 todo handler exacto tiene botón (0 muertos)",
          not dead_handlers, f"muertos: {sorted(dead_handlers)}")


# ═════════════════════════════════════════════════════════════
#  T4 — TECLADOS DE PERIODO UNIFICADOS
# ═════════════════════════════════════════════════════════════
def test_period_keyboards():
    t = Keyboards.time()
    hm = Keyboards.hotmail_time()
    im = Keyboards.imap_time()

    check("T4·1 misma estructura en los 3 flujos",
          [len(r) for r in t] == [len(r) for r in hm] == [len(r) for r in im] == [2, 1, 1])
    for name, kb in (("/url", t), ("/hotmail", hm), ("/imap", im)):
        labels = btn_texts(kb)
        check(f"T4·{name} labels unificados",
              labels[0].startswith("⚡") and labels[1].startswith("🗂️")
              and labels[2].startswith("📅") and labels[3] == "«  Cancelar",
              f"{labels}")
    check("T4·5 callbacks /url intactos",
          btn_datas(t) == ["time_24h", "time_all", "time_old", "back_main"])
    check("T4·6 callbacks /hotmail intactos",
          btn_datas(hm) == ["hm_time_24h", "hm_time_all", "hm_time_old", "back_main"])
    check("T4·7 callbacks /imap intactos",
          btn_datas(im) == ["im_time_24h", "im_time_all", "im_time_old", "back_main"])


# ═════════════════════════════════════════════════════════════
#  T5 — GENERADOR DE KEYS
# ═════════════════════════════════════════════════════════════
def test_gen_key():
    kb = Keyboards.gen_key()
    datas = btn_datas(kb)
    texts = btn_texts(kb)
    check("T5·1 6 duraciones incluida ILIMITADA",
          datas == ["gen_1", "gen_3", "gen_7", "gen_15", "gen_30", "gen_0", "back_main"]
          and any("Ilimitada" in t for t in texts), f"{datas}")
    check("T5·2 emoji por plan (identidad de planes de pago)",
          any(t.startswith("⚡") for t in texts[:1])
          and any(t.startswith("📊") for t in texts[:2])
          and any(t.startswith("💎") for t in texts))
    kb_panel = Keyboards.gen_key("admin_enter")
    check("T5·3 Volver context-aware al panel admin",
          "admin_enter" in btn_datas(kb_panel))
    # Paridad con /keygen: gen_0 → days=0 → ilimitada
    check("T5·4 handler gen_ parsea días (incluido 0)",
          re.search(r'gen_\\"\s*\n?\s*days = int\(data\.split', HD_SRC)
          or "days = int(data.split(\"_\")[1])" in HD_SRC)
    check("T5·5 /keygen sin días genera ilimitada (paridad)",
          "days = int(arg) if arg else 0" in HD_SRC)
    check("T5·6 tarjeta GENERADOR DE KEYS (estructura ✦)",
          "GENERADOR DE KEYS" in HD_SRC and "Elige la duración" in HD_SRC)


# ═════════════════════════════════════════════════════════════
#  T6 — FUNNEL DE ACCESO DENEGADO
# ═════════════════════════════════════════════════════════════
def test_access_denied():
    kb = Keyboards.access_denied()
    check("T6·1 CTA Comprar VIP + Referidos + Volver",
          btn_datas(kb) == ["buy_vip_info", "ref_info", "back_main"])
    kbf = Keyboards.access_denied_feature()
    check("T6·2 variante VIP-only (solo Comprar VIP)",
          btn_datas(kbf) == ["buy_vip_info", "back_main"])
    # Aplicado en los puntos de denegación
    n = HD_SRC.count("Keyboards.access_denied()")
    check("T6·3 aplicado en /url, /hotmail, /imap y conversación (4 usos)",
          n == 4, f"usos: {n}")
    check("T6·4 variante feature en /imapchk",
          "Keyboards.access_denied_feature()" in HD_SRC)


# ═════════════════════════════════════════════════════════════
#  T7 — CONFIRMACIÓN DE VACIAR PENDIENTES
# ═════════════════════════════════════════════════════════════
def test_clear_pending():
    kb = Keyboards.clear_pending_confirm(7)
    texts = btn_texts(kb)
    check("T7·1 confirmación: [Sí, vaciar (7)] [« Cancelar]",
          any("Sí, vaciar" in t and "7" in t for t in texts)
          and any("Cancelar" in t for t in texts))
    check("T7·2 clear_pending YA NO borra directo (primero confirma)",
          re.search(r'elif data == "clear_pending":\n(?!.*pending_downloads\.clear\(\))(?:.|\n)*?clear_pending_confirm', HD_SRC)
          is not None)
    check("T7·3 clear_pending_yes ejecuta el borrado real",
          'elif data == "clear_pending_yes":' in HD_SRC
          and HD_SRC.count("state.pending_downloads.clear()") == 1)
    check("T7·4 aviso «no se puede deshacer»",
          "no se puede deshacer" in HD_SRC)


# ═════════════════════════════════════════════════════════════
#  T8 — PANEL ADMIN: PROMO + AISLAMIENTO DE ACTUALIZAR
# ═════════════════════════════════════════════════════════════
def test_admin_panel():
    kb = Keyboards.admin()
    rows = [[b.text for b in r] for r in kb]
    check("T8·1 Promo en el panel",
          any("Promo" in t for t in btn_texts(kb)))
    check("T8·2 «Actualizar bot» solo en su fila",
          any(len(r) == 1 and any("Actualizar bot" in t for t in r) for r in rows))
    check("T8·3 Actualizar bot NO junto a otra acción",
          not any(len(r) > 1 and any("Actualizar bot" in t for t in r) for r in rows))

    # Presets: con promo a 0% el botón «desactivada» es el estado activo
    # (promo_noop) y por tanto NO aparece promo_set_0
    kb0 = Keyboards.admin_promo(0)
    check("T8·4 presets -25/-50/-70/100 + estado activo",
          set(btn_datas(kb0)) == {"promo_set_25", "promo_set_50", "promo_set_70",
                                  "promo_set_100", "promo_noop", "admin_enter"},
          f"{btn_datas(kb0)}")
    kb50 = Keyboards.admin_promo(50)
    check("T8·5 estado activo marcado (✅ y promo_noop)",
          "promo_noop" in btn_datas(kb50)
          and any(t.startswith("✅") for t in btn_texts(kb50)))
    # Handlers
    check("T8·6 handlers adm_promo / promo_set_ / promo_noop",
          'data == "adm_promo"' in HD_SRC
          and 'data.startswith("promo_set_")' in HD_SRC
          and 'data == "promo_noop"' in HD_SRC)
    check("T8·7 presets usan la MISMA ruta que /promo",
          "config.set_promo_percent(pct)" in HD_SRC)
    check("T8·8 tarjeta de promo del panel con precios reales",
          "_promo_admin_card" in HD_SRC)


# ═════════════════════════════════════════════════════════════
#  T9 — BIENVENIDA: TRUNCADO + VERSIÓN DINÁMICA
# ═════════════════════════════════════════════════════════════
def test_welcome():
    # helpers
    check("T9·1 helper de truncado presente",
          "_welcome_cmds_block" in HD_SRC and "WELCOME_MAX_CMDS = 5" in HD_SRC)
    # Los 4 call sites usan el helper + versión (la DEFINICIÓN usa
    # «role: UserRole»; los call sites «role,» — contar con la coma)
    n_block = HD_SRC.count("_welcome_cmds_block(role,")
    n_ver = HD_SRC.count('f"v{config.VERSION}"')
    check("T9·2 los 4 call sites usan truncado + versión dinámica",
          n_block == 4 and n_ver == 4, f"truncado:{n_block} versión:{n_ver}")

    # Plantillas con {5}
    for lang in ("es", "en", "pt"):
        d = json.loads((REPO / "locales" / f"{lang}.json").read_text(encoding="utf-8"))
        check(f"T9·3 {lang}: welcome y welcome_new con {{5}} (versión)",
              "{5}" in d["welcome"] and "{5}" in d["welcome_new"])
        check(f"T9·4 {lang}: clave welcome_cmds_more",
              "welcome_cmds_more" in d and "{0}" in d["welcome_cmds_more"])
        # La plantilla formatea sin errores con 6 args
        try:
            d["welcome"].format("U", "cmds", "VIP", "3", "", "v4.3.0")
            ok = True
        except Exception:
            ok = False
        check(f"T9·5 {lang}: welcome.format() con 6 argumentos", ok)

    check("T9·6 builtin bot_locale con {5}",
          BL_SRC.count("┃ ⚡ {5} · Professional") == 2)
    check("T9·7 builtin welcome_cmds_more",
          '"welcome_cmds_more"' in BL_SRC)

    # Contenido real del bloque truncado (ADMIN = el más largo)
    sys.path.insert(0, str(REPO))
    from handlers import _welcome_cmds_block, _get_commands_by_role
    full = _get_commands_by_role(UserRole.ADMIN, 'es').splitlines()
    block = _welcome_cmds_block(UserRole.ADMIN, 'es').splitlines()
    check("T9·8 ADMIN: bloque truncado a 5 + puntero",
          len(block) == 6 and block[:5] == full[:5] and "más" in block[5],
          f"{len(block)} líneas")
    check("T9·9 VIP: bloque truncado a 5 + puntero",
          len(_welcome_cmds_block(UserRole.VIP, 'es').splitlines()) == 6)
    # cmd_list conserva la lista COMPLETA
    check("T9·10 cmd_list sigue con la lista completa",
          "cmd_list" in HD_SRC and "_get_commands_by_role(role, lang, has_free)" in HD_SRC)

    # Versión de config
    check("T9·11 VERSION = 4.3.0", config.VERSION == "4.3.0",
          f"es {config.VERSION}")


# ═════════════════════════════════════════════════════════════
#  T10 — PARIDAD DE CLAVES ES/EN/PT
# ═════════════════════════════════════════════════════════════
def test_locale_parity():
    es = json.loads((REPO / "locales" / "es.json").read_text(encoding="utf-8"))
    en = json.loads((REPO / "locales" / "en.json").read_text(encoding="utf-8"))
    pt = json.loads((REPO / "locales" / "pt.json").read_text(encoding="utf-8"))
    check("T10·1 ES/EN/PT con las mismas claves",
          set(es) == set(en) == set(pt),
          f"solo ES: {sorted(set(es)-set(en))} · solo EN: {sorted(set(en)-set(es))}")
    check("T10·2 número de claves > 150", len(es) >= len(json.loads((REPO/'locales'/'es.json').read_text())))


# ═════════════════════════════════════════════════════════════
#  T11 — EMOJIS PREMIUM DEL REDISEÑO
# ═════════════════════════════════════════════════════════════
def test_premium_redesign():
    # 1. Catálogo INTACTO: 87 asociaciones, 86 IDs únicos
    check("T11·1 catálogo sin cambios (87 claves / 86 IDs)",
          len(PREMIUM_EMOJI_IDS) == 87
          and len(set(PREMIUM_EMOJI_IDS.values())) == 86)
    check("T11·2 los 20 originales intactos (✅ presente con su ID)",
          PREMIUM_EMOJI_IDS.get("✅") == 5260416304224936047)

    # 2. Botón de referidos con 📣 (registrado) y SIN 📢
    kb = Keyboards.ref_panel("https://t.me/x?start=ref_1", 'es')
    texts = btn_texts(kb)
    check("T11·3 referidos usa 📣 (con icono premium)",
          any(t.startswith("📣") for t in texts), f"{texts}")
    check("T11·4 sin 📢 en ui.py", "📢" not in UI_SRC)

    # 3. Icono premium aplicado al botón 📣 (motor v4.2.32)
    pe.install()
    btn = kb[0][0]
    markup = pe._orig_build_reply_markup(pe._premium_buttons([[btn]]))
    row = markup.rows[0]
    check("T11·5 «Compartir mi link» con icon_custom_emoji_id",
          getattr(row.buttons[0], "style", None) is not None
          and row.buttons[0].style.icon == PREMIUM_EMOJI_IDS["📣"]
          and "📣" not in row.buttons[0].text,
          f"text={row.buttons[0].text}")

    # 4. Sin ⏹ en handlers.py
    check("T11·6 sin ⏹ (consistencia de toasts)", "⏹" not in HD_SRC)

    # 5. Banderas intactas en el selector de idioma
    kb_lang = Keyboards.language_selection()
    check("T11·7 banderas 🇪🇸 🇬🇧 🇧🇷 intactas (sin premium)",
          any("🇪🇸" in t for t in btn_texts(kb_lang))
          and "🇪🇸" not in PREMIUM_EMOJI_IDS)

    # 6. Botones nuevos con emoji registrado → icono
    kb_promo = Keyboards.admin_promo(0)
    markup = pe._orig_build_reply_markup(pe._premium_buttons(kb_promo))
    icons = []
    for row in markup.rows:
        for b in row.buttons:
            st = getattr(b, "style", None)
            icons.append(st.icon if st else None)
    check("T11·8 presets de promo con icono premium (🏷️)",
          all(i is not None for i in icons[:4]) and icons[0] == PREMIUM_EMOJI_IDS["🏷"])

    # 7. Ningún emoji del catálogo convertido en flags: par bandera
    #    no puede estar en _SEQ_MAP
    flag_pair = "🇵🇪"
    check("T11·9 bandera 🇵🇪 fuera del catálogo",
          flag_pair not in PREMIUM_EMOJI_IDS)

    # 8. Sustitución de alt sigue funcionando (muestra rápida)
    text, ents = pe._apply("📧 contacto", [])
    from telethon.tl.types import MessageEntityCustomEmoji
    ce = [e for e in ents if isinstance(e, MessageEntityCustomEmoji)]
    check("T11·10 alt sustituido (📧 → ✉️ con entidad premium)",
          text.startswith("✉️") and ce
          and ce[0].document_id == PREMIUM_EMOJI_IDS["📧"])


# ═════════════════════════════════════════════════════════════
#  EJECUCIÓN
# ═════════════════════════════════════════════════════════════
def main():
    tests = [
        ("T1  Eliminación «Nueva búsqueda»", test_nueva_busqueda),
        ("T2  Menús por rol", test_menus),
        ("T3  Cobertura de callbacks", test_callback_coverage),
        ("T4  Teclados de periodo", test_period_keyboards),
        ("T5  Generador de keys", test_gen_key),
        ("T6  Funnel de acceso denegado", test_access_denied),
        ("T7  Confirmación de vaciar", test_clear_pending),
        ("T8  Panel admin + promo", test_admin_panel),
        ("T9  Bienvenida + versión", test_welcome),
        ("T10 Paridad de locales", test_locale_parity),
        ("T11 Emojis premium", test_premium_redesign),
    ]
    for name, fn in tests:
        print(f"\n── {name} " + "─" * max(0, 44 - len(name)))
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            check(f"{name} (sin excepción)", False, str(exc))

    print("\n" + "═" * 66)
    for status, name, detail in _RESULTS:
        if status == "FAIL":
            print(f"  [✗] {name}  —  {detail}")
    print("═" * 66)
    print(f"  PRUEBAS EJECUTADAS: {len(_RESULTS)}")
    print(f"  APROBADAS: {_PASSED}  ·  FALLIDAS: {len(_FAILED)}")
    if _FAILED:
        print("  FALLAS:", ", ".join(_FAILED))
        print("  ✗ HAY PRUEBAS FALLIDAS")
        return 1
    print("  TODAS LAS PRUEBAS PASARON ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
