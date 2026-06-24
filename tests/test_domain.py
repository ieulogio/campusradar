"""
Tests unitarios de la CAPA DE DOMINIO (POO pura, sin base de datos).

Validan las reglas de negocio centrales pedidas por el proyecto:
comportamiento temporal (lazy evaluation), reputación, consenso y polimorfismo.
"""

import datetime

import pytest

from app.domain import (
    Estudiante,
    Moderador,
    ReporteEmergencia,
    ReporteLogistica,
    Ubicacion,
    calcular_nivel,
    crear_reporte,
)
from app.domain import estados


# ------------------------------ Reputación --------------------------- #
def test_niveles_de_reputacion():
    assert calcular_nivel(0) == "Basico"
    assert calcular_nivel(19) == "Basico"
    assert calcular_nivel(20) == "Confiable"
    assert calcular_nivel(99) == "Confiable"
    assert calcular_nivel(100) == "Verificado"


def test_reputacion_no_baja_de_cero():
    est = Estudiante("Juan", "Pérez", 1)
    est.aumentar_reputacion(-50)
    assert est.reputacion == 0
    est.aumentar_reputacion(30)
    assert est.reputacion == 30
    assert est.nivel == "Confiable"


# --------------------- Lazy evaluation / tiempo ---------------------- #
def test_lazy_evaluation_expira():
    autor = Estudiante("Ana", "Gómez", 2)
    ub = Ubicacion("Hall Sur", 1, -33.45, -70.66)
    rep = ReporteLogistica("Sobra pizza", "En el hall", autor, ub)
    assert rep.estado == "Nuevo"

    # Simulamos el paso del tiempo SIN time.sleep, moviendo la fecha de creación.
    rep.fecha_creacion = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)
    # Logística dura 2 h por defecto -> debe estar expirado.
    assert rep.estado == "Expirado"
    assert rep.activo is False


def test_no_se_interactua_con_reporte_expirado():
    autor = Estudiante("Ana", "Gómez", 2)
    validador = Estudiante("Beto", "Lara", 3)
    ub = Ubicacion("Hall Sur", 1, -33.45, -70.66)
    rep = ReporteLogistica("Sobra pizza", "En el hall", autor, ub)
    rep.fecha_creacion = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=5)
    assert rep.agregar_confirmacion(validador) is False


# ------------------- Interacciones y consenso ------------------------ #
def test_confirmacion_premia_autor_y_no_duplica():
    autor = Estudiante("Carlos", "Soto", 4)
    validador = Estudiante("María", "Paz", 5)
    ub = Ubicacion("Biblioteca", 3, -33.45, -70.66)
    rep = crear_reporte("Logistica", titulo="Fila larga", descripcion="Mucha gente",
                        autor=autor, ubicacion=ub)

    assert rep.agregar_confirmacion(validador) is True
    assert autor.reputacion == 5
    # No puede volver a interactuar.
    assert rep.agregar_confirmacion(validador) is False
    # Tampoco puede desmentir tras confirmar.
    assert rep.agregar_desmentido(validador) is False


def test_estado_controvertido_y_verificado():
    autor = Estudiante("Carlos", "Soto", 4)
    ub = Ubicacion("Biblioteca", 3, -33.45, -70.66)
    rep = crear_reporte("Infraestructura", titulo="WiFi", descripcion="caído",
                        autor=autor, ubicacion=ub)

    # Más desmentidos que confirmaciones -> Controvertido.
    for i in range(3):
        rep.agregar_desmentido(Estudiante("D", str(i), 100 + i))
    assert rep.estado == "Controvertido"

    # Nuevo reporte con 5 confirmaciones -> Verificado.
    rep2 = crear_reporte("Infraestructura", titulo="Luz", descripcion="mala",
                         autor=autor, ubicacion=ub)
    for i in range(5):
        rep2.agregar_confirmacion(Estudiante("C", str(i), 200 + i))
    assert rep2.estado == "Verificado"


# ------------------------------ Polimorfismo ------------------------- #
def test_polimorfismo_protocolo_y_estado_critico():
    autor = Estudiante("Carlos", "Soto", 4)
    ub = Ubicacion("Edificio Civil", 1, -33.45, -70.66)
    emergencia = ReporteEmergencia("Incendio", "Humo en lab", autor, ub)
    logistica = ReporteLogistica("Café", "Hay café", autor, ub)

    # La emergencia nace en estado Crítico y tiene su propio protocolo.
    assert emergencia.estado == "Critico"
    assert "ALERTA" in emergencia.obtener_protocolo_atencion()
    assert emergencia.obtener_protocolo_atencion() != logistica.obtener_protocolo_atencion()


# ------------------------------ Permisos ----------------------------- #
def test_permisos_por_rol():
    est = Estudiante("E", "E", 1)
    mod = Moderador("M", "M", 2)
    assert est.puede("crear_reporte") is True
    assert est.puede("moderar") is False
    assert mod.puede("moderar") is True


# ------------------------------ Relevancia --------------------------- #
def test_relevancia_emergencia_es_alta():
    ahora = datetime.datetime.now(datetime.timezone.utc)
    r_normal = estados.calcular_relevancia(2, 0, 1, ahora, es_critico=False, ahora=ahora)
    r_critico = estados.calcular_relevancia(2, 0, 1, ahora, es_critico=True, ahora=ahora)
    assert r_critico > r_normal
