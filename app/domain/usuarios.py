"""
Jerarquía de usuarios del dominio (POO pura, sin base de datos).

Demuestra:
  - Herencia:        Estudiante/Moderador/Administrador heredan de Persona.
  - Encapsulamiento: la reputación se modifica solo por métodos controlados.
  - Polimorfismo:    cada subtipo define sus permisos vía `puede(accion)`.
  - Abstracción:     Persona define la interfaz común de todo actor.

Esta capa contiene la lógica de credibilidad y permisos. La capa de
persistencia (models.py) reutiliza estas mismas reglas para no duplicarlas.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

# Niveles de credibilidad según reputación acumulada.
NIVEL_BASICO = "Basico"
NIVEL_CONFIABLE = "Confiable"
NIVEL_VERIFICADO = "Verificado"

UMBRAL_CONFIABLE = 20
UMBRAL_VERIFICADO = 100


def calcular_nivel(reputacion: int) -> str:
    """Regla pura: traduce un puntaje de reputación a un nivel de credibilidad."""
    if reputacion < UMBRAL_CONFIABLE:
        return NIVEL_BASICO
    if reputacion < UMBRAL_VERIFICADO:
        return NIVEL_CONFIABLE
    return NIVEL_VERIFICADO


class Persona(ABC):
    """Clase base abstracta para todo actor del sistema."""

    def __init__(self, nombre: str, apellido: str, id_persona: int):
        self.nombre = nombre
        self.apellido = apellido
        self.id_persona = id_persona

    @property
    def nombre_completo(self) -> str:
        return f"{self.nombre} {self.apellido}"

    @abstractmethod
    def puede(self, accion: str) -> bool:
        """Define qué acciones puede realizar este tipo de usuario.

        Método abstracto -> obliga a cada subtipo a declarar sus permisos
        (polimorfismo de control de acceso).
        """
        raise NotImplementedError

    def __str__(self) -> str:
        return f"{self.nombre_completo} (ID: {self.id_persona})"


class Estudiante(Persona):
    """Usuario estándar con sistema de reputación/credibilidad."""

    # Acciones permitidas a un estudiante.
    _PERMISOS = {
        "crear_reporte",
        "comentar",
        "confirmar",
        "desmentir",
        "denunciar",
        "suscribirse",
    }

    def __init__(
        self,
        nombre: str,
        apellido: str,
        id_persona: int,
        carrera: str = "",
        matricula: str = "",
        reputacion: int = 0,
    ):
        super().__init__(nombre, apellido, id_persona)
        self.carrera = carrera
        self.matricula = matricula
        self._reputacion = reputacion  # encapsulado: solo se cambia por método
        self.activo = True

    @property
    def reputacion(self) -> int:
        return self._reputacion

    def aumentar_reputacion(self, puntos: int) -> None:
        """Único punto de entrada para modificar la reputación.

        Mantiene la invariante de que la reputación nunca sea negativa.
        """
        self._reputacion = max(0, self._reputacion + puntos)

    @property
    def nivel(self) -> str:
        return calcular_nivel(self._reputacion)

    def puede(self, accion: str) -> bool:
        if not self.activo:
            return False
        return accion in self._PERMISOS

    def __str__(self) -> str:
        return (
            f"Estudiante: {self.nombre_completo} "
            f"(Carrera: {self.carrera}, Reputacion: {self._reputacion}, "
            f"Nivel: {self.nivel})"
        )


class Moderador(Persona):
    """Usuario con capacidades de moderación además de las de estudiante."""

    _PERMISOS = {
        "crear_reporte",
        "comentar",
        "confirmar",
        "desmentir",
        "denunciar",
        "suscribirse",
        "moderar",
        "resolver_denuncia",
        "archivar_reporte",
        "forzar_estado",
    }

    def __init__(
        self,
        nombre: str,
        apellido: str,
        id_persona: int,
        area_moderacion: str = "General",
    ):
        super().__init__(nombre, apellido, id_persona)
        self.area_moderacion = area_moderacion

    def puede(self, accion: str) -> bool:
        return accion in self._PERMISOS

    def __str__(self) -> str:
        return f"Moderador: {self.nombre_completo} (Area: {self.area_moderacion})"


class Administrador(Persona):
    """Usuario con todos los permisos del sistema."""

    def __init__(
        self,
        nombre: str,
        apellido: str,
        id_persona: int,
        departamento: str = "TI",
    ):
        super().__init__(nombre, apellido, id_persona)
        self.departamento = departamento

    def puede(self, accion: str) -> bool:
        # El administrador puede ejecutar cualquier acción.
        return True

    def __str__(self) -> str:
        return f"Administrador: {self.nombre_completo} (Depto: {self.departamento})"
