# app/routers/mangas.py
from fastapi import APIRouter, HTTPException, Query
from bs4 import BeautifulSoup
import httpx
import re
from urllib.parse import urljoin
from typing import Optional, List, Dict, Any

from core.cache import get_cached, set_cache  # tu caché síncrona
from core.config import ZONATMO_BASE_URL, ZONATMO_HEADERS

router = APIRouter()

BASE_URL = ZONATMO_BASE_URL
HEADERS = ZONATMO_HEADERS


# ===========================
# Helpers
# ===========================

async def fetch_html_remote(url: str, force_refresh: bool = False) -> str:
    """
    Recupera HTML remoto con caché local. Si force_refresh es True se ignora la caché.
    """
    cached = None if force_refresh else get_cached(url)
    if cached:
        return cached

    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=15.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            text = resp.text
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Error fetching remote: {str(e)}")

    # almacenar sólo si no forzamos refresco
    if not force_refresh:
        set_cache(url, text)
    return text


def normalize_href(href: Optional[str]) -> Optional[str]:
    if not href:
        return None
    href = href.strip()
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        return BASE_URL.rstrip("/") + href
    if href.startswith("http"):
        return href
    return urljoin(BASE_URL, href)


def extract_cover_url_from_element(el) -> Optional[str]:
    # 1) img[src]
    img = el.select_one("img[src]")
    if img and img.get("src"):
        return normalize_href(img["src"])

    # 2) atributos data-*
    for attr in ("data-cover", "data-bg", "data-src", "data-image"):
        if el.has_attr(attr):
            return normalize_href(el[attr])

    # 3) style attribute (inline)
    style_attrs = []
    if el.has_attr("style"):
        style_attrs.append(el["style"])
    for child in el.find_all(attrs={"style": True}):
        style_attrs.append(child["style"])
    for s in style_attrs:
        m = re.search(r"url\(['\"]?(.*?)['\"]?\)", s)
        if m:
            return normalize_href(m.group(1))

    # 4) <style> tag interno
    style_tag = el.find("style")
    if style_tag and style_tag.string:
        m = re.search(r"url\(['\"]?(.*?)['\"]?\)", style_tag.string)
        if m:
            return normalize_href(m.group(1))

    return None

def detect_type_from_element(el) -> Optional[str]:
    """
    Intenta detectar si es:
    - manga
    - manhwa
    - manhua
    - novela
    - doujinshi
    - one_shot
    - oel
    """
    keywords = ["manhwa", "manhua", "manga", "novela", "doujinshi", "one_shot", "oel"]

    # 1) atributos data-type / data-format / data-media
    for attr in ("data-type", "data-format", "data-media"):
        if el.has_attr(attr):
            val = el[attr].strip().lower()
            for kw in keywords:
                if kw in val:
                    return kw

    # 2) badge o etiquetas
    badge = el.find(class_=re.compile(r"(type|format|badge|tag)", re.I))
    if badge and badge.get_text():
        t = badge.get_text(strip=True).lower().replace(" ", "_")
        for kw in keywords:
            if kw in t:
                return kw

    # 3) texto plano dentro del bloque
    txt = el.get_text(" ", strip=True).lower().replace(" ", "_")
    for kw in keywords:
        if kw in txt:
            return kw

    return None

def _parse_numeric(text: Optional[str]) -> Optional[float]:
    """
    Extrae un número de texto (acepta comas o puntos decimales).
    Devuelve float o None.
    """
    if not text:
        return None
    s = text.strip()
    s = s.replace(",", ".")
    m = re.search(r"-?\d+(\.\d+)?", s)
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def _normalize_number_value(val: Optional[float]) -> Optional[Any]:
    """
    Si es float con parte fraccionaria 0, devolver int para que el JSON quede más limpio.
    """
    if val is None:
        return None
    if abs(val - int(val)) < 1e-9:
        return int(val)
    return val


