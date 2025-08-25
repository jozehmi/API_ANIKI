from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List
from uuid import uuid4
import requests
import re
import json
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from core.config import ZONATMO_HEADERS

router = APIRouter()

class MangaRequest(BaseModel):
    url: str

class ImageInfo(BaseModel):
    filename: str
    page_number: int
    proxy_url: str

class MangaResponse(BaseModel):
    chapter_title: str
    images: List[ImageInfo]
    viewer_url: str
    message: str

viewers = {}

def create_session_with_retries():
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retries))
    return session

def extract_image_data(url: str):
    headers = ZONATMO_HEADERS
    session = create_session_with_retries()
    response = session.get(url, headers=headers, verify=False)
    if response.status_code != 200:
        raise HTTPException(status_code=400, detail=f"No se pudo acceder a la página: Código de estado {response.status_code}")
    
    soup = BeautifulSoup(response.text, 'html.parser')
    script_tags = soup.find_all('script')
    
    dir_path = None
    images = None
    referer = url
    
    for script in script_tags:
        if script.string and 'dirPath' in script.string and 'images = JSON.parse' in script.string:
            dir_match = re.search(r"dirPath = '([^']+)';", script.string)
            if dir_match:
                dir_path = dir_match.group(1)
            
            images_match = re.search(r"images = JSON\.parse\('([^']+)'\);", script.string)
            if images_match:
                try:
                    images = json.loads(images_match.group(1))
                except json.JSONDecodeError as e:
                    raise HTTPException(status_code=400, detail=f"Error al parsear JSON de imágenes: {str(e)}")
    
    if not dir_path or not images:
        raise HTTPException(status_code=400, detail="No se encontraron imágenes o directorio en la página")
    
    return dir_path, images, referer

def generate_viewer_html(chapter_title: str, images: List[str], viewer_id: str):
    html_content = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Visor de {chapter_title}</title>
        <style>
            body {{ font-family: Arial, sans-serif; text-align: center; background-color: #f0f0f0; }}
            img {{ max-width: 100%; height: auto; margin: 10px 0; }}
            h1 {{ color: #333; }}
            p {{ color: #555; }}
        </style>
    </head>
    <body>
        <h1>Visor de {chapter_title}</h1>
        <p>Imágenes cargadas automáticamente.</p>
        {"".join(f'<img src="/api/mangas/scrape-manga/image/{viewer_id}/{i+1}/{img}" alt="Página {i+1}"><br>' for i, img in enumerate(images))}
        <p>Fin del capítulo.</p>
    </body>
    </html>
    """
    return html_content

@router.post("/scrape-manga")
async def scrape_manga(request: MangaRequest):
    try:
        chapter_title = request.url.split('/')[-2] if 'viewer' in request.url else request.url.split('/')[-1].replace('.html', '').replace('-', '_')
        viewer_id = str(uuid4())
        
        dir_path, images, referer = extract_image_data(request.url)
        
        image_info_list = [
            ImageInfo(
                filename=img,
                page_number=i+1,
                proxy_url=f"http://localhost:8000/api/mangas/scrape-manga/image/{viewer_id}/{i+1}/{img}"
            ) for i, img in enumerate(images)
        ]
        
        if not image_info_list:
            raise HTTPException(status_code=400, detail="No se encontraron imágenes")
        
        viewers[viewer_id] = {
            "dir_path": dir_path,
            "referer": referer,
            "chapter_title": chapter_title,
            "images": images
        }
        
        return MangaResponse(
            chapter_title=chapter_title,
            images=image_info_list,
            viewer_url=f"http://localhost:8000/api/mangas/scrape-manga/viewer/{chapter_title}/{viewer_id[:8]}",
            message=f"Se generaron {len(image_info_list)} enlaces de imágenes. Abre el visor en http://localhost:8000/api/mangas/scrape-manga/viewer/{chapter_title}/{viewer_id[:8]}."
        )
    
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error inesperado: {str(e)}")

@router.get("/scrape-manga/viewer/{chapter_title}/{uuid}", response_class=HTMLResponse)
async def get_viewer(chapter_title: str, uuid: str):
    viewer_id = next((vid for vid in viewers if vid.startswith(uuid)), None)
    if not viewer_id or viewers[viewer_id]["chapter_title"] != chapter_title:
        raise HTTPException(status_code=404, detail="Página del visor no encontrada")
    
    viewer_info = viewers[viewer_id]
    html_content = generate_viewer_html(viewer_info["chapter_title"], viewer_info["images"], viewer_id)
    return HTMLResponse(content=html_content)

@router.get("/scrape-manga/image/{viewer_id}/{page_number}/{filename}")
async def proxy_image(viewer_id: str, page_number: int, filename: str):
    viewer_info = viewers.get(viewer_id)
    if not viewer_info:
        raise HTTPException(status_code=404, detail="Visor no encontrado")
    
    dir_path = viewer_info["dir_path"]
    referer = viewer_info["referer"]
    
    headers = ZONATMO_HEADERS.copy()
    headers["Referer"] = referer
    headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    session = create_session_with_retries()
    image_url = urljoin(dir_path, filename)
    response = session.get(image_url, headers=headers, stream=True, verify=False)
    
    if response.status_code != 200:
        raise HTTPException(status_code=400, detail=f"No se pudo obtener la imagen: Código de estado {response.status_code}")
    
    return Response(
        content=response.content,
        media_type=response.headers.get('content-type', 'image/webp')
    )