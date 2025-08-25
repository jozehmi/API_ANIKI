from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from pydantic import BaseModel
from playwright.async_api import async_playwright
from playwright.sync_api import sync_playwright
import urllib.parse
import re
import time
from app.core.config import ZONATMO_HEADERS

router = APIRouter()

# ----------------------------
# Lista de proxies autenticados
# Formato: IP:PUERTO:USUARIO:CONTRASEÑA
# ----------------------------
PROXIES = [
    "23.95.150.145:6114:xjyuuqko:u9oqfcqmfb7o",
    "198.23.239.134:6540:xjyuuqko:u9oqfcqmfb7o",
    "45.38.107.97:6014:xjyuuqko:u9oqfcqmfb7o",
    "107.172.163.27:6543:xjyuuqko:u9oqfcqmfb7o",
    "64.137.96.74:6641:xjyuuqko:u9oqfcqmfb7o",
    "45.43.186.39:6257:xjyuuqko:u9oqfcqmfb7o",
    "154.203.43.247:5536:xjyuuqko:u9oqfcqmfb7o",
    "216.10.27.159:6837:xjyuuqko:u9oqfcqmfb7o",
    "136.0.207.84:6661:xjyuuqko:u9oqfcqmfb7o",
    "142.147.128.93:6593:xjyuuqko:u9oqfcqmfb7o",
]

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
    GENRE_TO_ID = {g: i+1 for i, g in enumerate(VALID_GENRES)}

    query_params = {
        "order_item": order_item or "likes_count",
        "order_dir": order_dir or "desc",
        "title": title or "",
        "_pg": "1",
        "filter_by": filter_by,
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
        query_params["page"] = str(page)
    if genres:
        query_params["genders[]"] = [str(GENRE_TO_ID[g]) for g in genres]
    if exclude_genres:
        query_params["exclude_genders[]"] = [str(GENRE_TO_ID[g]) for g in exclude_genres]

    base_url = "https://zonatmo.com/library"
    return f"{base_url}?{urllib.parse.urlencode(query_params, doseq=True)}"

# ----------------------------
# Scrape usando Playwright con proxies
# ----------------------------
async def scrape(url: str) -> List[MangaSearchResult]:
    results: List[MangaSearchResult] = []

    async with async_playwright() as p:
        for proxy in PROXIES:
            ip, port, user, password = proxy.split(":")
            proxy_dict = {
                "server": f"http://{ip}:{port}",
                "username": user,
                "password": password
            }
            try:
                browser = await p.chromium.launch(
                    headless=True,
                    proxy=proxy_dict,
                    args=["--no-sandbox", "--disable-setuid-sandbox"]
                )
                page = await browser.new_page(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                               "AppleWebKit/537.36 (KHTML, like Gecko) "
                               "Chrome/117.0.0.0 Safari/537.36",
                    viewport={"width": 1280, "height": 800}
                )
                await page.goto(url, timeout=20000)
                await page.wait_for_timeout(5000)

                cards = await page.query_selector_all("div.element")
                if not cards:
                    await browser.close()
                    continue

                for card in cards:
                    a_elem = await card.query_selector("a[href]")
                    manga_url = await a_elem.get_attribute("href") if a_elem else "Unknown"

                    thumb = await card.query_selector("div.thumbnail.book")
                    if not thumb:
                        continue

                    title_elem = await thumb.query_selector("h4.text-truncate")
                    title_text = await title_elem.get_attribute("title") if title_elem else "Unknown"

                    score_elem = await thumb.query_selector("span.score > span")
                    try:
                        score = float((await score_elem.inner_text()).strip().replace(",", ".")) if score_elem else 0.0
                    except ValueError:
                        score = 0.0

                    type_elem = await thumb.query_selector("span.book-type")
                    type_text = await type_elem.inner_text() if type_elem else "Unknown"

                    demography_elem = await thumb.query_selector("span.demography")
                    demography_text = await demography_elem.get_attribute("title") if demography_elem else "Unknown"

                    erotic_tag = await thumb.query_selector("i[title='Erótico']")
                    is_erotic = erotic_tag is not None

                    styles = await thumb.query_selector_all("style")
                    image_url = "Unknown"
                    for style_tag in styles:
                        m = re.search(r"background-image:\s*url\(['\"]?(.*?)['\"]?\)", await style_tag.inner_text())
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

                await browser.close()
                if results:
                    break

            except Exception as e:
                print(f"Error con proxy {ip}:{port} -> {e}")

    return results

# ----------------------------
# Endpoint GET /search
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
    results = await scrape(url)
    return MangaSearchResponse(url=url, results=results)
