import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL  = os.getenv("DATABASE_URL", "postgresql://postgres@localhost:5432/mua_biodiversidad")
OLLAMA_URL    = os.getenv("OLLAMA_URL",   "http://localhost:11434")
OLLAMA_MODEL  = os.getenv("OLLAMA_MODEL", "gemma2:2b")
RAPIDFUZZ_THRESHOLD = int(os.getenv("RAPIDFUZZ_THRESHOLD", "80"))
MUESTRAS_DIR  = os.getenv("MUESTRAS_DIR", "../muestras")
INSTITUTION_CODE = "UDEA"

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
