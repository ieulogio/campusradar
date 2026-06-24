"""Capa de DOMINIO: modelo orientado a objetos puro, sin dependencias de
framework ni base de datos. Concentra las reglas de negocio y la jerarquía
de clases que se defiende en la presentación."""

from .estados import (
    ESTADOS_VALIDOS,
    UMBRAL_VERIFICACION,
    calcular_estado,
    calcular_relevancia,
    esta_expirado,
    recalcular_por_consenso,
)
from .interacciones import Comentario, Denuncia, Notificacion, Tag, Ubicacion
from .reportes import (
    TIPOS_REPORTE,
    ReporteActividad,
    ReporteBase,
    ReporteEmergencia,
    ReporteEvento,
    ReporteInfraestructura,
    ReporteLogistica,
    crear_reporte,
)
from .usuarios import (
    Administrador,
    Estudiante,
    Moderador,
    Persona,
    calcular_nivel,
)

__all__ = [
    "ESTADOS_VALIDOS",
    "UMBRAL_VERIFICACION",
    "calcular_estado",
    "calcular_relevancia",
    "esta_expirado",
    "recalcular_por_consenso",
    "Comentario",
    "Denuncia",
    "Notificacion",
    "Tag",
    "Ubicacion",
    "TIPOS_REPORTE",
    "ReporteActividad",
    "ReporteBase",
    "ReporteEmergencia",
    "ReporteEvento",
    "ReporteInfraestructura",
    "ReporteLogistica",
    "crear_reporte",
    "Administrador",
    "Estudiante",
    "Moderador",
    "Persona",
    "calcular_nivel",
]
