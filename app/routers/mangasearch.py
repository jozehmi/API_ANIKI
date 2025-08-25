from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel
import urllib.parse
import re
from core.config import ZONATMO_HEADERS

router = APIRouter()

# ----------------------------
# Models
# ----------------------------
class MangaSearchResult(BaseModel):
    title: str
    score: float
    type: str
    demography: str
    url: str
    image_url: str
    is_erotic: bool

class MangaSearchResponse(BaseModel):
    url: str
    results: List[MangaSearchResult]

# ----------------------------
# Valid constants
# ----------------------------
VALID_ORDER_ITEMS = ["likes_count", "title", "score", "created_at", "released_at", "chapters_count"]
VALID_ORDER_DIRS = ["asc", "desc"]
VALID_TYPES = ["manga", "manhua", "manhwa", "novel", "one_shot", "doujinshi", "oel"]
VALID_DEMOGRAPHIES = ["seinen", "shoujo", "shounen", "josei", "kodomo"]
VALID_STATUSES = ["publishing", "ended", "cancelled", "on_hold"]
VALID_TRANSLATION_STATUSES = ["active", "finished", "abandoned"]
VALID_BINARY_FILTERS = ["true", "false"]
VALID_GENRES = [
    "action", "adventure", "comedy", "drama", "slice_of_life", "ecchi", "fantasy", "magic",
    "supernatural", "horror", "mystery", "psychological", "romance", "sci_fi", "thriller",
    "sports", "girls_love", "boys_love", "harem", "mecha", "survival", "reincarnation",
    "gore", "apocalyptic", "tragedy", "school_life", "history", "military", "police",
    "crime", "super_powers", "vampires", "martial_arts", "samurai", "gender_bender",
    "virtual_reality", "cyberpunk", "music", "parody", "animation", "demons", "family",
    "foreign", "kids", "reality", "soap_opera", "war", "western", "traps"
]
VALID_FILTER_BY = ["title", "author", "company"]

# ----------------------------
# Utils
# ----------------------------
def validate_query(
    order_item, order_dir, type, demography, status,
    translation_status, webcomic, yonkoma, amateur, erotic,
    genres, exclude_genres, page, filter_by
):
    if order_item and order_item not in VALID_ORDER_ITEMS:
        raise HTTPException(status_code=400, detail=f"Invalid order_item. Must be one of {VALID_ORDER_ITEMS}")
    if order_dir and order_dir not in VALID_ORDER_DIRS:
        raise HTTPException(status_code=400, detail=f"Invalid order_dir. Must be one of {VALID_ORDER_DIRS}")
    if type and type not in VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid type. Must be one of {VALID_TYPES}")
    if demography and demography not in VALID_DEMOGRAPHIES:
        raise HTTPException(status_code=400, detail=f"Invalid demography. Must be one of {VALID_DEMOGRAPHIES}")
    if status and status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of {VALID_STATUSES}")
    if translation_status and translation_status not in VALID_TRANSLATION_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid translation_status. Must be one of {VALID_TRANSLATION_STATUSES}")
    for filter_name, value in [("webcomic", webcomic), ("yonkoma", yonkoma), ("amateur", amateur), ("erotic", erotic)]:
        if value and value not in VALID_BINARY_FILTERS:
            raise HTTPException(status_code=400, detail=f"Invalid {filter_name}. Must be one of {VALID_BINARY_FILTERS}")
    if genres:
        for genre in genres:
            if genre not in VALID_GENRES:
                raise HTTPException(status_code=400, detail=f"Invalid genre: {genre}. Must be one of {VALID_GENRES}")
    if exclude_genres:
        for genre in exclude_genres:
            if genre not in VALID_GENRES:
                raise HTTPException(status_code=400, detail=f"Invalid exclude_genre: {genre}. Must be one of {VALID_GENRES}")
    if page and page < 1:
        raise HTTPException(status_code=400, detail="Page number must be positive")
    if filter_by not in VALID_FILTER_BY:
        raise HTTPException(status_code=400, detail=f"Invalid filter_by. Must be one of {VALID_FILTER_BY}")

