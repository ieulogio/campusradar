"""Router de reportes: feed, creación, interacciones sociales y búsqueda."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_user
from ..services import moderacion_service, reporte_service
from ..services.serializers import reporte_out

router = APIRouter(prefix="/api/reportes", tags=["reportes"])


@router.get("", response_model=list[schemas.ReporteOut])
def listar(
    tipo: str | None = None,
    estado: str | None = None,
    edificio: str | None = None,
    piso: int | None = None,
    tag: str | None = None,
    q: str | None = None,
    mios: bool = False,
    incluir_inactivos: bool = False,
    orden: str = Query("relevancia", pattern="^(relevancia|reciente)$"),
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user),
):
    reportes = reporte_service.listar_reportes(
        db,
        tipo=tipo,
        estado=estado,
        edificio=edificio,
        piso=piso,
        tag=tag,
        q=q,
        autor_id=usuario.id if mios else None,
        incluir_inactivos=incluir_inactivos,
        orden=orden,
    )
    return [reporte_out(r) for r in reportes]


@router.post("", response_model=schemas.ReporteOut, status_code=201)
def crear(
    datos: schemas.ReporteIn,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(get_current_user),
):
    try:
        reporte = reporte_service.crear_reporte(
            db,
            usuario,
            datos.titulo,
            datos.descripcion,
            datos.tipo,
            datos.ubicacion.edificio,
            datos.ubicacion.piso,
            datos.ubicacion.lat,
            datos.ubicacion.lon,
            datos.tags,
        )
    except reporte_service.ReporteError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return reporte_out(reporte)


@router.get("/{reporte_id}", response_model=schemas.ReporteOut)
def detalle(reporte_id: int, db: Session = Depends(get_db),
            usuario: models.Usuario = Depends(get_current_user)):
    reporte = db.get(models.Reporte, reporte_id)
    if reporte is None:
        raise HTTPException(status_code=404, detail="Reporte no encontrado.")
    return reporte_out(reporte)


@router.post("/{reporte_id}/confirmar", response_model=schemas.ReporteOut)
def confirmar(reporte_id: int, db: Session = Depends(get_db),
              usuario: models.Usuario = Depends(get_current_user)):
    try:
        reporte = reporte_service.confirmar(db, usuario, reporte_id)
    except reporte_service.ReporteError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return reporte_out(reporte)


@router.post("/{reporte_id}/desmentir", response_model=schemas.ReporteOut)
def desmentir(reporte_id: int, db: Session = Depends(get_db),
              usuario: models.Usuario = Depends(get_current_user)):
    try:
        reporte = reporte_service.desmentir(db, usuario, reporte_id)
    except reporte_service.ReporteError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return reporte_out(reporte)


@router.get("/{reporte_id}/comentarios", response_model=list[schemas.ComentarioOut])
def listar_comentarios(reporte_id: int, db: Session = Depends(get_db),
                       usuario: models.Usuario = Depends(get_current_user)):
    reporte = db.get(models.Reporte, reporte_id)
    if reporte is None:
        raise HTTPException(status_code=404, detail="Reporte no encontrado.")
    return sorted(reporte.comentarios, key=lambda c: c.fecha_creacion)


@router.post("/{reporte_id}/comentarios", response_model=schemas.ComentarioOut, status_code=201)
def comentar(reporte_id: int, datos: schemas.ComentarioIn,
             db: Session = Depends(get_db),
             usuario: models.Usuario = Depends(get_current_user)):
    try:
        comentario = reporte_service.comentar(db, usuario, reporte_id, datos.contenido)
    except reporte_service.ReporteError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return comentario


@router.post("/{reporte_id}/denunciar", status_code=201)
def denunciar(reporte_id: int, datos: schemas.DenunciaIn,
              db: Session = Depends(get_db),
              usuario: models.Usuario = Depends(get_current_user)):
    try:
        reporte_service.denunciar(db, usuario, reporte_id, datos.razon)
    except reporte_service.ReporteError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"detail": "Denuncia registrada. Un moderador la revisará."}


# ---------------------- Acciones de moderación ----------------------- #
@router.post("/{reporte_id}/archivar", response_model=schemas.ReporteOut)
def archivar(reporte_id: int, db: Session = Depends(get_db),
             usuario: models.Usuario = Depends(get_current_user)):
    try:
        reporte = moderacion_service.archivar_reporte(db, usuario, reporte_id)
    except moderacion_service.ModeracionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    return reporte_out(reporte)


@router.post("/{reporte_id}/estado", response_model=schemas.ReporteOut)
def forzar_estado(reporte_id: int, datos: schemas.EstadoForzadoIn,
                  db: Session = Depends(get_db),
                  usuario: models.Usuario = Depends(get_current_user)):
    try:
        reporte = moderacion_service.forzar_estado(db, usuario, reporte_id, datos.estado)
    except moderacion_service.ModeracionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    return reporte_out(reporte)
