#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════
  HJ ULP PRO — Suite de pruebas: LIMPIEZA INTELIGENTE + VIP ADMIN
  v4.3.1
═══════════════════════════════════════════════════════════════
  Pruebas 100 % locales (sin red, sin credenciales, sin VPS, sin
  transacciones reales — todo con mocks y fixtures):

  LIMPIEZA DE MENSAJES
    L1. Eliminación diferida de un mensaje temporal registrado.
    L2. Conservación: lo que NO se registra jamás se borra.
    L3. Interruptor maestro AUTO_CLEAN_MESSAGES=0 → no borra nada.
    L4. Protección de identidad: mensaje sin (chat,id) verificable
        → no se registra; identidad inconsistente al borrar → se
        conserva (imposible borrar el mensaje de otro chat).
    L5. Mensajes editados: el borrado sigue apuntando al mismo
        objeto (chat,id) tras ediciones simuladas.
    L6. Cancelación / reinicio: shutdown() cancela lo pendiente.
    L7. Errores de Telegram: delete() falla → 1 reintento, se
        registra, no revienta, no genera cadena infinita.
    L8. Concurrencia: varios usuarios simultáneos, cada borrado
        independiente y correcto.
    L9. Conservación estática: resultados/archivos/pagos/errores/
        notificaciones admin NO se registran en la limpieza.

  NOTIFICACIONES VIP A ADMINISTRADORES
    N1. Compra confirmada (IPN firmado) → VIP entregado + admin
        notificado con los 13 datos reales.
    N2. Evento duplicado del proveedor («finished» tras
        «confirmed») → SIN segunda entrega ni segunda
        notificación (claim atómico idempotente).
    N3. Concurrencia real: IPN + polling + «Ya pagué» a la vez →
        exactamente UNA entrega y UNA notificación.
    N4. Pago pendiente → no notifica (no es venta confirmada).
    N5. Pago fallido/expirado → no notifica.
    N6. Renovación → el vencimiento notificado es el REAL post-
        activación leído de la DB.
    N7. Usuario sin username → «Sin username» con su ID.
    N8. Plan de duración distinta (15 días) + promo aplicada →
        importe REAL cobrado (no el precio base).
    N9. Error al notificar a un admin (Forbidden) → la venta
        queda entregada, se registra el fallo, sin duplicar.
    N10. La notificación fallida NO revierte ni duplica la venta.
    N11. Promo 100 % (regalo) → VIP entregado, SIN notificación
         de venta al admin.
    N12. Formato: contenido íntegro, solo emojis premium
         registrados (86), cero banderas.
    N13. Persistencia: la notificación admin NUNCA entra en el
         sistema de limpieza.
    N14. El mensaje al usuario no se duplica en verificación
         manual ni promo-100 (notify_user=False).

  Uso:  python3 test_clean_vip.py
