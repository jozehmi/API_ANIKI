import time
import requests
import re
import json
import asyncio
from typing import Optional, List
from datetime import datetime
from fastapi import FastAPI, Query, HTTPException
import httpx, demjson3
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait

app = FastAPI()

# Configuración global
BASE_URL = "https://animeav1.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36"
}
CACHE_TTL = 300  # segundos
cache = {}

VALID_CATEGORIES = ["tv-anime", "pelicula", "ova", "especial"]
VALID_GENRES = ["accion", "aventura", "ciencia-ficcion", "comedia", "deportes", "drama",
                "fantasia", "misterio", "recuentos-de-la-vida", "romance", "seinen",
                "shoujo", "shounen", "sobrenatural", "suspenso", "terror"]
VALID_STATUS = ["emision", "finalizado", "proximamente"]
VALID_ORDERS = ["predeterminado", "popular", "score", "title", "latest_added", "latest_released"]
VALID_LETTERS = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

# -------------------- Utilidades de caché --------------------

def get_cached(key):
    now = time.time()
    if key in cache and now - cache[key]["timestamp"] < CACHE_TTL:
        return cache[key]["data"]
    return None

def set_cache(key, value):
    cache[key] = {"timestamp": time.time(), "data": value}


# -------------------- Constructores de URLs --------------------

def build_poster_url(anime_id: int) -> str:
    return f"https://cdn.animeav1.com/posters/{anime_id}.jpg"

def build_backdrop_url(anime_id: int) -> str:
    return f"https://cdn.animeav1.com/backdrops/{anime_id}.jpg"

def build_episode_image_url(anime_id: int, episode_number: int) -> str:
    return f"https://cdn.animeav1.com/screenshots/{anime_id}/{episode_number}.jpg"

def build_episode_url(slug: str, episode_number: int) -> str:
    return f"/media/{slug}/{episode_number}"

def build_featured_image_url(anime_id: int) -> str:
    return f"https://cdn.animeav1.com/backdrops/{anime_id}.jpg"

def build_latest_episode_image_url(anime_id: int) -> str:
    return f"https://cdn.animeav1.com/thumbnails/{anime_id}.jpg"

def build_latest_media_image_url(anime_id: int) -> str:
    return f"https://cdn.animeav1.com/covers/{anime_id}.jpg"

def build_watch_url(slug: str) -> str:
    return f"/media/{slug}"


# -------------------- Utilidades de scraping --------------------

async def fetch_html(url):
    async with httpx.AsyncClient() as client:
        r = await client.get(url, headers=HEADERS)
        r.raise_for_status()
        return r.text

def find_sveltekit_script(soup):
    for s in soup.find_all("script"):
        if s.string and "__sveltekit" in s.string:
            return s.string
    return None

def extract_js_object(text: str, start_marker: str) -> str:
    start = text.find(start_marker)
    if start == -1:
        raise ValueError(f"No se encontró {start_marker}")
    start = text.find("{", start)
    brace_count = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            brace_count += 1
        elif text[i] == "}":
            brace_count -= 1
            if brace_count == 0:
                return text[start:i + 1]
    raise ValueError("No se cerró el objeto correctamente")

def extract_home_block(script_text: str) -> str:
    target_index = script_text.find("featured:")
    if target_index == -1:
        raise ValueError("No se encontró 'featured:' en el script")
    start_data = script_text.rfind("data:{", 0, target_index)
    if start_data == -1:
        raise ValueError("No se encontró 'data:{' antes de featured:")
    start_brace = script_text.find("{", start_data)
    brace_count = 0
    for i in range(start_brace, len(script_text)):
        if script_text[i] == "{":
            brace_count += 1
        elif script_text[i] == "}":
            brace_count -= 1
            if brace_count == 0:
                return script_text[start_brace:i + 1]
    raise ValueError("No se cerró el bloque correctamente")


# -------------------- Scraping Horario --------------------

async def fetch_media():
    html = await fetch_html(f"{BASE_URL}/horario")
    m = re.search(r'media\s*:\s*\[', html)
    start = html.find("[", m.start())
    depth, end = 0, None
    for i in range(start, len(html)):
        if html[i] == "[":
            depth += 1
        elif html[i] == "]":
            depth -= 1
            if depth == 0:
                end = i
                break
    media_js = html[start:end + 1]
    media_json = re.sub(r'([{\[,]\s*)([A-Za-z0-9_@$-]+)\s*:', r'\1"\2":', media_js)
    media_json = media_json.replace("undefined", "null")
    return json.loads(re.sub(r',\s*(\]|})', r'\1', media_json))

