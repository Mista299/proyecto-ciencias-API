import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import init_db
from api.routers import occurrences, taxa, stats, etl, auth
import config

app = FastAPI(
    title="MUA Biodiversidad API",
    description="API para gestión de colecciones biológicas del Museo Universidad de Antioquia",
    version="1.0.0",
    docs_url="/docs" if config.DEBUG else None,
    redoc_url="/redoc" if config.DEBUG else None,
    openapi_url="/openapi.json" if config.DEBUG else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup():
    init_db()
    logger = logging.getLogger("mua")
    if not config.SMTP_HOST or not config.SMTP_USER:
        logger.warning("⚠  SMTP no configurado — los correos de verificación/reset NO se enviarán")
        logger.warning("   Configura SMTP_HOST, SMTP_USER y SMTP_PASSWORD en .env")
    else:
        logger.info("✓  SMTP configurado: %s:%s", config.SMTP_HOST, config.SMTP_PORT)
    if config.TEST_MODE:
        logger.warning("⚠  TEST_MODE=true — los tokens se devuelven en la API (NO usar en producción)")

app.include_router(auth.router)
app.include_router(occurrences.router)
app.include_router(taxa.router)
app.include_router(stats.router)
app.include_router(etl.router)

@app.get("/")
def root():
    return {"status": "ok", "proyecto": "MUA Biodiversidad", "version": "1.0.0"}
