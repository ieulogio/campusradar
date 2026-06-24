"""
Tests de integración de la API (capas de servicio + persistencia + HTTP).

Usan una base de datos SQLite temporal y el TestClient de FastAPI para validar
los flujos completos: registro/login, creación de reportes, interacciones,
reputación y moderación.
"""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base, get_db
from app.main import app
from app.security import hash_password


@pytest.fixture()
def client():
    # Base de datos temporal aislada por test.
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    # Sembramos un moderador para los tests de moderación.
    db = TestingSession()
    db.add(models.Moderador(nombre="Mod", apellido="Test", email="mod@test.cl",
                            password_hash=hash_password("demo1234"), rol="moderador"))
    db.commit()
    db.close()

    yield TestClient(app)

    app.dependency_overrides.clear()
    os.remove(path)


def _registrar_y_token(client, email="user@test.cl"):
    r = client.post("/api/auth/register", json={
        "nombre": "Test", "apellido": "User", "email": email,
        "password": "demo1234", "carrera": "Eléctrica",
    })
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_registro_login_y_perfil(client):
    token = _registrar_y_token(client)
    r = client.get("/api/auth/me", headers=_headers(token))
    assert r.status_code == 200
    assert r.json()["nivel"] == "Basico"

    # Login con OAuth2 password flow.
    r = client.post("/api/auth/login", data={"username": "user@test.cl",
                                             "password": "demo1234"})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_no_se_puede_registrar_email_duplicado(client):
    _registrar_y_token(client, "dup@test.cl")
    r = client.post("/api/auth/register", json={
        "nombre": "X", "apellido": "Y", "email": "dup@test.cl",
        "password": "demo1234",
    })
    assert r.status_code == 400


def test_rutas_requieren_autenticacion(client):
    assert client.get("/api/reportes").status_code == 401


def test_crear_reporte_y_aparece_en_feed(client):
    token = _registrar_y_token(client)
    r = client.post("/api/reportes", headers=_headers(token), json={
        "titulo": "Microondas roto", "descripcion": "No funciona",
        "tipo": "Infraestructura",
        "ubicacion": {"edificio": "Hall Sur", "piso": 2, "lat": -33.45, "lon": -70.66},
        "tags": ["casino", "urgente"],
    })
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["estado"] == "Nuevo"
    assert "casino" in data["tags"]
    assert "Mantención" in data["protocolo"]

    feed = client.get("/api/reportes", headers=_headers(token)).json()
    assert len(feed) == 1


def test_emergencia_nace_critica(client):
    token = _registrar_y_token(client)
    r = client.post("/api/reportes", headers=_headers(token), json={
        "titulo": "Incendio", "descripcion": "Humo",
        "tipo": "Emergencia",
        "ubicacion": {"edificio": "Civil", "piso": 1, "lat": -33.45, "lon": -70.66},
        "tags": ["emergencia"],
    })
    assert r.json()["estado"] == "Critico"


def test_confirmar_sube_reputacion_y_no_duplica(client):
    autor_token = _registrar_y_token(client, "autor@test.cl")
    rep = client.post("/api/reportes", headers=_headers(autor_token), json={
        "titulo": "Fila larga", "descripcion": "Mucha gente", "tipo": "Logistica",
        "ubicacion": {"edificio": "Casino", "piso": 1, "lat": -33.45, "lon": -70.66},
        "tags": ["fila"],
    }).json()

    validador_token = _registrar_y_token(client, "valida@test.cl")
    r = client.post(f"/api/reportes/{rep['id']}/confirmar", headers=_headers(validador_token))
    assert r.status_code == 200
    assert r.json()["total_confirmaciones"] == 1

    # El autor ganó reputación (+3 crear, +5 confirmado = 8).
    perfil_autor = client.get("/api/auth/me", headers=_headers(autor_token)).json()
    assert perfil_autor["reputacion"] == 8

    # No puede confirmar dos veces.
    r2 = client.post(f"/api/reportes/{rep['id']}/confirmar", headers=_headers(validador_token))
    assert r2.status_code == 400


def test_busqueda_y_filtros(client):
    token = _registrar_y_token(client)
    for titulo, tipo, tag in [("WiFi caído", "Infraestructura", "wifi"),
                              ("Sobra pizza", "Logistica", "comida")]:
        client.post("/api/reportes", headers=_headers(token), json={
            "titulo": titulo, "descripcion": "x", "tipo": tipo,
            "ubicacion": {"edificio": "Hall Sur", "piso": 1, "lat": -33.4, "lon": -70.6},
            "tags": [tag],
        })

    r = client.get("/api/reportes?q=pizza", headers=_headers(token)).json()
    assert len(r) == 1 and r[0]["titulo"] == "Sobra pizza"

    r = client.get("/api/reportes?tipo=Infraestructura", headers=_headers(token)).json()
    assert len(r) == 1 and r[0]["tipo"] == "Infraestructura"

    r = client.get("/api/reportes?tag=comida", headers=_headers(token)).json()
    assert len(r) == 1


def test_suscripcion_genera_notificacion(client):
    # Usuario A se suscribe al tag "comida".
    token_a = _registrar_y_token(client, "a@test.cl")
    client.post("/api/suscripciones", headers=_headers(token_a),
                json={"nombre_tag": "comida"})

    # Usuario B publica un reporte con ese tag.
    token_b = _registrar_y_token(client, "b@test.cl")
    client.post("/api/reportes", headers=_headers(token_b), json={
        "titulo": "Sobra comida", "descripcion": "ven", "tipo": "Logistica",
        "ubicacion": {"edificio": "Hall Sur", "piso": 0, "lat": -33.4, "lon": -70.6},
        "tags": ["comida"],
    })

    # A debe haber recibido una notificación.
    notifs = client.get("/api/notificaciones", headers=_headers(token_a)).json()
    assert len(notifs) == 1
    assert "comida" in notifs[0]["mensaje"]


def test_moderacion_resuelve_denuncia_y_archiva(client):
    # Un estudiante crea y denuncia un reporte.
    token = _registrar_y_token(client, "est@test.cl")
    rep = client.post("/api/reportes", headers=_headers(token), json={
        "titulo": "Spam", "descripcion": "contenido inválido", "tipo": "Actividad",
        "ubicacion": {"edificio": "Hall Sur", "piso": 1, "lat": -33.4, "lon": -70.6},
        "tags": [],
    }).json()
    client.post(f"/api/reportes/{rep['id']}/denunciar", headers=_headers(token),
                json={"razon": "spam"})

    # Un estudiante NO puede ver denuncias.
    assert client.get("/api/moderacion/denuncias", headers=_headers(token)).status_code == 403

    # El moderador inicia sesión y resuelve la denuncia.
    mod_token = client.post("/api/auth/login", data={"username": "mod@test.cl",
                                                     "password": "demo1234"}).json()["access_token"]
    denuncias = client.get("/api/moderacion/denuncias", headers=_headers(mod_token)).json()
    assert len(denuncias) == 1
    did = denuncias[0]["id"]
    r = client.post(f"/api/moderacion/denuncias/{did}/resolver", headers=_headers(mod_token),
                    json={"estado": "Aceptada"})
    assert r.status_code == 200

    # Al aceptar la denuncia, el reporte queda archivado (fuera del feed activo).
    feed = client.get("/api/reportes", headers=_headers(token)).json()
    assert all(rr["id"] != rep["id"] for rr in feed)
