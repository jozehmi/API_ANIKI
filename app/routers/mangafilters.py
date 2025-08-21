from fastapi import APIRouter
import json

router = APIRouter()

# Definición de los filtros y sus valores válidos, sin incluir campos con null
FILTERS = {
    "title": {
        "description": "Búsqueda por título (texto libre)",
        "type": "string",
        "example": "Solo Leveling"
    },
    "order_item": {
        "description": "Criterio de ordenación",
        "type": "string",
        "values": [
            "likes_count",  # Me gusta
            "title",        # Alfabético
            "score",        # Puntuación
            "created_at",   # Creación
            "released_at",  # Fecha estreno
            "chapters_count" # Núm. Capítulos
        ],
        "default": "likes_count"
    },
    "order_dir": {
        "description": "Dirección de ordenación",
        "type": "string",
        "values": ["asc", "desc"],
        "default": "desc"
    },
    "type": {
        "description": "Tipo de contenido",
        "type": "string",
        "values": [
            "manga",
            "manhua",
            "manhwa",
            "novel",
            "one_shot",
            "doujinshi",
            "oel"
        ]
    },
    "demography": {
        "description": "Demografía",
        "type": "string",
        "values": [
            "seinen",
            "shoujo",
            "shounen",
            "josei",
            "kodomo"
        ]
    },
    "status": {
        "description": "Estado de publicación",
        "type": "string",
        "values": [
            "publishing",  # Publicándose
            "finished",    # Finalizado
            "canceled",    # Cancelado
            "paused"       # Pausado
        ]
    },
    "translation_status": {
        "description": "Estado de traducción",
        "type": "string",
        "values": [
            "active",      # Activo
            "finished",    # Finalizado
            "abandoned"    # Abandonado
        ]
    },
    "webcomic": {
        "description": "Filtrar por webcomic",
        "type": "string",
        "values": ["yes", "no"]
    },
    "yonkoma": {
        "description": "Filtrar por yonkoma",
        "type": "string",
        "values": ["yes", "no"]
    },
    "amateur": {
        "description": "Filtrar por contenido amateur",
        "type": "string",
        "values": ["yes", "no"]
    },
    "erotic": {
        "description": "Filtrar por contenido erótico",
        "type": "string",
        "values": ["yes", "no"]
    },
    "genres": {
        "description": "Géneros a incluir (múltiples valores permitidos)",
        "type": "list",
        "values": [
            "action",
            "adventure",
            "comedy",
            "drama",
            "slice_of_life",
            "ecchi",
            "fantasy",
            "magic",
            "supernatural",
            "horror",
            "mystery",
            "psychological",
            "romance",
            "sci_fi",
            "thriller",
            "sports",
            "girls_love",
            "boys_love",
            "harem",
            "mecha",
            "survival",
            "reincarnation",
            "gore",
            "apocalyptic",
            "tragedy",
            "school_life",
            "history",
            "military",
            "police",
            "crime",
            "super_powers",
            "vampires",
            "martial_arts",
            "samurai",
            "gender_bender",
            "virtual_reality",
            "cyberpunk",
            "music",
            "parody",
            "animation",
            "demons",
            "family",
            "foreign",
            "kids",
            "reality",
            "soap_opera",
            "war",
            "western",
            "traps"
        ]
    },
    "exclude_genres": {
        "description": "Géneros a excluir (múltiples valores permitidos)",
        "type": "list",
        "values": [
            "action",
            "adventure",
            "comedy",
            "drama",
            "slice_of_life",
            "ecchi",
            "fantasy",
            "magic",
            "supernatural",
            "horror",
            "mystery",
            "psychological",
            "romance",
            "sci_fi",
            "thriller",
            "sports",
            "girls_love",
            "boys_love",
            "harem",
            "mecha",
            "survival",
            "reincarnation",
            "gore",
            "apocalyptic",
            "tragedy",
            "school_life",
            "history",
            "military",
            "police",
            "crime",
            "super_powers",
            "vampires",
            "martial_arts",
            "samurai",
            "gender_bender",
            "virtual_reality",
            "cyberpunk",
            "music",
            "parody",
            "animation",
            "demons",
            "family",
            "foreign",
            "kids",
            "reality",
            "soap_opera",
            "war",
            "western",
            "traps"
        ]
    },
    "page": {
        "description": "Número de página para paginación",
        "type": "integer",
        "default": 1,
        "minimum": 1
    }
}

@router.get("/filters", summary="Obtener filtros disponibles")
async def get_filters():
    """
    Devuelve todos los filtros disponibles para la búsqueda de mangas en la biblioteca.

    Respuesta:
    - filters: Diccionario con los filtros y sus opciones válidas, incluyendo descripción, tipo y valores posibles.
    """
    # Depuración para verificar que FILTERS no contiene null
    print("FILTERS:", json.dumps(FILTERS, indent=2, ensure_ascii=False))
    return {"filters": FILTERS}