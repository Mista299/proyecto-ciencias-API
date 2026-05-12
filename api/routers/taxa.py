from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from models.taxon import Taxon
from auth.dependencies import get_current_user
from models.user import User

router = APIRouter(prefix="/taxa", tags=["taxa"])


@router.get("/")
def list_taxa(
    skip:  int = Query(0, ge=0),
    limit: int = Query(100, le=1000),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return [
        {
            "taxon_id":       t.taxon_id,
            "scientificName": t.scientific_name,
            "taxonRank":      t.taxon_rank,
            "family":         t.family,
            "genus":          t.genus,
        }
        for t in db.query(Taxon).offset(skip).limit(limit).all()
    ]


@router.get("/resumen")
def resumen_taxa(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
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
