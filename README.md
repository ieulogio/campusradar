# CampusRadar

Plataforma colaborativa de información del campus en tiempo real, al estilo de
**SOSAFE / Waze**, pero enfocada en la vida universitaria: cortes de agua, fallas
de infraestructura, emergencias, eventos, comida gratis, filas, etc. Los usuarios
publican reportes geolocalizados, los confirman o desmienten entre todos, y cada
reporte avanza por un ciclo de vida (Nuevo → Verificado / Controvertido →
Expirado) según el consenso de la comunidad.

Proyecto del curso **EL4203 — Programación Avanzada**, Universidad de Chile.

---

## 1. Cómo ejecutarlo

### Opción A — Docker (recomendada, sin instalar dependencias)

```bash
docker compose up --build
```

Luego abrir <http://localhost:8000>. La base de datos se crea sola y se cargan
datos de demostración automáticamente.

Alternativa solo con Docker (sin compose):

```bash
docker build -t campusradar .
docker run -p 8000:8000 campusradar
```

### Opción B — Local con Python

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Abrir <http://localhost:8000>.

### Documentación interactiva de la API

FastAPI genera documentación automática en <http://localhost:8000/docs>.

---

## 2. Cuentas de demostración

Todas usan la contraseña **`demo1234`**:

| Email                | Rol           | Notas                          |
|----------------------|---------------|--------------------------------|
| `javita@uchile.cl`   | Estudiante    | Suscrita al tag `comida`       |
| `carlos@uchile.cl`   | Estudiante    |                                |
| `maria@uchile.cl`    | Estudiante    | Reputación alta (Verificado)   |
| `luis@uchile.cl`     | Estudiante    |                                |
| `mod@uchile.cl`      | Moderador     | Ve el panel de moderación      |
| `admin@uchile.cl`    | Administrador |                                |

---

## 3. Arquitectura

El sistema sigue una **arquitectura en capas** con una regla central: *las reglas
de negocio viven en un único lugar* (la capa de dominio) y el resto de las capas
las orquestan o las exponen, sin duplicarlas.

```
┌─────────────────────────────────────────────────────────────┐
│  PRESENTACIÓN                                                │
│  app/api/*  (routers FastAPI)   ·   app/schemas.py (Pydantic)│
│  static/    (SPA: index.html + app.js + Leaflet)            │
├─────────────────────────────────────────────────────────────┤
│  LÓGICA DE NEGOCIO / ORQUESTACIÓN                            │
│  app/services/*  (auth, reportes, moderación, serializers)  │
├─────────────────────────────────────────────────────────────┤
│  PERSISTENCIA                                                │
│  app/models.py  (ORM SQLAlchemy, herencia polimórfica)      │
├─────────────────────────────────────────────────────────────┤
│  DOMINIO (POO pura, sin dependencias de framework ni de BD) │
│  app/domain/  estados · usuarios · interacciones · reportes │
└─────────────────────────────────────────────────────────────┘
```

### Por qué esta separación

- **Dominio puro (`app/domain/`)**: contiene las clases y funciones de negocio
  sin importar SQLAlchemy ni FastAPI. Es la *única fuente de verdad* de las
  reglas (cuándo un reporte expira, cuándo pasa a Verificado, qué nivel de
  reputación tiene un usuario, qué protocolo de atención aplica). Al no depender
  de la base de datos, es trivialmente testeable y reutilizable.

- **Persistencia (`app/models.py`)**: los modelos ORM *delegan* en el dominio en
  lugar de reimplementar la lógica. Por ejemplo, el estado de un reporte se
  calcula con la misma función del dominio tanto si el objeto es una clase pura
  como si es una fila de la base de datos. Esto evita la duplicación de reglas,
  que es la principal fuente de bugs en este tipo de sistemas.

- **Servicios (`app/services/`)**: coordinan los efectos secundarios que el
  dominio puro no debe conocer: persistir, sumar reputación, crear
  notificaciones, archivar por moderación.

- **Presentación (`app/api/` + `static/`)**: los routers solo traducen
  HTTP ↔ servicios y validan con Pydantic; no contienen lógica de negocio. El
  frontend es una SPA en JavaScript vanilla que consume la API.

---

## 4. Conceptos de POO (y dónde están)

| Concepto          | Implementación                                                                                 |
|-------------------|-----------------------------------------------------------------------------------------------|
| **Abstracción**   | `Persona(ABC)` y `ReporteBase(ABC)` definen interfaces; no se instancian directamente.         |
| **Herencia**      | `Estudiante`, `Moderador`, `Administrador` heredan de `Persona`. Los 5 tipos de reporte heredan de `ReporteBase`. La ORM replica esta jerarquía con herencia polimórfica de tabla única. |
| **Polimorfismo**  | `puede(accion)` se resuelve distinto por rol; `obtener_protocolo_atencion()` devuelve un protocolo por tipo de reporte; el estado se calcula con la misma interfaz para cualquier subtipo. |
| **Encapsulamiento** | Atributos privados expuestos por *properties* (p. ej. la reputación nunca baja de 0; el estado interno se lee a través de una property que aplica las reglas de expiración). |
| **Composición**   | Un `Reporte` *se compone de* una `Ubicacion`, varios `Tag`, `Comentario`, `Confirmacion`/`Desmentido` y `Denuncia`. |

### Jerarquías principales

```
Persona (ABC)                    ReporteBase (ABC)
├── Estudiante                   ├── ReporteInfraestructura   (24 h)
├── Moderador                    ├── ReporteEmergencia        (4 h, nace "Critico")
└── Administrador                ├── ReporteEvento            (48 h)
                                 ├── ReporteLogistica         (2 h)
                                 └── ReporteActividad         (24 h)
```

