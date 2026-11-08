"""
═══════════════════════════════════════════════════════════════
  HJ ULP EXTRACTOR BOT — Limpieza Inteligente de Mensajes v4.3.1
═══════════════════════════════════════════════════════════════
  Mantiene las conversaciones limpias eliminando SOLO los mensajes
  temporales del bot que dejaron de ser útiles.

  PRINCIPIOS DE SEGURIDAD (nada se borra por aproximación):
  • OPT-IN EXPLÍCITO — un mensaje solo se borra si el código que lo
    crea lo REGISTRA aquí en el momento exacto en que queda obsoleto.
    Todo lo que no se registra (resultados, archivos, pagos, errores,
    menús con botones, mensajes del usuario, notificaciones admin)
    jamás se toca.
  • IDENTIDAD EXACTA — se conserva la REFERENCIA AL PROPIO OBJETO
    Message de Telethon y se borra con msg.delete(), que actúa sobre
    el chat al que el mensaje PERTENECE. Nunca se llama a
    delete_messages con listas de IDs sueltas → es IMPOSIBLE borrar
    un mensaje de otro chat por un identificador equivocado.
  • NUNCA DURANTE LA OPERACIÓN — se registra al COMPLETAR, no al
    crear: el aviso de progreso vive mientras la operación corre.
  • NO BLOQUEANTE — cada limpieza es una tarea asyncio independiente;
    comandos, búsquedas y descargas siguen fluidos. Errores de
    borrado se loguean y ya (1 reintento como máximo, sin cadenas
    infinitas).
  • APAGADO LIMPIO — shutdown() cancela las tareas pendientes; el
    bot puede reiniciarse (/updateBot) sin esperas.

  Categorías de retardo (configurables por .env):
  • temp  — avisos de carga/cola obsoletos      → AUTO_CLEAN_TEMP_SECONDS (10 s)
  • info  — confirmaciones/avisos ya cumplidos  → AUTO_CLEAN_INFO_SECONDS (90 s)
═══════════════════════════════════════════════════════════════
"""

import asyncio
import time
from typing import Optional

from config import config
from logger_setup import logger

# Retardo del reintento único de borrado (module-level para tests)
_RETRY_DELAY = 2.0