def scrape_schedule_all_days():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    driver = webdriver.Chrome(options=options)

    slug_to_data = {}
    try:
        driver.get(f"{BASE_URL}/horario")

        # Esperar a que existan los botones de días
        WebDriverWait(driver, 15).until(lambda d: d.find_elements(By.CSS_SELECTOR, "div.tabs button"))
        day_buttons = driver.find_elements(By.CSS_SELECTOR, "div.tabs button")
        dias_html = [btn.text.strip() for btn in day_buttons if btn.text.strip()]

        for idx, btn in enumerate(day_buttons):
            # Click en el botón
            driver.execute_script("arguments[0].click();", btn)

            # Esperar a que aparezcan los animes en el grid
            WebDriverWait(driver, 15).until(
                lambda d: d.find_elements(By.CSS_SELECTOR, "div.grid div.relative")
            )

            # Parsear la página con BeautifulSoup
            soup = BeautifulSoup(driver.page_source, "html.parser")
            grid = soup.select_one("div.grid.grid-cols-2")
            if not grid:
                continue

            for card in grid.select("div.relative"):
                hora_tag = card.select_one("div.bg-line.text-subs")
                hora = hora_tag.get_text(strip=True) if hora_tag else None

                link_tag = card.select_one("a[href*='/media/']")
                if not link_tag:
                    continue
                slug = link_tag["href"].strip("/").split("/")[-1]

                poster_tag = card.select_one("figure img.aspect-poster")
                poster = poster_tag["src"] if poster_tag else None

                slug_to_data[slug] = {
                    "day": dias_html[idx],
                    "time": hora,
                    "poster": poster
                }

        return slug_to_data

    finally:
        driver.quit()

# -------------------- Endpoints --------------------
@app.get("/animes")
def get_animes(
    category: Optional[List[str]] = Query(None),
    genre: Optional[List[str]] = Query(None),
    min_year: Optional[int] = None,
    max_year: Optional[int] = None,
    status: Optional[str] = None,
    order: Optional[str] = "predeterminado",
    letter: Optional[str] = None,
    page: int = 1
):
    # Validaciones
    if category and not all(c in VALID_CATEGORIES for c in category):
        raise HTTPException(status_code=400, detail=f"Category inválida. Opciones: {VALID_CATEGORIES}")
    if genre and not all(g in VALID_GENRES for g in genre):
        raise HTTPException(status_code=400, detail=f"Genre inválido. Opciones: {VALID_GENRES}")
    if status and status not in VALID_STATUS:
        raise HTTPException(status_code=400, detail=f"Status inválido. Opciones: {VALID_STATUS}")
    if order and order not in VALID_ORDERS:
        raise HTTPException(status_code=400, detail=f"Order inválido. Opciones: {VALID_ORDERS}")
    if letter and letter.upper() not in VALID_LETTERS:
        raise HTTPException(status_code=400, detail=f"Letter inválida. Opciones: {VALID_LETTERS}")
    if min_year and max_year and min_year > max_year:
        raise HTTPException(status_code=400, detail="min_year no puede ser mayor que max_year")

    base_url = "https://animeav1.com/catalogo"
    params = []
    if category:
        for cat in category:
            params.append(f"category={cat}")
    if genre:
        for g in genre:
            params.append(f"genre={g}")
    if min_year:
        params.append(f"minYear={min_year}")
    if max_year:
        params.append(f"maxYear={max_year}")
    if status:
        params.append(f"status={status}")
    if order:
        params.append(f"order={order}")
    if letter:
        params.append(f"letter={letter.upper()}")
    params.append(f"page={page}")
    
    url = base_url + "?" + "&".join(params) if params else base_url
    response = requests.get(url)
    if response.status_code != 200:
        return {"error": "Failed to fetch the page", "url": url}
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Buscar el script con los datos
    scripts = soup.find_all('script')
    data_script = None
    for script in scripts:
        if script.string and '__sveltekit_' in script.string:
            data_script = script.string
            break
    
    if not data_script:
        return {"error": "Data script not found", "url": url}
    
    # Extraer los resultados con regex
    results_match = re.search(r'results:\s*\[([\s\S]*?)\]\s*}', data_script)
    if not results_match:
        return {"error": "Results not found in script", "url": url}
    
    results_str = results_match.group(1)
    anime_strs = re.split(r'\}\s*,\s*\{', results_str)
    animes = []
    for i, anime_str in enumerate(anime_strs):
        if i > 0:
            anime_str = '{' + anime_str
        if i < len(anime_strs) - 1:
            anime_str += '}'
        
        # Extraer campos
        id_match = re.search(r'id:"([^"]+)"', anime_str)
        title_match = re.search(r'title:"([^"]+)"', anime_str)
        synopsis_pattern = r'synopsis:"(.*?)"(?=\s*,\s*categoryId:)'
        synopsis_match = re.search(synopsis_pattern, anime_str, re.DOTALL)
        category_id_match = re.search(r'categoryId:(\d+)', anime_str)
        slug_match = re.search(r'slug:"([^"]+)"', anime_str)

        anime_dict = {}
        if id_match:
            anime_id = id_match.group(1)
            anime_dict["id"] = anime_id
            # 👇 añadimos la URL del cover
            anime_dict["cover"] = f"https://cdn.animeav1.com/covers/{anime_id}.jpg"
        if title_match:
            anime_dict["title"] = title_match.group(1)
        if synopsis_match:
            anime_dict["synopsis"] = synopsis_match.group(1).replace('\\n', '\n')
        if category_id_match:
            anime_dict["categoryId"] = int(category_id_match.group(1))
        if slug_match:
            anime_dict["slug"] = slug_match.group(1)

        # Categoría
        category_match = re.search(r'a\.name="([^"]+)"', data_script)
        category_name = category_match.group(1) if category_match else "Unknown"
        anime_dict["category"] = {
            "id": anime_dict.get("categoryId"),
            "name": category_name,
            "slug": "tv-anime"
        }
        
        if anime_dict:
            animes.append(anime_dict)
    
    # Total de resultados
    total_results = len(animes)
    results_elem = soup.find(string=re.compile(r'\d+ Resultados'))
    if results_elem:
        match = re.search(r'\d+', results_elem)
        if match:
            total_results = int(match.group())
    
    # Total de páginas
    total_pages = 1
    pagination_links = soup.find_all("a", href=lambda href: href and "page=" in href if href else False)
    pages = [int(plink.text) for plink in pagination_links if plink.text.isdigit()]
    if pages:
        total_pages = max(pages)
    
    return {
        "url": url,
        "page": page,
        "total_results": total_results,
        "total_pages": total_pages,
        "animes": animes
    }

