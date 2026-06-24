"""
Reglas puras del ciclo de vida de un reporte (máquina de estados).

Este módulo NO conoce la base de datos ni el framework web. Contiene solo
las reglas de negocio del ciclo de vida, expresadas como funciones puras.

Es la ÚNICA fuente de verdad sobre cómo evoluciona el estado de un reporte:
tanto la capa de dominio (`domain/reportes.py`) como la capa de persistencia
(`models.py`) lo reutilizan, evitando duplicar lógica.

Estados del sistema:
    Nuevo         -> recién creado, sin consenso fuerte.
    Verificado    -> alcanzó el umbral de confirmaciones de la comunidad.
    Controvertido -> hay más desmentidos que confirmaciones.
    Critico       -> reportes de emergencia (estado forzado por el tipo).
    Expirado      -> superó su tiempo de vida (cálculo perezoso / lazy).
    Archivado     -> retirado manualmente por un moderador/admin.
"""

from __future__ import annotations

import datetime
from typing import Iterable

# Estados que son "terminales": una vez en ellos, el consenso ya no los cambia.
ESTADOS_TERMINALES = ("Archivado", "Expirado")

# Estados que NO se ven afectados por el recálculo de consenso comunitario.
ESTADOS_PROTEGIDOS = ("Archivado", "Expirado", "Critico")

ESTADOS_VALIDOS = (
    "Nuevo",
    "Verificado",
    "Controvertido",
    "Critico",
    "Expirado",
    "Archivado",
)

# Umbral de confirmaciones para que un reporte pase a "Verificado".
UMBRAL_VERIFICACION = 5


def esta_expirado(
    fecha_creacion: datetime.datetime,
    duracion_horas: float,
    ahora: datetime.datetime | None = None,
) -> bool:
    """Determina si un reporte superó su tiempo de vida.

    Implementa la base del *lazy evaluation*: en lugar de usar un proceso
    bloqueante (time.sleep, loops) que "marque" el reporte como expirado,
    el cálculo se hace en el instante exacto en que se consulta el estado.
    """
    ahora = ahora or datetime.datetime.now(datetime.timezone.utc)
    # Normalizamos para comparar timestamps "naive" y "aware" de forma segura.
    if fecha_creacion.tzinfo is None:
        ahora = ahora.replace(tzinfo=None)
    limite = fecha_creacion + datetime.timedelta(hours=duracion_horas)
    return ahora > limite


def calcular_estado(
    estado_interno: str,
    fecha_creacion: datetime.datetime,
    duracion_horas: float,
    ahora: datetime.datetime | None = None,
) -> str:
    """Calcula el estado VISIBLE de un reporte de forma perezosa.

    Combina el estado interno persistido con el paso del tiempo. Si el
    reporte está en un estado terminal, se respeta. En caso contrario, se
    evalúa la expiración dinámicamente.
    """
    if estado_interno in ESTADOS_TERMINALES:
        return estado_interno
    if esta_expirado(fecha_creacion, duracion_horas, ahora):
        return "Expirado"
    return estado_interno


def recalcular_por_consenso(
    estado_interno: str,
    n_confirmaciones: int,
    n_desmentidos: int,
) -> str:
    """Recalcula el estado interno según el consenso de la comunidad.

    No toca estados protegidos (Archivado, Expirado, Critico). Reglas:
      - más desmentidos que confirmaciones  -> Controvertido
      - confirmaciones >= UMBRAL_VERIFICACION -> Verificado
      - en otro caso                         -> Nuevo
    """
    if estado_interno in ESTADOS_PROTEGIDOS:
        return estado_interno

    if n_desmentidos > n_confirmaciones:
        return "Controvertido"
    if n_confirmaciones >= UMBRAL_VERIFICACION:
        return "Verificado"
    return "Nuevo"


def calcular_relevancia(
    n_confirmaciones: int,
    n_desmentidos: int,
    n_comentarios: int,
    fecha_creacion: datetime.datetime,
    es_critico: bool = False,
    ahora: datetime.datetime | None = None,
) -> float:
    """Puntaje de relevancia para ordenar el feed (ranking).

    Combina validación comunitaria, actividad (comentarios) y frescura
    temporal (decaimiento). Las emergencias reciben un fuerte bono para
    aparecer arriba mientras estén activas.
    """
    ahora = ahora or datetime.datetime.now(datetime.timezone.utc)
    if fecha_creacion.tzinfo is None:
        ahora = ahora.replace(tzinfo=None)

    horas = max((ahora - fecha_creacion).total_seconds() / 3600.0, 0.0)
    frescura = 1.0 / (1.0 + horas)  # decae con el tiempo

    consenso = (n_confirmaciones * 2) - (n_desmentidos * 3)
    actividad = n_comentarios * 0.5
    bono_critico = 100.0 if es_critico else 0.0

    return bono_critico + consenso + actividad + (frescura * 10.0)
