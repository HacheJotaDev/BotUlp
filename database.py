"""
═══════════════════════════════════════════════════════════════
  HJ ULP EXTRACTOR BOT — Database Module
═══════════════════════════════════════════════════════════════
"""

import sqlite3
import random
import string
import threading
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Dict, List

from config import config
from logger_setup import logger


class Database:
    """Base de datos SQLite con WAL mode para maximo rendimiento concurrente.

    FIX: threading.Lock protege todas las escrituras para evitar
    'database is locked' cuando asyncio.gather ejecuta writes en paralelo.
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("PRAGMA cache_size=-64000")
        self.conn.execute("PRAGMA temp_store=MEMORY")
        self._init_schema()

    def _init_schema(self):
        c = self.conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            role TEXT DEFAULT 'FREE',
            vip_expiry TEXT,
            search_count INTEGER DEFAULT 0,
            language TEXT DEFAULT 'es',
            first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
            last_active TEXT DEFAULT CURRENT_TIMESTAMP,
            free_search_used INTEGER DEFAULT 0
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS keys (
            key_code TEXT PRIMARY KEY,
            days INTEGER,
            created_by INTEGER,
            used_by INTEGER,
            is_used INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS download_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            file_size INTEGER DEFAULT 0,
            chat_id INTEGER,
            downloaded_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS allowed_groups (
            chat_id INTEGER PRIMARY KEY,
            added_by INTEGER,
            added_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            invoice_id TEXT NOT NULL,
            order_id TEXT,
            days INTEGER,
            amount_usd REAL,
            status TEXT DEFAULT 'pending',
            lang TEXT DEFAULT 'es',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")

        # Indices para performance (evita full-scan cada 30s en polling)
        try:
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status)")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_payments_invoice_id ON payments(invoice_id)")
        except Exception as e:
            logger.warning(f"Error creando indices: {e}")

        # Migraciones
        c.execute("PRAGMA table_info(users)")
        columns = [info[1] for info in c.fetchall()]

        migrations = [
            ('language', "ALTER TABLE users ADD COLUMN language TEXT DEFAULT 'es'"),
            ('first_seen', "ALTER TABLE users ADD COLUMN first_seen TEXT DEFAULT CURRENT_TIMESTAMP"),
            ('last_active', "ALTER TABLE users ADD COLUMN last_active TEXT DEFAULT CURRENT_TIMESTAMP"),
            ('free_search_used', "ALTER TABLE users ADD COLUMN free_search_used INTEGER DEFAULT 0"),
        ]
        for col_name, alter_sql in migrations:
            if col_name not in columns:
                logger.info(f"Migrando DB: agregando columna '{col_name}'...")
                try:
                    c.execute(alter_sql)
                    self.conn.commit()
                    logger.info(f"Columna '{col_name}' agregada correctamente.")
                except Exception as e:
                    logger.error(f"Error migrando DB: {e}")

        self.conn.commit()

    def get_user(self, uid: int) -> dict:
        c = self.conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id = ?", (uid,))
        row = c.fetchone()
        if not row:
            now = datetime.now(timezone.utc).isoformat()
            c.execute(
                "INSERT INTO users (user_id, first_seen, last_active) VALUES (?, ?, ?)",
                (uid, now, now)
            )
            self.conn.commit()
            return {
                'user_id': uid, 'role': 'FREE', 'vip_expiry': None,
                'search_count': 0, 'language': 'es',
                'first_seen': now, 'last_active': now,
                'free_search_used': 0
            }
        try:
            c.execute(
                "UPDATE users SET last_active = ? WHERE user_id = ?",
                (datetime.now(timezone.utc).isoformat(), uid)
            )
            self.conn.commit()
        except Exception:
            pass
        return dict(row)

    def is_new_user(self, uid: int) -> bool:
        """Verificar si el usuario es nuevo (nunca ha usado su busqueda gratis)."""
        user = self.get_user(uid)
        return user.get('free_search_used', 0) == 0

    def mark_free_search_used(self, uid: int):
        """Marcar que el usuario ya uso su busqueda gratis."""
        with self._lock:
            c = self.conn.cursor()
            c.execute(
                "UPDATE users SET free_search_used = 1, search_count = search_count + 1 WHERE user_id = ?",
                (uid,)
            )
            self.conn.commit()

    def set_language(self, uid: int, lang: str):
        with self._lock:
            c = self.conn.cursor()
            c.execute("UPDATE users SET language = ? WHERE user_id = ?", (lang, uid))
            self.conn.commit()

    def set_role(self, uid: int, role: str, days: int = 0):
        expiry = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat() if role == 'VIP' else None
        with self._lock:
            c = self.conn.cursor()
            c.execute(
                "INSERT INTO users (user_id, role, vip_expiry) VALUES (?, ?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET role=excluded.role, vip_expiry=excluded.vip_expiry",
                (uid, role, expiry)
            )
            self.conn.commit()

    def remove_vip(self, uid: int):
        with self._lock:
            c = self.conn.cursor()
            c.execute("UPDATE users SET role='FREE', vip_expiry=NULL WHERE user_id=?", (uid,))
            self.conn.commit()

    def gen_key(self, creator: int, days: int) -> str:
        code = f"HJ-{''.join(random.choices(string.ascii_uppercase + string.digits, k=12))}"
        with self._lock:
            c = self.conn.cursor()
            c.execute(
                "INSERT INTO keys (key_code, days, created_by) VALUES (?, ?, ?)",
                (code, days, creator)
            )
            self.conn.commit()
        return code

    def redeem(self, uid: int, code: str) -> bool:
        with self._lock:
            c = self.conn.cursor()
            c.execute("SELECT days FROM keys WHERE key_code = ? AND is_used = 0", (code,))
            row = c.fetchone()
            if not row:
                return False
            days = row['days']
            now = datetime.now(timezone.utc)
            c.execute("SELECT vip_expiry FROM users WHERE user_id = ?", (uid,))
            user_row = c.fetchone()
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
            c.execute("UPDATE keys SET is_used = 1, used_by = ? WHERE key_code = ?", (uid, code))
            c.execute(
                "INSERT INTO users (user_id, role, vip_expiry) VALUES (?, 'VIP', ?) "
                "ON CONFLICT(user_id) DO UPDATE SET role='VIP', vip_expiry=excluded.vip_expiry",
                (uid, expiry)
            )
            self.conn.commit()
        return True

    def add_search(self, uid: int):
        with self._lock:
            c = self.conn.cursor()
            c.execute("UPDATE users SET search_count = search_count + 1 WHERE user_id = ?", (uid,))
            self.conn.commit()

    def get_stats(self) -> dict:
        self.cleanup_expired_vips()
        c = self.conn.cursor()
        c.execute("SELECT COUNT(*) FROM users WHERE role='VIP'")
        vips = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM users WHERE role='SELLER'")
        sellers = c.fetchone()[0]
        c.execute("SELECT SUM(search_count) FROM users")
        total_searches = c.fetchone()[0] or 0
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM users WHERE free_search_used = 0")
        new_users = c.fetchone()[0]
        return {
            'vips': vips, 'sellers': sellers,
            'searches': total_searches, 'total_users': total_users,
            'new_users': new_users
        }

    def cleanup_expired_vips(self) -> int:
        """Cambiar a FREE los VIPs cuya fecha de expiracion ya paso. Retorna la cantidad limpiada."""
        with self._lock:
            c = self.conn.cursor()
            now_iso = datetime.now(timezone.utc).isoformat()
            c.execute(
                "UPDATE users SET role='FREE', vip_expiry=NULL "
                "WHERE role='VIP' AND vip_expiry IS NOT NULL AND vip_expiry < ?",
                (now_iso,)
            )
            count = c.rowcount
            if count > 0:
                self.conn.commit()
                logger.info(f"VIPs expirados limpiados: {count}")
        return count

    def list_vips(self) -> List[dict]:
        self.cleanup_expired_vips()
        c = self.conn.cursor()
        c.execute("SELECT user_id, vip_expiry, search_count FROM users WHERE role='VIP' OR role='SELLER'")
        return [dict(r) for r in c.fetchall()]

    def list_sellers(self) -> List[int]:
        c = self.conn.cursor()
        c.execute("SELECT user_id FROM users WHERE role='SELLER'")
        return [r['user_id'] for r in c.fetchall()]

    def get_all_users(self) -> List[int]:
        c = self.conn.cursor()
        c.execute("SELECT user_id FROM users")
        return [row[0] for row in c.fetchall()]

    def add_allowed_group(self, chat_id: int, added_by: int):
        with self._lock:
            c = self.conn.cursor()
            c.execute(
                "INSERT OR IGNORE INTO allowed_groups (chat_id, added_by) VALUES (?, ?)",
                (chat_id, added_by)
            )
            self.conn.commit()

    def remove_allowed_group(self, chat_id: int):
        with self._lock:
            c = self.conn.cursor()
            c.execute("DELETE FROM allowed_groups WHERE chat_id = ?", (chat_id,))
            self.conn.commit()

    def get_allowed_groups(self) -> list:
        c = self.conn.cursor()
        c.execute("SELECT chat_id FROM allowed_groups")
        return [row['chat_id'] for row in c.fetchall()]

    def log_download(self, filename: str, file_size: int, chat_id: int):
        with self._lock:
            c = self.conn.cursor()
            c.execute(
                "INSERT INTO download_log (filename, file_size, chat_id) VALUES (?, ?, ?)",
                (filename, file_size, chat_id)
            )
            self.conn.commit()

    # ── Pagos NOWPayments ──

    def create_payment(self, user_id: int, invoice_id: str, order_id: str,
                       days: int, amount_usd: float, status: str, lang: str = 'es'):
        with self._lock:
            c = self.conn.cursor()
            c.execute(
                "INSERT INTO payments (user_id, invoice_id, order_id, days, amount_usd, status, lang) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, invoice_id, order_id, days, amount_usd, status, lang)
            )
            self.conn.commit()

    def get_pending_payments(self) -> List[dict]:
        c = self.conn.cursor()
        c.execute("SELECT * FROM payments WHERE status = 'pending'")
        return [dict(r) for r in c.fetchall()]

    def update_payment_status(self, invoice_id: str, status: str):
        with self._lock:
            c = self.conn.cursor()
            now = datetime.now(timezone.utc).isoformat()
            c.execute(
                "UPDATE payments SET status = ?, updated_at = ? WHERE invoice_id = ?",
                (status, now, invoice_id)
            )
            self.conn.commit()

    def get_user_payments(self, user_id: int) -> List[dict]:
        c = self.conn.cursor()
        c.execute(
            "SELECT * FROM payments WHERE user_id = ? ORDER BY created_at DESC LIMIT 5",
            (user_id,)
        )
        return [dict(r) for r in c.fetchall()]


db = Database(config.DB_FILE)