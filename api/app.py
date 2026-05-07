from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import init_db
from api.routers import occurrences, taxa, stats, etl

app = FastAPI(
    title="MUA Biodiversidad API",
    description="API para gestión de colecciones biológicas del Museo Universidad de Antioquia",
    version="1.0.0",
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

app.include_router(occurrences.router)
app.include_router(taxa.router)
app.include_router(stats.router)
app.include_router(etl.router)

@app.get("/")
def root():
    return {"status": "ok", "proyecto": "MUA Biodiversidad", "version": "1.0.0"}
