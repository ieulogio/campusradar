"""
Objetos de valor e interacciones del dominio (POO pura).

Demuestra COMPOSICIÓN: un reporte se compone de una Ubicacion, varios Tags,
Comentarios y Denuncias. Estos objetos no tienen sentido por sí solos fuera
del reporte que los contiene (salvo el Tag, que es compartible).
"""

from __future__ import annotations

import datetime


class Ubicacion:
    """Ubicación aproximada de un reporte dentro del campus.

    Geolocalización básica: edificio + piso + coordenadas (lat, lon).
    """

    def __init__(
        self,
        edificio: str,
        piso: int,
        lat: float,
        lon: float,
        id_ubicacion: int | None = None,
    ):
        self.id_ubicacion = id_ubicacion
        self.edificio = edificio
        self.piso = piso
        self.lat = lat
        self.lon = lon

    @property
    def coordenadas(self) -> tuple[float, float]:
        return (self.lat, self.lon)

    def __str__(self) -> str:
        return f"{self.edificio} (Piso {self.piso}) [{self.lat:.5f}, {self.lon:.5f}]"


class Tag:
    """Etiqueta de clasificación. Se normaliza a minúsculas."""

    def __init__(self, nombre_tag: str, descripcion: str = "", id_tag: int | None = None):
        self.id_tag = id_tag
        self.nombre_tag = nombre_tag.strip().lower()
        self.descripcion = descripcion

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Tag) and other.nombre_tag == self.nombre_tag

    def __hash__(self) -> int:
        return hash(self.nombre_tag)

    def __str__(self) -> str:
        return f"#{self.nombre_tag}"


class Comentario:
    """Comentario de un usuario sobre un reporte."""

    def __init__(self, contenido: str, autor, id_comentario: int | None = None):
        self.id_comentario = id_comentario
        self.contenido = contenido
        self.autor = autor
        self.fecha_creacion = datetime.datetime.now(datetime.timezone.utc)

    def editar(self, nuevo_contenido: str) -> None:
        self.contenido = nuevo_contenido

    def __str__(self) -> str:
        return f"[{self.autor.nombre_completo}] {self.contenido}"


class Denuncia:
    """Denuncia de un usuario sobre un reporte, gestionada por moderación."""

    ESTADOS = ("Pendiente", "Aceptada", "Rechazada")

    def __init__(self, reporte, razon: str, denunciante, id_denuncia: int | None = None):
        self.id_denuncia = id_denuncia
        self.reporte = reporte
        self.razon = razon
        self.denunciante = denunciante
        self.fecha_creacion = datetime.datetime.now(datetime.timezone.utc)
        self.estado = "Pendiente"

    def resolver(self, nuevo_estado: str) -> bool:
        """Cambia el estado de la denuncia validando la transición."""
        if nuevo_estado in self.ESTADOS and nuevo_estado != "Pendiente":
            self.estado = nuevo_estado
            return True
        return False


class Notificacion:
    """Notificación generada para un usuario (p. ej. por un tag seguido)."""

    def __init__(self, destinatario, mensaje: str, id_notificacion: int | None = None):
        self.id_notificacion = id_notificacion
        self.destinatario = destinatario
        self.mensaje = mensaje
        self.fecha_creacion = datetime.datetime.now(datetime.timezone.utc)
        self.leido = False

    def marcar_como_leido(self) -> None:
        self.leido = True
