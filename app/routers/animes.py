from fastapi import APIRouter, Query, HTTPException
from bs4 import BeautifulSoup
import re, json, demjson3, asyncio, requests
from utils.scraping import fetch_html, find_sveltekit_script, extract_js_object, extract_home_block
from utils.builders import (
    build_poster_url, build_backdrop_url,
    build_episode_image_url, build_episode_url,
    build_featured_image_url, build_latest_episode_image_url,
    build_latest_media_image_url, build_watch_url
)
from core.cache import get_cached, set_cache
from core.config import BASE_URL, VALID_CATEGORIES, VALID_GENRES, VALID_STATUS, VALID_ORDERS, VALID_LETTERS

router = APIRouter()

# -------------------- /animes --------------------
@router.get("")
def get_animes(
    category: list[str] = Query(None),
    genre: list[str] = Query(None),
    min_year: int = None,
    max_year: int = None,
    status: str = None,
    order: str = "predeterminado",
    letter: str = None,
    page: int = 1
):
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

    base_url = f"{BASE_URL}/catalogo"
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

    soup = BeautifulSoup(response.text, "html.parser")

    scripts = soup.find_all("script")
    data_script = None
    for script in scripts:
        if script.string and "__sveltekit_" in script.string:
            data_script = script.string
            break

    if not data_script:
        return {"error": "Data script not found", "url": url}

    results_match = re.search(r"results:\s*\[([\s\S]*?)\]\s*}", data_script)
    if not results_match:
        return {"error": "Results not found in script", "url": url}

    results_str = results_match.group(1)
    anime_strs = re.split(r"\}\s*,\s*\{", results_str)
    animes = []
    for i, anime_str in enumerate(anime_strs):
        if i > 0:
            anime_str = "{" + anime_str
        if i < len(anime_strs) - 1:
            anime_str += "}"

        id_match = re.search(r'id:"([^"]+)"', anime_str)
        title_match = re.search(r'title:"([^"]+)"', anime_str)
        synopsis_match = re.search(r'synopsis:"(.*?)"(?=\s*,\s*categoryId:)', anime_str, re.DOTALL)
        category_id_match = re.search(r'categoryId:(\d+)', anime_str)
        slug_match = re.search(r'slug:"([^"]+)"', anime_str)

        anime_dict = {}
        if id_match:
            anime_id = id_match.group(1)
            anime_dict["id"] = anime_id
            anime_dict["cover"] = f"https://cdn.animeav1.com/covers/{anime_id}.jpg"
        if title_match:
            anime_dict["title"] = title_match.group(1)
        if synopsis_match:
            anime_dict["synopsis"] = synopsis_match.group(1).replace("\\n", "\n")
        if category_id_match:
            anime_dict["categoryId"] = int(category_id_match.group(1))
        if slug_match:
            anime_dict["slug"] = slug_match.group(1)

        category_match = re.search(r'a\.name="([^"]+)"', data_script)
        category_name = category_match.group(1) if category_match else "Unknown"
        anime_dict["category"] = {
            "id": anime_dict.get("categoryId"),
            "name": category_name,
            "slug": "tv-anime"
        }

        if anime_dict:
            animes.append(anime_dict)

    total_results = len(animes)
    results_elem = soup.find(string=re.compile(r"\d+ Resultados"))
    if results_elem:
        match = re.search(r"\d+", results_elem)
        if match:
            total_results = int(match.group())

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
        "animes": animes,
    }

# -------------------- /home --------------------
@router.get("/home")
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

# -------------------- /{slug} --------------------
@router.get("/{slug}")
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

# -------------------- /{slug}/{number} --------------------
@router.get("/{slug}/{number}")
async def get_episode(slug: str, number: int, force_refresh: bool = Query(False)):
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
        m = re.search(r"data\s*:\s*\[", script_text)
        if not m:
            raise HTTPException(status_code=500, detail="No se encontró 'data:[' en el script")

        start = script_text.find("[", m.start())
        depth, end = 0, None
        for i in range(start, len(script_text)):
            ch = script_text[i]
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end is None:
            raise HTTPException(status_code=500, detail="No se cerró el array de 'data'")

        data_js = script_text[start:end + 1]
        data_json = re.sub(r'([{\[,]\s*)([A-Za-z0-9_@$-]+)\s*:', r'\1"\2":', data_js)
        data_json = data_json.replace("undefined", "null").replace("void 0", "null")
        data_json = re.sub(r',\s*(\]|})', r'\1', data_json)

        data = json.loads(data_json)

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
