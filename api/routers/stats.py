from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from models.occurrence import Occurrence
from models.taxon import Taxon
from models.event import Event
from models.location import Location
from auth.dependencies import get_current_user
from models.user import User

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/calidad")
def calidad(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    total = db.query(func.count(Occurrence.occurrence_id)).scalar() or 0

    def pct(n: int) -> float:
        return round(n / total * 100, 1) if total else 0.0

    con_fecha = (
        db.query(func.count(Occurrence.occurrence_id))
        .join(Event, Occurrence.event_id == Event.event_id)
        .filter(Event.event_date.isnot(None))
        .scalar() or 0
    )
    con_coords = (
        db.query(func.count(Occurrence.occurrence_id))
        .join(Location, Occurrence.location_id == Location.location_id)
        .filter(
            Location.decimal_latitude.isnot(None),
            Location.decimal_longitude.isnot(None),
        )
        .scalar() or 0
    )
    con_sci = (
        db.query(func.count(Occurrence.occurrence_id))
        .join(Taxon, Occurrence.taxon_id == Taxon.taxon_id)
        .filter(Taxon.scientific_name.isnot(None))
        .scalar() or 0
    )
    con_pais = (
        db.query(func.count(Occurrence.occurrence_id))
        .join(Location, Occurrence.location_id == Location.location_id)
        .filter(Location.country.isnot(None))
        .scalar() or 0
    )

    por_coleccion = dict(
        db.query(Occurrence.collection_code, func.count(Occurrence.occurrence_id))
        .group_by(Occurrence.collection_code)
        .all()
    )
    por_estado = dict(
        db.query(Occurrence.occurrence_status, func.count(Occurrence.occurrence_id))
        .group_by(Occurrence.occurrence_status)
        .all()
    )

    return {
        "total_registros": total,
        "completitud": {
            "con_fecha_evento":      {"cantidad": con_fecha,  "porcentaje": pct(con_fecha)},
            "con_coordenadas":       {"cantidad": con_coords, "porcentaje": pct(con_coords)},
            "con_nombre_cientifico": {"cantidad": con_sci,    "porcentaje": pct(con_sci)},
            "con_pais":              {"cantidad": con_pais,   "porcentaje": pct(con_pais)},
        },
        "por_coleccion": por_coleccion,
        "por_estado":    por_estado,
    }


@router.get("/distribucion-geografica")
def distribucion(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = (
        db.query(Location.country, func.count(Occurrence.occurrence_id).label("count"))
        .join(Occurrence, Location.location_id == Occurrence.location_id)
        .group_by(Location.country)
        .order_by(func.count(Occurrence.occurrence_id).desc())
        .all()
    )
    return [{"country": r[0] or "(sin país)", "count": r[1]} for r in rows]


@router.get("/mapa")
def mapa(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = (
        db.query(
            Location.decimal_latitude,
            Location.decimal_longitude,
            Occurrence.occurrence_id,
            Occurrence.catalog_number,
            Occurrence.disposition,
            Taxon.scientific_name,
            Taxon.family,
            Taxon.order,
            Location.state_province,
        )
        .join(Occurrence, Location.location_id == Occurrence.location_id)
        .join(Taxon, Occurrence.taxon_id == Taxon.taxon_id, isouter=True)
        .filter(
            Location.decimal_latitude.isnot(None),
            Location.decimal_longitude.isnot(None),
        )
        .limit(5000)
        .all()
    )
    return [
        {
            "lat":            r[0],
            "lng":            r[1],
            "occurrenceId":   r[2],
            "catalogNumber":  r[3],
            "disposition":    r[4],
            "scientificName": r[5],
            "family":         r[6],
            "taxonOrder":     r[7],
            "stateProvince":  r[8],
        }
        for r in rows
    ]
