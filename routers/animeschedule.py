from fastapi import APIRouter, Query
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from bs4 import BeautifulSoup
import asyncio, re, json
from core.cache import get_cached, set_cache
from core.config import BASE_URL
from utils.scraping import fetch_html

router = APIRouter()

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

        WebDriverWait(driver, 15).until(lambda d: d.find_elements(By.CSS_SELECTOR, "div.tabs button"))
        day_buttons = driver.find_elements(By.CSS_SELECTOR, "div.tabs button")
        dias_html = [btn.text.strip() for btn in day_buttons if btn.text.strip()]

        for idx, btn in enumerate(day_buttons):
            driver.execute_script("arguments[0].click();", btn)
            WebDriverWait(driver, 15).until(lambda d: d.find_elements(By.CSS_SELECTOR, "div.grid div.relative"))
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

@router.get("/horario")
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