@app.get("/filters")
def get_filters():
    from datetime import datetime
    current_year = datetime.now().year

    return {
        "Category": {
            "type": "multiple",
            "options": VALID_CATEGORIES
        },
        "Genre": {
            "type": "multiple",
            "options": VALID_GENRES
        },
        "minYear": {
            "type": "integer",
            "min": 1990,
            "max": current_year
        },
        "maxYear": {
            "type": "integer",
            "min": 1990,
            "max": current_year
        },
        "Status": {
            "type": "single",
            "options": VALID_STATUS
        },
        "Order": {
            "type": "single",
            "options": VALID_ORDERS
        },
        "Letter": {
            "type": "single",
            "options": VALID_LETTERS
        },
        "Page": {
            "type": "integer",
            "min": 1
        }
    }

@app.get("/api/animes/home")
async def get_home_data(force_refresh: bool = Query(False)):
    if not force_refresh:
        cached = get_cached("home_data")
        if cached:
            return cached

    html = await fetch_html(BASE_URL)
    soup = BeautifulSoup(html, "html.parser")
    script_tag = find_sveltekit_script(soup)
    result = {"featured": [], "latestEpisodes": [], "latestMedia": []}

    if script_tag:
        try:
            home_js = extract_home_block(script_tag)
            home_data = demjson3.decode(home_js)

            # Featured
            for item in home_data.get("featured", []):
                anime_id = item.get("id")
                slug = item.get("slug")
                item["image_url"] = build_featured_image_url(anime_id)
                item["watch_url"] = build_watch_url(slug)
                result["featured"].append(item)

            # Latest Episodes
            for ep in home_data.get("latestEpisodes", []):
                media = ep.get("media", {})
                anime_id = media.get("id")
                slug = media.get("slug")
                ep["image_url"] = build_latest_episode_image_url(anime_id)
                ep["watch_url"] = build_watch_url(slug)
                result["latestEpisodes"].append(ep)

            # Latest Media
            for item in home_data.get("latestMedia", []):
                anime_id = item.get("id")
                slug = item.get("slug")
                item["image_url"] = build_latest_media_image_url(anime_id)
                item["watch_url"] = build_watch_url(slug)
                result["latestMedia"].append(item)

            set_cache("home_data", result)
            return result
        except Exception as e:
            print(f"[WARN] Fallback a scraping: {e}")

    set_cache("home_data", result)
    return result


@app.get("/api/horario")
async def get_horario(force_refresh: bool = Query(False)):
    if not force_refresh:
        cached = get_cached("horario")
        if cached:
            return {"schedule": cached}

    media, slug_to_data = await asyncio.gather(
        fetch_media(),
        asyncio.to_thread(scrape_schedule_all_days)
    )

    for item in media:
        slug = item.get("slug")
        if slug in slug_to_data:
            item.update(slug_to_data[slug])
        else:
            item.update({"day": None, "time": None, "poster": None})

    set_cache("horario", media)
    return {"schedule": media}


