# Backend — Sistema DwC MUA Biodiversidad

**Proyecto:** Sistema de estandarización de datos bajo el estándar Darwin Core  
**Grupo:** 6 — Ciencias virtual, Universidad de Antioquia  
**Fase:** 3 — Pipeline Python con IA local (Ollama + rapidfuzz)

---

## Tabla de contenido

1. [¿Qué hace este backend?](#1-qué-hace-este-backend)
2. [Requisitos previos](#2-requisitos-previos)
3. [Estructura de archivos](#3-estructura-de-archivos)
4. [Configuración](#4-configuración)
5. [Cómo ejecutar](#5-cómo-ejecutar)
6. [Cómo funciona el pipeline ETL](#6-cómo-funciona-el-pipeline-etl)
7. [Integración con IA (Ollama + rapidfuzz)](#7-integración-con-ia-ollama--rapidfuzz)
8. [Modelo de datos (5 entidades DwC)](#8-modelo-de-datos-5-entidades-dwc)
9. [API REST — Endpoints](#9-api-rest--endpoints)
10. [Consultas útiles en PostgreSQL](#10-consultas-útiles-en-postgresql)

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

## 2. Requisitos previos

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

## 3. Estructura de archivos

```
backend/
├── main.py                  # Punto de entrada — CLI y servidor
├── config.py                # Variables de configuración centralizadas
├── database.py              # Conexión SQLAlchemy + creación de tablas
├── requirements.txt         # Dependencias Python
├── .env                     # Variables de entorno (DB, Ollama, rutas)
│
├── models/                  # Definición de las 5 tablas DwC (ORM)
│   ├── taxon.py             # Tabla: taxon
│   ├── event.py             # Tabla: event
│   ├── location.py          # Tabla: location
│   ├── occurrence.py        # Tabla: occurrence (tabla principal)
│   └── identification.py    # Tabla: identification
│
├── etl/                     # Pipeline de procesamiento de datos
│   ├── loader.py            # Lee Excel/CSV, detecta hoja de datos
│   ├── mapper.py            # Mapea columnas reales → términos DwC
│   ├── normalizer.py        # Normaliza fechas, coordenadas, taxonomía
│   └── pipeline.py          # Orquesta el proceso completo fila por fila
│
└── api/                     # Servidor web FastAPI
    ├── app.py               # Configuración de la app y rutas
    └── routers/
        ├── occurrences.py   # Endpoints: listar, buscar, eliminar registros
        ├── taxa.py          # Endpoints: taxones y resumen taxonómico
        ├── stats.py         # Endpoints: métricas de calidad de datos
        └── etl.py           # Endpoints: subir archivos y disparar ETL
```

---

## 4. Configuración

El archivo `backend/.env` contiene toda la configuración:

```env
DATABASE_URL=postgresql://postgres@localhost:5432/mua_biodiversidad
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=gemma2:2b
RAPIDFUZZ_THRESHOLD=80
MUESTRAS_DIR=../muestras
```

| Variable | Descripción |
|---|---|
| `DATABASE_URL` | Cadena de conexión a PostgreSQL |
| `OLLAMA_URL` | URL donde corre el servidor Ollama |
| `OLLAMA_MODEL` | Modelo a usar (gemma2:2b por defecto) |
| `RAPIDFUZZ_THRESHOLD` | Confianza mínima (0–100) para aceptar un mapeo por fuzzy matching |
| `MUESTRAS_DIR` | Carpeta con los archivos Excel/CSV a cargar |

---

## 5. Cómo ejecutar

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

## 6. Cómo funciona el pipeline ETL

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

## 7. Integración con IA (Ollama + rapidfuzz)

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

## 8. Modelo de datos (5 entidades DwC)

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

## 9. API REST — Endpoints

Con el servidor corriendo en `http://localhost:8000`, estos son los endpoints disponibles:

### Registros biológicos

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/occurrences/` | Lista registros. Parámetros: `?limit=50&collection_code=MUA-MAM&taxon=Anoura` |
| `GET` | `/occurrences/{id}` | Detalle completo de un registro con taxon, evento y ubicación |
| `DELETE` | `/occurrences/{id}` | Elimina un registro |

**Ejemplo:**
```bash
curl "http://localhost:8000/occurrences/?collection_code=MUA-MAM&limit=5"
curl "http://localhost:8000/occurrences/UDEA:MUA-MAM:MUA-MAM000001"
```

### Taxonomía

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/taxa/` | Lista taxones. Parámetros: `?nombre=Anoura&familia=Phyllostomidae` |
| `GET` | `/taxa/resumen` | Conteo de taxones por familia y orden |

### Estadísticas de calidad

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/stats/calidad` | Completitud de campos clave (fecha, coords, nombre científico) |
| `GET` | `/stats/distribucion-geografica` | Registros por departamento |

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

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/etl/cargar-directorio` | Procesa todos los archivos de `muestras/` |
| `POST` | `/etl/cargar-archivo` | Sube y procesa un archivo específico (multipart) |
| `POST` | `/etl/previsualizar-mapeo` | Muestra el mapeo de columnas sin cargar datos |

**Subir un archivo por curl:**
```bash
curl -X POST http://localhost:8000/etl/cargar-archivo \
  -F "archivo=@/ruta/a/MiColeccion.xlsx"
```

---

## 10. Consultas útiles en PostgreSQL

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
