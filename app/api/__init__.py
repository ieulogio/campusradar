"""Routers complementarios: usuarios, tags/suscripciones, notificaciones,
moderación y estadísticas."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_user, require_moderador
from ..services import moderacion_service, reporte_service
from ..services.serializers import usuario_publico

# ------------------------------ Usuarios ----------------------------- #
usuarios_router = APIRouter(prefix="/api/usuarios", tags=["usuarios"])


@usuarios_router.get("", response_model=list[schemas.UsuarioPublico])
def comunidad(db: Session = Depends(get_db),
              usuario: models.Usuario = Depends(get_current_user)):
    usuarios = (
        db.query(models.Usuario)
        .order_by(models.Usuario.reputacion.desc())
        .all()
    )
    return [usuario_publico(u) for u in usuarios]


# ------------------------- Tags y suscripciones ---------------------- #
tags_router = APIRouter(prefix="/api", tags=["tags"])


@tags_router.get("/tags")
def listar_tags(db: Session = Depends(get_db),
                usuario: models.Usuario = Depends(get_current_user)):
    tags = db.query(models.Tag).all()
    seguidos = {t.id for t in usuario.tags_seguidos}
    return [
        {"nombre_tag": t.nombre_tag, "seguido": t.id in seguidos}
        for t in tags
    ]


@tags_router.post("/suscripciones", status_code=201)
def suscribir(datos: schemas.SuscripcionIn, db: Session = Depends(get_db),
              usuario: models.Usuario = Depends(get_current_user)):
    reporte_service.suscribir_a_tag(db, usuario, datos.nombre_tag)
    return {"detail": f"Suscrito al tag #{datos.nombre_tag.lower()}"}


# ---------------------------- Notificaciones ------------------------- #
notif_router = APIRouter(prefix="/api/notificaciones", tags=["notificaciones"])


@notif_router.get("", response_model=list[schemas.NotificacionOut])
def mis_notificaciones(db: Session = Depends(get_db),
                       usuario: models.Usuario = Depends(get_current_user)):
    return (
        db.query(models.Notificacion)
        .filter(models.Notificacion.destinatario_id == usuario.id)
        .order_by(models.Notificacion.fecha_creacion.desc())
        .all()
    )


@notif_router.post("/{notif_id}/leer")
def marcar_leida(notif_id: int, db: Session = Depends(get_db),
                 usuario: models.Usuario = Depends(get_current_user)):
    notif = db.get(models.Notificacion, notif_id)
    if notif is None or notif.destinatario_id != usuario.id:
        raise HTTPException(status_code=404, detail="Notificación no encontrada.")
    notif.leido = True
    db.commit()
    return {"detail": "Notificación marcada como leída."}


# ------------------------------ Moderación --------------------------- #
moderacion_router = APIRouter(prefix="/api/moderacion", tags=["moderacion"])


@moderacion_router.get("/denuncias", response_model=list[schemas.DenunciaOut])
def denuncias(solo_pendientes: bool = True, db: Session = Depends(get_db),
              moderador: models.Usuario = Depends(require_moderador)):
    return moderacion_service.listar_denuncias(db, solo_pendientes)


@moderacion_router.post("/denuncias/{denuncia_id}/resolver",
                        response_model=schemas.DenunciaOut)
def resolver(denuncia_id: int, datos: schemas.ResolverDenunciaIn,
             db: Session = Depends(get_db),
             moderador: models.Usuario = Depends(require_moderador)):
    try:
        return moderacion_service.resolver_denuncia(
            db, moderador, denuncia_id, datos.estado
        )
    except moderacion_service.ModeracionError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ----------------------------- Estadísticas -------------------------- #
stats_router = APIRouter(prefix="/api", tags=["stats"])


@stats_router.get("/stats", response_model=schemas.StatsOut)
def estadisticas(db: Session = Depends(get_db),
                 usuario: models.Usuario = Depends(get_current_user)):
    reportes = db.query(models.Reporte).all()
    activos = [r for r in reportes if r.activo]
    return schemas.StatsOut(
        reportes_activos=len(activos),
        verificados=sum(1 for r in activos if r.estado == "Verificado"),
        criticos=sum(1 for r in activos if r.estado == "Critico"),
        usuarios=db.query(models.Usuario).count(),
    )
