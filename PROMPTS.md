# PROMPTS.md

Registro de los prompts utilizados con asistentes de IA durante el desarrollo de
CampusRadar, organizados por sección del código. El uso de IA estaba permitido
por el enunciado; este archivo documenta cómo se ocupó.

> Nota metodológica: la IA se usó como apoyo para acelerar el *boilerplate* y
> proponer estructura, pero las decisiones de arquitectura (dominio puro,
> evaluación perezosa, delegación ORM → dominio) se definieron manualmente y
> luego se le pidió a la IA implementarlas. Cada salida se revisó, ajustó y
> testeó.

---

## 1. Arquitectura y planificación

> "Quiero construir una app tipo SOSAFE para un campus universitario con FastAPI,
> SQLAlchemy y pytest. Propón una arquitectura en capas donde las reglas de
> negocio (ciclo de vida de reportes, reputación) vivan en una capa de dominio de
> POO pura, sin que la ORM ni los routers dupliquen esa lógica. Lista los módulos
> y su responsabilidad."

> "Justifica las ventajas y desventajas de un 'dominio rico' separado de la ORM
> frente a poner la lógica directamente en los modelos SQLAlchemy."

---

## 2. Capa de dominio

### Estados y ciclo de vida (`app/domain/estados.py`)

> "Implementa el ciclo de vida de un reporte usando SOLO evaluación perezosa: el
> estado debe calcularse al consultarlo, sin time.sleep ni hilos. Reglas: si
> superó su duración → Expirado; si tiene ≥5 confirmaciones → Verificado; si los
> desmentidos superan a las confirmaciones → Controvertido. Define los estados
> terminales y protegidos como constantes."

> "Agrega una función `calcular_relevancia` para rankear el feed que combine
> recencia (decaimiento temporal) con un bono para reportes críticos."

### Usuarios y permisos (`app/domain/usuarios.py`)

> "Crea una clase abstracta `Persona` y subclases `Estudiante`, `Moderador`,
> `Administrador`. La reputación debe estar encapsulada y nunca bajar de 0.
> Niveles: Básico (<20), Confiable (<100), Verificado (≥100). Implementa
> `puede(accion)` de forma polimórfica para los permisos de cada rol."

### Interacciones (`app/domain/interacciones.py`)

> "Define las clases de composición de un reporte: `Ubicacion` (edificio, piso,
> lat, lon), `Tag` (normalizado en minúsculas, con `__eq__`/`__hash__`),
> `Comentario`, `Denuncia` y `Notificacion`, con type hints y encapsulamiento."

### Reportes (`app/domain/reportes.py`)

> "Crea `ReporteBase(ABC)` con una *property* `estado` perezosa y métodos
> `agregar_confirmacion` (+5 a la reputación del autor) y `agregar_desmentido`
> (−5). Hazlo polimórfico con `obtener_protocolo_atencion()`. Define 5 subtipos
> con su duración y estado inicial: Infraestructura 24 h, Emergencia 4 h
> (nace 'Critico'), Evento 48 h, Logistica 2 h, Actividad 24 h. Agrega una
> factory `crear_reporte(tipo, ...)`."

---

## 3. Persistencia (`app/models.py`, `app/database.py`)

> "Traduce la jerarquía del dominio a modelos SQLAlchemy 2.0 usando herencia
> polimórfica de tabla única (polymorphic_on). Importante: el estado del reporte
> y el nivel del usuario deben DELEGAR en las funciones del dominio, no
> reimplementarse. Usa una hybrid_property para `estado`."

> "Define las tablas de asociación M:N para confirmaciones, desmentidos, tags de
> reportes y suscripciones."

---

## 4. Esquemas y seguridad (`app/schemas.py`, `app/security.py`)

> "Genera los esquemas Pydantic de entrada/salida para registro, login, reportes,
> comentarios, denuncias, notificaciones y estadísticas, con `from_attributes`."

> "Implementa hashing de contraseñas con bcrypt y creación/validación de tokens
> JWT con python-jose, leyendo SECRET_KEY desde variables de entorno."

---

## 5. Servicios (`app/services/`)

> "Escribe la capa de servicios que orquesta los efectos secundarios: registrar y
> autenticar usuarios; crear reportes (get-or-create de tags y notificar a los
> suscriptores); confirmar/desmentir/comentar/denunciar ajustando reputación;
> listar reportes con filtros en memoria sobre el estado perezoso; y la
> moderación (resolver denuncias archivando el reporte, forzar estado). Usa
> excepciones de dominio propias para los errores."

> "Crea serializadores que conviertan los modelos ORM a los esquemas de salida,
> incluyendo relevancia, protocolo y totales de interacción."

---

## 6. API / routers (`app/api/`, `app/deps.py`)

> "Expón los servicios como endpoints FastAPI. Los routers deben ser delgados:
> validar con Pydantic, llamar al servicio y traducir las excepciones de dominio
> a HTTPException. Agrega dependencias `get_current_user` (Bearer) y
> `require_moderador`."

---

## 7. Datos de demo y arranque (`app/seed.py`, `app/main.py`)

> "Crea un seed idempotente con usuarios demo (estudiantes, un moderador y un
> admin, password 'demo1234'), tags y ~5 reportes en edificios reales de Beauchef
> con coordenadas aproximadas. En `main.py`, usa el lifespan para crear tablas y
> sembrar; monta los routers y sirve `static/index.html` en `/`."

---

## 8. Frontend (`static/index.html`, `static/app.js`)

> "Diseña una SPA con tema oscuro estilo dashboard (sidebar + feed + panel
> derecho) que consuma la API: login/registro con JWT, feed con tarjetas de
> reporte, filtros, creación de reportes con selector de ubicación en un mapa
> Leaflet, mapa global de reportes, comentarios, notificaciones, panel de
> comunidad y vista de moderación. JavaScript vanilla, sin frameworks."

---

## 9. Tests (`tests/`)

> "Escribe tests con pytest: unitarios del dominio (reputación que no baja de 0,
> expiración perezosa, no permitir interacción en reportes expirados, consenso
> hacia Verificado/Controvertido, polimorfismo de permisos y protocolos,
> relevancia) e integración de la API con TestClient y una SQLite temporal
> (registro/login, duplicados, autenticación requerida, creación, emergencia que
> nace Crítica, confirmación + reputación, búsqueda/filtros, suscripción →
> notificación, flujo de moderación)."

---

## 10. Despliegue (`Dockerfile`, `docker-compose.yml`)

> "Crea un Dockerfile con python:3.12-slim que instale dependencias, copie la app
> y arranque con uvicorn, sin pasos de build manuales. Agrega un docker-compose
> con un volumen para persistir la base de datos y variables de entorno para
> configurar BD, clave secreta y seed."
