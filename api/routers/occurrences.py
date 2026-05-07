from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import uuid
from database import get_db
from models.occurrence import Occurrence
from models.taxon import Taxon
from models.event import Event
from models.location import Location
from models.identification import Identification


class OccurrenceUpdate(BaseModel):
    occurrenceStatus: Optional[str] = None
    disposition: Optional[str] = None
    sex: Optional[str] = None
    recordedBy: Optional[str] = None
    preparations: Optional[str] = None
    individualCount: Optional[int] = None


class TaxonUpdate(BaseModel):
    scientificName: Optional[str] = None
    taxonRank: Optional[str] = None
    family: Optional[str] = None
    genus: Optional[str] = None
    specificEpithet: Optional[str] = None


class EventUpdate(BaseModel):
    eventDate: Optional[str] = None
    habitat: Optional[str] = None
    samplingProtocol: Optional[str] = None


class LocationUpdate(BaseModel):
    country: Optional[str] = None
    stateProvince: Optional[str] = None
    county: Optional[str] = None
    municipality: Optional[str] = None
    locality: Optional[str] = None
    decimalLatitude: Optional[float] = None
    decimalLongitude: Optional[float] = None


class IdentificationUpdate(BaseModel):
    identifiedBy: Optional[str] = None
    dateIdentified: Optional[str] = None
    verificationStatus: Optional[str] = None


class NewOccurrence(BaseModel):
    catalogNumber: str
    collectionCode: str
    basisOfRecord: str = "PreservedSpecimen"
    occurrenceStatus: str = "PRESENT"
    disposition: Optional[str] = None
    sex: Optional[str] = None
    recordedBy: Optional[str] = None
    preparations: Optional[str] = None
    # Taxon
    scientificName: Optional[str] = None
    taxonRank: Optional[str] = None
    family: Optional[str] = None
    genus: Optional[str] = None
    # Event
    eventDate: Optional[str] = None
    habitat: Optional[str] = None
    # Location
    country: Optional[str] = None
    stateProvince: Optional[str] = None
    county: Optional[str] = None
    locality: Optional[str] = None
    decimalLatitude: Optional[float] = None
    decimalLongitude: Optional[float] = None


router = APIRouter(prefix="/occurrences", tags=["occurrences"])


