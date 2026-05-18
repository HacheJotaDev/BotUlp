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
                if datetime.now(timezone.utc) < datetime.fromisoformat(exp):
                    return UserRole.VIP
            except Exception:
                pass
    return UserRole.FREE