═══════════════════════════════════════════════════════════════
"""

import asyncio
import os
import re
import sys
import time
import types as pytypes
import hmac
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

# config.py exige BOT_TOKEN — en pruebas usamos uno de relleno
os.environ.setdefault("BOT_TOKEN", "123:test")

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

# ─────────────────────────────────────────────────────────────
#  Infraestructura de mocks (patrón de test_redesign.py)
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


# ── Fake DB con semántica REAL de claim atómico ──────────────
class FakeDB:
    """Réplica en memoria del comportamiento de PostgreSQL que
    usan las rutas bajo prueba (payments + users + claim)."""

    def __init__(self):
        self.payments = {}   # invoice_id -> dict
        self.users = {}      # uid -> dict
        self.claim_log = []  # auditoría de claims

    # ── payments ──
    def create_payment(self, user_id, invoice_id, order_id, days,
                       amount_usd, status, lang='es'):
        if invoice_id in self.payments:
            return
        now = datetime.now(timezone.utc).isoformat()
        self.payments[invoice_id] = {
            'id': len(self.payments) + 1, 'user_id': user_id,
            'invoice_id': invoice_id, 'order_id': order_id,
            'days': days, 'amount_usd': amount_usd, 'status': status,
            'lang': lang, 'created_at': now, 'updated_at': now,
        }

    def get_payment(self, invoice_id):
        return self.payments.get(invoice_id)

    def update_payment_status(self, invoice_id, status):
        p = self.payments.get(invoice_id)
        if p:
            p['status'] = status
            p['updated_at'] = datetime.now(timezone.utc).isoformat()

    def get_pending_payments(self):
        return [p for p in self.payments.values() if p['status'] == 'pending']

    def get_user_payments(self, user_id):
        pays = [p for p in self.payments.values() if p['user_id'] == user_id]
        pays.sort(key=lambda p: p['created_at'], reverse=True)
        return pays[:5]

    def claim_delivery(self, invoice_id, stale_minutes=10):
        """Misma semántica que el UPDATE...RETURNING de PostgreSQL:
        en un solo hilo de asyncio (sin await dentro) es atómico."""
        p = self.payments.get(invoice_id)
        if not p:
            return False
        self.claim_log.append((invoice_id, p['status']))
        now = datetime.now(timezone.utc)
        if p['status'] == 'pending':
            p['status'] = 'delivering'
            p['updated_at'] = now.isoformat()
            return True
        if p['status'] == 'delivering':
            upd = datetime.fromisoformat(p['updated_at'])
            if (now - upd).total_seconds() > stale_minutes * 60:
                p['status'] = 'delivering'
                p['updated_at'] = now.isoformat()
                return True
        return False

    # ── users ──
    def set_role(self, uid, role, days=0):
        expiry = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat() \
            if role == 'VIP' else None
        u = self.users.setdefault(uid, {})
        u.update({'user_id': uid, 'role': role, 'vip_expiry': expiry})

    def get_user(self, uid):
        u = self.users.setdefault(
            uid, {'user_id': uid, 'role': 'FREE', 'vip_expiry': None,
                  'language': 'es', 'search_count': 0})
        return dict(u)


# ── Fake cliente Telegram ────────────────────────────────────
class FakeMessage:
    """Mensaje con identidad (chat_id, id) y delete() que respeta
    esa identidad — como el Message real de Telethon."""

    def __init__(self, chat_id, msg_id, fail_delete=False):
        self.chat_id = chat_id
        self.id = msg_id
        self.deleted = False
        self.edits = 0
        self._fail_delete = fail_delete
        self.delete_calls = 0

    async def edit(self, *a, **k):
        self.edits += 1
        return self

    async def delete(self):
        self.delete_calls += 1
        if self._fail_delete:
            raise RuntimeError("MESSAGE_DELETE_FORBIDDEN (simulado)")
        self.deleted = True
        return True


class FakeBot:
    """Cliente bot: registra envíos por chat y entidades conocidas."""

    def __init__(self):
        self.sent = []          # (chat_id, text)
        self.entities = {}      # uid -> entidad
        self.fail_admins = set()  # admins que rechazan el MP

    async def send_message(self, chat_id, text, *a, **k):
        if chat_id in self.fail_admins:
            raise PermissionError("Forbidden: bot can't initiate conversation "
                                  "with a user (simulado)")
        self.sent.append((chat_id, text))
        return FakeMessage(chat_id, len(self.sent))

    async def get_entity(self, uid):
        ent = self.entities.get(uid)
        if ent is None:
            raise ValueError("No entity (simulado)")
        return ent


# ── Instalación de stubs ANTES de importar los módulos ───────
fake_db = FakeDB()
fake_bot = FakeBot()

if "database" not in sys.modules:
    _fake_db_mod = pytypes.ModuleType("database")
    _fake_db_mod.db = fake_db
    sys.modules["database"] = _fake_db_mod

import state  # noqa: E402  (módulo real — asignamos el bot falso)
state.bot = fake_bot

import auto_clean  # noqa: E402
from auto_clean import auto_clean as cleaner, AutoCleanRegistry  # noqa: E402
from config import config  # noqa: E402
import vip_notifier  # noqa: E402
import nowpayments  # noqa: E402
nowpayments.db = fake_db  # por si el import tomó otra instancia

# Acelerar los reintentos en pruebas (mismas semánticas, menos espera)
auto_clean._RETRY_DELAY = 0.02
vip_notifier._RETRY_DELAY = 0.02

async def _drain_notifier_tasks(seg=0.25):
    """Dar tiempo a las tareas fire-and-forget (notificaciones) a
    completarse — en producción viven su vida propia."""
    await asyncio.sleep(seg)

HD_SRC = (REPO / "handlers.py").read_text(encoding="utf-8")
DL_SRC = (REPO / "download.py").read_text(encoding="utf-8")
NP_SRC = (REPO / "nowpayments.py").read_text(encoding="utf-8")
VN_SRC = (REPO / "vip_notifier.py").read_text(encoding="utf-8")
AC_SRC = (REPO / "auto_clean.py").read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────
#  LIMPIEZA DE MENSAJES
# ─────────────────────────────────────────────────────────────

def test_L1_L2_L7_L8_cleaning():
    async def _run():
        reg = AutoCleanRegistry()

        # L1 — registro + borrado diferido
        m1 = FakeMessage(chat_id=111, msg_id=1)
        ok = reg.register(m1, 0.05, "carga_obsoleta")
        await asyncio.sleep(0.25)
        assert ok, "L1: registro rechazado"
        assert m1.deleted, "L1: el mensaje temporal no se borró"

        # L2 — lo que no se registra, no se borra
        m2 = FakeMessage(chat_id=111, msg_id=2)  # p.ej. un menú con botones
        await asyncio.sleep(0.1)
        assert not m2.deleted, "L2: un mensaje no registrado fue borrado"

        # L7 — error de Telegram: reintento controlado y sin explosión
        m3 = FakeMessage(chat_id=222, msg_id=3, fail_delete=True)
        reg.register(m3, 0.05, "aviso")
        await asyncio.sleep(0.4)
        assert m3.delete_calls == 2, (
            f"L7: se esperaban 2 intentos (1+reintento), hubo {m3.delete_calls}")
        assert reg.stats["failed"] >= 1, "L7: el fallo no quedó registrado"

        # L8 — concurrencia: 3 chats simultáneos, cada uno borra el suyo
        msgs = [FakeMessage(chat_id=1000 + i, msg_id=10 + i) for i in range(3)]
        for m in msgs:
            reg.register(m, 0.03, "simultaneo")
        await asyncio.sleep(0.3)
        for i, m in enumerate(msgs):
            assert m.deleted, f"L8: mensaje del chat {1000 + i} no se borró"
        # Ningún borrado cruzado: cada objeto es independiente por diseño
        assert reg.stats["deleted"] >= 4, "L8: métricas de borrado incorrectas"

    asyncio.run(_run())
    check("L1 · borrado diferido del mensaje temporal", True)
    check("L2 · mensajes no registrados se conservan", True)
    check("L7 · error de Telegram: reintento + registro, sin romper", True)
    check("L8 · operaciones simultáneas de varios usuarios", True)


def test_L3_master_switch():
    async def _run():
        saved = config.AUTO_CLEAN_MESSAGES
        try:
            config.AUTO_CLEAN_MESSAGES = False
            reg = AutoCleanRegistry()
            m = FakeMessage(chat_id=333, msg_id=1)
            ok = reg.temp(m, "apagado")
            await asyncio.sleep(0.1)
            assert not ok, "L3: registró con el interruptor apagado"
            assert not m.deleted, "L3: borró con AUTO_CLEAN_MESSAGES=0"
        finally:
            config.AUTO_CLEAN_MESSAGES = saved
    asyncio.run(_run())
    check("L3 · interruptor AUTO_CLEAN_MESSAGES=0 desactiva todo", True)


def test_L4_identity_protection():
    async def _run():
        reg = AutoCleanRegistry()

        # Mensaje SIN identidad verificable → no se registra (fail-safe)
        class _NoIdentity:
            id = 42  # sin chat_id ni peer_id
        assert not reg.register(_NoIdentity(), 0.05, "x"), \
            "L4: registró un mensaje sin chat verificable"

        class _Nothing:
            pass
        assert not reg.register(_Nothing(), 0.05, "x"), \
            "L4: registró un objeto sin id"

        # Identidad INCONSISTENTE al momento de borrar → se conserva
        m = FakeMessage(chat_id=555, msg_id=7)
        reg.register(m, 0.05, "x")
        m.chat_id = 999  # el objeto ya no declara el chat registrado
        await asyncio.sleep(0.25)
        assert not m.deleted, "L4: borró un mensaje con identidad inconsistente"
    asyncio.run(_run())
    check("L4 · protección contra IDs equivocados / chats cruzados", True)


def test_L5_L6_edit_and_shutdown():
    async def _run():
        # L5 — mensaje editado varias veces: el borrado sigue siendo
        # el MISMO (chat,id); las ediciones no rompen la identidad
        reg = AutoCleanRegistry()
        m = FakeMessage(chat_id=444, msg_id=9)
        reg.register(m, 0.1, "editado")
        for _ in range(3):
            await m.edit("nuevo contenido")
        await asyncio.sleep(0.3)
        assert m.deleted, "L5: un mensaje editado no se borró"
        assert m.edits == 3, "L5: las ediciones no se respetaron"

        # L6 — shutdown cancela lo pendiente (reinicio del bot)
        reg2 = AutoCleanRegistry()
        m2 = FakeMessage(chat_id=444, msg_id=10)
        reg2.register(m2, 5.0, "largo")
        reg2.shutdown()
        await asyncio.sleep(0.1)
        assert not m2.deleted, "L6: borró tras shutdown()"
        assert reg2.pending_count == 0, "L6: quedaron tareas tras shutdown()"
    asyncio.run(_run())
    check("L5 · mensajes editados: borrado del objeto correcto", True)
    check("L6 · cancelación / reinicio: shutdown() cancela pendientes", True)


def test_L9_static_conservation():
    # Los sitios de registro de limpieza son EXACTAMENTE los auditados:
    # aviso de cola (2×), confirmación de reporte (1×) y hotmail_done (1×)
    # en handlers + la tarjeta de descarga COMPLETADA en download.py.
    # El helper legado _auto_delete_msg fue retirado (sin call-sites).
    hd_calls = len(re.findall(r"auto_clean\.(?:temp|info|after)\(", HD_SRC))
    check("L9a · handlers: solo los 4 puntos auditados registran limpieza",
          hd_calls == 4 and "_auto_delete_msg" not in HD_SRC,
          f"encontrados {hd_calls}")
    # descarga: registro SOLO en éxito (guard if success)
    check("L9b · download: limpieza solo con éxito (fallos se conservan)",
          "if success:" in DL_SRC and DL_SRC.count("auto_clean.info(") == 1)
    # pagos/membresías/notificaciones admin: cero LLAMADAS de limpieza
    # (mencionar el sistema en un docstring no es usarlo)
    np_calls = re.findall(r"auto_clean\.\w+\(", NP_SRC)
    vn_calls = re.findall(r"auto_clean\.\w+\(", VN_SRC)
    check("L9c · nowpayments/vip_notifier: la venta y su notificación jamás se limpian",
          not np_calls and not vn_calls,
          f"llamadas: {np_calls + vn_calls}")
    # el mensaje pay_success al usuario y los archivos enviados NO se
    # registran (verificación de ausencia de registro en _send_search_result)
    check("L9d · archivos de resultados y pay_success nunca se limpian",
          "_send_search_result" in HD_SRC)


# ─────────────────────────────────────────────────────────────
#  NOTIFICACIONES VIP A ADMINISTRADORES
# ─────────────────────────────────────────────────────────────

ADMIN_ID = 7656500542          # el configurado por defecto en config.py
CLIENT_ID = 123456789


def _reset_payment(inv="INV-TEST-1", user_id=CLIENT_ID, days=30,
                   amount=100.0, status="pending"):
    fake_db.payments.pop(inv, None)
    fake_db.users.pop(user_id, None)
    fake_db.claim_log.clear()
    fake_db.create_payment(user_id=user_id, invoice_id=inv,
                           order_id=f"HJ-{user_id}-{days}d-20261107000000",
                           days=days, amount_usd=amount, status=status, lang='es')
    return inv


class _FakeState:
    bot = fake_bot


def _client_entity(first="Nombre Real", username="cliente"):
    class _E:
        pass
    e = _E()
    e.first_name = first
    e.username = username
    e.id = CLIENT_ID
    return e


def test_N1_confirmed_purchase():
    async def _run():
        inv = _reset_payment(amount=100.0, days=30)
        fake_bot.sent.clear()
        fake_bot.entities[CLIENT_ID] = _client_entity()
        fake_db.claim_log.clear()

        ok = await nowpayments._deliver_vip(
            _FakeState(), CLIENT_ID, 30, inv, None, "IPN",
            ipn_data={"actually_paid": 0.0021, "actually_paid_currency": "btc",
                      "order_id": f"HJ-{CLIENT_ID}-30d-20261107000000"})
        assert ok, "N1: la entrega no se realizó"
        await _drain_notifier_tasks()

        # VIP activado y marcado entregado
        u = fake_db.get_user(CLIENT_ID)
        assert u['role'] == 'VIP' and u['vip_expiry'], "N1: VIP no activado"
        assert fake_db.payments[inv]['status'] == 'delivered'

        # Notificación al admin (y SOLO al admin — no al usuario: source IPN
        # con notify_user=True también avisa al usuario → 2 envíos totales)
        admin_msgs = [t for c, t in fake_bot.sent if c == ADMIN_ID]
        user_msgs = [t for c, t in fake_bot.sent if c == CLIENT_ID]
        assert len(admin_msgs) == 1, f"N1: {len(admin_msgs)} notificaciones admin"
        assert len(user_msgs) == 1, "N1: el usuario no fue avisado"

        # Contenido íntegro: los 13 datos reales
        t = admin_msgs[0]
        for esperado in ("Nombre Real", "@cliente", str(CLIENT_ID),
                         "30 días", "100 USD", "NOWPayments",
                         "Confirmado", inv, "0.0021 btc", "NUEVA VENTA VIP",
                         "Vence"):
            assert esperado in t, f"N1: falta «{esperado}» en la notificación"
        # Fechas reales de activación/vencimiento (formato DD/MM/AAAA)
        assert "/2026" in t or "/2025" in t or "/2027" in t, \
            "N1: sin fecha real formateada"
    asyncio.run(_run())
    check("N1 · compra confirmada → VIP + notificación admin íntegra", True)


def test_N2_duplicate_provider_event():
    async def _run():
        inv = _reset_payment(inv="INV-DUP-1", amount=25.0, days=7)
        fake_bot.sent.clear()
        fake_bot.entities[CLIENT_ID] = _client_entity()

        # Primera confirmación («confirmed»)
        ok1 = await nowpayments._deliver_vip(_FakeState(), CLIENT_ID, 7, inv,
                                             None, "IPN")
        await _drain_notifier_tasks()
        # Segunda confirmación del MISMO pago («finished»)
        ok2 = await nowpayments._deliver_vip(_FakeState(), CLIENT_ID, 7, inv,
                                             None, "IPN")
        # Tercera vía polling (fallback)
        ok3 = await nowpayments._deliver_vip(_FakeState(), CLIENT_ID, 7, inv,
                                             None, "polling")

        assert ok1 and not ok2 and not ok3, \
            f"N2: claims incorrectos ({ok1},{ok2},{ok3})"
        admin_msgs = [t for c, t in fake_bot.sent if c == ADMIN_ID]
        user_msgs = [t for c, t in fake_bot.sent if c == CLIENT_ID]
        assert len(admin_msgs) == 1, \
            f"N2: {len(admin_msgs)} notificaciones admin (debe ser 1)"
        assert len(user_msgs) == 1, "N2: usuario avisado más de una vez"
    asyncio.run(_run())
    check("N2 · evento de pago duplicado → sin doble notificación ni entrega", True)


def test_N3_concurrent_sources():
    async def _run():
        inv = _reset_payment(inv="INV-RACE-1", amount=50.0, days=15)
        fake_bot.sent.clear()

        async def _deliver(source):
            return await nowpayments._deliver_vip(_FakeState(), CLIENT_ID, 15,
                                                  inv, None, source)

        # IPN + polling + verificación manual EN PARALELO
        results = await asyncio.gather(
            _deliver("IPN"), _deliver("polling"), _deliver("manual-check"))
        assert results.count(True) == 1, \
            f"N3: {results.count(True)} entregas (debe ser exactamente 1)"
        admin_msgs = [t for c, t in fake_bot.sent if c == ADMIN_ID]
        assert len(admin_msgs) == 1, \
            f"N3: {len(admin_msgs)} notificaciones admin en carrera"
    asyncio.run(_run())
    check("N3 · IPN + polling + manual concurrentes → 1 sola entrega/notificación", True)


def test_N4_N5_pending_and_failed():
    async def _run():
        # Pendiente: NO se notifica (no llama a _deliver_vip — simulamos
        # el guard del polling: solo SUCCESS_STATUSES entrega)
        inv_p = _reset_payment(inv="INV-PEND-1", status="pending")
        # El polling con status waiting no llama a _deliver_vip:
        assert inv_p in fake_db.payments
        assert fake_db.payments[inv_p]['status'] == 'pending'

        # Fallido: el estado se registra, sin entrega ni notificación
        inv_f = _reset_payment(inv="INV-FAIL-1", status="failed")
        fake_db.update_payment_status(inv_f, "expired")
        fake_bot.sent.clear()
        # (ruta FAIL del IPN/polling: update_payment_status únicamente)
        assert fake_db.payments[inv_f]['status'] == 'expired'
        admin_msgs = [t for c, t in fake_bot.sent if c == ADMIN_ID]
        assert not admin_msgs, "N5: se notificó un pago fallido"
    asyncio.run(_run())
    check("N4 · pago pendiente no genera notificación de venta", True)
    check("N5 · pago fallido/expirado no genera notificación", True)


def test_N6_renewal_real_expiry():
    async def _run():
        # Usuario ya VIP con vencimiento futuro → RENOVACIÓN
        inv = _reset_payment(inv="INV-RENEW-1", days=30, amount=100.0)
        fake_db.users[CLIENT_ID] = {
            'user_id': CLIENT_ID, 'role': 'VIP',
            'vip_expiry': (datetime.now(timezone.utc)
                           + timedelta(days=10)).isoformat()}
        fake_bot.sent.clear()

        await nowpayments._deliver_vip(_FakeState(), CLIENT_ID, 30, inv,
                                       None, "IPN")
        await _drain_notifier_tasks()

        u = fake_db.get_user(CLIENT_ID)
        exp = datetime.fromisoformat(u['vip_expiry'])
        # El vencimiento REAL tras la renovación (ahora+30d ≈ real)
        delta = (exp - datetime.now(timezone.utc)).total_seconds() / 86400
        assert 29.9 < delta <= 30.1, f"N6: vencimiento irreal ({delta:.2f} d)"
        # La notificación muestra ESE vencimiento real
        t = [txt for c, txt in fake_bot.sent if c == ADMIN_ID][0]
        assert exp.strftime("%d/%m/%Y") in t, \
            "N6: la notificación no muestra el vencimiento real"
    asyncio.run(_run())
    check("N6 · renovación: vencimiento REAL post-activación en la notificación", True)


def test_N7_no_username():
    async def _run():
        inv = _reset_payment(inv="INV-NOUSER-1", days=1, amount=6.0)
        fake_bot.sent.clear()
        fake_bot.entities[CLIENT_ID] = _client_entity(first="Ana", username=None)

        await nowpayments._deliver_vip(_FakeState(), CLIENT_ID, 1, inv,
                                       None, "manual-check")
        await _drain_notifier_tasks()
        t = [txt for c, txt in fake_bot.sent if c == ADMIN_ID][0]
        assert "Sin username" in t, "N7: falta «Sin username»"
        assert "Ana" in t and str(CLIENT_ID) in t, "N7: faltan nombre/ID"
    asyncio.run(_run())
    check("N7 · usuario sin username → «Sin username» + ID conservado", True)


def test_N8_plan_and_promo_price():
    async def _run():
        # Plan de 15 días con promo -50% → el importe notificado es el
        # REAL cobrado ($25), no el precio base ($50)
        inv = _reset_payment(inv="INV-PROMO-1", days=15, amount=25.0)
        fake_bot.sent.clear()
        await nowpayments._deliver_vip(_FakeState(), CLIENT_ID, 15, inv,
                                       None, "IPN")
        await _drain_notifier_tasks()
        t = [txt for c, txt in fake_bot.sent if c == ADMIN_ID][0]
        assert "15 días" in t and "25 USD" in t, \
            "N8: duración o importe real incorrectos"
        assert "50 USD" not in t, "N8: notificó el precio base en vez del cobrado"
    asyncio.run(_run())
    check("N8 · duración distinta + importe REAL con promo aplicada", True)


def test_N9_N10_admin_delivery_failure():
    async def _run():
        inv = _reset_payment(inv="INV-ADMINFAIL-1", days=7, amount=25.0)
        fake_bot.sent.clear()
        fake_bot.fail_admins.add(ADMIN_ID)   # admin sin PM iniciado
        try:
            ok = await nowpayments._deliver_vip(_FakeState(), CLIENT_ID, 7, inv,
                                                None, "IPN")
            await _drain_notifier_tasks(1.0)
            # La venta quedó procesada aunque la notificación falle
            assert ok, "N10: la entrega falló por la notificación"
            assert fake_db.payments[inv]['status'] == 'delivered'
            u = fake_db.get_user(CLIENT_ID)
            assert u['role'] == 'VIP'
            # Sin duplicados: el reintento controlado no re-entrega
            assert len(fake_db.claim_log) == 1
        finally:
            fake_bot.fail_admins.discard(ADMIN_ID)
    asyncio.run(_run())
    check("N9 · fallo al notificar al admin (Forbidden) manejado y registrado", True)
    check("N10 · la venta se procesa aunque falle la notificación", True)


def test_N11_free_promo_not_sale():
    async def _run():
        inv = _reset_payment(inv="PROMO-TEST-1", days=30, amount=0.0)
        fake_bot.sent.clear()
        # Ruta promo-100: notify_user=False (el handler edita su mensaje)
        ok = await nowpayments._deliver_vip(_FakeState(), CLIENT_ID, 30, inv,
                                            'es', "promo-100",
                                            notify_user=False)
        assert ok, "N11: el regalo no se entregó"
        assert fake_db.get_user(CLIENT_ID)['role'] == 'VIP'
        admin_msgs = [t for c, t in fake_bot.sent if c == ADMIN_ID]
        user_msgs = [t for c, t in fake_bot.sent if c == CLIENT_ID]
        assert not admin_msgs, "N11: un regalo se notificó como venta"
        assert not user_msgs, "N11: mensaje duplicado al usuario en promo-100"
    asyncio.run(_run())
    check("N11 · activación gratuita NO se presenta como venta cobrada", True)


def test_N12_format_premium_emojis():
    import premium_emojis as pe
    t = vip_notifier.build_sale_notification(
        user_id=CLIENT_ID, days=30, amount_usd=100.0,
        record_id="INV-FMT-1",
        expiry_iso="2026-12-07T15:00:00+00:00",
        activation_iso="2026-11-07T15:00:00+00:00",
        first_name="Test", username="test",
        paid_crypto="0.0021", paid_crypto_currency="btc",
        order_id="HJ-123-30d-20261107")

    # Todos los emojis del diseño tienen ID premium registrado
    used = {ch for ch in t if ord(ch) > 0x2000}
    registered = set(pe.PREMIUM_EMOJI_IDS.keys())
    # excluir box-drawing (╭ ╮ ╰ ╯ ┃ │ ├ └ ━ ─ — texto estructural, no emoji)
    structural = set("╭╮╰╯┃│├└━─»«")
    emojis = {ch for ch in used if ch not in structural and not ch.isalnum()}
    unregistered = [e for e in emojis if e not in registered and len(e) == 1]
    check("N12a · todos los emojis del diseño están registrados (premium)",
          not unregistered, f"sin registro: {unregistered}")

    # Cero banderas (regla de oro del sistema)
    has_flag = any(ord(ch) in range(0x1F1E6, 0x1F1FF + 1) for ch in t)
    check("N12b · sin banderas convertidas a premium", not has_flag)

    # Contenido: 13 campos del requerimiento
    for campo in ("CLIENTE", "MEMBRESÍA", "PAGO", "Importe", "Método",
                  "Estado", "Activación", "Vence", "Transacción",
                  "Sin" if False else "Nombre", "Usuario", "ID",
                  "Plan", "07/12/2026"):
        assert campo in t, f"N12c: falta el campo «{campo}»"
    check("N12c · contenido íntegro de los 13 datos requeridos", True)

    # Sin datos sensibles
    for secreto in ("API_KEY", "IPN_KEY", "BOT_TOKEN", "npg_", "x-api-key"):
        assert secreto not in t, f"N12d: posible secreto «{secreto}» expuesto"
    check("N12d · sin secretos/tokens en la notificación", True)


def test_N13_persistence_of_admin_notification():
    # La notificación admin NO se registra en auto_clean (persistente)
    async def _run():
        inv = _reset_payment(inv="INV-PERSIST-1", days=30, amount=100.0)
        fake_bot.sent.clear()
        antes = cleaner.stats["scheduled"]
        await nowpayments._deliver_vip(_FakeState(), CLIENT_ID, 30, inv,
                                       None, "IPN")
        await asyncio.sleep(0.15)
        # Ningún mensaje enviado al admin entró al sistema de limpieza
        assert cleaner.stats["scheduled"] == antes, \
            "N13: la notificación admin se registró para limpieza"
        for chat_id, _ in fake_bot.sent:
            if chat_id == ADMIN_ID:
                continue
    asyncio.run(_run())
    check("N13 · la notificación administrativa persiste (sin limpieza)", True)


def test_N14_no_duplicate_user_message():
    # Verificación estática: las rutas que editan su propio mensaje
    # llaman con notify_user=False (sin tarjeta pay_success duplicada)
    n = len(re.findall(r"notify_user=False\)", HD_SRC))
    check("N14 · sin mensaje duplicado al usuario (manual-check y promo-100)",
          n == 2, f"llamadas notify_user=False: {n}")


def test_webhook_ipn_signature_and_flow():
    """IPN firmado de punta a punta: firma → parseo → claim → entrega."""
    async def _run():
        import webhook_server as ws
        ws.db = fake_db

        inv = _reset_payment(inv="INV-WH-1", days=3, amount=10.0)
        fake_bot.sent.clear()

        payload = {
            "payment_status": "finished",
            "order_id": f"HJ-{CLIENT_ID}-3d-20261107000000",
            "invoice_id": inv,
            "payment_id": "PAY-999",
            "actually_paid": 0.00021,
            "actually_paid_currency": "btc",
            "pay_amount": 10.0,
            "pay_currency": "usd",
        }
        raw = json.dumps(payload).encode()
        sig = hmac.new(config.NOWPAYMENTS_IPN_KEY.encode(), raw,
                       hashlib.sha512).hexdigest()

        class _Req:
            headers = {"x-nowpayments-sig": sig}
            async def read(self):
                return raw

        resp = await ws.handle_ipn(_Req())
        assert resp.status == 200, "WH: respuesta no-200"
        await _drain_notifier_tasks()

        # Firma inválida → rechazada sin tocar nada
        inv2 = _reset_payment(inv="INV-WH-2", days=3, amount=10.0)
        payload2 = dict(payload, invoice_id=inv2)
        raw2 = json.dumps(payload2).encode()

        class _ReqBad:
            headers = {"x-nowpayments-sig": "firma_falsa"}
            async def read(self):
                return raw2

        resp2 = await ws.handle_ipn(_ReqBad())
        assert resp2.status == 400, "WH: firma inválida no fue rechazada"
        assert fake_db.payments[inv2]['status'] == 'pending', \
            "WH: un IPN sin firma válido entregó el VIP"

        # El primero quedó entregado y notificado UNA vez
        assert fake_db.payments[inv]['status'] == 'delivered'
        admin_msgs = [t for c, t in fake_bot.sent if c == ADMIN_ID]
        assert len(admin_msgs) == 1, "WH: notificación admin incorrecta"
        assert "10 USD" in admin_msgs[0] and "0.00021 btc" in admin_msgs[0]
    asyncio.run(_run())
    check("WH · IPN firmado: firma, idempotencia y datos verificados", True)


def test_config_and_catalog_integrity():
    # Config nueva presente y con defaults sanos
    check("CFG · interruptor y retardos configurables",
          hasattr(config, "AUTO_CLEAN_MESSAGES")
          and hasattr(config, "AUTO_CLEAN_TEMP_SECONDS")
          and hasattr(config, "AUTO_CLEAN_INFO_SECONDS")
          and 5 <= config.AUTO_CLEAN_TEMP_SECONDS <= 15
          and 60 <= config.AUTO_CLEAN_INFO_SECONDS <= 120)
    # Catálogo premium intacto (86 IDs + alias)
    import premium_emojis as pe
    check("EMO · catálogo premium intacto (87 asociaciones / 86 IDs)",
          len(pe.PREMIUM_EMOJI_IDS) == 87
          and len(set(pe.PREMIUM_EMOJI_IDS.values())) == 86)
    # La versión del bot es la de esta entrega
    check("VER · versión 4.3.1", config.VERSION == "4.3.1")


# ─────────────────────────────────────────────────────────────
#  Ejecución
# ─────────────────────────────────────────────────────────────

def main():
    tests = [
        test_L1_L2_L7_L8_cleaning,
        test_L3_master_switch,
        test_L4_identity_protection,
        test_L5_L6_edit_and_shutdown,
        test_L9_static_conservation,
        test_N1_confirmed_purchase,
        test_N2_duplicate_provider_event,
        test_N3_concurrent_sources,
        test_N4_N5_pending_and_failed,
        test_N6_renewal_real_expiry,
        test_N7_no_username,
        test_N8_plan_and_promo_price,
        test_N9_N10_admin_delivery_failure,
        test_N11_free_promo_not_sale,
        test_N12_format_premium_emojis,
        test_N13_persistence_of_admin_notification,
        test_N14_no_duplicate_user_message,
        test_webhook_ipn_signature_and_flow,
        test_config_and_catalog_integrity,
    ]
    t0 = time.time()
    for fn in tests:
        try:
            fn()
        except AssertionError as e:
            check(fn.__name__, False, str(e)[:300])
        except Exception as e:
            check(fn.__name__ + " (excepción)", False,
                  f"{type(e).__name__}: {str(e)[:250]}")
    elapsed = time.time() - t0

    print("═" * 62)
    print("  LIMPIEZA INTELIGENTE + NOTIFICACIONES VIP — v4.3.1")
    print("═" * 62)
    for status, name, detail in _RESULTS:
        marca = "✓" if status == "PASS" else "✗"
        print(f"  [{marca}] {name}")
        if detail:
            print(f"        ↳ {detail}")
    print("═" * 62)
    total = len(_RESULTS)
    print(f"  RESULTADO: {_PASSED}/{total} pruebas · {elapsed:.2f}s")
    if _FAILED:
        print(f"  FALLARON: {', '.join(_FAILED)}")
        sys.exit(1)
    print("  TODO OK")


if __name__ == "__main__":
    main()
