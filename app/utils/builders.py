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
