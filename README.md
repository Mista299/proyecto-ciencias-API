# Backend — Sistema DwC MUA Biodiversidad

**Proyecto:** Sistema de estandarización de datos bajo el estándar Darwin Core  
**Grupo:** 6 — Ciencias virtual, Universidad de Antioquia  
**Fase:** 3 — Pipeline Python con IA local (Ollama + rapidfuzz)

---

## Tabla de contenido

1. [¿Qué hace este backend?](#1-qué-hace-este-backend)
2. [Stack tecnológico](#2-stack-tecnológico)
3. [Requisitos previos](#3-requisitos-previos)
4. [Estructura de archivos](#4-estructura-de-archivos)
5. [Configuración](#5-configuración)
6. [Cómo ejecutar](#6-cómo-ejecutar)
7. [Sistema de autenticación (JWT + roles)](#7-sistema-de-autenticación-jwt--roles)
8. [Cómo funciona el pipeline ETL](#8-cómo-funciona-el-pipeline-etl)
9. [Integración con IA (Ollama + rapidfuzz)](#9-integración-con-ia-ollama--rapidfuzz)
10. [Modelo de datos (5 entidades DwC)](#10-modelo-de-datos-5-entidades-dwc)
11. [API REST — Endpoints](#11-api-rest--endpoints)
12. [Pruebas](#12-pruebas)
13. [Consultas útiles en PostgreSQL](#13-consultas-útiles-en-postgresql)

---

## 1. ¿Qué hace este backend?

Toma archivos Excel/CSV de colecciones biológicas con columnas en formato interno del MUA (ej. `genero_TA`, `latitud_IG`, `dia_colecta_IC`) y los estandariza al estándar internacional **Darwin Core (DwC)**, almacenando el resultado en una base de datos PostgreSQL.

El proceso completo es:

```
Archivo Excel/CSV
      ↓
  [Loader]         Lee el archivo, detecta la hoja con datos reales
      ↓
  [Mapper]         Detecta a qué campo DwC corresponde cada columna
  (rapidfuzz + Ollama gemma2:2b)
      ↓
  [Normalizer]     Convierte fechas a ISO 8601, coordenadas a decimal WGS84,
                   construye nombres científicos en formato estándar
      ↓
  [Pipeline]       Inserta/actualiza en PostgreSQL sin duplicar registros
      ↓
PostgreSQL → tablas: occurrence, taxon, event, location, identification
```

---

## 2. Stack tecnológico

### API Web

| Componente | Versión | Rol |
|---|---|---|
| **FastAPI** | 0.115+ | Framework web asíncrono. Genera `/docs` (Swagger UI) y `/redoc` automáticamente |
| **Uvicorn** | 0.30+ | Servidor ASGI; soporte para `reload=True` en desarrollo |
| **SQLAlchemy** | 2.0+ | ORM con `mapped_column` y tipado estricto; sesiones con `Depends(get_db)` |
| **Pydantic** | 2.x | Validación de cuerpos de request y serialización de respuestas |
| **psycopg2-binary** | — | Driver PostgreSQL para SQLAlchemy |

### Autenticación

| Componente | Rol |
|---|---|
| **python-jose[cryptography]** | Generación y validación de tokens JWT (HS256) |
| **bcrypt** | Hashing de contraseñas con salt aleatorio |
| **OAuth2PasswordBearer** (FastAPI) | Esquema estándar OAuth2; habilita el botón "Authorize" en Swagger |

### Pipeline ETL

| Componente | Rol |
|---|---|
| **pandas / openpyxl** | Lectura de archivos Excel y CSV |
| **rapidfuzz** | Fuzzy matching para mapeo automático de columnas → términos DwC |
| **Ollama + gemma2:2b** | Modelo de IA local para columnas con nombres ambiguos |

---

## 3. Requisitos previos

| Componente | Versión | Para qué |
|---|---|---|
| Python | 3.11+ | Lenguaje base |
| PostgreSQL | 14+ | Base de datos |
| Ollama | cualquiera | Modelo de IA local |
| gemma2:2b | — | Modelo de lenguaje para mapeo ambiguo |

### Instalar dependencias Python

```bash
# Desde la raíz del proyecto (donde está el .venv)
source .venv/bin/activate
pip install -r backend/requirements.txt
```

### Instalar modelo de Ollama

```bash
ollama pull gemma2:2b
```

### Crear la base de datos

```bash
psql -U postgres -c "CREATE DATABASE mua_biodiversidad ENCODING 'UTF8';"
```

---

## 4. Estructura de archivos

```
backend/
├── main.py                  # Punto de entrada — CLI y servidor
├── config.py                # Variables de configuración centralizadas
├── database.py              # Conexión SQLAlchemy + creación de tablas
├── requirements.txt         # Dependencias Python
├── .env                     # Variables de entorno (DB, Ollama, rutas)
│
├── models/                  # Definición de las tablas (ORM SQLAlchemy 2.0)
│   ├── occurrence.py        # Tabla: occurrence (registro principal)
│   ├── taxon.py             # Tabla: taxon
│   ├── event.py             # Tabla: event
│   ├── location.py          # Tabla: location
│   ├── identification.py    # Tabla: identification
│   └── user.py              # Tabla: user (autenticación)
│
├── auth/                    # Sistema de autenticación JWT
│   ├── core.py              # hash_password, verify_password, create/decode JWT
│   └── dependencies.py      # get_current_user, require_admin (FastAPI Depends)
│
├── etl/                     # Pipeline de procesamiento de datos
│   ├── loader.py            # Lee Excel/CSV, detecta hoja de datos
│   ├── mapper.py            # Mapea columnas reales → términos DwC
│   ├── normalizer.py        # Normaliza fechas, coordenadas, taxonomía
│   └── pipeline.py          # Orquesta el proceso completo fila por fila
│
├── api/                     # Servidor web FastAPI
│   ├── app.py               # Configuración de la app y routers
│   └── routers/
│       ├── auth.py          # Endpoints: login, gestión de usuarios
│       ├── occurrences.py   # Endpoints: registros (CRUD + export CSV)
│       ├── taxa.py          # Endpoints: taxones y resumen taxonómico
│       ├── stats.py         # Endpoints: métricas de calidad de datos
│       └── etl.py           # Endpoints: subir archivos y disparar ETL
│
├── seed_admin.py            # Crea el usuario admin inicial (idempotente)
│
└── tests/
    └── test_auth.sh         # Suite de pruebas del sistema de autenticación
```

---

## 5. Configuración

El archivo `backend/.env` contiene toda la configuración:
```env
DATABASE_URL=postgresql://postgres@localhost:5432/mua_biodiversidad
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=gemma2:2b
RAPIDFUZZ_THRESHOLD=80
MUESTRAS_DIR=../muestras

# Autenticación JWT
SECRET_KEY=<genera uno con: python3 -c "import secrets; print(secrets.token_hex(32))">
ACCESS_TOKEN_EXPIRE_HOURS=8
```

| Variable | Descripción |
|---|---|
| `DATABASE_URL` | Cadena de conexión a PostgreSQL |
| `OLLAMA_URL` | URL donde corre el servidor Ollama |
| `OLLAMA_MODEL` | Modelo a usar (gemma2:2b por defecto) |
| `RAPIDFUZZ_THRESHOLD` | Confianza mínima (0–100) para aceptar un mapeo por fuzzy matching |
| `MUESTRAS_DIR` | Carpeta con los archivos Excel/CSV a cargar |
| `SECRET_KEY` | Clave secreta para firmar los tokens JWT. **Cambiar antes de producción** |
| `ACCESS_TOKEN_EXPIRE_HOURS` | Duración del token en horas (por defecto 8) |

---

## 6. Cómo ejecutar

Todos los comandos se corren desde la carpeta `backend/`. No es necesario activar el virtualenv; el script lo encuentra automáticamente.

### Levantar el servidor web (API)

```bash
python3 main.py
```

- Inicia el servidor en `http://localhost:8000`
- Documentación interactiva (Swagger): `http://localhost:8000/docs`
- **No carga datos** — solo expone los endpoints para consultar y subir archivos
- El servidor se reinicia automáticamente si modificas el código

### Ejecutar el pipeline ETL (cargar datos)

```bash
python3 main.py --etl
```

- Lee todos los `.xlsx` y `.csv` de `muestras/`
- Procesa cada archivo: mapea columnas, normaliza, inserta en PostgreSQL
- Hace **upsert**: si un registro ya existe lo actualiza, no lo duplica
- No levanta ningún servidor web

### Ver reporte de mapeo de columnas

```bash
python3 main.py --mapeo
```

- Muestra qué columnas de cada archivo se detectan como campos DwC
- Útil para diagnosticar antes de cargar datos
- No modifica la base de datos

---

## 7. Sistema de autenticación (JWT + roles)

### Descripción general

La API usa **JWT stateless** (JSON Web Tokens) con el algoritmo HS256. No hay sesiones en servidor ni cookies: el cliente envía el token en cada petición mediante el header `Authorization: Bearer <token>`.

```
Cliente                            API
  │                                 │
  │  POST /auth/login               │
  │  username + password ────────►  │  Verifica bcrypt
  │                                 │  Crea JWT firmado (8h)
  │  ◄──── { access_token, role } ─ │
  │                                 │
  │  GET /occurrences/              │
  │  Authorization: Bearer <token>  │
  │  ───────────────────────────►   │  Decodifica JWT
  │                                 │  Verifica firma + expiración
  │  ◄──── [ lista de registros ] ─ │  Busca user en DB
```

### Roles

| Rol | Permisos |
|---|---|
| `admin` | Lectura + escritura + ETL + gestión de usuarios |
| `user` | Solo lectura (`GET`) en `/occurrences/`, `/taxa/`, `/stats/` |

### Control de acceso por endpoint

| Endpoints | Acceso requerido |
|---|---|
| `POST /auth/login` | Público |
| `GET /occurrences/`, `GET /taxa/`, `GET /stats/` | Cualquier usuario autenticado |
| `GET /occurrences/export` | Cualquier usuario autenticado |
| `POST /occurrences/`, `PATCH /occurrences/*`, `DELETE /occurrences/*` | Solo admin |
| `POST /etl/*` (4 endpoints) | Solo admin |
| `GET /auth/me` | Cualquier usuario autenticado |
| `GET /auth/users`, `POST /auth/users`, `DELETE /auth/users/{id}` | Solo admin |

### Cómo funciona por dentro

**1. Hash de contraseñas** (`auth/core.py`)

```python
import bcrypt

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())
```

Bcrypt genera un salt aleatorio en cada llamada: dos hashes de la misma contraseña son siempre distintos. No hay posibilidad de comparación directa sin la función `checkpw`.

**2. Generación del token** (`auth/core.py`)

```python
def create_access_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")
```

El payload incluye `sub` (user ID), `username`, `role` y `exp` (expiración). Está firmado con la `SECRET_KEY` del `.env`.

**3. Validación de cada petición** (`auth/dependencies.py`)

FastAPI inyecta `get_current_user` como dependencia en cada endpoint protegido:

```python
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_current_user(token = Depends(oauth2_scheme), db = Depends(get_db)) -> User:
    payload = decode_token(token)          # lanza JWTError si expirado o firma inválida
    user = db.get(User, payload["sub"])    # verifica que el usuario aún existe y está activo
    return user

def require_admin(user = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(403, "Solo administradores pueden realizar esta acción")
    return user
```

**4. Crear el usuario admin inicial**

No hay registro público. El primer admin se crea con el script `seed_admin.py`:

```bash
# Con la contraseña por defecto (cambiar antes de producción)
python3 seed_admin.py

# Con contraseña personalizada
SEED_ADMIN_PASSWORD=mi_clave_segura python3 seed_admin.py
```

El script es idempotente: si el usuario `admin` ya existe, no hace nada.

### Uso en Swagger UI

Al abrir `http://localhost:8000/docs`, aparece el botón **Authorize** (🔒). Ingresa las credenciales del admin para que todas las peticiones de prueba incluyan el token automáticamente.

---

## 8. Cómo funciona el pipeline ETL

El archivo `etl/pipeline.py` procesa cada fila del Excel así:

### Paso 1 — Leer el archivo (`loader.py`)

Lee el Excel con `pandas`. Si el archivo tiene varias hojas, detecta automáticamente cuál contiene los datos reales (descarta hojas de diccionarios/metadatos buscando palabras clave como "Variable", "Definicion", "Clase").

### Paso 2 — Mapear columnas (`mapper.py`)

Para cada columna del archivo, determina a qué término DwC corresponde usando dos estrategias en cascada:

**Capa 1 — rapidfuzz** (rápida, sin conexión a red):
- Compara el nombre de la columna contra una lista de pistas semánticas conocidas
- Ejemplo: `latitud_IG` → detecta "latitud" → mapea a `decimalLatitude`
- Si la similitud supera el umbral (80 por defecto), acepta el mapeo

**Capa 2 — Ollama gemma2:2b** (para columnas ambiguas):
- Solo se activa si rapidfuzz no encontró un mapeo con suficiente confianza
- Le pregunta al modelo: *"¿A cuál término DwC corresponde la columna X?"*
- El modelo responde con el nombre exacto del término o `null`
- Opera completamente offline (Ollama corre en la máquina local)

### Paso 3 — Normalizar datos (`normalizer.py`)

| Dato | Problema original | Resultado normalizado |
|---|---|---|
| Fecha | Columnas separadas `dia_colecta_IC`, `mes_colecta_IC`, `ano_colecta_IC` con valores como `16.0`, `11.0`, `1981.0` | `1981-11-16` (ISO 8601) |
| Coordenadas | Valores en grados-minutos-segundos o con coma decimal | `-75.502719` (decimal WGS84) |
| Nombre científico | `genero_TA` = "Anoura" + `epiteto_TA` = "caudifer" | `Anoura caudifer` |
| Estado | "Bueno", "Excelente", "Malo" | `present` (vocabulario DwC) |
| Disposición | "Bueno" → colección, "Extraviado" → perdido | `En colección` / `Extraviado` |

### Paso 4 — Insertar en PostgreSQL (`pipeline.py`)

Para cada fila crea o actualiza los 5 registros relacionados usando **upsert** (`INSERT ON CONFLICT DO UPDATE`):

1. `taxon` — nombre científico + jerarquía taxonómica
2. `event` — fecha y datos de la colecta
3. `location` — coordenadas y ubicación geográfica
4. `occurrence` — registro principal del espécimen (enlaza los anteriores)
5. `identification` — quién determinó el taxón y cuándo

El `occurrenceID` se genera con el formato estándar DwC: `UDEA:MUA-MAM:MUA-MAM000001`.

---

## 9. Integración con IA (Ollama + rapidfuzz)

### ¿Por qué se necesita IA?

Los archivos del MUA tienen columnas con nombres internos (`genero_TA`, `epiteto_TA`, `pais_IG`) que no coinciden directamente con los términos Darwin Core (`genus`, `specificEpithet`, `country`). El mapper automático resuelve esta brecha.

### Estrategia en dos capas

```
Nombre de columna
      ↓
  rapidfuzz               ← rápido, determinista, sin red
  similitud >= 80%?
      ↓ No
  Ollama gemma2:2b        ← IA local, para casos ambiguos
  ¿qué término DwC es?
      ↓
  Término DwC mapeado (o None si no hay coincidencia)
```

### Ejemplo real

```
columna: "departamento_IG"
  rapidfuzz: "departamento" ≈ "departamento" en hints → stateProvince (95%)  ✓

columna: "elev_minima_IG"
  rapidfuzz: sin coincidencia clara
  Ollama: "minimumElevationInMeters"  ✓
```

### Los resultados se cachean

Para no llamar a Ollama dos veces con la misma columna, los resultados se guardan en memoria con `@lru_cache`. Si procesas varios archivos con columnas iguales, Ollama solo se consulta una vez.

---

## 10. Modelo de datos (5 entidades DwC)

Las 5 tablas implementan el estándar Darwin Core:

```
TAXON ←──────────── IDENTIFICATION
  ↑                       ↑
  │                       │
OCCURRENCE ─────────────→ (FK)
  ↓           ↓
EVENT      LOCATION
```

### Tabla `occurrence` (registro principal)

| Campo | Tipo | Descripción |
|---|---|---|
| `occurrence_id` | PK | `UDEA:MUA-MAM:MUA-MAM000001` |
| `catalog_number` | string | Número original del catálogo |
| `collection_code` | string | `MUA-MAM`, `MUA-ANF`, etc. |
| `basis_of_record` | string | Siempre `PreservedSpecimen` |
| `occurrence_status` | string | `present` / `absent` |
| `disposition` | string | `En colección` / `Extraviado` / `Prestado` |
| `sex` | string | `Macho` / `Hembra` |
| `event_id` | FK → event | |
| `taxon_id` | FK → taxon | |
| `location_id` | FK → location | |

### Tabla `taxon`

| Campo | Tipo | Descripción |
|---|---|---|
| `taxon_id` | PK | UUID generado desde el nombre científico |
| `scientific_name` | string | `Anoura caudifer` |
| `taxon_rank` | string | `species` / `genus` / `family` |
| `kingdom` → `specific_epithet` | string | Jerarquía completa |

### Tabla `event`

| Campo | Tipo | Descripción |
|---|---|---|
| `event_id` | PK | UUID generado |
| `event_date` | string | `1981-11-16` (ISO 8601) |
| `year`, `month`, `day` | int | Campos separados para filtrado |
| `habitat` | string | Tipo de hábitat de colecta |

### Tabla `location`

| Campo | Tipo | Descripción |
|---|---|---|
| `location_id` | PK | UUID generado desde coordenadas + lugar |
| `country` | string | `Colombia` |
| `state_province` | string | `Antioquia` |
| `county` | string | `Medellín` |
| `decimal_latitude` | decimal | Coordenada WGS84 |
| `decimal_longitude` | decimal | Coordenada WGS84 |

### Tabla `identification`

| Campo | Tipo | Descripción |
|---|---|---|
| `identification_id` | PK | UUID generado |
| `identified_by` | string | Nombre del taxónomo que determinó |
| `verification_status` | string | `unverified` / `accepted` |

---

## 11. API REST — Endpoints

Con el servidor corriendo en `http://localhost:8000`, estos son los endpoints disponibles.

> **Nota:** Todos los endpoints excepto `POST /auth/login` requieren el header `Authorization: Bearer <token>`. Los marcados con 🔒 requieren rol `admin`.

### Autenticación

| Método | Ruta | Acceso | Descripción |
|---|---|---|---|
| `POST` | `/auth/login` | Público | Obtiene un token JWT. Body: `username=...&password=...` (form) |
| `GET` | `/auth/me` | Autenticado | Devuelve los datos del usuario actual |
| `GET` | `/auth/users` | 🔒 Admin | Lista todos los usuarios del sistema |
| `POST` | `/auth/users` | 🔒 Admin | Crea un usuario. Body JSON: `{username, password, role}` |
| `DELETE` | `/auth/users/{id}` | 🔒 Admin | Elimina un usuario (no puede eliminarse a sí mismo) |

**Obtener token:**
```bash
# Obtener token
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -d "username=admin&password=changeme123" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Usar el token en peticiones subsiguientes
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/occurrences/
```

### Registros biológicos

| Método | Ruta | Acceso | Descripción |
|---|---|---|---|
| `GET` | `/occurrences/` | Autenticado | Lista registros con filtros: `collection_code`, `taxon`, `state_province`, `disposition`, `year_from`, `year_to`, `con_coordenadas` |
| `GET` | `/occurrences/export` | Autenticado | Descarga todos los registros filtrados en CSV (Darwin Core) |
| `GET` | `/occurrences/{id}` | Autenticado | Detalle completo de un registro |
| `POST` | `/occurrences/` | 🔒 Admin | Crea un nuevo registro |
| `PATCH` | `/occurrences/{id}` | 🔒 Admin | Actualiza campos del registro |
| `PATCH` | `/occurrences/{id}/taxon` | 🔒 Admin | Actualiza datos taxonómicos |
| `PATCH` | `/occurrences/{id}/event` | 🔒 Admin | Actualiza datos del evento de colecta |
| `PATCH` | `/occurrences/{id}/location` | 🔒 Admin | Actualiza datos de ubicación |
| `PATCH` | `/occurrences/{id}/identification` | 🔒 Admin | Actualiza datos de identificación |
| `DELETE` | `/occurrences/{id}` | 🔒 Admin | Elimina un registro |

### Taxonomía

| Método | Ruta | Acceso | Descripción |
|---|---|---|---|
| `GET` | `/taxa/` | Autenticado | Lista taxones. Filtros: `nombre`, `familia` |
| `GET` | `/taxa/resumen` | Autenticado | Conteo de taxones por familia |

### Estadísticas de calidad

| Método | Ruta | Acceso | Descripción |
|---|---|---|---|
| `GET` | `/stats/calidad` | Autenticado | Completitud de campos clave |
| `GET` | `/stats/distribucion-geografica` | Autenticado | Registros por departamento |

**Ejemplo de respuesta `/stats/calidad`:**
```json
{
  "total_registros": 1114,
  "completitud": {
    "con_fecha_evento":       { "cantidad": 566,  "porcentaje": 50.8 },
    "con_coordenadas":        { "cantidad": 446,  "porcentaje": 40.0 },
    "con_nombre_cientifico":  { "cantidad": 1077, "porcentaje": 96.7 },
    "con_pais":               { "cantidad": 602,  "porcentaje": 54.0 }
  },
  "por_coleccion": { "MUA-MAM": 647, "MUA-ANF": 467 }
}
```

### ETL (carga de datos)

| Método | Ruta | Acceso | Descripción |
|---|---|---|---|
| `POST` | `/etl/cargar-directorio` | 🔒 Admin | Procesa todos los archivos de `muestras/` |
| `POST` | `/etl/cargar-archivo` | 🔒 Admin | Sube y procesa un archivo (multipart) |
| `POST` | `/etl/cargar-multiples` | 🔒 Admin | Sube y procesa varios archivos a la vez |
| `POST` | `/etl/previsualizar-mapeo` | 🔒 Admin | Muestra el mapeo de columnas sin insertar datos |

**Subir un archivo:**
```bash
curl -X POST http://localhost:8000/etl/cargar-archivo \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/ruta/a/MiColeccion.xlsx"
```

---

## 12. Pruebas

El directorio `tests/` contiene scripts `.sh` que prueban la API contra un servidor real en ejecución.

### Ejecutar la suite de autenticación

```bash
# Asegúrate de tener el servidor corriendo
python3 main.py

# En otra terminal
bash tests/test_auth.sh
```

**Salida esperada (23 pruebas):**

```
▸ 1. Login
  ✓  Login admin → 200, token recibido, role=admin
  ✓  Contraseña incorrecta → 401 Unauthorized
  ✓  Usuario inexistente → 401 Unauthorized
  ✓  Login sin cuerpo → 422 Unprocessable Entity

▸ 2. Protección de endpoints (sin token)
  ✓  GET /occurrences/ sin token → 401
  ✓  GET /taxa/resumen sin token → 401
  ✓  GET /stats/calidad sin token → 401
  ✓  GET /auth/me sin token → 401
  ✓  Token malformado → 401

▸ 3. Acceso con token de admin
  ✓  GET /auth/me → 200, username=admin, role=admin
  ✓  GET /occurrences/ con token admin → 200
  ✓  GET /auth/users con token admin → 200

▸ 4. Gestión de usuarios
  ✓  Crear usuario normal → 201
  ✓  Crear usuario duplicado → 409 Conflict
  ✓  Listar usuarios contiene al usuario recién creado

▸ 5. Control de acceso por rol (RBAC)
  ✓  Login usuario normal → 200, role=user
  ✓  GET /occurrences/ con token user → 200 (lectura permitida)
  ✓  GET /auth/users con token user → 403 Forbidden
  ✓  DELETE /occurrences/ con token user → 403 Forbidden
  ✓  POST /etl/cargar-directorio con token user → 403 Forbidden
  ✓  Admin intenta eliminarse a sí mismo → 400 Bad Request

▸ 6. Limpieza
  ✓  Eliminar usuario de prueba → 204 No Content
  ✓  Usuario eliminado ya no puede hacer login → 401

TODAS LAS PRUEBAS PASARON  23/23
```

El script acepta una URL base como argumento para probar contra entornos distintos:

```bash
bash tests/test_auth.sh http://mi-servidor:8000
```

---

## 13. Consultas útiles en PostgreSQL

```bash
# Entrar a la consola interactiva
psql -U postgres -d mua_biodiversidad

# Contar registros por colección
SELECT collection_code, count(*) FROM occurrence GROUP BY collection_code;

# Ver registros con toda la información relacionada
SELECT o.catalog_number, t.scientific_name, l.state_province,
       l.decimal_latitude, l.decimal_longitude, e.event_date
FROM occurrence o
JOIN taxon     t ON o.taxon_id     = t.taxon_id
JOIN location  l ON o.location_id  = l.location_id
JOIN event     e ON o.event_id     = e.event_id
LIMIT 20;

# Buscar una especie
SELECT * FROM taxon WHERE scientific_name ILIKE '%Anoura%';

# Top 10 familias con más registros
SELECT t.family, count(*) as registros
FROM occurrence o JOIN taxon t ON o.taxon_id = t.taxon_id
WHERE t.family IS NOT NULL
GROUP BY t.family ORDER BY registros DESC LIMIT 10;

# Registros con coordenadas válidas
SELECT count(*) FROM location
WHERE decimal_latitude IS NOT NULL AND decimal_longitude IS NOT NULL;

# Registros por año de colecta
SELECT year, count(*) FROM event
WHERE year IS NOT NULL GROUP BY year ORDER BY year;
```

---

*Backend desarrollado para el proyecto Grupo 6 — Ciencias virtual, Fundamentos de Ingeniería, Universidad de Antioquia, 2026-1*
