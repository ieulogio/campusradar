"""
Capa de PERSISTENCIA: modelos ORM (SQLAlchemy).

Mantiene la MISMA jerarquía del dominio mediante *herencia de tabla única*
(single-table inheritance) polimórfica:

    Usuario  --(discriminador rol)-->  Estudiante / Moderador / Administrador
    Reporte  --(discriminador tipo)--> Infraestructura / Emergencia / ...

Las reglas de negocio (estado perezoso, niveles de reputación, permisos) NO se
reimplementan aquí: se delegan a la capa de dominio (`app.domain`), que es la
única fuente de verdad. Así, persistencia y dominio quedan separados pero sin
duplicar lógica.
"""

from __future__ import annotations

import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Column,
    Text,
)
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base
from .domain import estados as dom_estados
from .domain import reportes as dom_reportes
from .domain import usuarios as dom_usuarios


def _ahora() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


# --------------------------------------------------------------------- #
# Tablas de asociación (relaciones M:N)
# --------------------------------------------------------------------- #
confirmaciones_table = Table(
    "confirmaciones",
    Base.metadata,
    Column("reporte_id", ForeignKey("reportes.id"), primary_key=True),
    Column("usuario_id", ForeignKey("usuarios.id"), primary_key=True),
)

desmentidos_table = Table(
    "desmentidos",
    Base.metadata,
    Column("reporte_id", ForeignKey("reportes.id"), primary_key=True),
    Column("usuario_id", ForeignKey("usuarios.id"), primary_key=True),
)

