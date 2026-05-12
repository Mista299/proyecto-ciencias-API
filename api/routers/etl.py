import os
import shutil
import tempfile
import logging
from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from etl.pipeline import procesar_archivo, ejecutar_pipeline
from etl.mapper import generar_reporte_mapeo
from etl.loader import cargar_archivo
from auth.dependencies import require_admin
from models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/etl", tags=["etl"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


async def _validate_upload(file: UploadFile) -> tuple[str, str]:
    """Validate extension and size; return (suffix, tmp_path)."""
    suffix = os.path.splitext(file.filename or "")[1].lower()
    if suffix not in (".xlsx", ".xls", ".csv"):
        raise HTTPException(400, "Formato no soportado. Use .xlsx, .xls o .csv")

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        size = 0
        chunk_size = 64 * 1024
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                tmp.close()
                os.unlink(tmp.name)
                raise HTTPException(413, f"El archivo supera el límite de {MAX_UPLOAD_BYTES // (1024*1024)} MB")
            tmp.write(chunk)
        tmp_path = tmp.name

    return suffix, tmp_path


@router.post("/cargar-directorio")
def cargar_directorio(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    try:
        return ejecutar_pipeline(db)
    except FileNotFoundError:
        raise HTTPException(404, "Directorio de muestras no encontrado")
    except Exception as e:
        logger.exception("Error en cargar-directorio")
        raise HTTPException(500, "Error interno al procesar el directorio")


@router.post("/cargar-archivo")
async def cargar_archivo_endpoint(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    suffix, tmp_path = await _validate_upload(file)
    named_path = tmp_path + "_" + (file.filename or "upload" + suffix)
    try:
        os.rename(tmp_path, named_path)
        return procesar_archivo(named_path, db)
    except Exception as e:
        logger.exception("Error procesando archivo %s", file.filename)
        raise HTTPException(500, "Error interno al procesar el archivo")
    finally:
        try:
            os.unlink(named_path)
        except OSError:
            pass


@router.post("/cargar-multiples")
async def cargar_multiples(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    resultados = []
    for upload in files:
        try:
            suffix, tmp_path = await _validate_upload(upload)
        except HTTPException as exc:
            resultados.append({
                "archivo": upload.filename, "total_filas": 0,
                "insertados": 0, "actualizados": 0, "omitidos": 0,
                "errores": [exc.detail],
                "mapeo": {"total_columnas": 0, "mapeadas": 0, "sin_mapear": []},
            })
            continue

        named_path = tmp_path + "_" + (upload.filename or "upload" + suffix)
        try:
            os.rename(tmp_path, named_path)
            resultados.append(procesar_archivo(named_path, db))
        except Exception:
            logger.exception("Error procesando archivo %s", upload.filename)
            resultados.append({
                "archivo": upload.filename, "total_filas": 0,
                "insertados": 0, "actualizados": 0, "omitidos": 0,
                "errores": ["Error interno al procesar el archivo"],
                "mapeo": {"total_columnas": 0, "mapeadas": 0, "sin_mapear": []},
            })
        finally:
            try:
                os.unlink(named_path)
            except OSError:
                pass
    return resultados


@router.post("/previsualizar-mapeo")
async def previsualizar_mapeo(
    file: UploadFile = File(...),
    _: User = Depends(require_admin),
):
    suffix, tmp_path = await _validate_upload(file)
    try:
        df = cargar_archivo(tmp_path)
        return generar_reporte_mapeo(list(df.columns))
    except Exception:
        logger.exception("Error en previsualizar-mapeo para %s", file.filename)
        raise HTTPException(500, "Error interno al analizar el archivo")
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
