import os
import hashlib
import uuid
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from config import MUESTRAS_DIR, INSTITUTION_CODE
from database import SessionLocal
from etl.loader import cargar_archivo, inferir_collection_code
from etl.normalizer import (
    normalizar_fecha, normalizar_coordenada, construir_scientific_name,
    normalizar_occurrence_status, normalizar_disposition, construir_occurrence_id,
)
from models.taxon import Taxon
from models.event import Event
from models.location import Location
from models.occurrence import Occurrence


def _make_id(*parts) -> str:
    text = "|".join(str(p) for p in parts if p)
    return str(uuid.UUID(hashlib.md5(text.encode()).hexdigest()))


def _to_int(valor) -> int | None:
    if valor is None:
        return None
    try:
        return int(float(str(valor)))
    except Exception:
        return None


def _upsert(db: Session, model, data: dict, pk: str):
    stmt = (
        pg_insert(model.__table__)
        .values(**data)
        .on_conflict_do_update(
            index_elements=[pk],
            set_={k: v for k, v in data.items() if k != pk},
        )
    )
    db.execute(stmt)


def _find_col(df_cols: list[str], *fragments) -> str | None:
    for frag in fragments:
        for c in df_cols:
            if frag.lower() in c.lower():
                return c
    return None


def procesar_archivo(path: str, db: Session) -> dict:
    df = cargar_archivo(path)
    collection_code = inferir_collection_code(path)
    cols = list(df.columns)

    insertados = actualizados = omitidos = 0
    errores: list[str] = []

    # Column detection
    c_genero       = _find_col(cols, "genero", "género", "genus")
    c_epiteto      = _find_col(cols, "epiteto", "especie", "specificepithet")
    c_determinacion = _find_col(cols, "determinacion", "determinación", "scientificname", "nombre cientifico")
    c_familia      = _find_col(cols, "familia", "family")
    c_orden        = _find_col(cols, "orden", "order")
    c_clase        = _find_col(cols, "clase", "class")
    c_filo         = _find_col(cols, "phylum", "filo")
    c_reino        = _find_col(cols, "reino", "kingdom")
    c_subfamilia   = _find_col(cols, "subfamilia", "subfamily")
    c_rank         = _find_col(cols, "rango", "rank", "taxonrank")
    c_dia          = _find_col(cols, "dia", "day")
    c_mes          = _find_col(cols, "mes", "month")
    c_ano          = _find_col(cols, "ano", "año", "year")
    c_habitat      = _find_col(cols, "habitat", "hábitat")
    c_pais         = _find_col(cols, "pais", "país", "country")
    c_depto        = _find_col(cols, "departamento", "dpto", "state")
    c_municipio    = _find_col(cols, "municipio", "county")
    c_localidad    = _find_col(cols, "localidad", "locality")
    c_lat          = _find_col(cols, "latitud", "latitude", "decimallat")
    c_lon          = _find_col(cols, "longitud", "longitude", "decimallon")
    c_elev         = _find_col(cols, "altitud", "elevacion", "elevation")
    c_catalog      = _find_col(cols, "numero", "catalogo", "catalog", "id")
    c_sexo         = _find_col(cols, "sexo", "sex")
    c_disp         = _find_col(cols, "disposicion", "disposición", "disposition")
    c_prep         = _find_col(cols, "preparacion", "preparación", "preparation")
    c_ind_count    = _find_col(cols, "individuos", "individualcount")
    c_recorded_by  = _find_col(cols, "colector", "collector", "recordedby")

    for idx, row in df.iterrows():
        try:
            g   = row.get(c_genero) if c_genero else None
            ep  = row.get(c_epiteto) if c_epiteto else None
            det = row.get(c_determinacion) if c_determinacion else None
            sci = construir_scientific_name(g, ep, det)
            if not sci:
                omitidos += 1
                continue

            rank     = row.get(c_rank) if c_rank else "species"
            familia  = row.get(c_familia) if c_familia else None
            orden    = row.get(c_orden) if c_orden else None
            clase    = row.get(c_clase) if c_clase else None
            filo     = row.get(c_filo) if c_filo else None
            reino    = row.get(c_reino) if c_reino else None
            subfam   = row.get(c_subfamilia) if c_subfamilia else None

            taxon_id = _make_id(sci, familia, orden)
            taxon_data = {
                "taxon_id": taxon_id,
                "scientific_name": sci,
                "taxon_rank": rank,
                "kingdom": reino,
                "phylum": filo,
                "class": clase,
                "order": orden,
                "family": familia,
                "subfamily": subfam,
                "genus": g,
                "specific_epithet": ep,
            }
            _upsert(db, Taxon, taxon_data, "taxon_id")

            dia = row.get(c_dia) if c_dia else None
            mes = row.get(c_mes) if c_mes else None
            ano = row.get(c_ano) if c_ano else None
            fecha = normalizar_fecha(dia, mes, ano)

            event_id = _make_id(fecha, collection_code, idx)
            event_data = {
                "event_id": event_id,
                "event_date": fecha,
                "year":  _to_int(ano),
                "month": _to_int(mes),
                "day":   _to_int(dia),
                "habitat": row.get(c_habitat) if c_habitat else None,
            }
            _upsert(db, Event, event_data, "event_id")

            lat = normalizar_coordenada(row.get(c_lat) if c_lat else None, "lat")
            lon = normalizar_coordenada(row.get(c_lon) if c_lon else None, "lon")
            pais   = row.get(c_pais) if c_pais else None
            depto  = row.get(c_depto) if c_depto else None
            mun    = row.get(c_municipio) if c_municipio else None
            loc    = row.get(c_localidad) if c_localidad else None
            elev   = None
            try:
                elev = float(str(row.get(c_elev))) if c_elev and row.get(c_elev) else None
            except Exception:
                pass

            location_id = _make_id(pais, depto, mun, loc, lat, lon)
            location_data = {
                "location_id": location_id,
                "event_id": event_id,
                "country": pais,
                "state_province": depto,
                "county": mun,
                "locality": loc,
                "decimal_latitude": lat,
                "decimal_longitude": lon,
                "geodetic_datum": "WGS84" if lat and lon else None,
                "minimum_elevation": elev,
            }
            _upsert(db, Location, location_data, "location_id")

            cat_raw = row.get(c_catalog) if c_catalog else None
            cat_num = str(cat_raw).strip() if cat_raw else f"{collection_code}{str(idx+1).zfill(6)}"
            occ_id  = construir_occurrence_id(collection_code, cat_num)

            from sqlalchemy import text
            existing = db.execute(
                text("SELECT 1 FROM occurrence WHERE occurrence_id = :id"),
                {"id": occ_id}
            ).fetchone()

            occ_data = {
                "occurrence_id":    occ_id,
                "basis_of_record":  "PreservedSpecimen",
                "institution_code": INSTITUTION_CODE,
                "collection_code":  collection_code,
                "catalog_number":   cat_num,
                "occurrence_status": normalizar_occurrence_status(None),
                "disposition":      normalizar_disposition(row.get(c_disp) if c_disp else None),
                "preparations":     row.get(c_prep) if c_prep else None,
                "sex":              row.get(c_sexo) if c_sexo else None,
                "individual_count": _to_int(row.get(c_ind_count)) if c_ind_count else None,
                "recorded_by":      row.get(c_recorded_by) if c_recorded_by else None,
                "event_id":    event_id,
                "taxon_id":    taxon_id,
                "location_id": location_id,
            }
            _upsert(db, Occurrence, occ_data, "occurrence_id")

            if existing:
                actualizados += 1
            else:
                insertados += 1

        except Exception as e:
            errores.append(f"Fila {idx}: {e}")
            omitidos += 1

    db.commit()

    from etl.mapper import generar_reporte_mapeo
    reporte_mapeo = generar_reporte_mapeo(cols)

    return {
        "archivo":     os.path.basename(path),
        "total_filas": len(df),
        "insertados":  insertados,
        "actualizados": actualizados,
        "omitidos":    omitidos,
        "errores":     errores[:20],
        "mapeo": {
            "total_columnas": reporte_mapeo["total_columnas"],
            "mapeadas":       reporte_mapeo["mapeadas"],
            "sin_mapear":     reporte_mapeo["sin_mapear"],
        },
    }


def ejecutar_pipeline(db: Session) -> list[dict]:
    resultados = []
    directorio = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", MUESTRAS_DIR))
    if not os.path.isdir(directorio):
        raise FileNotFoundError(f"Directorio no encontrado: {directorio}")

    archivos = [
        os.path.join(directorio, f)
        for f in os.listdir(directorio)
        if f.lower().endswith((".xlsx", ".xls", ".csv"))
    ]
    for path in sorted(archivos):
        print(f"  Procesando: {os.path.basename(path)}")
        resultado = procesar_archivo(path, db)
        resultados.append(resultado)
        print(f"    → {resultado['insertados']} insertados, {resultado['actualizados']} actualizados, {resultado['omitidos']} omitidos")

    return resultados
