"""
═══════════════════════════════════════════════════════════════
  HJ ULP EXTRACTOR BOT — Roles & Permissions Module
═══════════════════════════════════════════════════════════════
"""

from enum import Enum
from datetime import datetime, timezone

from config import config
from database import db


class UserRole(Enum):
    ADMIN = "ADMIN"
    SELLER = "SELLER"
    VIP = "VIP"
    FREE = "FREE"


class SearchMode(Enum):
    ULP = "ULP"
    MAIL = "MAIL:PASS"
    USERPASS = "USER:PASS"


def get_user_role(uid: int) -> UserRole:
    """Obtener el rol de un usuario."""
    if uid in config.ADMIN_IDS:
        return UserRole.ADMIN
    user = db.get_user(uid)
    role_str = user.get('role', 'FREE')
    if role_str == 'SELLER':
        return UserRole.SELLER
    if role_str == 'VIP':
        exp = user.get('vip_expiry')
        if exp:
            try:
                # FIX #12: fromisoformat() no parsea timezone en Python <3.11
                # Reemplazar +00:00 con Z para compatibilidad, o usar fromisoformat directamente
                exp_clean = exp.replace('+00:00', '+00:00')
                dt = datetime.fromisoformat(exp_clean)
                if dt.tzinfo is None:
                    # Si no tiene timezone, asumir UTC
                    dt = dt.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) < dt:
                    return UserRole.VIP
            except Exception:
                pass
    return UserRole.FREE