---

## 5. Ciclo de vida por *evaluación perezosa* (requisito clave)

El estado de un reporte **no se actualiza con temporizadores, hilos ni
`time.sleep`**. Se calcula *en el momento en que se consulta*, mediante una
*property* que evalúa la antigüedad y el consenso:

- Si el reporte superó su duración → **Expirado** (calculado al vuelo).
- Si tiene ≥ 5 confirmaciones → **Verificado**.
- Si los desmentidos superan a las confirmaciones → **Controvertido**.
- Una `Emergencia` nace **Crítico** y ese estado está protegido.
- `Archivado` y `Expirado` son estados terminales: ya no admiten interacciones.

Esto significa que el sistema es *stateless* respecto al tiempo: dos consultas al
mismo reporte en distintos momentos pueden devolver estados distintos sin que
ningún proceso en segundo plano haya modificado nada. Es eficiente (no hay
polling) y determinista (el estado es función pura de los datos + la hora
actual).

El **ranking del feed** usa una relevancia que combina recencia, consenso y un
bono para reportes críticos, también calculada de forma perezosa.

---

## 6. Endpoints de la API

**Autenticación**
- `POST /api/auth/register` — registro de estudiante.
- `POST /api/auth/login` — login (OAuth2 password flow; `username` = email).
- `GET  /api/auth/me` — perfil del usuario autenticado.

**Reportes y feed**
- `GET  /api/reportes` — feed con filtros: `tipo`, `estado`, `edificio`, `piso`,
  `tag`, `q` (búsqueda), `mios`, `orden` (`relevancia` | `reciente`).
- `POST /api/reportes` — crear reporte (notifica a suscriptores del tag).
- `GET  /api/reportes/{id}` — detalle.
- `POST /api/reportes/{id}/confirmar` · `/desmentir` — interacción social.
- `GET|POST /api/reportes/{id}/comentarios` — comentarios.
- `POST /api/reportes/{id}/denunciar` — denunciar contenido.

**Moderación** (rol moderador/administrador)
- `POST /api/reportes/{id}/archivar` · `/estado` — acciones directas.
- `GET  /api/moderacion/denuncias` — bandeja de denuncias.
- `POST /api/moderacion/denuncias/{id}/resolver` — aceptar/rechazar.

**Comunidad, tags y notificaciones**
- `GET  /api/usuarios` — ranking de la comunidad por reputación.
- `GET  /api/tags` · `POST /api/suscripciones` — tags y suscripciones.
- `GET  /api/notificaciones` · `POST /api/notificaciones/{id}/leer`.

**Otros**
- `GET  /api/stats` — estadísticas en vivo del campus.
- `GET  /health` — healthcheck. `GET /` — frontend.

---

## 7. Funcionalidades implementadas

- Usuarios con autenticación JWT, roles y **reputación** (Básico < 20,
  Confiable < 100, Verificado ≥ 100). Las acciones suman o restan reputación.
- Reportes geolocalizados con **mapa interactivo Leaflet / OpenStreetMap**
  (selector de ubicación al crear y mapa global de reportes).
- Interacción social: confirmar, desmentir, comentar y denunciar.
- **Tags, búsqueda y filtros** (por tipo, estado, edificio, piso, texto) y feed
  ordenable por relevancia o por recencia.
- **Suscripciones a tags** con **notificaciones** automáticas.
- **Moderación**: bandeja de denuncias, archivado y forzado de estado.
- Frontend completo (feed, "mis reportes", mapa, comunidad, moderación).

---

## 8. Tests

```bash
pytest                # o:  SEED_ON_STARTUP=false python -m pytest -q
```

Hay **18 tests**: unitarios del dominio (reputación, expiración perezosa,
consenso, polimorfismo de permisos y protocolos, relevancia) e integración de la
API (registro/login, creación, confirmación con reputación, búsqueda y filtros,
suscripción → notificación, flujo de moderación).

---

## 9. Despliegue en la nube (opcional)

La imagen Docker funciona en cualquier plataforma que ejecute contenedores:

- **Render / Railway / Fly.io**: apuntar al `Dockerfile`; exponer el puerto 8000;
  definir `SECRET_KEY` (y opcionalmente `DATABASE_URL` con PostgreSQL para
  persistencia real). Con SQLite el `docker-compose.yml` usa un volumen para no
  perder datos entre reinicios.
- Variables relevantes: `DATABASE_URL`, `SECRET_KEY`, `SEED_ON_STARTUP`,
  `ACCESS_TOKEN_EXPIRE_MINUTES`.

---

## 10. Decisiones de diseño (justificación)

1. **Dominio rico y desacoplado de la BD.** Mantener las reglas en clases puras
   permite testearlas sin levantar una base de datos y reutilizarlas desde la
   ORM, evitando duplicar la lógica de estados/reputación en dos lugares.

2. **Evaluación perezosa del estado.** Se evita cualquier proceso temporizado:
   el estado es función pura de `(creado_en, ahora, confirmaciones, desmentidos)`.
   Más simple, sin condiciones de carrera y sin coste de polling.

3. **Herencia polimórfica en la ORM (tabla única).** Refleja la jerarquía del
   dominio en la base de datos y permite agregar nuevos tipos de reporte con
   mínimo código.

4. **Servicios como frontera de efectos secundarios.** El dominio nunca persiste
   ni notifica; eso lo hacen los servicios, manteniendo el dominio libre de I/O.

5. **SQLite por defecto, PostgreSQL opcional.** Cero configuración para evaluar,
   pero listo para producción cambiando una variable de entorno.

6. **Frontend sin frameworks.** JavaScript vanilla + Leaflet vía CDN: liviano,
   sin paso de build, fácil de desplegar junto al backend.
