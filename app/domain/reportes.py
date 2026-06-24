"""
Núcleo del dominio: jerarquía de reportes.

Demuestra los cuatro pilares de la POO exigidos por el proyecto:
  - Abstracción:    ReporteBase es abstracta (ABC) y define la interfaz común.
  - Herencia:       cada tipo de reporte hereda de ReporteBase.
  - Polimorfismo:   `obtener_protocolo_atencion()` se resuelve según el tipo.
  - Encapsulamiento:el estado interno (_estado_interno) se controla con reglas.
  - Composición:    un reporte se compone de Ubicacion, Tags, Comentarios, etc.

El ciclo de vida (expiración perezosa y consenso) se delega a `estados.py`,
que es la única fuente de verdad de esas reglas.
"""

from __future__ import annotations

import datetime
from abc import ABC, abstractmethod

from . import estados


class ReporteBase(ABC):
    """Clase abstracta base de todo reporte de CampusRadar."""

    #: Duración de vida por defecto (horas). Cada subtipo puede ajustarla.
    DURACION_DEFAULT = 24
    #: Estado con el que nace el reporte. Las emergencias lo sobrescriben.
    ESTADO_INICIAL = "Nuevo"

    def __init__(
        self,
        titulo: str,
        descripcion: str,
        autor,
        ubicacion,
        id_reporte: int | None = None,
        fecha_creacion: datetime.datetime | None = None,
        duracion_horas: int | None = None,
    ):
        self.id_reporte = id_reporte
        self.titulo = titulo
        self.descripcion = descripcion
        self.autor = autor                 # composición/asociación con Persona
        self.ubicacion = ubicacion         # composición con Ubicacion
        self.fecha_creacion = fecha_creacion or datetime.datetime.now(
            datetime.timezone.utc
        )
        self.duracion_horas = duracion_horas or self.DURACION_DEFAULT

        self._estado_interno = self.ESTADO_INICIAL
        self.confirmaciones: list = []     # usuarios que confirman
        self.desmentidos: list = []        # usuarios que desmienten
        self.comentarios: list = []        # composición con Comentario
        self.tags: list = []               # composición con Tag

    # ------------------------------------------------------------------ #
    # Ciclo de vida (lazy evaluation, sin mecanismos bloqueantes)
    # ------------------------------------------------------------------ #
    @property
    def estado(self) -> str:
        """Estado VISIBLE calculado de forma perezosa al momento de leerlo."""
        self._estado_interno = estados.calcular_estado(
            self._estado_interno, self.fecha_creacion, self.duracion_horas
        )
        return self._estado_interno

    @estado.setter
    def estado(self, nuevo_estado: str) -> None:
        """Permite forzar un estado válido (uso por moderadores/lógica interna)."""
        if nuevo_estado not in estados.ESTADOS_VALIDOS:
            raise ValueError(f"Estado '{nuevo_estado}' no es válido.")
        self._estado_interno = nuevo_estado

    @property
    def activo(self) -> bool:
        return self.estado not in estados.ESTADOS_TERMINALES

    # ------------------------------------------------------------------ #
    # Interacciones sociales (afectan estado y reputación)
    # ------------------------------------------------------------------ #
    def agregar_confirmacion(self, usuario) -> bool:
        """Registra una confirmación si el usuario no interactuó antes."""
        if not self.activo:
            return False
        if usuario in self.confirmaciones or usuario in self.desmentidos:
            return False
        self.confirmaciones.append(usuario)
        if hasattr(self.autor, "aumentar_reputacion"):
            self.autor.aumentar_reputacion(5)  # validar premia al autor
        self.recalcular_estado()
        return True

    def agregar_desmentido(self, usuario) -> bool:
        """Registra un desmentido si el usuario no interactuó antes."""
        if not self.activo:
            return False
        if usuario in self.desmentidos or usuario in self.confirmaciones:
            return False
        self.desmentidos.append(usuario)
        if hasattr(self.autor, "aumentar_reputacion"):
            self.autor.aumentar_reputacion(-5)  # desmentir penaliza al autor
        self.recalcular_estado()
        return True

    def agregar_comentario(self, comentario) -> None:
        self.comentarios.append(comentario)

    def agregar_tag(self, tag) -> None:
        if tag not in self.tags:
            self.tags.append(tag)

    def recalcular_estado(self) -> None:
        """Actualiza el estado interno según el consenso comunitario."""
        self._estado_interno = estados.recalcular_por_consenso(
            self._estado_interno, len(self.confirmaciones), len(self.desmentidos)
        )

    def archivar(self) -> None:
        self._estado_interno = "Archivado"

    @property
    def relevancia(self) -> float:
        return estados.calcular_relevancia(
            len(self.confirmaciones),
            len(self.desmentidos),
            len(self.comentarios),
            self.fecha_creacion,
            es_critico=(self._estado_interno == "Critico"),
        )

    # ------------------------------------------------------------------ #
    # Polimorfismo: cada subtipo define su protocolo de atención
    # ------------------------------------------------------------------ #
    @abstractmethod
    def obtener_protocolo_atencion(self) -> str:
        """Cada tipo de reporte define cómo debe ser atendido."""
        raise NotImplementedError

    @property
    def tipo(self) -> str:
        """Nombre de tipo legible (usado por la API y el frontend)."""
        return self.__class__.TIPO

    def __str__(self) -> str:
        return (
            f"[{self.id_reporte}] {self.titulo} "
            f"({self.tipo}, {self.estado}) "
            f"+{len(self.confirmaciones)}/-{len(self.desmentidos)}"
        )


