"""Serializadores: traducen objetos ORM a esquemas de salida de la API."""

from __future__ import annotations

from .. import models, schemas


def usuario_publico(u: "models.Usuario") -> schemas.UsuarioPublico:
    return schemas.UsuarioPublico(
        id=u.id,
        nombre=u.nombre,
        apellido=u.apellido,
        rol=u.rol,
        reputacion=u.reputacion,
        nivel=u.nivel,
    )


def reporte_out(r: "models.Reporte") -> schemas.ReporteOut:
    """Arma la representación pública de un reporte, incluyendo métricas y el
    protocolo polimórfico de atención."""
    return schemas.ReporteOut(
        id=r.id,
        titulo=r.titulo,
        descripcion=r.descripcion,
        tipo=r.tipo,
        estado=r.estado,                       # lazy property (puede ser "Expirado")
        relevancia=round(r.relevancia, 2),
        duracion_horas=r.duracion_horas,
        fecha_creacion=r.fecha_creacion,
        autor=usuario_publico(r.autor),
        ubicacion=schemas.UbicacionOut.model_validate(r.ubicacion),
        tags=[t.nombre_tag for t in r.tags],
        total_confirmaciones=len(r.confirmaciones),
        total_desmentidos=len(r.desmentidos),
        total_comentarios=len(r.comentarios),
        protocolo=r.obtener_protocolo_atencion(),
    )
