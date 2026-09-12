"""
═══════════════════════════════════════════════════════════════
  HJ ULP EXTRACTOR BOT — Database Module (PostgreSQL Edition)
═══════════════════════════════════════════════════════════════
  • Backend: PostgreSQL (probado con Neon, sirve para cualquier PG)
  • Driver: psycopg3 + psycopg-pool (pool thread-safe)
  • Caché de usuarios en RAM (igual que antes: cero SQL por mensaje)
  • Schema idéntico al de SQLite (mismas tablas, mismos campos)
  • Placeholders: %s (estilo psycopg) en vez de ? (estilo sqlite3)
═══════════════════════════════════════════════════════════════
"""

import random
import string
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from config import config
from logger_setup import logger


class Database:
    """Base de datos PostgreSQL con pool de conexiones y caché de usuarios en RAM.

    - El pool (psycopg-pool) es thread-safe: cada llamada pide una conexión,
      hace su trabajo y la devuelve. No hace falta lock para escrituras.
    - La caché de usuarios en RAM evita un SELECT + UPDATE por cada mensaje
      (igual que en la versión SQLite).
    - Los IDs de Telegram se guardan como BIGINT (pueden superar 2^31).
    """

    def __init__(self, db_url: str):
        self.db_url = db_url
        # Caché de usuarios en RAM: uid -> (dict_usuario, timestamp)
        self._user_cache: Dict[int, Tuple[dict, float]] = {}
        self._last_active_ts: Dict[int, float] = {}
        # Lock solo para proteger la caché en RAM (no para DB)
        self._cache_lock = threading.Lock()

        # Pool de conexiones Postgres
        # min_size=1, max_size=5: suficiente para un bot de Telegram
        # (las llamadas DB son rápidas y la caché evita la mayoría)
        try:
            self.pool = ConnectionPool(
                conninfo=db_url,
                min_size=1,
                max_size=5,
                timeout=30,
                configure=self._configure_conn,
                open=True,
            )
            logger.info("Pool de PostgreSQL conectado correctamente")
        except Exception as e:
            logger.critical(f"No se pudo conectar a PostgreSQL: {e}")
            raise

        self._init_schema()

    @staticmethod
    def _configure_conn(conn):
        """Configurar cada conexión del pool: devolver filas como dict."""
        conn.row_factory = dict_row

    # ── Caché de usuarios ───────────────────────────────────

    def _cache_get(self, uid: int):
        with self._cache_lock:
            entry = self._user_cache.get(uid)
        if entry and (time.time() - entry[1]) < config.USER_CACHE_TTL:
            return entry[0]
        return None

    def _cache_set(self, user: dict):
        with self._cache_lock:
            self._user_cache[user['user_id']] = (user, time.time())

    def _cache_invalidate(self, uid: int):
        with self._cache_lock:
            self._user_cache.pop(uid, None)

    # ── Inicialización del schema ──────────────────────────

    def _init_schema(self):
        """Crear tablas si no existen + migraciones de columnas."""
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                # ── Tabla: users ──
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY,
                        role TEXT DEFAULT 'FREE',
                        vip_expiry TEXT,
                        search_count INTEGER DEFAULT 0,
                        language TEXT DEFAULT 'es',
                        first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
                        last_active TEXT DEFAULT CURRENT_TIMESTAMP,
                        free_search_used INTEGER DEFAULT 0,
                        bonus_searches INTEGER DEFAULT 0,
                        referrer_id BIGINT
                    )
                """)

                # ── Tabla: keys ──
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS keys (
                        key_code TEXT PRIMARY KEY,
                        days INTEGER,
                        created_by BIGINT,
                        used_by BIGINT,
                        is_used INTEGER DEFAULT 0,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # ── Tabla: download_log ──
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS download_log (
                        id BIGSERIAL PRIMARY KEY,
                        filename TEXT,
                        file_size BIGINT DEFAULT 0,
                        chat_id BIGINT,
                        downloaded_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # ── Tabla: allowed_groups ──
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS allowed_groups (
                        chat_id BIGINT PRIMARY KEY,
                        added_by BIGINT,
                        added_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # ── Tabla: payments ──
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS payments (
                        id BIGSERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        invoice_id TEXT NOT NULL,
                        order_id TEXT,
                        days INTEGER,
                        amount_usd REAL,
                        status TEXT DEFAULT 'pending',
                        lang TEXT DEFAULT 'es',
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Indices para performance
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_payments_status
                    ON payments(status)
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_payments_invoice_id
                    ON payments(invoice_id)
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_payments_order_id
                    ON payments(order_id)
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_users_referrer
                    ON users(referrer_id)
                """)

                # ── Migraciones: añadir columnas que falten en users ──
                cur.execute("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = 'users'
                """)
                existing_cols = {row['column_name'] for row in cur.fetchall()}

                migrations = [
                    ('language', "ALTER TABLE users ADD COLUMN language TEXT DEFAULT 'es'"),
                    ('first_seen', "ALTER TABLE users ADD COLUMN first_seen TEXT DEFAULT CURRENT_TIMESTAMP"),
                    ('last_active', "ALTER TABLE users ADD COLUMN last_active TEXT DEFAULT CURRENT_TIMESTAMP"),
                    ('free_search_used', "ALTER TABLE users ADD COLUMN free_search_used INTEGER DEFAULT 0"),
                    ('bonus_searches', "ALTER TABLE users ADD COLUMN bonus_searches INTEGER DEFAULT 0"),
                    ('referrer_id', "ALTER TABLE users ADD COLUMN referrer_id BIGINT"),
                ]
                for col_name, alter_sql in migrations:
                    if col_name not in existing_cols:
                        logger.info(f"Migrando DB: agregando columna '{col_name}'...")
                        try:
                            cur.execute(alter_sql)
                            logger.info(f"Columna '{col_name}' agregada correctamente.")
                        except psycopg.errors.DuplicateColumn:
                            pass  # ya existe, ignorar
                        except Exception as e:
                            logger.error(f"Error migrando DB ({col_name}): {e}")

            conn.commit()
        logger.info("Schema de PostgreSQL verificado/creado correctamente")

    # ── Operaciones de usuario ─────────────────────────────

    def get_user(self, uid: int) -> dict:
        # 1) Servir desde caché (lecturas rapidísimas, cero SQL)
        cached = self._cache_get(uid)
        if cached is not None:
            return cached

        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM users WHERE user_id = %s", (uid,))
                row = cur.fetchone()

                if not row:
                    now = datetime.now(timezone.utc).isoformat()
                    cur.execute(
                        "INSERT INTO users (user_id, first_seen, last_active) "
                        "VALUES (%s, %s, %s)",
                        (uid, now, now)
                    )
                    conn.commit()
                    user = {
                        'user_id': uid, 'role': 'FREE', 'vip_expiry': None,
                        'search_count': 0, 'language': 'es',
                        'first_seen': now, 'last_active': now,
                        'free_search_used': 0,
                        'bonus_searches': 0, 'referrer_id': None
                    }
                    self._cache_set(user)
                    return user

                user = dict(row)

                # 2) last_active con throttle
                now_ts = time.time()
                last_upd = self._last_active_ts.get(uid, 0)
                if now_ts - last_upd > config.LAST_ACTIVE_INTERVAL:
                    self._last_active_ts[uid] = now_ts
                    try:
                        cur.execute(
                            "UPDATE users SET last_active = %s WHERE user_id = %s",
                            (datetime.now(timezone.utc).isoformat(), uid)
                        )
                        conn.commit()
                    except Exception:
                        pass

        self._cache_set(user)
        return user

    def is_new_user(self, uid: int) -> bool:
        """Verificar si el usuario es nuevo (nunca ha usado su búsqueda gratis)."""
        user = self.get_user(uid)
        return user.get('free_search_used', 0) == 0

    def user_exists(self, uid: int) -> bool:
        """Comprobar si el usuario ya existe SIN crear registro (lectura pura)."""
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM users WHERE user_id = %s", (uid,))
                return cur.fetchone() is not None

    def mark_free_search_used(self, uid: int):
        """Marcar que el usuario ya usó su búsqueda gratis."""
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET free_search_used = 1, "
                    "search_count = search_count + 1 WHERE user_id = %s",
                    (uid,)
                )
            conn.commit()
        self._cache_invalidate(uid)

    def set_language(self, uid: int, lang: str):
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET language = %s WHERE user_id = %s",
                    (lang, uid)
                )
            conn.commit()
        self._cache_invalidate(uid)

    def set_role(self, uid: int, role: str, days: int = 0):
        expiry = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat() if role == 'VIP' else None
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO users (user_id, role, vip_expiry) VALUES (%s, %s, %s) "
                    "ON CONFLICT(user_id) DO UPDATE SET "
                    "role=EXCLUDED.role, vip_expiry=EXCLUDED.vip_expiry",
                    (uid, role, expiry)
                )
            conn.commit()
        self._cache_invalidate(uid)

    def remove_vip(self, uid: int):
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET role='FREE', vip_expiry=NULL WHERE user_id=%s",
                    (uid,)
                )
            conn.commit()
        self._cache_invalidate(uid)

    # ── Keys ───────────────────────────────────────────────

    def gen_key(self, creator: int, days: int) -> str:
        code = f"HJ-{''.join(random.choices(string.ascii_uppercase + string.digits, k=12))}"
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO keys (key_code, days, created_by) VALUES (%s, %s, %s)",
                    (code, days, creator)
                )
            conn.commit()
        return code

    def redeem(self, uid: int, code: str) -> bool:
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT days FROM keys WHERE key_code = %s AND is_used = 0",
                    (code,)
                )
                row = cur.fetchone()
                if not row:
                    return False
                days = row['days']
                now = datetime.now(timezone.utc)
                cur.execute("SELECT vip_expiry FROM users WHERE user_id = %s", (uid,))
                user_row = cur.fetchone()
                if user_row and user_row['vip_expiry']:
                    try:
                        existing_exp = datetime.fromisoformat(user_row['vip_expiry'])
                        if existing_exp.tzinfo is None:
                            existing_exp = existing_exp.replace(tzinfo=timezone.utc)
                        if existing_exp > now:
                            base = existing_exp
                        else:
                            base = now
                    except Exception:
                        base = now
                else:
                    base = now
                expiry = (base + timedelta(days=days)).isoformat()
                cur.execute(
                    "UPDATE keys SET is_used = 1, used_by = %s WHERE key_code = %s",
                    (uid, code)
                )
                cur.execute(
                    "INSERT INTO users (user_id, role, vip_expiry) VALUES (%s, 'VIP', %s) "
                    "ON CONFLICT(user_id) DO UPDATE SET "
                    "role='VIP', vip_expiry=EXCLUDED.vip_expiry",
                    (uid, expiry)
                )
            conn.commit()
        self._cache_invalidate(uid)
        return True

    def add_search(self, uid: int):
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET search_count = search_count + 1 WHERE user_id = %s",
                    (uid,)
                )
            conn.commit()
        self._cache_invalidate(uid)

    # ── Sistema de referidos ────────────────────────────────

    def apply_referral(self, new_uid: int, referrer_id: int) -> bool:
        """Aplicar un referido: +1 búsqueda gratis para el invitado Y el referidor.

        Reglas anti-abuso (atómicas en una sola transacción):
          • El invitado debe ser nuevo y NO tener ya un referidor
          • El referidor debe existir en la base de datos (usuario real)
          • Nadie puede referirse a sí mismo
        """
        if new_uid == referrer_id:
            return False
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                # El referidor debe ser un usuario real del bot
                cur.execute("SELECT 1 FROM users WHERE user_id = %s", (referrer_id,))
                if not cur.fetchone():
                    return False
                # Garantizar la fila del invitado
                now_iso = datetime.now(timezone.utc).isoformat()
                cur.execute(
                    "INSERT INTO users (user_id, first_seen, last_active) "
                    "VALUES (%s, %s, %s) ON CONFLICT (user_id) DO NOTHING",
                    (new_uid, now_iso, now_iso)
                )
                # El invitado solo puede ser referido una vez (guard atómico)
                cur.execute(
                    "UPDATE users SET referrer_id = %s, bonus_searches = bonus_searches + 1 "
                    "WHERE user_id = %s AND referrer_id IS NULL",
                    (referrer_id, new_uid)
                )
                if cur.rowcount == 0:
                    return False
                # Recompensa al referidor: +1 búsqueda gratis
                cur.execute(
                    "UPDATE users SET bonus_searches = bonus_searches + 1 WHERE user_id = %s",
                    (referrer_id,)
                )
            conn.commit()
        self._cache_invalidate(new_uid)
        self._cache_invalidate(referrer_id)
        logger.info(f"Referido aplicado: {new_uid} invitado por {referrer_id} (+1 bonus a cada uno)")
        return True

    def get_referral_count(self, uid: int) -> int:
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS c FROM users WHERE referrer_id = %s", (uid,))
                return cur.fetchone()['c']

    def consume_bonus_search(self, uid: int) -> bool:
        """Consumir 1 búsqueda de bono (referidos). Retorna False si no tiene."""
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET bonus_searches = bonus_searches - 1, "
                    "search_count = search_count + 1 "
                    "WHERE user_id = %s AND bonus_searches > 0",
                    (uid,)
                )
                ok = cur.rowcount > 0
            if ok:
                conn.commit()
        self._cache_invalidate(uid)
        return ok

    # ── Stats y limpieza ────────────────────────────────────

    def get_stats(self) -> dict:
        self.cleanup_expired_vips()
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS c FROM users WHERE role='VIP'")
                vips = cur.fetchone()['c']
                cur.execute("SELECT COUNT(*) AS c FROM users WHERE role='SELLER'")
                sellers = cur.fetchone()['c']
                cur.execute("SELECT COALESCE(SUM(search_count), 0) AS s FROM users")
                total_searches = cur.fetchone()['s']
                cur.execute("SELECT COUNT(*) AS c FROM users")
                total_users = cur.fetchone()['c']
                cur.execute("SELECT COUNT(*) AS c FROM users WHERE free_search_used = 0")
                new_users = cur.fetchone()['c']
                cur.execute("SELECT COUNT(*) AS c FROM users WHERE referrer_id IS NOT NULL")
                referred_users = cur.fetchone()['c']
        return {
            'vips': vips, 'sellers': sellers,
            'searches': total_searches, 'total_users': total_users,
            'new_users': new_users, 'referred_users': referred_users
        }

    def cleanup_expired_vips(self) -> int:
        """Cambiar a FREE los VIPs cuya fecha de expiración ya pasó."""
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                now_iso = datetime.now(timezone.utc).isoformat()
                cur.execute(
                    "UPDATE users SET role='FREE', vip_expiry=NULL "
                    "WHERE role='VIP' AND vip_expiry IS NOT NULL AND vip_expiry < %s",
                    (now_iso,)
                )
                count = cur.rowcount
            if count > 0:
                conn.commit()
                logger.info(f"VIPs expirados limpiados: {count}")
        if count > 0:
            # Invalidar toda la caché (no sabemos qué users se vencieron)
            with self._cache_lock:
                self._user_cache.clear()
        return count

    def list_vips(self) -> List[dict]:
        self.cleanup_expired_vips()
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT user_id, vip_expiry, search_count FROM users "
                    "WHERE role='VIP' OR role='SELLER'"
                )
                return cur.fetchall()

    def list_sellers(self) -> List[int]:
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT user_id FROM users WHERE role='SELLER'")
                return [row['user_id'] for row in cur.fetchall()]

    def get_all_users(self) -> List[int]:
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT user_id FROM users")
                return [row['user_id'] for row in cur.fetchall()]

    # ── Grupos permitidos ──────────────────────────────────

    def add_allowed_group(self, chat_id: int, added_by: int):
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO allowed_groups (chat_id, added_by) "
                    "VALUES (%s, %s) ON CONFLICT (chat_id) DO NOTHING",
                    (chat_id, added_by)
                )
            conn.commit()

    def remove_allowed_group(self, chat_id: int):
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM allowed_groups WHERE chat_id = %s", (chat_id,))
            conn.commit()

    def get_allowed_groups(self) -> list:
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT chat_id FROM allowed_groups")
                return [row['chat_id'] for row in cur.fetchall()]

    # ── Download log ───────────────────────────────────────

    def log_download(self, filename: str, file_size: int, chat_id: int):
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO download_log (filename, file_size, chat_id) "
                    "VALUES (%s, %s, %s)",
                    (filename, file_size, chat_id)
                )
            conn.commit()

    # ── Pagos NOWPayments ──────────────────────────────────

    def create_payment(self, user_id: int, invoice_id: str, order_id: str,
                       days: int, amount_usd: float, status: str, lang: str = 'es'):
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                # Evitar duplicados: si ya existe el invoice_id, no insertar de nuevo
                cur.execute("SELECT id FROM payments WHERE invoice_id = %s", (invoice_id,))
                if cur.fetchone():
                    logger.warning(f"create_payment: invoice_id {invoice_id} ya existe en DB, saltando")
                    return
                cur.execute(
                    "INSERT INTO payments (user_id, invoice_id, order_id, days, amount_usd, status, lang) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (user_id, invoice_id, order_id, days, amount_usd, status, lang)
                )
            conn.commit()

    def get_pending_payments(self) -> List[dict]:
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM payments WHERE status = 'pending'")
                return cur.fetchall()

    def update_payment_status(self, invoice_id: str, status: str):
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                now = datetime.now(timezone.utc).isoformat()
                cur.execute(
                    "UPDATE payments SET status = %s, updated_at = %s WHERE invoice_id = %s",
                    (status, now, invoice_id)
                )
            conn.commit()

    def get_user_payments(self, user_id: int) -> List[dict]:
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM payments WHERE user_id = %s "
                    "ORDER BY created_at DESC LIMIT 5",
                    (user_id,)
                )
                return cur.fetchall()

    # ── Shutdown ───────────────────────────────────────────

    def close(self):
        """Cerrar el pool de conexiones ordenadamente (shutdown)."""
        try:
            self.pool.close()
            logger.info("Pool de PostgreSQL cerrado correctamente")
        except Exception as e:
            logger.warning(f"Error cerrando pool de PostgreSQL: {e}")


# ── Instancia global ────────────────────────────────────────
#  Se inicializa con la DATABASE_URL del .env (Neon, Supabase, etc.)
#  Si no hay URL, falla temprano con un mensaje claro.
db = Database(config.DATABASE_URL)