def build_url(
    title, order_item, order_dir, type, demography, status,
    translation_status, webcomic, yonkoma, amateur, erotic,
    genres, exclude_genres, page, filter_by
) -> str:
    GENRE_TO_ID = {
        "action": 1,
        "adventure": 2,
        "comedy": 3,
        "drama": 4,
        "slice_of_life": 5,
        "ecchi": 6,
        "fantasy": 7,
        "magic": 8,
        "supernatural": 9,
        "horror": 10,
        "mystery": 11,
        "psychological": 12,
        "romance": 13,
        "sci_fi": 14,
        "thriller": 15,
        "sports": 16,
        "girls_love": 17,
        "boys_love": 18,
        "harem": 19,
        "mecha": 20,
        "survival": 21,
        "reincarnation": 22,
        "gore": 23,
        "apocalyptic": 24,
        "tragedy": 25,
        "school_life": 26,
        "history": 27,
        "military": 28,
        "police": 29,
        "crime": 30,
        "super_powers": 31,
        "vampires": 32,
        "martial_arts": 33,
        "samurai": 34,
        "gender_bender": 35,
        "virtual_reality": 36,
        "cyberpunk": 37,
        "music": 38,
        "parody": 39,
        "animation": 40,
        "demons": 41,
        "family": 42,
        "foreign": 43,
        "kids": 44,
        "reality": 45,
        "soap_opera": 46,
        "war": 47,
        "western": 48,
        "traps": 49
    }

    query_params = {
        "order_item": order_item or "likes_count",
        "order_dir": order_dir or "desc",
        "title": title or "",
        "_pg": "1",  # Always set to "1" as a fixed parameter
        "filter_by": filter_by,  # Always include filter_by, defaults to "title"
        "type": type or "",
        "demography": demography or "",
        "status": status or "",
        "translation_status": translation_status or "",
        "webcomic": webcomic or "",
        "yonkoma": yonkoma or "",
        "amateur": amateur or "",
        "erotic": erotic or ""
    }
    if page and page > 1:
        query_params["page"] = str(page)  # Only add "page" if greater than 1
    if genres:
        query_params["genders[]"] = [str(GENRE_TO_ID[g]) for g in genres]
    if exclude_genres:
        query_params["exclude_genders[]"] = [str(GENRE_TO_ID[g]) for g in exclude_genres]

    base_url = "https://zonatmo.com/library"
    return f"{base_url}?{urllib.parse.urlencode(query_params, doseq=True)}"

def scrape(url: str) -> List[MangaSearchResult]:
    headers = ZONATMO_HEADERS
    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch data from ZonaTMO: {str(e)}")

    soup = BeautifulSoup(response.text, "html.parser")
    cards = soup.select("div.element")

    results: List[MangaSearchResult] = []

    for card in cards:
        a_elem = card.find("a", href=True)
        if not a_elem:
            continue
        manga_url = a_elem["href"].strip()
        thumb = a_elem.select_one("div.thumbnail.book")
        if not thumb:
            continue

        # Título
        title_elem = thumb.select_one(".thumbnail-title h4.text-truncate")
        title_text = (title_elem.get("title") or title_elem.get_text(strip=True)) if title_elem else "Unknown"

        # Score
        score_elem = thumb.select_one("span.score > span")
        score_text = score_elem.get_text(strip=True) if score_elem else "0"
        try:
            score = float(score_text.replace(",", "."))
        except ValueError:
            score = 0.0

        # Tipo
        type_elem = thumb.select_one("span.book-type")
        type_text = type_elem.get_text(strip=True) if type_elem else "Unknown"

        # Demografía
        demography_elem = thumb.select_one("span.demography")
        demography_text = demography_elem.get_text(strip=True) if demography_elem else "Unknown"

        # Erótico
        is_erotic = thumb.select_one("i.fas.fa-heartbeat") is not None

        # Imagen
        image_url = "Unknown"
        for style_tag in thumb.find_all("style"):
            m = re.search(r"background-image:\s*url\(['\"]?(.*?)['\"]?\)", style_tag.text)
            if m:
                image_url = m.group(1).strip()
                break

        results.append(MangaSearchResult(
            title=title_text,
            score=score,
            type=type_text,
            demography=demography_text,
            url=manga_url,
            image_url=image_url,
            is_erotic=is_erotic
        ))

    return results

# ----------------------------
# Endpoint SOLO GET
# ----------------------------
@router.get("/search", response_model=MangaSearchResponse)
async def search_get(
    title: Optional[str] = Query(None),
    order_item: Optional[str] = Query(None),
    order_dir: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    demography: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    translation_status: Optional[str] = Query(None),
    webcomic: Optional[str] = Query(None),
    yonkoma: Optional[str] = Query(None),
    amateur: Optional[str] = Query(None),
    erotic: Optional[str] = Query(None),
    genres: Optional[List[str]] = Query(None),
    exclude_genres: Optional[List[str]] = Query(None),
    page: Optional[int] = Query(1),
    filter_by: str = Query("title")
):
    validate_query(order_item, order_dir, type, demography, status,
                   translation_status, webcomic, yonkoma, amateur,
                   erotic, genres, exclude_genres, page, filter_by)
    url = build_url(title, order_item, order_dir, type, demography, status,
                    translation_status, webcomic, yonkoma, amateur, erotic,
                    genres, exclude_genres, page, filter_by)
    results = scrape(url)
    return MangaSearchResponse(url=url, results=results)
    return MangaSearchResponse(url=url, results=results)
