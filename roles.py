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
    # Rango máximo (definido por config.ADMIN_IDS). Se muestra como OWNER.
    OWNER = "OWNER"
    # Alias de compatibilidad: UserRole.ADMIN es exactamente UserRole.OWNER
    ADMIN = "OWNER"
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
                dt = datetime.fromisoformat(exp)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) < dt:
                    return UserRole.VIP
            except Exception:
                pass
    return UserRole.FREE


def can_search(uid: int) -> bool:
    """Verificar si un usuario puede realizar busquedas.
    
    Usuarios VIP, SELLER y ADMIN siempre pueden.
    Usuarios FREE pueden si aun no usaron su busqueda gratis.
    """
    role = get_user_role(uid)
    if role in (UserRole.VIP, UserRole.SELLER, UserRole.ADMIN):
        return True
    if role == UserRole.FREE:
        return db.is_new_user(uid)
    return False