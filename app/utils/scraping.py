import re, json, httpx
from bs4 import BeautifulSoup
from core.config import HEADERS

async def fetch_html(url):
    async with httpx.AsyncClient() as client:
        r = await client.get(url, headers=HEADERS)
        r.raise_for_status()
        return r.text

def find_sveltekit_script(soup: BeautifulSoup):
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
