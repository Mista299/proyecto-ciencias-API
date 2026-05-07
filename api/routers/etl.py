import os
import shutil
import tempfile
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from etl.pipeline import procesar_archivo, ejecutar_pipeline
from etl.mapper import generar_reporte_mapeo
from etl.loader import cargar_archivo

router = APIRouter(prefix="/etl", tags=["etl"])


@router.post("/cargar-directorio")
def cargar_directorio(db: Session = Depends(get_db)):
    try:
        resultados = ejecutar_pipeline(db)
        return resultados
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/cargar-archivo")
async def cargar_archivo_endpoint(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    suffix = os.path.splitext(file.filename or "")[1].lower()
    if suffix not in (".xlsx", ".xls", ".csv"):
        raise HTTPException(400, "Formato no soportado. Use .xlsx o .csv")

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        # Preserve original filename so inferir_collection_code works
        named_path = tmp_path + "_" + (file.filename or "upload" + suffix)
        os.rename(tmp_path, named_path)
        resultado = procesar_archivo(named_path, db)
        return resultado
    finally:
        try:
            os.unlink(named_path)
        except Exception:
            pass


@router.post("/previsualizar-mapeo")
async def previsualizar_mapeo(file: UploadFile = File(...)):
    suffix = os.path.splitext(file.filename or "")[1].lower()
    if suffix not in (".xlsx", ".xls", ".csv"):
        raise HTTPException(400, "Formato no soportado. Use .xlsx o .csv")

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        df = cargar_archivo(tmp_path)
        reporte = generar_reporte_mapeo(list(df.columns))
        return reporte
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
