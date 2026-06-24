"""
Capa de PRESENTACIÓN (contratos de datos): esquemas Pydantic.

Definen y validan la forma de los datos que entran y salen por la API,
desacoplando los modelos internos (ORM/dominio) de la representación HTTP.
"""

from __future__ import annotations

import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

# --------------------------- Autenticación --------------------------- #
class RegistroIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=80)
    apellido: str = Field(min_length=1, max_length=80)
    email: EmailStr
    password: str = Field(min_length=4, max_length=128)
    carrera: str = ""


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ------------------------------ Usuarios ----------------------------- #
class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    apellido: str
    email: EmailStr
    rol: str
    reputacion: int
    nivel: str
    activo: bool


class UsuarioPublico(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    apellido: str
    rol: str
    reputacion: int
    nivel: str


# ------------------------------ Ubicación ---------------------------- #
class UbicacionIn(BaseModel):
    edificio: str
    piso: int = 0
    lat: float
    lon: float


class UbicacionOut(UbicacionIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ------------------------------ Reportes ----------------------------- #
class ReporteIn(BaseModel):
    titulo: str = Field(min_length=1, max_length=200)
    descripcion: str = Field(min_length=1)
    tipo: str
    ubicacion: UbicacionIn
    tags: list[str] = []


class ComentarioIn(BaseModel):
    contenido: str = Field(min_length=1)


class ComentarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    contenido: str
    fecha_creacion: datetime.datetime
    autor: UsuarioPublico


class DenunciaIn(BaseModel):
    razon: str = Field(min_length=1, max_length=255)


class ReporteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    titulo: str
    descripcion: str
    tipo: str
    estado: str
    relevancia: float
    duracion_horas: int
    fecha_creacion: datetime.datetime
    autor: UsuarioPublico
    ubicacion: UbicacionOut
    tags: list[str]
    total_confirmaciones: int
    total_desmentidos: int
    total_comentarios: int
    protocolo: str


class EstadoForzadoIn(BaseModel):
    estado: str


# --------------------------- Notificaciones -------------------------- #
class NotificacionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    mensaje: str
    leido: bool
    fecha_creacion: datetime.datetime


class SuscripcionIn(BaseModel):
    nombre_tag: str


# ------------------------------ Moderación --------------------------- #
class DenunciaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    razon: str
    estado: str
    fecha_creacion: datetime.datetime
    reporte_id: int
    denunciante: UsuarioPublico


class ResolverDenunciaIn(BaseModel):
    estado: str  # "Aceptada" | "Rechazada"


# ------------------------------ Estadísticas ------------------------- #
class StatsOut(BaseModel):
    reportes_activos: int
    verificados: int
    criticos: int
    usuarios: int
