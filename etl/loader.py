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

_DICT_COLUMNS = {"variable", "definicion", "clase", "ejemplo", "valor", "unidades", "obligatorio"}

def _detectar_hoja_datos(xl: pd.ExcelFile) -> str:
    """Devuelve el nombre de la hoja con datos reales (descarta hojas tipo diccionario)."""
    best_sheet = xl.sheet_names[0]
    best_cols  = 0
    for sheet in xl.sheet_names:
        df = pd.read_excel(xl, sheet_name=sheet, dtype=str, nrows=1)
        cols_lower = {str(c).strip().lower() for c in df.columns}
        # Salta hojas que parecen diccionarios de variables
        if cols_lower <= _DICT_COLUMNS or len(df.columns) < 10:
            continue
        if len(df.columns) > best_cols:
            best_cols  = len(df.columns)
            best_sheet = sheet
    return best_sheet

def cargar_archivo(path: str) -> pd.DataFrame:
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xls"):
        xl = pd.ExcelFile(path)
        sheet = _detectar_hoja_datos(xl)
        df = pd.read_excel(xl, sheet_name=sheet, dtype=str)
    elif ext == ".csv":
        df = pd.read_csv(path, dtype=str, encoding="utf-8-sig")
    else:
        raise ValueError(f"Formato no soportado: {ext}")
    df.columns = [str(c).strip() for c in df.columns]
    # dtype=str convierte NaN a la cadena 'nan' — hay que limpiarla
    df = df.where(pd.notna(df), None)
    df = df.replace('nan', None)
    return df
