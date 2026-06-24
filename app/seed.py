"""
Carga de datos de ejemplo (seed) para que la app sea usable al desplegar.

Crea usuarios de demo (incluido un moderador y un admin), tags y un conjunto
de reportes de distintos tipos y ubicaciones del campus Beauchef.

Credenciales de demo (password en todos: "demo1234"):
    javita@uchile.cl      (estudiante)
    carlos@uchile.cl      (estudiante)
    maria@uchile.cl       (estudiante, alta reputación)
    mod@uchile.cl         (moderador)
    admin@uchile.cl       (administrador)
"""

from __future__ import annotations

import datetime

from sqlalchemy.orm import Session

from . import models, security
from .domain import reportes as dom_reportes

PASSWORD_DEMO = "demo1234"

# Coordenadas aproximadas de Beauchef (FCFM, Universidad de Chile).
EDIFICIOS = {
    "Hall Sur": (-33.4575, -70.6625),
    "Biblioteca": (-33.4570, -70.6618),
    "Edificio Civil": (-33.4580, -70.6630),
    "Casino Central": (-33.4573, -70.6622),
    "Edificio Electrica": (-33.4568, -70.6628),
}


def _ahora_menos(minutos: int) -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
        minutes=minutos
    )


def seed(db: Session) -> None:
    """Puebla la base solo si está vacía (idempotente)."""
    if db.query(models.Usuario).count() > 0:
        return

    pw = security.hash_password(PASSWORD_DEMO)

    javita = models.Estudiante(nombre="Javita", apellido="Villarroel",
                               email="javita@uchile.cl", password_hash=pw,
                               rol="estudiante", carrera="Eléctrica", reputacion=0)
    carlos = models.Estudiante(nombre="Carlos", apellido="Soto",
                               email="carlos@uchile.cl", password_hash=pw,
                               rol="estudiante", carrera="Computación", reputacion=45)
    maria = models.Estudiante(nombre="María", apellido="Paz",
                              email="maria@uchile.cl", password_hash=pw,
                              rol="estudiante", carrera="Industrial", reputacion=120)
    luis = models.Estudiante(nombre="Luis", apellido="Tapia",
                             email="luis@uchile.cl", password_hash=pw,
                             rol="estudiante", carrera="Minas", reputacion=8)
    mod = models.Moderador(nombre="Sofía", apellido="Rojas",
                           email="mod@uchile.cl", password_hash=pw,
                           rol="moderador", area_moderacion="Infraestructura")
    admin = models.Administrador(nombre="Admin", apellido="Campus",
                                 email="admin@uchile.cl", password_hash=pw,
                                 rol="administrador", departamento="TI")

    db.add_all([javita, carlos, maria, luis, mod, admin])
    db.flush()

    def tag(nombre: str) -> models.Tag:
        t = db.query(models.Tag).filter(models.Tag.nombre_tag == nombre).first()
        if not t:
            t = models.Tag(nombre_tag=nombre)
            db.add(t)
            db.flush()
        return t

    def ubic(edificio: str, piso: int) -> models.Ubicacion:
        lat, lon = EDIFICIOS[edificio]
        u = models.Ubicacion(edificio=edificio, piso=piso, lat=lat, lon=lon)
        db.add(u)
        db.flush()
        return u

    def reporte(modelo, *, titulo, desc, tipo, autor, edificio, piso, tags,
                hace_min, estado_interno=None, confirman=(), desmienten=()):
        cls_dom = dom_reportes.TIPOS_REPORTE[tipo]
        r = modelo(
            titulo=titulo, descripcion=desc, tipo=tipo,
            estado_interno=estado_interno or cls_dom.ESTADO_INICIAL,
            duracion_horas=cls_dom.DURACION_DEFAULT,
            autor_id=autor.id, ubicacion_id=ubic(edificio, piso).id,
            fecha_creacion=_ahora_menos(hace_min),
        )
        for nt in tags:
            r.tags.append(tag(nt))
        for u in confirman:
            r.confirmaciones.append(u)
        for u in desmienten:
            r.desmentidos.append(u)
        db.add(r)
        db.flush()
        return r

    reporte(models.ReporteInfraestructura,
            titulo="Microondas roto piso 2",
            desc="El microondas del casino del piso 2 del Hall Sur está dañado. "
                 "No calienta y hace ruido extraño.",
            tipo="Infraestructura", autor=carlos, edificio="Hall Sur", piso=2,
            tags=["infraestructura", "casino"], hace_min=30,
            estado_interno="Verificado",
            confirman=[javita, maria, luis])

    reporte(models.ReporteEmergencia,
            titulo="Corte de agua Edificio Civil",
            desc="Se reporta corte total de agua en los baños del Edificio Civil. "
                 "Se notificó al equipo de mantención.",
            tipo="Emergencia", autor=maria, edificio="Edificio Civil", piso=1,
            tags=["emergencia", "agua"], hace_min=20,
            confirman=[javita, luis])

    reporte(models.ReporteLogistica,
            titulo="Sobra pizza en charla DII",
            desc="Quedó pizza del evento de la Dirección de Investigación. "
                 "Sala B-25. ¡Vámonos!",
            tipo="Logistica", autor=luis, edificio="Edificio Civil", piso=2,
            tags=["comida", "gratis"], hace_min=15,
            confirman=[carlos], desmienten=[maria])

    reporte(models.ReporteEvento,
            titulo="Feria de clubs estudiantiles",
            desc="Hoy hasta las 18:00 en el patio central. Más de 15 clubs "
                 "universitarios presentes.",
            tipo="Evento", autor=javita, edificio="Hall Sur", piso=0,
            tags=["evento", "clubs"], hace_min=120,
            confirman=[carlos, maria])

    reporte(models.ReporteInfraestructura,
            titulo="WiFi caído en Biblioteca",
            desc="La red eduroam está sin conexión en la biblioteca central. "
                 "Lleva al menos 1 hora sin servicio.",
            tipo="Infraestructura", autor=carlos, edificio="Biblioteca", piso=1,
            tags=["wifi", "red", "infraestructura"], hace_min=45,
            estado_interno="Controvertido",
            confirman=[luis], desmienten=[javita, maria])

    # Suscripción de demo: Javita sigue el tag "comida".
    javita.tags_seguidos.append(tag("comida"))

    db.commit()
