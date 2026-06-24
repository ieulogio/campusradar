"""
Punto de entrada de la aplicación CampusRadar (capa de PRESENTACIÓN / HTTP).

Ensambla la API FastAPI, registra los routers, sirve el frontend estático y
prepara la base de datos (creación de tablas + datos de ejemplo).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import models  # noqa: F401  (registra los modelos en la metadata)
from .api import (
    moderacion_router,
    notif_router,
    stats_router,
    tags_router,
    usuarios_router,
)
from .api.auth import router as auth_router
from .api.reportes import router as reportes_router
from .config import settings
from .database import Base, SessionLocal, engine
from .seed import seed

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa la base de datos al arrancar (crea tablas y carga seed)."""
    Base.metadata.create_all(bind=engine)
    if settings.SEED_ON_STARTUP:
        db = SessionLocal()
        try:
            seed(db)
        finally:
            db.close()
    yield


app = FastAPI(
    title="CampusRadar API",
    description="Plataforma colaborativa de información universitaria.",
    version="1.0.0",
    lifespan=lifespan,
)

# Routers de la API.
app.include_router(auth_router)
app.include_router(reportes_router)
app.include_router(usuarios_router)
app.include_router(tags_router)
app.include_router(notif_router)
app.include_router(moderacion_router)
app.include_router(stats_router)


@app.get("/health", tags=["infra"])
def health():
    return {"status": "ok"}


# Frontend: la SPA y sus assets se sirven como archivos estáticos.
@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
