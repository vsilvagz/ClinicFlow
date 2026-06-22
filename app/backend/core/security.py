"""Primitivas de seguridad: hashing de contraseñas y tokens de sesión.

Aísla las librerías de seguridad (passlib para el hash bcrypt, python-jose para
los JWT) detrás de funciones simples, de modo que el resto del sistema no dependa
directamente de ellas. La clave de firma y la expiración salen de la
configuración central.
"""

from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.backend.core.config import settings

_ALGORITMO = "HS256"


def hash_password(plano: str) -> str:
    """Devuelve el hash bcrypt de una contraseña en texto plano.

    bcrypt agrega una "sal" aleatoria, así que dos contraseñas iguales producen
    hashes distintos. El algoritmo solo considera los primeros 72 bytes.
    """
    return bcrypt.hashpw(plano.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def verificar_password(plano: str, hash_: str) -> bool:
    """Compara una contraseña en texto plano contra su hash almacenado."""
    if not hash_:
        return False
    try:
        return bcrypt.checkpw(plano.encode("utf-8")[:72], hash_.encode("utf-8"))
    except ValueError:
        return False


def crear_token(sub: str) -> str:
    """Crea un JWT firmado cuyo `sub` identifica al usuario (su RUN)."""
    expira = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    return jwt.encode({"sub": sub, "exp": expira}, settings.secret_key, algorithm=_ALGORITMO)


def leer_token(token: str) -> str | None:
    """Valida un JWT y devuelve su `sub`, o None si es inválido o expiró."""
    try:
        datos = jwt.decode(token, settings.secret_key, algorithms=[_ALGORITMO])
    except JWTError:
        return None
    return datos.get("sub")
