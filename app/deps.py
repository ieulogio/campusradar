"""Dependencias de FastAPI: obtención del usuario autenticado desde el JWT."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from . import models, security
from .database import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login", auto_error=False)


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.Usuario:
    """Resuelve el usuario actual a partir del token Bearer."""
    credenciales_invalidas = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No autenticado.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credenciales_invalidas

    usuario_id = security.decodificar_token(token)
    if usuario_id is None:
        raise credenciales_invalidas

    usuario = db.get(models.Usuario, usuario_id)
    if usuario is None or not usuario.activo:
        raise credenciales_invalidas
    return usuario


def require_moderador(
    usuario: models.Usuario = Depends(get_current_user),
) -> models.Usuario:
    """Restringe el acceso a moderadores y administradores."""
    if not usuario.puede("moderar"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requiere permisos de moderación.",
        )
    return usuario
