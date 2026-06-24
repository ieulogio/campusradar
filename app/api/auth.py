"""Router de autenticación: registro, login y perfil del usuario actual."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from .. import models, schemas, security
from ..database import get_db
from ..deps import get_current_user
from ..services import auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=schemas.TokenOut, status_code=201)
def registrar(datos: schemas.RegistroIn, db: Session = Depends(get_db)):
    try:
        usuario = auth_service.registrar_estudiante(
            db,
            datos.nombre,
            datos.apellido,
            datos.email,
            datos.password,
            datos.carrera,
        )
    except auth_service.AuthError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return schemas.TokenOut(access_token=security.crear_token(usuario.id))


@router.post("/login", response_model=schemas.TokenOut)
def login(
    form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    """Login compatible con OAuth2 password flow (username = email)."""
    try:
        usuario = auth_service.autenticar(db, form.username, form.password)
    except auth_service.AuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)
        )
    return schemas.TokenOut(access_token=security.crear_token(usuario.id))


@router.get("/me", response_model=schemas.UsuarioOut)
def perfil(usuario: models.Usuario = Depends(get_current_user)):
    return usuario
