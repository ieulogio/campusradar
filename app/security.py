"""Seguridad: hashing de contraseñas (bcrypt) y tokens JWT.

Autenticación básica según lo pedido por el proyecto. No se evalúan aspectos
avanzados de seguridad informática, pero usamos primitivas estándar correctas.
"""

from __future__ import annotations

import datetime

import bcrypt
from jose import JWTError, jwt

from .config import settings


def hash_password(password: str) -> str:
    """Genera un hash bcrypt de la contraseña."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verifica una contraseña en texto plano contra su hash almacenado."""
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"), password_hash.encode("utf-8")
        )
    except (ValueError, TypeError):
        return False


def crear_token(usuario_id: int) -> str:
    """Crea un JWT firmado con el id del usuario y una expiración."""
    expira = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": str(usuario_id), "exp": expira}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decodificar_token(token: str) -> int | None:
    """Devuelve el id del usuario contenido en el token, o None si es inválido."""
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        sub = payload.get("sub")
        return int(sub) if sub is not None else None
    except (JWTError, ValueError):
        return None
