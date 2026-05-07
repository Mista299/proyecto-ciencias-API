import re
from config import INSTITUTION_CODE


def normalizar_fecha(dia=None, mes=None, ano=None) -> str | None:
    try:
        parts = []
        if ano:
            parts.append(str(int(float(str(ano)))).zfill(4))
        if mes:
            parts.append(str(int(float(str(mes)))).zfill(2))
        if dia:
            parts.append(str(int(float(str(dia)))).zfill(2))
        return "-".join(parts) if parts else None
    except Exception:
        return None


def normalizar_coordenada(valor, tipo: str) -> float | None:
    if valor is None:
        return None
    try:
        f = float(str(valor).replace(",", ".").strip())
        if tipo == "lat"  and not (-90  <= f <= 90):  return None
        if tipo == "lon"  and not (-180 <= f <= 180): return None
        return f
    except Exception:
        return None


def construir_scientific_name(genero=None, epiteto=None, determinacion=None) -> str | None:
    if determinacion:
        return str(determinacion).strip()
    parts = [p for p in [genero, epiteto] if p]
    return " ".join(parts) if parts else None


def normalizar_occurrence_status(valor=None) -> str:
    if not valor:
        return "PRESENT"
    v = str(valor).strip().upper()
    if v in ("PRESENT", "PRESENTE"):
        return "PRESENT"
    if v in ("ABSENT", "AUSENTE"):
        return "ABSENT"
    return "PRESENT"


def normalizar_disposition(valor=None) -> str | None:
    if not valor:
        return None
    v = str(valor).strip()
    KNOWN = ["En colección", "Extraviado", "Prestado", "Destruido", "Donado"]
    for k in KNOWN:
        if k.lower() in v.lower():
            return k
    return v


def construir_occurrence_id(collection_code: str, catalog_number: str) -> str:
    return f"{INSTITUTION_CODE}:{collection_code}:{catalog_number}"