def _serialize(occ: Occurrence, taxon=None, event=None, location=None, ident=None) -> dict:
    d = {
        "occurrenceID":     occ.occurrence_id,
        "catalogNumber":    occ.catalog_number,
        "collectionCode":   occ.collection_code,
        "basisOfRecord":    occ.basis_of_record,
        "occurrenceStatus": occ.occurrence_status,
        "disposition":      occ.disposition,
        "sex":              occ.sex,
        "recordedBy":       occ.recorded_by,
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
    if ident:
        d["identification"] = {
            "identifiedBy":      ident.identified_by,
            "dateIdentified":    ident.date_identified,
            "verificationStatus": ident.verification_status,
        }
    return d


def _base_query(db: Session):
    return (
        db.query(Occurrence, Taxon, Event, Location, Identification)
        .outerjoin(Taxon,           Occurrence.taxon_id    == Taxon.taxon_id)
        .outerjoin(Event,           Occurrence.event_id    == Event.event_id)
        .outerjoin(Location,        Occurrence.location_id == Location.location_id)
        .outerjoin(Identification,  Identification.occurrence_id == Occurrence.occurrence_id)
    )


@router.post("/", status_code=201)
def create_occurrence(body: NewOccurrence, db: Session = Depends(get_db)):
    occurrence_id = f"UDEA:{body.collectionCode}:{body.catalogNumber}"
    if db.get(Occurrence, occurrence_id):
        raise HTTPException(409, f"Ya existe un registro con catalogNumber '{body.catalogNumber}' en '{body.collectionCode}'")

    taxon = None
    if body.scientificName:
        taxon = Taxon(
            taxon_id=str(uuid.uuid4()),
            scientific_name=body.scientificName,
            taxon_rank=body.taxonRank,
            family=body.family,
            genus=body.genus,
        )
        db.add(taxon)

    event = None
    if body.eventDate or body.habitat:
        year = month = day = None
        if body.eventDate:
            try:
                from datetime import datetime
                dt = datetime.strptime(body.eventDate[:10], "%Y-%m-%d")
                year, month, day = dt.year, dt.month, dt.day
            except Exception:
                pass
        event = Event(
            event_id=str(uuid.uuid4()),
            event_date=body.eventDate,
            year=year, month=month, day=day,
            habitat=body.habitat,
        )
        db.add(event)

    location = None
    if any([body.country, body.stateProvince, body.county, body.locality,
            body.decimalLatitude, body.decimalLongitude]):
        location = Location(
            location_id=str(uuid.uuid4()),
            country=body.country,
            state_province=body.stateProvince,
            county=body.county,
            locality=body.locality,
            decimal_latitude=body.decimalLatitude,
            decimal_longitude=body.decimalLongitude,
        )
        db.add(location)

    occ = Occurrence(
        occurrence_id=occurrence_id,
        catalog_number=body.catalogNumber,
        collection_code=body.collectionCode,
        basis_of_record=body.basisOfRecord,
        occurrence_status=body.occurrenceStatus,
        institution_code="UDEA",
        disposition=body.disposition,
        sex=body.sex,
        recorded_by=body.recordedBy,
        preparations=body.preparations,
        taxon_id=taxon.taxon_id if taxon else None,
        event_id=event.event_id if event else None,
        location_id=location.location_id if location else None,
    )
    db.add(occ)
    db.commit()
    db.refresh(occ)

    row = _base_query(db).filter(Occurrence.occurrence_id == occurrence_id).first()
    o, t, e, l, i = row
    return _serialize(o, t, e, l, i)


@router.get("/")
def list_occurrences(
    collection_code: str | None = Query(None),
    taxon:           str | None = Query(None),
    family:          str | None = Query(None),
    state_province:  str | None = Query(None),
    disposition:     str | None = Query(None),
    identified_by:   str | None = Query(None),
    verification_status: str | None = Query(None),
    con_coordenadas: bool | None = Query(None),
    year_from:       int | None = Query(None),
    year_to:         int | None = Query(None),
    skip:  int = Query(0, ge=0),
    limit: int = Query(50, le=500),
    db: Session = Depends(get_db),
):
    q = _base_query(db)

    if collection_code:
        q = q.filter(Occurrence.collection_code == collection_code)
    if taxon:
        q = q.filter(Taxon.scientific_name.ilike(f"%{taxon}%"))
    if family:
        q = q.filter(Taxon.family.ilike(f"%{family}%"))
    if state_province:
        q = q.filter(Location.state_province.ilike(f"%{state_province}%"))
    if disposition:
        q = q.filter(Occurrence.disposition == disposition)
    if identified_by:
        q = q.filter(Identification.identified_by.ilike(f"%{identified_by}%"))
    if verification_status:
        q = q.filter(Identification.verification_status == verification_status)
    if con_coordenadas is True:
        q = q.filter(
            Location.decimal_latitude.isnot(None),
            Location.decimal_longitude.isnot(None),
        )
    if year_from:
        q = q.filter(Event.year >= year_from)
    if year_to:
        q = q.filter(Event.year <= year_to)

    rows = q.offset(skip).limit(limit).all()
    return [_serialize(o, t, e, l, i) for o, t, e, l, i in rows]


@router.get("/{occurrence_id}")
def get_occurrence(occurrence_id: str, db: Session = Depends(get_db)):
    row = (
        _base_query(db)
        .filter(Occurrence.occurrence_id == occurrence_id)
        .first()
    )
    if not row:
        raise HTTPException(404, "Ocurrencia no encontrada")
    o, t, e, l, i = row
    return _serialize(o, t, e, l, i)


@router.delete("/{occurrence_id}", status_code=204)
def delete_occurrence(occurrence_id: str, db: Session = Depends(get_db)):
    occ = db.get(Occurrence, occurrence_id)
    if not occ:
        raise HTTPException(404, "Ocurrencia no encontrada")
    db.query(Identification).filter(Identification.occurrence_id == occurrence_id).delete()
    db.delete(occ)
    db.commit()


def _get_full(occurrence_id: str, db: Session):
    row = _base_query(db).filter(Occurrence.occurrence_id == occurrence_id).first()
    if not row:
        raise HTTPException(404, "Ocurrencia no encontrada")
    return row


@router.patch("/{occurrence_id}")
def update_occurrence(occurrence_id: str, body: OccurrenceUpdate, db: Session = Depends(get_db)):
    occ = db.get(Occurrence, occurrence_id)
    if not occ:
        raise HTTPException(404, "Ocurrencia no encontrada")
    if body.occurrenceStatus is not None: occ.occurrence_status = body.occurrenceStatus
    if body.disposition     is not None: occ.disposition        = body.disposition
    if body.sex             is not None: occ.sex                = body.sex
    if body.recordedBy      is not None: occ.recorded_by        = body.recordedBy
    if body.preparations    is not None: occ.preparations       = body.preparations
    if body.individualCount is not None: occ.individual_count   = body.individualCount
    db.commit()
    o, t, e, l, i = _get_full(occurrence_id, db)
    return _serialize(o, t, e, l, i)


@router.patch("/{occurrence_id}/taxon")
def update_taxon(occurrence_id: str, body: TaxonUpdate, db: Session = Depends(get_db)):
    occ = db.get(Occurrence, occurrence_id)
    if not occ or not occ.taxon_id:
        raise HTTPException(404, "Taxón no encontrado para esta ocurrencia")
    taxon = db.get(Taxon, occ.taxon_id)
    if not taxon:
        raise HTTPException(404, "Taxón no encontrado")
    if body.scientificName  is not None: taxon.scientific_name   = body.scientificName
    if body.taxonRank       is not None: taxon.taxon_rank        = body.taxonRank
    if body.family          is not None: taxon.family            = body.family
    if body.genus           is not None: taxon.genus             = body.genus
    if body.specificEpithet is not None: taxon.specific_epithet  = body.specificEpithet
    db.commit()
    o, t, e, l, i = _get_full(occurrence_id, db)
    return _serialize(o, t, e, l, i)


@router.patch("/{occurrence_id}/event")
def update_event(occurrence_id: str, body: EventUpdate, db: Session = Depends(get_db)):
    occ = db.get(Occurrence, occurrence_id)
    if not occ or not occ.event_id:
        raise HTTPException(404, "Evento no encontrado para esta ocurrencia")
    event = db.get(Event, occ.event_id)
    if not event:
        raise HTTPException(404, "Evento no encontrado")
    if body.eventDate        is not None:
        event.event_date = body.eventDate
        try:
            from datetime import datetime
            dt = datetime.strptime(body.eventDate[:10], "%Y-%m-%d")
            event.year, event.month, event.day = dt.year, dt.month, dt.day
        except Exception:
            pass
    if body.habitat          is not None: event.habitat           = body.habitat
    if body.samplingProtocol is not None: event.sampling_protocol = body.samplingProtocol
    db.commit()
    o, t, e, l, i = _get_full(occurrence_id, db)
    return _serialize(o, t, e, l, i)


@router.patch("/{occurrence_id}/location")
def update_location(occurrence_id: str, body: LocationUpdate, db: Session = Depends(get_db)):
    occ = db.get(Occurrence, occurrence_id)
    if not occ or not occ.location_id:
        raise HTTPException(404, "Ubicación no encontrada para esta ocurrencia")
    loc = db.get(Location, occ.location_id)
    if not loc:
        raise HTTPException(404, "Ubicación no encontrada")
    if body.country          is not None: loc.country          = body.country
    if body.stateProvince    is not None: loc.state_province   = body.stateProvince
    if body.county           is not None: loc.county           = body.county
    if body.municipality     is not None: loc.municipality     = body.municipality
    if body.locality         is not None: loc.locality         = body.locality
    if body.decimalLatitude  is not None: loc.decimal_latitude  = body.decimalLatitude
    if body.decimalLongitude is not None: loc.decimal_longitude = body.decimalLongitude
    db.commit()
    o, t, e, l, i = _get_full(occurrence_id, db)
    return _serialize(o, t, e, l, i)


@router.patch("/{occurrence_id}/identification")
def update_identification(occurrence_id: str, body: IdentificationUpdate, db: Session = Depends(get_db)):
    occ = db.get(Occurrence, occurrence_id)
    if not occ:
        raise HTTPException(404, "Ocurrencia no encontrada")
    ident = db.query(Identification).filter(Identification.occurrence_id == occurrence_id).first()
    if not ident:
        ident = Identification(
            identification_id=str(uuid.uuid4()),
            occurrence_id=occurrence_id,
            taxon_id=occ.taxon_id,
        )
        db.add(ident)
    if body.identifiedBy      is not None: ident.identified_by       = body.identifiedBy
    if body.dateIdentified    is not None: ident.date_identified      = body.dateIdentified
    if body.verificationStatus is not None: ident.verification_status = body.verificationStatus
    db.commit()
    o, t, e, l, i = _get_full(occurrence_id, db)
    return _serialize(o, t, e, l, i)