class AutoCleanRegistry:
    """Registro central de mensajes temporales con borrado diferido."""

    def __init__(self):
        # Referencias vivas de las tareas de borrado (evita GC prematuro)
        self._tasks = set()
        # Diagnóstico: (chat_id, msg_id) -> deadline epoch
        self._pending = {}
        self._shutting_down = False
        # Métricas simples para /ping o logs
        self.stats = {"scheduled": 0, "deleted": 0, "failed": 0, "skipped": 0}

    # ── API pública ──────────────────────────────────────────

    def register(self, msg, delay: float, reason: str = "") -> bool:
        """Programar el borrado diferido de UN mensaje concreto.

        Se llama SOLO cuando el mensaje ya cumplió su función (la
        operación terminó y el resultado definitivo fue entregado).

        Retorna True si quedó programado; False si el interruptor
        global está apagado o el mensaje no es verificable.
        """
        if not config.AUTO_CLEAN_MESSAGES:
            self.stats["skipped"] += 1
            return False
        if self._shutting_down:
            return False
        if msg is None or delay is None or delay <= 0:
            return False

        # ── Identidad exacta: el objeto guarda su propio chat ──
        # Si el mensaje no permite verificar (chat_id, id) con certeza,
        # NO se registra (fail-safe: el mensaje se queda, no se arriesga).
        chat_id = self._extract_chat_id(msg)
        msg_id = getattr(msg, "id", None)
        if chat_id is None or msg_id is None:
            logger.debug(
                f"AUTO_CLEAN: mensaje sin identidad verificable "
                f"(chat={chat_id}, id={msg_id}) — no se registra [{reason}]"
            )
            return False

        try:
            task = asyncio.create_task(
                self._delete_later(msg, chat_id, int(msg_id), float(delay), reason)
            )
        except RuntimeError:
            # Sin event loop corriendo (p.ej. import en test) — nada que hacer
            return False

        self._tasks.add(task)
        self._pending[(chat_id, int(msg_id))] = time.time() + delay
        task.add_done_callback(lambda t: self._task_done(chat_id, int(msg_id), t))
        self.stats["scheduled"] += 1
        return True

    def temp(self, msg, reason: str = "") -> bool:
        """Aviso de carga/cola que quedó obsoleto (retardo corto)."""
        return self.register(msg, config.AUTO_CLEAN_TEMP_SECONDS, reason)

    def info(self, msg, reason: str = "") -> bool:
        """Confirmación/aviso informativo ya cumplido (retardo medio)."""
        return self.register(msg, config.AUTO_CLEAN_INFO_SECONDS, reason)

    def after(self, msg, seconds: float, reason: str = "") -> bool:
        """Retardo personalizado para casos concretos."""
        return self.register(msg, seconds, reason)

    def forget(self, msg) -> None:
        """Des-programar el borrado de un mensaje (p. ej. el flujo lo
        reutilizó para algo que debe quedarse). Idempotente."""
        chat_id = self._extract_chat_id(msg)
        msg_id = getattr(msg, "id", None)
        if chat_id is None or msg_id is None:
            return
        key = (chat_id, int(msg_id))
        if key in self._pending:
            self._pending.pop(key, None)
            self.stats["skipped"] += 1

    def shutdown(self) -> None:
        """Apagado ordenado: cancela los borrados pendientes."""
        self._shutting_down = True
        for task in list(self._tasks):
            if not task.done():
                task.cancel()
        self._tasks.clear()
        self._pending.clear()

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    # ── Internos ─────────────────────────────────────────────

    @staticmethod
    def _extract_chat_id(msg) -> Optional[int]:
        """Chat al que el mensaje PERTENECE, leído del propio objeto.

        Nunca se deduce del contexto ni de variables globales: si el
        objeto no lo declara, no hay borrado (fail-safe).
        """
        try:
            cid = getattr(msg, "chat_id", None)
            if cid is not None:
                return int(cid)
            # Fallback estructural (Message de Telethon siempre trae
            # peer_id; si un mock de prueba no lo trae, no se registra)
            peer = getattr(msg, "peer_id", None)
            if peer is not None:
                uid = getattr(peer, "user_id", None)
                if uid is not None:
                    return int(uid)
                cid = getattr(peer, "channel_id", None) or getattr(peer, "chat_id", None)
                if cid is not None:
                    return int(cid)
        except (TypeError, ValueError):
            return None
        return None

    def _task_done(self, chat_id: int, msg_id: int, task) -> None:
        self._tasks.discard(task)
        self._pending.pop((chat_id, msg_id), None)
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.warning(f"AUTO_CLEAN: tarea de borrado terminó con error: {exc}")

    async def _delete_later(self, msg, chat_id: int, msg_id: int,
                            delay: float, reason: str) -> None:
        """Esperar el intervalo prudente y borrar con identidad exacta.

        El borrado usa msg.delete() del PROPIO objeto: Telethon resuelve
        el peer correcto (privado, grupo o canal) → riesgo cero de
        borrar en otro chat por un ID mal calculado.
        """
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            return

        if self._shutting_down:
            return

        # Doble verificación de identidad ANTES de borrar: el objeto
        # debe seguir apuntando al mismo (chat, id) registrado.
        try:
            if int(getattr(msg, "id", -1)) != msg_id:
                self.stats["skipped"] += 1
                return
            if self._extract_chat_id(msg) != chat_id:
                self.stats["skipped"] += 1
                logger.warning(
                    f"AUTO_CLEAN: identidad inconsistente al borrar "
                    f"msg={msg_id} chat={chat_id} — se conserva [{reason}]"
                )
                return
        except Exception:
            return

        # 1 intento + 1 reintento corto (sin cadenas infinitas)
        for attempt in (1, 2):
            try:
                await msg.delete()
                self.stats["deleted"] += 1
                logger.info(
                    f"AUTO_CLEAN: msg {msg_id} del chat {chat_id} eliminado "
                    f"[{reason}] (+{delay:.0f}s)"
                )
                return
            except asyncio.CancelledError:
                return
            except Exception as exc:
                # MessageIdInvalid / el mensaje ya no existe → silencio
                name = type(exc).__name__
                if attempt == 1:
                    logger.debug(
                        f"AUTO_CLEAN: reintento por {name} en msg {msg_id} "
                        f"chat {chat_id} [{reason}]"
                    )
                    await asyncio.sleep(_RETRY_DELAY)
                    continue
                self.stats["failed"] += 1
                # Registrado sin afectar al resto del bot
                logger.warning(
                    f"AUTO_CLEAN: no se pudo borrar msg {msg_id} del chat "
                    f"{chat_id} [{reason}]: {name}: {exc}"
                )
                return


# ── Instancia global (misma convención que state/db) ──────────
auto_clean = AutoCleanRegistry()
