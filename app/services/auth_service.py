"""Lógica de negocio de autenticación y registro de usuarios."""

from __future__ import annotations

from sqlalchemy.orm import Session

from .. import models, security


class AuthError(Exception):
    """Error de autenticación / registro (email duplicado, credenciales malas)."""


def registrar_estudiante(
    db: Session, nombre: str, apellido: str, email: str, password: str, carrera: str
) -> models.Usuario:
    existe = db.query(models.Usuario).filter(models.Usuario.email == email).first()
    if existe:
        raise AuthError("Ya existe un usuario con ese email.")

    usuario = models.Estudiante(
        nombre=nombre,
        apellido=apellido,
        email=email,
        password_hash=security.hash_password(password),
        carrera=carrera,
        rol="estudiante",
        reputacion=0,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


def autenticar(db: Session, email: str, password: str) -> models.Usuario:
    usuario = db.query(models.Usuario).filter(models.Usuario.email == email).first()
    if usuario is None or not security.verify_password(password, usuario.password_hash):
        raise AuthError("Email o contraseña incorrectos.")
    if not usuario.activo:
        raise AuthError("La cuenta está deshabilitada.")
    return usuario
