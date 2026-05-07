import os
import pandas as pd

COLLECTION_PATTERNS = {
    "MAM": "MUA-MAM",
    "ANF": "MUA-ANF",
    "AVE": "MUA-AVE",
    "REP": "MUA-REP",
    "PEZ": "MUA-PEZ",
    "INV": "MUA-INV",
}

def inferir_collection_code(path: str) -> str:
    name = os.path.basename(path).upper()
    for key, code in COLLECTION_PATTERNS.items():
        if key in name:
            return code
    return "MUA-GEN"

def cargar_archivo(path: str) -> pd.DataFrame:
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xls"):
        df = pd.read_excel(path, dtype=str)
    elif ext == ".csv":
        df = pd.read_csv(path, dtype=str, encoding="utf-8-sig")
    else:
        raise ValueError(f"Formato no soportado: {ext}")
    df.columns = [str(c).strip() for c in df.columns]
    df = df.where(pd.notna(df), None)
    return df
