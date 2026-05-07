from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select
from database import get_db
from models.occurrence import Occurrence
from models.taxon import Taxon
from models.event import Event
from models.location import Location

router = APIRouter(prefix="/occurrences", tags=["occurrences"])


def _serialize(occ: Occurrence, taxon=None, event=None, location=None) -> dict:
    d = {
        "occurrenceID":    occ.occurrence_id,
        "catalogNumber":   occ.catalog_number,
        "collectionCode":  occ.collection_code,
        "basisOfRecord":   occ.basis_of_record,
        "occurrenceStatus": occ.occurrence_status,
        "disposition":     occ.disposition,
        "sex":             occ.sex,
        "recordedBy":      occ.recorded_by,
    }
    if taxon:
        d["taxon"] = {
            "scientificName": taxon.scientific_name,
            "taxonRank":      taxon.taxon_rank,
            "family":         taxon.family,
            "genus":          taxon.genus,
        }
    if event:
        d["event"] = {
            "eventDate": event.event_date,
            "habitat":   event.habitat,
        }
    if location:
        d["location"] = {
            "country":          location.country,
            "stateProvince":    location.state_province,
            "county":           location.county,
            "locality":         location.locality,
            "decimalLatitude":  location.decimal_latitude,
            "decimalLongitude": location.decimal_longitude,
        }
    return d


@router.get("/")
def list_occurrences(
    collection_code: str | None = Query(None),
    taxon: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, le=500),
    db: Session = Depends(get_db),
):
    q = (
        db.query(Occurrence, Taxon, Event, Location)
        .outerjoin(Taxon,    Occurrence.taxon_id    == Taxon.taxon_id)
        .outerjoin(Event,    Occurrence.event_id    == Event.event_id)
        .outerjoin(Location, Occurrence.location_id == Location.location_id)
    )
    if collection_code:
        q = q.filter(Occurrence.collection_code == collection_code)
    if taxon:
        q = q.filter(Taxon.scientific_name.ilike(f"%{taxon}%"))
    rows = q.offset(skip).limit(limit).all()
    return [_serialize(o, t, e, l) for o, t, e, l in rows]


@router.get("/{occurrence_id}")
def get_occurrence(occurrence_id: str, db: Session = Depends(get_db)):
    row = (
        db.query(Occurrence, Taxon, Event, Location)
        .outerjoin(Taxon,    Occurrence.taxon_id    == Taxon.taxon_id)
        .outerjoin(Event,    Occurrence.event_id    == Event.event_id)
        .outerjoin(Location, Occurrence.location_id == Location.location_id)
        .filter(Occurrence.occurrence_id == occurrence_id)
        .first()
    )
    if not row:
        raise HTTPException(404, "Ocurrencia no encontrada")
    o, t, e, l = row
    return _serialize(o, t, e, l)


@router.delete("/{occurrence_id}", status_code=204)
def delete_occurrence(occurrence_id: str, db: Session = Depends(get_db)):
    occ = db.get(Occurrence, occurrence_id)
    if not occ:
        raise HTTPException(404, "Ocurrencia no encontrada")
    db.delete(occ)
    db.commit()
