"""Configuración central de la aplicación (12-factor: vía variables de entorno)."""

from __future__ import annotations

import os


class Settings:
    """Parámetros de configuración. Se leen del entorno con valores por defecto
    razonables para desarrollo local y Docker."""

    # Base de datos. Por defecto SQLite (cero configuración); en despliegue se
    # puede inyectar una URL de PostgreSQL vía DATABASE_URL.
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./campusradar.db")

    # Seguridad de autenticación (JWT).
    SECRET_KEY: str = os.getenv("SECRET_KEY", "cambia-esta-clave-en-produccion")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440")  # 24 h
    )

    # Si es True, al iniciar se cargan datos de ejemplo (usuarios y reportes).
    SEED_ON_STARTUP: bool = os.getenv("SEED_ON_STARTUP", "true").lower() == "true"


settings = Settings()
