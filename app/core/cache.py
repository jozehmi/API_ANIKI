import time
from core.config import CACHE_TTL

cache = {}

def get_cached(key):
    now = time.time()
    if key in cache and now - cache[key]["timestamp"] < CACHE_TTL:
        return cache[key]["data"]
    return None

def set_cache(key, value):
    cache[key] = {"timestamp": time.time(), "data": value}