def parse_elements(container) -> List[Dict]:
    items: List[Dict] = []
    if not container:
        return items

    # intentar select típico, si no existe, buscar otras clases comunes
    els = container.select(".element")
    if not els:
        els = container.select(".upload-file-row, .upload-thumbnail, .thumbnail, .thumbnail.upload, .card, a[href]")
    if not els:
        els = container.find_all("a", href=True)

    for el in els:
        # si el es un <a> que envuelve todo, usarlo como 'a' y como contexto de búsqueda
        if getattr(el, "name", None) == "a" and el.get("href"):
            a = el
            context = el
        else:
            a = el.find("a", href=True)
            context = el

        href = normalize_href(a["href"]) if a else None

        # --- Título ---
        title = None
        title_tag = (
            context.select_one(".thumbnail-title h4")
            or context.select_one("h4")
            or context.select_one(".title")
            or (a if a and a.get_text(strip=True) else None)
        )
        if title_tag:
            if getattr(title_tag, "get", None):
                title = title_tag.get("title") or title_tag.get_text(strip=True)
            else:
                title = title_tag.get_text(strip=True)
        elif a and a.get_text(strip=True):
            title = a.get_text(strip=True)

        # --- Score ---
        score_tag = context.select_one(".score span") or context.select_one(".score")
        score = score_tag.get_text(strip=True) if score_tag else None

        # --- Demography ---
        demography = None
        demo_span = context.find("span", class_=re.compile(r"demography", re.I))
        if demo_span and demo_span.get_text(strip=True):
            demography = demo_span.get_text(strip=True)
        else:
            span_alt = context.find("span", string=re.compile(r"(shounen|seinen|josei|shoujo)", re.I))
            if span_alt:
                demography = span_alt.get_text(strip=True)
            else:
                all_classes = " ".join(context.get("class") or [])
                if re.search(r"shounen", all_classes, re.I):
                    demography = "Shounen"
                elif re.search(r"seinen", all_classes, re.I):
                    demography = "Seinen"
                elif re.search(r"josei", all_classes, re.I):
                    demography = "Josei"
                elif re.search(r"shoujo", all_classes, re.I):
                    demography = "Shoujo"

        # --- Upload time ---
        upload_time = None
        time_tag = context.select_one(".upload_time .number") or context.select_one(".upload_time")
        if time_tag:
            upload_time = time_tag.get_text(strip=True)

        # --- Popularidad (porcentaje) ---
        popularity = None
        pop_arrow = context.select_one(".popularity .gauge-arrow")
        if pop_arrow and pop_arrow.has_attr("data-percentage"):
            parsed = _parse_numeric(pop_arrow["data-percentage"])
            popularity = _normalize_number_value(parsed)
        else:
            pop_text_tag = context.select_one(".popularity")
            if pop_text_tag:
                parsed = _parse_numeric(pop_text_tag.get_text(" ", strip=True))
                popularity = _normalize_number_value(parsed)

        # --- Capítulo ---
        chapter = None
        chapter_tag = context.select_one(".chapter-number .number") or context.select_one(".chapter-number")
        if chapter_tag:
            if getattr(chapter_tag, "get_text", None):
                ch_text = chapter_tag.get_text(strip=True)
            else:
                ch_text = str(chapter_tag).strip()
            parsed = _parse_numeric(ch_text)
            chapter = _normalize_number_value(parsed)
        else:
            # fallback: buscar texto "Capítulo" en el bloque
            ch_string = context.find(string=re.compile(r"Capítulo|Capitulo|Chapter", re.I))
            if ch_string:
                parsed = _parse_numeric(str(ch_string))
                chapter = _normalize_number_value(parsed)

        cover = extract_cover_url_from_element(context)
        mtype = detect_type_from_element(context)

        items.append(
            {
                "title": title,
                "url": href,
                "score": score,
                "cover": cover,
                "type": mtype,
                "demography": demography,
                "upload_time": upload_time,
                "popularity": popularity,  # número (ej. 3 -> significa 3%)
                "chapter": chapter,
            }
        )

    return items


async def find_tab_content_by_button_text_async(soup: BeautifulSoup, texts: List[str], force_refresh: bool = False):
    """
    Busca pestañas por texto de botón/enlace. Si necesita abrir una URL real, usa fetch_html_remote(..., force_refresh=force_refresh)
    """
    texts_lower = [t.lower() for t in texts]

    def candidate_fn(tag):
        if tag.name not in ("a", "button", "li"):
            return False
        txt = tag.get_text(" ", strip=True)
        if not txt:
            return False
        low = txt.lower()
        return any(t in low for t in texts_lower)

    candidates = soup.find_all(candidate_fn)
    for tag in candidates:
        href = tag.get("href")
        data_target = tag.get("data-target")
        aria = tag.get("aria-controls")
        target = None
        if data_target:
            target = data_target.lstrip("#")
        elif aria:
            target = aria
        elif href and href.startswith("#"):
            target = href.lstrip("#")
        if target:
            node = soup.select_one(f"#{target}")
            if node:
                return node

        if href and (href.startswith("/") or href.startswith("http")):
            full = normalize_href(href)
            try:
                html = await fetch_html_remote(full, force_refresh=force_refresh)
                return BeautifulSoup(html, "lxml")
            except Exception:
                continue
    return None