reporte_tags_table = Table(
    "reporte_tags",
    Base.metadata,
    Column("reporte_id", ForeignKey("reportes.id"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id"), primary_key=True),
)

suscripciones_table = Table(
    "suscripciones",
    Base.metadata,
    Column("usuario_id", ForeignKey("usuarios.id"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id"), primary_key=True),
)


# --------------------------------------------------------------------- #
# Jerarquía de usuarios (single-table inheritance)
# --------------------------------------------------------------------- #
class Usuario(Base):
    """Persona base. El campo `rol` actúa como discriminador polimórfico."""

    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(80))
    apellido: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    rol: Mapped[str] = mapped_column(String(20))
    reputacion: Mapped[int] = mapped_column(Integer, default=0)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    fecha_registro: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_ahora
    )

    # Campos específicos de subtipos (nullable porque conviven en una tabla).
    carrera: Mapped[str | None] = mapped_column(String(80), nullable=True)
    area_moderacion: Mapped[str | None] = mapped_column(String(80), nullable=True)
    departamento: Mapped[str | None] = mapped_column(String(80), nullable=True)

    reportes = relationship("Reporte", back_populates="autor")
    notificaciones = relationship("Notificacion", back_populates="destinatario")
    tags_seguidos = relationship("Tag", secondary=suscripciones_table)

    __mapper_args__ = {"polymorphic_on": rol, "polymorphic_identity": "usuario"}

    @property
    def nombre_completo(self) -> str:
        return f"{self.nombre} {self.apellido}"

    @property
    def nivel(self) -> str:
        """Nivel de credibilidad: regla tomada del dominio (no duplicada)."""
        return dom_usuarios.calcular_nivel(self.reputacion)

    def puede(self, accion: str) -> bool:
        """Permisos: se delega al objeto de dominio equivalente."""
        return self._a_dominio().puede(accion)

    def _a_dominio(self) -> dom_usuarios.Persona:
        """Convierte el registro ORM en su objeto de dominio (para permisos)."""
        if self.rol == "moderador":
            return dom_usuarios.Moderador(
                self.nombre, self.apellido, self.id, self.area_moderacion or "General"
            )
        if self.rol == "administrador":
            return dom_usuarios.Administrador(
                self.nombre, self.apellido, self.id, self.departamento or "TI"
            )
        est = dom_usuarios.Estudiante(
            self.nombre, self.apellido, self.id, self.carrera or "", "", self.reputacion
        )
        est.activo = self.activo
        return est


class Estudiante(Usuario):
    __mapper_args__ = {"polymorphic_identity": "estudiante"}


class Moderador(Usuario):
    __mapper_args__ = {"polymorphic_identity": "moderador"}


class Administrador(Usuario):
    __mapper_args__ = {"polymorphic_identity": "administrador"}


# --------------------------------------------------------------------- #
# Geolocalización y clasificación
# --------------------------------------------------------------------- #
class Ubicacion(Base):
    __tablename__ = "ubicaciones"

    id: Mapped[int] = mapped_column(primary_key=True)
    edificio: Mapped[str] = mapped_column(String(120))
    piso: Mapped[int] = mapped_column(Integer, default=0)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre_tag: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    descripcion: Mapped[str] = mapped_column(String(255), default="")


# --------------------------------------------------------------------- #
# Jerarquía de reportes (single-table inheritance polimórfica)
# --------------------------------------------------------------------- #
class Reporte(Base):
    """Reporte base. El campo `tipo` es el discriminador polimórfico."""

    __tablename__ = "reportes"

    id: Mapped[int] = mapped_column(primary_key=True)
    titulo: Mapped[str] = mapped_column(String(200))
    descripcion: Mapped[str] = mapped_column(Text)
    tipo: Mapped[str] = mapped_column(String(30))
    estado_interno: Mapped[str] = mapped_column(String(20), default="Nuevo")
    duracion_horas: Mapped[int] = mapped_column(Integer, default=24)
    fecha_creacion: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_ahora
    )

    autor_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    ubicacion_id: Mapped[int] = mapped_column(ForeignKey("ubicaciones.id"))

    autor = relationship("Usuario", back_populates="reportes")
    ubicacion = relationship("Ubicacion")
    comentarios = relationship(
        "Comentario", back_populates="reporte", cascade="all, delete-orphan"
    )
    denuncias = relationship(
        "Denuncia", back_populates="reporte", cascade="all, delete-orphan"
    )
    tags = relationship("Tag", secondary=reporte_tags_table)
    confirmaciones = relationship("Usuario", secondary=confirmaciones_table)
    desmentidos = relationship("Usuario", secondary=desmentidos_table)

    __mapper_args__ = {"polymorphic_on": tipo, "polymorphic_identity": "reporte"}

    # ---- Comportamiento de dominio (delegado a app.domain.estados) ---- #
    @hybrid_property
    def estado(self) -> str:
        """Estado visible calculado de forma perezosa (lazy evaluation)."""
        return dom_estados.calcular_estado(
            self.estado_interno, self.fecha_creacion, self.duracion_horas
        )

    @property
    def activo(self) -> bool:
        return self.estado not in dom_estados.ESTADOS_TERMINALES

    @property
    def relevancia(self) -> float:
        return dom_estados.calcular_relevancia(
            len(self.confirmaciones),
            len(self.desmentidos),
            len(self.comentarios),
            self.fecha_creacion,
            es_critico=(self.estado_interno == "Critico"),
        )

    def recalcular_estado(self) -> None:
        self.estado_interno = dom_estados.recalcular_por_consenso(
            self.estado_interno, len(self.confirmaciones), len(self.desmentidos)
        )

    def obtener_protocolo_atencion(self) -> str:
        """Polimorfismo: delega al subtipo de dominio correspondiente."""
        cls = dom_reportes.TIPOS_REPORTE.get(self.tipo)
        if cls is None:
            return "Sin protocolo definido."
        # Instancia liviana solo para invocar el método polimórfico.
        instancia = cls.__new__(cls)
        return instancia.obtener_protocolo_atencion()


class ReporteInfraestructura(Reporte):
    __mapper_args__ = {"polymorphic_identity": "Infraestructura"}


class ReporteEmergencia(Reporte):
    __mapper_args__ = {"polymorphic_identity": "Emergencia"}


class ReporteEvento(Reporte):
    __mapper_args__ = {"polymorphic_identity": "Evento"}


class ReporteLogistica(Reporte):
    __mapper_args__ = {"polymorphic_identity": "Logistica"}


class ReporteActividad(Reporte):
    __mapper_args__ = {"polymorphic_identity": "Actividad"}


# --------------------------------------------------------------------- #
# Interacciones sociales y moderación
# --------------------------------------------------------------------- #
class Comentario(Base):
    __tablename__ = "comentarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    contenido: Mapped[str] = mapped_column(Text)
    fecha_creacion: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_ahora
    )
    reporte_id: Mapped[int] = mapped_column(ForeignKey("reportes.id"))
    autor_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))

    reporte = relationship("Reporte", back_populates="comentarios")
    autor = relationship("Usuario")


class Denuncia(Base):
    __tablename__ = "denuncias"

    id: Mapped[int] = mapped_column(primary_key=True)
    razon: Mapped[str] = mapped_column(String(255))
    estado: Mapped[str] = mapped_column(String(20), default="Pendiente")
    fecha_creacion: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_ahora
    )
    reporte_id: Mapped[int] = mapped_column(ForeignKey("reportes.id"))
    denunciante_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))

    reporte = relationship("Reporte", back_populates="denuncias")
    denunciante = relationship("Usuario")


class Notificacion(Base):
    __tablename__ = "notificaciones"

    id: Mapped[int] = mapped_column(primary_key=True)
    mensaje: Mapped[str] = mapped_column(String(255))
    leido: Mapped[bool] = mapped_column(Boolean, default=False)
    fecha_creacion: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_ahora
    )
    destinatario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))

    destinatario = relationship("Usuario", back_populates="notificaciones")
