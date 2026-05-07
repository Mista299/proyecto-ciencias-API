from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from models.taxon import Taxon

router = APIRouter(prefix="/taxa", tags=["taxa"])


@router.get("/")
def list_taxa(db: Session = Depends(get_db)):
    return [
        {
            "taxon_id":       t.taxon_id,
            "scientificName": t.scientific_name,
            "taxonRank":      t.taxon_rank,
            "family":         t.family,
            "genus":          t.genus,
        }
        for t in db.query(Taxon).all()
    ]


@router.get("/resumen")
def resumen_taxa(db: Session = Depends(get_db)):
    total = db.query(func.count(Taxon.taxon_id)).scalar()

    por_familia = (
        db.query(Taxon.family, func.count(Taxon.taxon_id).label("count"))
        .group_by(Taxon.family)
        .order_by(func.count(Taxon.taxon_id).desc())
        .all()
    )
    por_orden = (
        db.query(Taxon.order, func.count(Taxon.taxon_id).label("count"))
        .group_by(Taxon.order)
        .order_by(func.count(Taxon.taxon_id).desc())
        .all()
    )

    return {
        "total_taxones": total,
        "por_familia": [{"familia": r[0] or "(sin familia)", "count": r[1]} for r in por_familia],
        "por_orden":   [{"orden":   r[0] or "(sin orden)",   "count": r[1]} for r in por_orden],
    }