# ===========================
# Home (resumen completo)
# ===========================
@router.get("/home", summary="Resumen completo de mangas (home)")
async def home(
    force_refresh: bool = Query(False, description="Forzar refresco y evitar caché (boolean)")
):
    """
    Devuelve un único JSON con las secciones en el siguiente orden:
    - populares (general, seinen, josei)
    - trending (general, seinen, josei)
    - ultimos_anadidos
    - ultimas_subidas
    - top_semanal
    - top_mensual

    Parámetros:
    - force_refresh (query boolean): si es True, se ignora la caché al obtener HTML remoto.
    """
    html = await fetch_html_remote(BASE_URL, force_refresh=force_refresh)
    soup = BeautifulSoup(html, "lxml")

    # ======================
    # Populares
    # ======================
    general_container = soup.select_one("#pills-populars")
    populares_general = parse_elements(general_container)

    seinen_container = await find_tab_content_by_button_text_async(soup, ["p.seinen", "seinen"], force_refresh=force_refresh)
    josei_container = await find_tab_content_by_button_text_async(soup, ["p.josei", "josei"], force_refresh=force_refresh)

    populares_seinen = parse_elements(seinen_container) if seinen_container else []
    populares_josei = parse_elements(josei_container) if josei_container else []

    # ======================
    # Trending
    # ======================
    trending_container = soup.select_one("#pills-trending")
    trending_general = parse_elements(trending_container)

    t_seinen_container = await find_tab_content_by_button_text_async(soup, ["t.seinen", "seinen"], force_refresh=force_refresh)
    t_josei_container = await find_tab_content_by_button_text_async(soup, ["t.josei", "josei"], force_refresh=force_refresh)

    trending_seinen = parse_elements(t_seinen_container) if t_seinen_container else []
    trending_josei = parse_elements(t_josei_container) if t_josei_container else []

    # ======================
    # Últimos añadidos
    # ======================
    header_added = soup.find(lambda t: t.name in ["h1", "h2", "h3"] and "añadid" in t.get_text(strip=True).lower())
    container_added = header_added.find_next("div") if header_added else None
    ultimos_anadidos = parse_elements(container_added)

    # ======================
    # Últimas subidas
    # ======================
    header_uploaded = soup.find(lambda t: t.name in ["h1", "h2", "h3"] and "subida" in t.get_text(strip=True).lower())
    container_uploaded = header_uploaded.find_next("div") if header_uploaded else None
    ultimas_subidas = parse_elements(container_uploaded)

    # ======================
    # Top semanal
    # ======================
    weekly = soup.select_one("#pills-weekly")
    top_semanal: List[Dict] = []
    if weekly:
        for row in weekly.select(".ranked-item"):
            a = row.find("a", href=True)
            pos = row.select_one(".position")
            badge = row.select_one(".badge")
            mtype = badge.get_text(strip=True).lower() if badge else None

            top_semanal.append({
                "position": int(pos.get_text(strip=True).replace(".", "")) if pos else None,
                "title": a.get_text(strip=True) if a else None,
                "url": normalize_href(a["href"]) if a else None,
                "type": mtype
            })

    # ======================
    # Top mensual
    # ======================
    monthly = soup.select_one("#pills-monthly")
    top_mensual: List[Dict] = []
    if monthly:
        for row in monthly.select(".ranked-item"):
            a = row.find("a", href=True)
            pos = row.select_one(".position")
            badge = row.select_one(".badge")
            mtype = badge.get_text(strip=True).lower() if badge else None

            top_mensual.append({
                "position": int(pos.get_text(strip=True).replace(".", "")) if pos else None,
                "title": a.get_text(strip=True) if a else None,
                "url": normalize_href(a["href"]) if a else None,
                "type": mtype
            })

    result = {
        "populares": {
            "general": {"count": len(populares_general), "items": populares_general},
            "seinen": {"count": len(populares_seinen), "items": populares_seinen},
            "josei": {"count": len(populares_josei), "items": populares_josei},
        },
        "trending": {
            "general": {"count": len(trending_general), "items": trending_general},
            "seinen": {"count": len(trending_seinen), "items": trending_seinen},
            "josei": {"count": len(trending_josei), "items": trending_josei},
        },
        "ultimos_anadidos": {"count": len(ultimos_anadidos), "items": ultimos_anadidos},
        "ultimas_subidas": {"count": len(ultimas_subidas), "items": ultimas_subidas},
        "top_semanal": {"count": len(top_semanal), "items": top_semanal},
        "top_mensual": {"count": len(top_mensual), "items": top_mensual},
    }

    return result
    

    return result
