BASE_URL = "https://animeav1.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36"
    )
}

CACHE_TTL = 300  # segundos

VALID_CATEGORIES = ["tv-anime", "pelicula", "ova", "especial"]
VALID_GENRES = [
    "accion", "aventura", "ciencia-ficcion", "comedia", "deportes",
    "drama", "fantasia", "misterio", "recuentos-de-la-vida", "romance",
    "seinen", "shoujo", "shounen", "sobrenatural", "suspenso", "terror"
]
VALID_STATUS = ["emision", "finalizado", "proximamente"]
VALID_ORDERS = ["predeterminado", "popular", "score", "title", "latest_added", "latest_released"]
VALID_LETTERS = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
