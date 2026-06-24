"""
Lógica de negocio de reportes e interacciones.

Orquesta el dominio y la persistencia: aplica reglas de reputación, dispara
notificaciones por suscripción a tags, gestiona el consenso comunitario y la
búsqueda/filtrado del feed. Las reglas "puras" (estado, niveles, relevancia)
viven en `app.domain`; aquí se coordinan los efectos secundarios y el acceso
a datos.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from .. import models
from ..domain import reportes as dom_reportes

# Puntos de reputación por cada acción (reglas de negocio centralizadas).
REP_CREAR = 3
REP_CONFIRMAR_ACTOR = 2
REP_COMENTAR = 1
REP_AUTOR_CONFIRMADO = 5
REP_AUTOR_DESMENTIDO = -5


class ReporteError(Exception):
    """Error de regla de negocio sobre reportes (interacción inválida, etc.)."""


# --------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------- #
def _get_or_create_tag(db: Session, nombre: str) -> models.Tag:
    nombre = nombre.strip().lower()
    tag = db.query(models.Tag).filter(models.Tag.nombre_tag == nombre).first()
    if tag is None:
        tag = models.Tag(nombre_tag=nombre)
        db.add(tag)
        db.flush()
    return tag


def _crear_notificacion(db: Session, destinatario: models.Usuario, mensaje: str) -> None:
    db.add(models.Notificacion(destinatario_id=destinatario.id, mensaje=mensaje))


def _notificar_suscriptores(db: Session, reporte: models.Reporte) -> None:
    """Notifica a los usuarios suscritos a cualquiera de los tags del reporte."""
    notificados: set[int] = set()
    for tag in reporte.tags:
        suscriptores = (
            db.query(models.Usuario)
            .filter(models.Usuario.tags_seguidos.any(models.Tag.id == tag.id))
            .all()
        )
        for usuario in suscriptores:
            if usuario.id == reporte.autor_id or usuario.id in notificados:
                continue
            notificados.add(usuario.id)
            _crear_notificacion(
                db,
                usuario,
                f"Nuevo reporte [{reporte.tipo}] con #{tag.nombre_tag}: {reporte.titulo}",
            )


# --------------------------------------------------------------------- #
# Casos de uso
# --------------------------------------------------------------------- #
def crear_reporte(
    db: Session,
    autor: models.Usuario,
    titulo: str,
    descripcion: str,
    tipo: str,
    edificio: str,
    piso: int,
    lat: float,
    lon: float,
    tags: list[str],
) -> models.Reporte:
    if not autor.puede("crear_reporte"):
        raise ReporteError("No tienes permiso para crear reportes.")

    cls_dominio = dom_reportes.TIPOS_REPORTE.get(tipo)
    if cls_dominio is None:
        raise ReporteError(f"Tipo de reporte inválido: {tipo}")

    ubicacion = models.Ubicacion(edificio=edificio, piso=piso, lat=lat, lon=lon)
    db.add(ubicacion)
    db.flush()

    # El subtipo de dominio define la duración de vida y el estado inicial.
    modelo_orm = {
        "Infraestructura": models.ReporteInfraestructura,
        "Emergencia": models.ReporteEmergencia,
        "Evento": models.ReporteEvento,
        "Logistica": models.ReporteLogistica,
        "Actividad": models.ReporteActividad,
    }[tipo]

    reporte = modelo_orm(
        titulo=titulo,
        descripcion=descripcion,
        tipo=tipo,
        estado_interno=cls_dominio.ESTADO_INICIAL,
        duracion_horas=cls_dominio.DURACION_DEFAULT,
        autor_id=autor.id,
        ubicacion_id=ubicacion.id,
    )
    for nombre_tag in tags:
        if nombre_tag.strip():
            reporte.tags.append(_get_or_create_tag(db, nombre_tag))

    db.add(reporte)
    db.flush()

    # Efectos secundarios: reputación + notificaciones a suscriptores.
    autor.reputacion = max(0, autor.reputacion + REP_CREAR)
    _notificar_suscriptores(db, reporte)

    db.commit()
    db.refresh(reporte)
    return reporte


def _buscar_reporte(db: Session, reporte_id: int) -> models.Reporte:
    reporte = db.get(models.Reporte, reporte_id)
    if reporte is None:
        raise ReporteError("El reporte no existe.")
    return reporte


def confirmar(db: Session, usuario: models.Usuario, reporte_id: int) -> models.Reporte:
    reporte = _buscar_reporte(db, reporte_id)
    if not reporte.activo:
        raise ReporteError("El reporte ya expiró o fue archivado.")
    if usuario in reporte.confirmaciones:
        raise ReporteError("Ya confirmaste este reporte.")
    if usuario in reporte.desmentidos:
        raise ReporteError("Ya desmentiste este reporte; no puedes confirmar.")

    reporte.confirmaciones.append(usuario)
    reporte.autor.reputacion = max(0, reporte.autor.reputacion + REP_AUTOR_CONFIRMADO)
    usuario.reputacion = max(0, usuario.reputacion + REP_CONFIRMAR_ACTOR)
    reporte.recalcular_estado()

    db.commit()
    db.refresh(reporte)
    return reporte


def desmentir(db: Session, usuario: models.Usuario, reporte_id: int) -> models.Reporte:
    reporte = _buscar_reporte(db, reporte_id)
    if not reporte.activo:
        raise ReporteError("El reporte ya expiró o fue archivado.")
    if usuario in reporte.desmentidos:
        raise ReporteError("Ya desmentiste este reporte.")
    if usuario in reporte.confirmaciones:
        raise ReporteError("Ya confirmaste este reporte; no puedes desmentir.")

    reporte.desmentidos.append(usuario)
    reporte.autor.reputacion = max(0, reporte.autor.reputacion + REP_AUTOR_DESMENTIDO)
    reporte.recalcular_estado()

    db.commit()
    db.refresh(reporte)
    return reporte


def comentar(
    db: Session, usuario: models.Usuario, reporte_id: int, contenido: str
) -> models.Comentario:
    reporte = _buscar_reporte(db, reporte_id)
    if not reporte.activo:
        raise ReporteError("No se puede comentar un reporte inactivo.")

    comentario = models.Comentario(
        contenido=contenido, reporte_id=reporte.id, autor_id=usuario.id
    )
    db.add(comentario)
    usuario.reputacion = max(0, usuario.reputacion + REP_COMENTAR)
    db.commit()
    db.refresh(comentario)
    return comentario


def denunciar(
    db: Session, usuario: models.Usuario, reporte_id: int, razon: str
) -> models.Denuncia:
    reporte = _buscar_reporte(db, reporte_id)
    denuncia = models.Denuncia(
        razon=razon, reporte_id=reporte.id, denunciante_id=usuario.id
    )
    db.add(denuncia)
    db.commit()
    db.refresh(denuncia)
    return denuncia


def suscribir_a_tag(db: Session, usuario: models.Usuario, nombre_tag: str) -> None:
    tag = _get_or_create_tag(db, nombre_tag)
    if tag not in usuario.tags_seguidos:
        usuario.tags_seguidos.append(tag)
        db.commit()


# --------------------------------------------------------------------- #
# Búsqueda, filtrado y organización del feed (Sección 3.4 del proyecto)
# --------------------------------------------------------------------- #
def listar_reportes(
    db: Session,
    *,
    tipo: str | None = None,
    estado: str | None = None,
    edificio: str | None = None,
    piso: int | None = None,
    tag: str | None = None,
    q: str | None = None,
    autor_id: int | None = None,
    incluir_inactivos: bool = False,
    orden: str = "relevancia",
) -> list[models.Reporte]:
    """Devuelve el feed aplicando filtros en memoria sobre el estado perezoso.

    El estado se calcula al vuelo (lazy), por lo que el filtrado por estado e
    inactividad se resuelve en Python tras leer la propiedad `estado`.
    """
    reportes = db.query(models.Reporte).all()

    def coincide(r: models.Reporte) -> bool:
        est = r.estado
        if not incluir_inactivos and est in ("Expirado", "Archivado"):
            return False
        if tipo and r.tipo != tipo:
            return False
        if estado and est != estado:
            return False
        if edificio and r.ubicacion.edificio.lower() != edificio.lower():
            return False
        if piso is not None and r.ubicacion.piso != piso:
            return False
        if autor_id is not None and r.autor_id != autor_id:
            return False
        if tag and not any(t.nombre_tag == tag.lower() for t in r.tags):
            return False
        if q:
            ql = q.lower()
            en_texto = ql in r.titulo.lower() or ql in r.descripcion.lower()
            en_tags = any(ql in t.nombre_tag for t in r.tags)
            if not (en_texto or en_tags):
                return False
        return True

    filtrados = [r for r in reportes if coincide(r)]

    if orden == "relevancia":
        filtrados.sort(key=lambda r: r.relevancia, reverse=True)
    else:  # "reciente"
        filtrados.sort(key=lambda r: r.fecha_creacion, reverse=True)
    return filtrados
