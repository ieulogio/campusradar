"""Lógica de negocio de moderación: resolución de denuncias y acciones de control."""

from __future__ import annotations

from sqlalchemy.orm import Session

from .. import models


class ModeracionError(Exception):
    pass


def listar_denuncias(db: Session, solo_pendientes: bool = True) -> list[models.Denuncia]:
    query = db.query(models.Denuncia)
    if solo_pendientes:
        query = query.filter(models.Denuncia.estado == "Pendiente")
    return query.order_by(models.Denuncia.fecha_creacion.desc()).all()


def resolver_denuncia(
    db: Session, moderador: models.Usuario, denuncia_id: int, nuevo_estado: str
) -> models.Denuncia:
    if not moderador.puede("resolver_denuncia"):
        raise ModeracionError("No tienes permiso para moderar.")
    if nuevo_estado not in ("Aceptada", "Rechazada"):
        raise ModeracionError("Estado de resolución inválido.")

    denuncia = db.get(models.Denuncia, denuncia_id)
    if denuncia is None:
        raise ModeracionError("La denuncia no existe.")

    denuncia.estado = nuevo_estado
    # Si se acepta la denuncia, el reporte se archiva (manejo de contenido inválido).
    if nuevo_estado == "Aceptada":
        denuncia.reporte.estado_interno = "Archivado"
    db.commit()
    db.refresh(denuncia)
    return denuncia


def archivar_reporte(
    db: Session, moderador: models.Usuario, reporte_id: int
) -> models.Reporte:
    if not moderador.puede("archivar_reporte"):
        raise ModeracionError("No tienes permiso para archivar reportes.")
    reporte = db.get(models.Reporte, reporte_id)
    if reporte is None:
        raise ModeracionError("El reporte no existe.")
    reporte.estado_interno = "Archivado"
    db.commit()
    db.refresh(reporte)
    return reporte


def forzar_estado(
    db: Session, moderador: models.Usuario, reporte_id: int, estado: str
) -> models.Reporte:
    if not moderador.puede("forzar_estado"):
        raise ModeracionError("No tienes permiso para cambiar el estado.")
    from ..domain import estados as dom_estados

    if estado not in dom_estados.ESTADOS_VALIDOS:
        raise ModeracionError("Estado inválido.")
    reporte = db.get(models.Reporte, reporte_id)
    if reporte is None:
        raise ModeracionError("El reporte no existe.")
    reporte.estado_interno = estado
    db.commit()
    db.refresh(reporte)
    return reporte