@app.get("/api/animes/{slug}")
async def get_anime_details(slug: str, force_refresh: bool = Query(False)):
    if not force_refresh:
        cached = get_cached(slug)
        if cached:
            return cached

    html = await fetch_html(f"{BASE_URL}/media/{slug}")
    soup = BeautifulSoup(html, "html.parser")
    script_tag = find_sveltekit_script(soup)
    if not script_tag:
        return {"error": "No se encontró el bloque de datos JSON"}

    try:
        media_js = extract_js_object(script_tag, "media:")
        media_data = demjson3.decode(media_js)
    except Exception as e:
        return {"error": f"Fallo al extraer/parsear media: {str(e)}"}

    anime_id = media_data.get("id")

    # Construir imágenes y URLs de episodios
    episodes = []
    for ep in media_data.get("episodes", []):
        num = ep.get("number")
        if num is not None:
            episodes.append({
                "number": num,
                "image": build_episode_image_url(anime_id, num),
                "url": build_episode_url(slug, num)
            })

    media_data.update({
        "poster": build_poster_url(anime_id),
        "backdrop": build_backdrop_url(anime_id),
        "episodes": episodes
    })

    set_cache(slug, media_data)
    return media_data


@app.get("/api/animes/{slug}/{number}")
async def get_episode(slug: str, number: int, force_refresh: bool = Query(False)):
    """
    Devuelve info de un episodio: datos del anime, episodio, embeds (ver online) y downloads.
    Usa extracción por conteo de corchetes como en fetch_media() para evitar fallos de regex.
    """
    cache_key = f"{slug}_ep_{number}"
    if not force_refresh:
        cached = get_cached(cache_key)
        if cached:
            return cached

    url = f"{BASE_URL}/media/{slug}/{number}"
    html = await fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")
    script_text = find_sveltekit_script(soup)
    if not script_text:
        raise HTTPException(status_code=500, detail="No se encontró bloque de datos")

    try:
        # 1) Localizar el inicio de data:[ ... ]
        m = re.search(r'data\s*:\s*\[', script_text)
        if not m:
            raise HTTPException(status_code=500, detail="No se encontró 'data:[' en el script")

        start = script_text.find('[', m.start())
        depth, end = 0, None
        for i in range(start, len(script_text)):
            ch = script_text[i]
            if ch == '[':
                depth += 1
            elif ch == ']':
                depth -= 1
                if depth == 0:
                    end = i
                    break

        if end is None:
            raise HTTPException(status_code=500, detail="No se cerró el array de 'data'")

        data_js = script_text[start:end + 1]

        # 2) Normalizar JS -> JSON (mismas reglas que usas en fetch_media)
        data_json = re.sub(r'([{\[,]\s*)([A-Za-z0-9_@$-]+)\s*:', r'\1"\2":', data_js)  # claves sin comillas
        data_json = data_json.replace("undefined", "null").replace("void 0", "null")    # undefined/void 0 -> null
        data_json = re.sub(r',\s*(\]|})', r'\1', data_json)                             # comas colgantes

        data = json.loads(data_json)

        # 3) Encontrar bloques relevantes dentro del array (sin asumir índices fijos)
        media_block = None
        ep_block = None
        for item in data:
            if isinstance(item, dict) and item.get("type") == "data":
                dd = item.get("data", {})
                if media_block is None and "media" in dd:
                    media_block = dd["media"]
                if ep_block is None and "episode" in dd:
                    ep_block = dd

        if not media_block or not ep_block:
            raise HTTPException(status_code=500, detail="No se encontraron bloques 'media' o 'episode'")

        media = media_block
        episode = ep_block["episode"]

        # 4) Recolectar embeds/downloads de todas las variantes (SUB, LAT, etc)
        def collect_servers(section: dict) -> list:
            out = []
            if not isinstance(section, dict):
                return out
            for variant, items in section.items():
                if isinstance(items, list):
                    for it in items:
                        out.append({
                            "server": it.get("server"),
                            "url": it.get("url"),
                            "variant": variant
                        })
            return out

        embeds = collect_servers(ep_block.get("embeds", {}))
        downloads = collect_servers(ep_block.get("downloads", {}))

        result = {
            "anime": {
                "id": media.get("id"),
                "title": media.get("title"),
                "aka": media.get("aka"),
                "genres": [g.get("name") for g in media.get("genres", []) if isinstance(g, dict)],
                "score": media.get("score"),
                "votes": media.get("votes"),
                "malId": media.get("malId"),
                "status": media.get("status"),
                "episodes_count": media.get("episodesCount"),
            },
            "episode": {
                "id": episode.get("id"),
                "number": episode.get("number"),
                "filler": episode.get("filler"),
            },
            "embeds": embeds,
            "downloads": downloads,
        }

        set_cache(cache_key, result)
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al parsear episodio: {e}")
