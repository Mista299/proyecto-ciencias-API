import json
import requests
from functools import lru_cache
from rapidfuzz import process, fuzz
from config import DWC_FIELDS, COLUMN_HINTS, OLLAMA_URL, OLLAMA_MODEL, RAPIDFUZZ_THRESHOLD


def mapear_columnas(columnas: list[str]) -> dict[str, str | None]:
    resultado: dict[str, str | None] = {}
    for col in columnas:
        mapped = _mapear_una(col)
        resultado[col] = mapped
    return resultado


def _mapear_una(col: str) -> str | None:
    col_lower = col.lower().strip()

    # Layer 1 — substring hints
    for hint, dwc_term in COLUMN_HINTS.items():
        if hint in col_lower:
            return dwc_term

    # Layer 2 — rapidfuzz fuzzy match against DwC field names
    match = process.extractOne(col_lower, [f.lower() for f in DWC_FIELDS], scorer=fuzz.WRatio)
    if match and match[1] >= RAPIDFUZZ_THRESHOLD:
        idx = [f.lower() for f in DWC_FIELDS].index(match[0])
        return DWC_FIELDS[idx]

    # Layer 3 — Ollama LLM fallback
    return _consultar_ollama(col)


@lru_cache(maxsize=256)
def _consultar_ollama(col: str) -> str | None:
    prompt = (
        f"Map this column name to a Darwin Core term. "
        f"Column: '{col}'. "
        f"Available DwC terms: {', '.join(DWC_FIELDS)}. "
        f"Reply with only the matching term, or 'null' if no match."
    )
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=15,
        )
        resp.raise_for_status()
        answer = resp.json().get("response", "").strip()
        if answer and answer.lower() != "null":
            for field in DWC_FIELDS:
                if field.lower() == answer.lower():
                    return field
    except Exception:
        pass
    return None


def generar_reporte_mapeo(columnas: list[str]) -> dict:
    mapeo = mapear_columnas(columnas)
    mapeadas    = [c for c, v in mapeo.items() if v is not None]
    sin_mapear  = [c for c, v in mapeo.items() if v is None]
    dwc_cubiertos = list({v for v in mapeo.values() if v is not None})
    dwc_faltantes = [f for f in DWC_FIELDS if f not in dwc_cubiertos]
    cobertura_pct = round(len(dwc_cubiertos) / len(DWC_FIELDS) * 100, 1) if DWC_FIELDS else 0.0

    return {
        "total_columnas": len(columnas),
        "mapeadas":        len(mapeadas),
        "sin_mapear":      sin_mapear,
        "dwc_cubiertos":   dwc_cubiertos,
        "dwc_faltantes":   dwc_faltantes,
        "cobertura_pct":   cobertura_pct,
        "mapeo":           mapeo,
    }
