import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL  = os.getenv("DATABASE_URL", "postgresql://postgres@localhost:5432/mua_biodiversidad")
OLLAMA_URL    = os.getenv("OLLAMA_URL",   "http://localhost:11434")
OLLAMA_MODEL  = os.getenv("OLLAMA_MODEL", "gemma2:2b")
RAPIDFUZZ_THRESHOLD = int(os.getenv("RAPIDFUZZ_THRESHOLD", "80"))
MUESTRAS_DIR  = os.getenv("MUESTRAS_DIR", "../muestras")
INSTITUTION_CODE = "UDEA"

SECRET_KEY            = os.getenv("SECRET_KEY", "dev-insecure-change-me")
ALGORITHM             = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("ACCESS_TOKEN_EXPIRE_HOURS", "8"))

SMTP_HOST     = os.getenv("SMTP_HOST", "")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER     = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM     = os.getenv("SMTP_FROM", "MUA Biodiversidad <noreply@example.com>")
BASE_URL      = os.getenv("BASE_URL", "http://localhost:8000")
FRONTEND_URL  = os.getenv("FRONTEND_URL", "http://localhost:19006")
TEST_MODE     = os.getenv("TEST_MODE", "false").lower() == "true"

DWC_FIELDS = [
    "occurrenceID",
    "basisOfRecord",
    "institutionCode",
    "collectionCode",
    "catalogNumber",
    "occurrenceStatus",
    "disposition",
    "eventDate",
    "country",
    "stateProvince",
    "county",
    "locality",
    "decimalLatitude",
    "decimalLongitude",
    "scientificName",
    "taxonRank",
]

# Hints for rapidfuzz: column name fragments → DwC term
COLUMN_HINTS: dict[str, str] = {
    "occurrence":    "occurrenceID",
    "basis":         "basisOfRecord",
    "institution":   "institutionCode",
    "collection":    "collectionCode",
    "catalog":       "catalogNumber",
    "numero":        "catalogNumber",
    "status":        "occurrenceStatus",
    "estado":        "occurrenceStatus",
    "disposition":   "disposition",
    "disposicion":   "disposition",
    "date":          "eventDate",
    "fecha":         "eventDate",
    "country":       "country",
    "pais":          "country",
    "state":         "stateProvince",
    "departamento":  "stateProvince",
    "province":      "stateProvince",
    "county":        "county",
    "municipio":     "county",
    "locality":      "locality",
    "localidad":     "locality",
    "latitude":      "decimalLatitude",
    "latitud":       "decimalLatitude",
    "longitude":     "decimalLongitude",
    "longitud":      "decimalLongitude",
    "scientific":    "scientificName",
    "cientifico":    "scientificName",
    "rank":          "taxonRank",
    "rango":         "taxonRank",
}