# --------------------------------------------------------------------- #
# Subtipos concretos (herencia + polimorfismo)
# --------------------------------------------------------------------- #
class ReporteInfraestructura(ReporteBase):
    """Fallas de infraestructura (microondas roto, corte de luz, WiFi caído)."""

    TIPO = "Infraestructura"
    DURACION_DEFAULT = 24

    def obtener_protocolo_atencion(self) -> str:
        return "Derivar ticket al Departamento de Mantención y Operaciones."


class ReporteEmergencia(ReporteBase):
    """Alertas críticas (accidentes, amagos de incendio, cortes de agua)."""

    TIPO = "Emergencia"
    DURACION_DEFAULT = 4         # expira rápido para evitar pánico rezagado
    ESTADO_INICIAL = "Critico"   # nace en estado crítico

    def obtener_protocolo_atencion(self) -> str:
        return "ALERTA: notificar a guardia de seguridad y activar evacuación."


class ReporteEvento(ReporteBase):
    """Actividades extraprogramáticas, ferias, asambleas."""

    TIPO = "Evento"
    DURACION_DEFAULT = 48

    def obtener_protocolo_atencion(self) -> str:
        return "Difundir en el feed general y calendarizar para la comunidad."


class ReporteLogistica(ReporteBase):
    """Avisos efímeros (sobra comida, sala liberada, filas)."""

    TIPO = "Logistica"
    DURACION_DEFAULT = 2         # cambia rápido, vida corta

    def obtener_protocolo_atencion(self) -> str:
        return "Monitoreo comunitario de disponibilidad en tiempo real."


class ReporteActividad(ReporteBase):
    """Actividad genérica del campus (talleres, charlas, deportes)."""

    TIPO = "Actividad"
    DURACION_DEFAULT = 24

    def obtener_protocolo_atencion(self) -> str:
        return "Publicar en el feed e invitar a la comunidad a participar."


# Fábrica: mapea el nombre de tipo a su clase concreta (usada por servicios/tests).
TIPOS_REPORTE: dict[str, type[ReporteBase]] = {
    cls.TIPO: cls
    for cls in (
        ReporteInfraestructura,
        ReporteEmergencia,
        ReporteEvento,
        ReporteLogistica,
        ReporteActividad,
    )
}


def crear_reporte(tipo: str, **kwargs) -> ReporteBase:
    """Crea la instancia concreta correcta según el tipo solicitado."""
    if tipo not in TIPOS_REPORTE:
        raise ValueError(f"Tipo de reporte inválido: {tipo}")
    return TIPOS_REPORTE[tipo](**kwargs)
