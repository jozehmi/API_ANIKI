import logging
from fastapi import APIRouter, HTTPException, Query
from bs4 import BeautifulSoup
import httpx
import re
from typing import Dict

from core.cache import get_cached, set_cache
from core.config import ZONATMO_BASE_URL, ZONATMO_HEADERS
from routers.mangas import normalize_href, extract_cover_url_from_element, detect_type_from_element

# Configuración básica de logs
logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(asctime)s] %(message)s")
logger = logging.getLogger(__name__)

router = APIRouter()

BASE_URL = ZONATMO_BASE_URL
HEADERS = ZONATMO_HEADERS


async def fetch_html_remote(url: str, force_refresh: bool = False) -> str:
    """
    Descarga HTML remoto con caché opcional.
    """
    cached = None if force_refresh else get_cached(url)
    if cached:
        logger.info(f"[CACHE HIT] {url}")
        return cached

    logger.info(f"[FETCH] Descargando: {url}")
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=15.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            text = resp.text
    except httpx.HTTPError as e:
        logger.error(f"[ERROR] Fallo al obtener {url}: {e}")
        raise HTTPException(status_code=502, detail=f"Error al obtener página: {str(e)}")

    if not force_refresh:
        set_cache(url, text)
        logger.info(f"[CACHE SET] Guardado en caché: {url}")

    return text


async def resolve_final_chapter_url(upload_url: str) -> str:
    """
    Convierte una URL /view_uploads/xxxxx en /viewer/<uniqid>/paginated.
    Primero intenta resolver mediante redirección (Location),
    si no, usa regex en el HTML.
    """
    logger.info(f"[RESOLVE] Resolviendo uniqid en: {upload_url}")
    async with httpx.AsyncClient(headers=HEADERS, timeout=15.0, follow_redirects=False) as client:
        resp = await client.get(upload_url)

        # Caso 1: Redirección directa -> usar cabecera Location
        if resp.status_code in (301, 302, 303, 307, 308):
            final_url = resp.headers.get("Location")
            if not final_url.startswith("http"):
                final_url = BASE_URL + final_url
            logger.info(f"[OK:REDIRECT] {upload_url} -> {final_url}")
            return final_url

        # Caso 2: No hubo redirect -> buscar uniqid en el HTML
        html = resp.text
        match = re.search(r"uniqid:\s*['\"]([^'\"]+)['\"]", html)
        if not match:
            logger.warning(f"[WARN] No se encontró uniqid en {upload_url}")
            raise HTTPException(status_code=500, detail=f"No se encontró uniqid en {upload_url}")

        uniqid = match.group(1)
        final_url = f"{BASE_URL}/viewer/{uniqid}/paginated"
        logger.info(f"[OK:HTML] {upload_url} -> {final_url}")
        return final_url


def parse_detail(soup: BeautifulSoup, url: str) -> Dict:
    """
    Extrae todos los detalles de una obra en ZonaTMO.
    """
    container = soup.select_one("header.element") or soup.select_one(".element-header-content")
    if not container:
        raise HTTPException(status_code=404, detail="No se encontró información de detalle")

    # Título, subtítulo, descripción
    title_tag = container.select_one(".element-title")
    subtitle_tag = container.select_one(".element-subtitle")
    desc_tag = container.select_one(".element-description")

    title = title_tag.get_text(strip=True) if title_tag else None
    subtitle = subtitle_tag.get_text(strip=True) if subtitle_tag else None
    description = desc_tag.get_text(strip=True) if desc_tag else None

    # Imagen de portada, tipo, demografía, estado
    cover = extract_cover_url_from_element(container)
    mtype = detect_type_from_element(container)
    demo_tag = container.select_one(".demography")
    demography = demo_tag.get_text(strip=True) if demo_tag else None
    state_tag = soup.select_one(".book-status")
    state = state_tag.get_text(strip=True) if state_tag else None

    # Géneros, títulos alternativos, sinónimos
    genres = [a.get_text(strip=True) for a in soup.select(".element-subtitle ~ h6 a.badge-primary")]
    alt_titles = [span.get_text(strip=True) for span in soup.select("h5:contains('Títulos alternativos') ~ span")]
    synonyms = [span.get_text(strip=True) for span in soup.select("h5:contains('Sinónimos') ~ span")]

    # Lista de capítulos
    chapters = []
    for li in soup.select("#chapters li.list-group-item"):
        # Título del capítulo
        cap_title = li.select_one("a.btn-collapse")
        cap_text = cap_title.get_text(" ", strip=True) if cap_title else None

        # Botón de reproducción -> URL real (view_uploads/xxxxx)
        play_button = li.select_one("a.btn.btn-default[href*='/view_uploads/']")
        cap_url = play_button["href"] if play_button else None

        # Fecha y grupo
        date_tag = li.select_one(".badge-primary")
        date = date_tag.get_text(strip=True) if date_tag else None
        group_tag = li.select_one(".chapter-list-element a")
        group = group_tag.get_text(strip=True) if group_tag else None

        chapters.append({
            "title": cap_text,
            "url": normalize_href(cap_url) if cap_url else None,
            "date": date,
            "group": group
        })

    logger.info(f"[INFO] Se extrajeron {len(chapters)} capítulos de {url}")

    return {
        "title": title,
        "subtitle": subtitle,
        "description": description,
        "cover": cover,
        "type": mtype,
        "demography": demography,
        "state": state,
        "genres": genres,
        "alt_titles": alt_titles,
        "synonyms": synonyms,
        "chapters": chapters,
        "source_url": url
    }


@router.get("/detalle", summary="Detalle de una obra (manga/manhwa/manhua/etc.)")
async def detalle(
    url: str = Query(..., description="URL completa de la obra en ZonaTMO"),
    force_refresh: bool = Query(False, description="Forzar refresco (ignorar caché)")
):
    """
    Obtiene todos los detalles de una obra desde su URL en ZonaTMO.
    Entrega las URLs de capítulos en formato /view_uploads/... sin resolver automáticamente.
    """
    logger.info(f"[START] Procesando obra: {url}")
    html = await fetch_html_remote(url, force_refresh=force_refresh)
    soup = BeautifulSoup(html, "lxml")
    data = parse_detail(soup, url)
    logger.info(f"[END] Finalizado scrapeo de: {url}")
    return data

@router.get("/resolve_chapter", summary="Resuelve URL de capítulo a su forma final")
async def resolve_chapter(
    upload_url: str = Query(..., description="URL de capítulo en formato /view_uploads/xxxxx"),
    force_refresh: bool = Query(False, description="Forzar refresco (ignorar caché)")
):
    """
    Resuelve una URL /view_uploads/xxxxx a su forma final /viewer/<uniqid>/paginated.
    """
    if not upload_url.startswith(BASE_URL):
        upload_url = normalize_href(upload_url)

    try:
        final_url = await resolve_final_chapter_url(upload_url)
        return {"final_url": final_url}
    except Exception as e:
        logger.error(f"[ERROR] No se pudo resolver {upload_url}: {e}")
        raise HTTPException(status_code=500, detail=f"Error al resolver URL: {str(e)}")


