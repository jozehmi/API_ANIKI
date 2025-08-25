from fastapi import APIRouter
from datetime import datetime
from core.config import VALID_CATEGORIES, VALID_GENRES, VALID_STATUS, VALID_ORDERS, VALID_LETTERS

router = APIRouter()

@router.get("/filters")
def get_filters():
    current_year = datetime.now().year
    return {
        "Category": {"type": "multiple", "options": VALID_CATEGORIES},
        "Genre": {"type": "multiple", "options": VALID_GENRES},
        "minYear": {"type": "integer", "min": 1990, "max": current_year},
        "maxYear": {"type": "integer", "min": 1990, "max": current_year},
        "Status": {"type": "single", "options": VALID_STATUS},
        "Order": {"type": "single", "options": VALID_ORDERS},
        "Letter": {"type": "single", "options": VALID_LETTERS},
        "Page": {"type": "integer", "min": 1},
    }
