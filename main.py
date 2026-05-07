import sys
import os
import glob
import site

# Auto-detect and activate .venv so the script works without manual activation
_base = os.path.dirname(os.path.abspath(__file__))
_venv_patterns = [
    os.path.join(_base, ".venv", "lib", "python*", "site-packages"),
    os.path.join(_base, "..", ".venv", "lib", "python*", "site-packages"),
]
for _pattern in _venv_patterns:
    _matches = glob.glob(_pattern)
    if _matches:
        site.addsitedir(_matches[0])
        break

sys.path.insert(0, _base)


def run_api():
    import uvicorn
    uvicorn.run("api.app:app", host="0.0.0.0", port=8000, reload=True)


def run_etl():
    from database import SessionLocal, init_db
    init_db()
    db = SessionLocal()
    try:
        from etl.pipeline import ejecutar_pipeline
        resultados = ejecutar_pipeline(db)
        print("\n=== Resumen ETL ===")
        for r in resultados:
            print(f"  {r['archivo']}: {r['insertados']} insertados, {r['actualizados']} actualizados, {r['omitidos']} omitidos")
            if r['errores']:
                print(f"    Errores: {len(r['errores'])}")
    finally:
        db.close()


def run_mapeo():
    import os
    from config import MUESTRAS_DIR
    from etl.loader import cargar_archivo
    from etl.mapper import generar_reporte_mapeo

    directorio = os.path.abspath(os.path.join(_base, MUESTRAS_DIR))
    archivos = glob.glob(os.path.join(directorio, "*.xlsx")) + glob.glob(os.path.join(directorio, "*.csv"))
    for path in sorted(archivos):
        df = cargar_archivo(path)
        reporte = generar_reporte_mapeo(list(df.columns))
        print(f"\n=== {os.path.basename(path)} ===")
        print(f"  Columnas: {reporte['total_columnas']}  Mapeadas: {reporte['mapeadas']}  Cobertura: {reporte['cobertura_pct']}%")
        if reporte['sin_mapear']:
            print(f"  Sin mapear: {reporte['sin_mapear']}")


if __name__ == "__main__":
    if "--etl" in sys.argv:
        run_etl()
    elif "--mapeo" in sys.argv:
        run_mapeo()
    else:
        run_api()
